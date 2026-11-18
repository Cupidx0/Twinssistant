"""Artifacts: complete HTML pages the model wraps in <artifact> tags (section 13).

Saved per conversation with versions so earlier ones can be restored.
"""
import re
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from auth_utils import require_auth
from services import db

artifacts_bp = Blueprint("artifacts", __name__)

ARTIFACT_RE = re.compile(
    r'<artifact\s+type="(?P<type>[\w-]+)"\s+title="(?P<title>[^"]*)"\s*>(?P<body>.*?)</artifact>',
    re.DOTALL)
MAX_VERSIONS = 10
MAX_ARTIFACT_CHARS = 90_000  # keeps 10 versions under Firestore's 1 MiB document cap


def extract_artifacts(text):
    return [{"type": m.group("type"), "title": m.group("title").strip() or "Untitled",
             "html": m.group("body").strip()} for m in ARTIFACT_RE.finditer(text or "")]


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "artifact"


def save_artifacts(user_id, conv_id, reply):
    saved = []
    for art in extract_artifacts(reply):
        if len(art["html"]) > MAX_ARTIFACT_CHARS:
            continue
        doc_id = f"{_slug(user_id)}_{_slug(conv_id)}_{_slug(art['title'])}"
        ref = db().collection("artifacts").document(doc_id)
        try:
            snap = ref.get()
            versions = (snap.to_dict() or {}).get("versions", []) if snap.exists else []
            if not versions or versions[-1].get("html") != art["html"]:
                versions.append({"html": art["html"], "created_at": datetime.now(timezone.utc).isoformat()})
            versions = versions[-MAX_VERSIONS:]
            ref.set({"user_id": user_id, "conv_id": conv_id, "title": art["title"],
                     "type": art["type"], "versions": versions,
                     "updated_at": datetime.now(timezone.utc).isoformat()})
            saved.append({"id": doc_id, "title": art["title"], "version": len(versions)})
        except Exception as e:
            print(f"Artifact save failed: {e}")
    return saved


@artifacts_bp.route("/api/artifacts", methods=["GET"])
@require_auth
def list_artifacts():
    user_id = request.user["uid"]
    try:
        docs = db().collection("artifacts").where("user_id", "==", user_id).stream()
        items = [{"id": d.id, "title": (x := d.to_dict()).get("title"), "conv_id": x.get("conv_id"),
                  "versions": len(x.get("versions", [])), "updated_at": x.get("updated_at")} for d in docs]
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"artifacts": sorted(items, key=lambda a: a.get("updated_at") or "", reverse=True)})


@artifacts_bp.route("/api/artifacts/<artifact_id>", methods=["GET"])
@require_auth
def get_artifact(artifact_id):
    snap = db().collection("artifacts").document(artifact_id).get()
    data = snap.to_dict() if snap.exists else None
    if not data or data.get("user_id") != request.user["uid"]:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"id": artifact_id, **data})
