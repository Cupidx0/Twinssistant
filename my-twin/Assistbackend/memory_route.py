"""Memory viewer, profile and writing-sample endpoints."""
import uuid
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

import memory
from auth_utils import require_auth
from context import load_profile, save_profile
from services import db

memory_bp = Blueprint("memory", __name__)

PROFILE_FIELDS = ("name", "course", "location", "goals", "preferences", "about")


@memory_bp.route("/api/memory", methods=["GET"])
@require_auth
def list_memories():
    user_id = request.user["uid"]
    memory._invalidate(user_id)
    facts = memory.list_facts(user_id)
    facts.sort(key=lambda f: f.get("updated_at") or "", reverse=True)
    return jsonify({"facts": [{k: f.get(k) for k in
                               ("id", "text", "topic", "entities", "conv_id", "created_at", "updated_at", "history")}
                              for f in facts],
                    "aliases": memory.list_aliases(user_id)})


@memory_bp.route("/api/memory/<fact_id>", methods=["PATCH"])
@require_auth
def edit_memory(fact_id):
    text = ((request.get_json(silent=True) or {}).get("text") or "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400
    if memory.contains_secret(text):
        return jsonify({"error": "That looks like a secret or ID number, which is never stored."}), 400
    if not memory.update_fact(request.user["uid"], fact_id, text):
        return jsonify({"error": "Not found or unchanged"}), 404
    return jsonify({"ok": True})


@memory_bp.route("/api/memory/<fact_id>", methods=["DELETE"])
@require_auth
def delete_memory(fact_id):
    if not memory.delete_fact(request.user["uid"], fact_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"ok": True})


@memory_bp.route("/api/profile", methods=["GET", "PUT"])
@require_auth
def profile():
    user_id = request.user["uid"]
    if request.method == "GET":
        return jsonify({"profile": load_profile(user_id)})
    body = request.get_json(silent=True) or {}
    clean = {}
    for key in PROFILE_FIELDS:
        value = body.get(key)
        if isinstance(value, list):
            value = [str(v).strip() for v in value if str(v).strip()]
        elif value is not None:
            value = str(value).strip()
        if value:
            clean[key] = value
    save_profile(user_id, clean)
    return jsonify({"profile": clean})


def _samples(user_id):
    return db().collection("users").document(user_id).collection("writing_samples")


@memory_bp.route("/api/writing_samples", methods=["GET", "POST"])
@require_auth
def writing_samples():
    user_id = request.user["uid"]
    if request.method == "GET":
        return jsonify({"samples": [d.to_dict() | {"id": d.id} for d in _samples(user_id).stream()]})
    body = request.get_json(silent=True) or {}
    text = (body.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400
    sample_id = uuid.uuid4().hex
    _samples(user_id).document(sample_id).set({
        "title": (body.get("title") or "Untitled").strip()[:200], "text": text[:30000],
        "created_at": datetime.now(timezone.utc).isoformat()})
    return jsonify({"id": sample_id})


@memory_bp.route("/api/writing_samples/<sample_id>", methods=["DELETE"])
@require_auth
def delete_writing_sample(sample_id):
    _samples(request.user["uid"]).document(sample_id).delete()
    return jsonify({"ok": True})
