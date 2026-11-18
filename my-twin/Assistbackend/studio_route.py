"""Writing and grading jobs. They take minutes, so they run in the background
and the UI polls /api/studio/jobs/<id>."""
import threading
import traceback
import uuid
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from auth_utils import require_auth
from ratelimit import rate_limited
from services import db
from uploads import load_upload_text

studio_bp = Blueprint("studio", __name__)

JOBS = {}
_lock = threading.Lock()
MAX_JOBS_PER_USER = 2


def _update(job_id, **fields):
    with _lock:
        JOBS[job_id].update(fields)


def _start(user_id, kind, fn):
    with _lock:
        running = sum(1 for j in JOBS.values() if j["user_id"] == user_id and j["status"] == "running")
        if running >= MAX_JOBS_PER_USER:
            return None
        job_id = uuid.uuid4().hex
        JOBS[job_id] = {"id": job_id, "user_id": user_id, "kind": kind, "status": "running",
                        "progress": "Starting", "result": None, "error": None,
                        "created_at": datetime.now(timezone.utc).isoformat()}

    def run():
        try:
            result = fn(lambda msg: _update(job_id, progress=msg))
            _update(job_id, status="done", progress="Done", result=result)
            collection = "writing_docs" if kind == "write" else "assessments"
            try:
                db().collection(collection).document(job_id).set(
                    {"user_id": user_id, "result": result, "created_at": JOBS[job_id]["created_at"]})
            except Exception as e:
                print(f"Saving {kind} result failed: {e}")
        except Exception as e:
            traceback.print_exc()
            _update(job_id, status="error", error=str(e))

    threading.Thread(target=run, daemon=True).start()
    return job_id


@studio_bp.route("/api/studio/write", methods=["POST"])
@require_auth
@rate_limited("studio")
def start_write():
    from pipelines.writing import write_document
    user_id = request.user["uid"]
    body = request.get_json(silent=True) or {}
    brief = (body.get("brief") or "").strip()
    if not brief:
        return jsonify({"error": "brief is required"}), 400
    criteria = (body.get("criteria") or "").strip()
    try:
        words = max(100, min(int(body.get("word_count") or 1000), 10000))
    except (TypeError, ValueError):
        return jsonify({"error": "word_count must be a number"}), 400
    sources = [s for s in (body.get("sources") or []) if isinstance(s, dict) and s.get("url")]
    job_id = _start(user_id, "write",
                    lambda progress: write_document(brief, criteria, words, user_id, sources or None, progress))
    if not job_id:
        return jsonify({"error": "You already have jobs running. Wait for one to finish."}), 429
    return jsonify({"job_id": job_id})


@studio_bp.route("/api/studio/grade", methods=["POST"])
@require_auth
@rate_limited("studio")
def start_grade():
    from pipelines.grading import grade
    user_id = request.user["uid"]
    body = request.get_json(silent=True) or {}
    brief = (body.get("brief") or "").strip()
    criteria = (body.get("criteria") or "").strip()
    submission = (body.get("submission") or "").strip()
    if not submission and body.get("upload_id"):
        submission = (load_upload_text(user_id, body["upload_id"]) or "").strip()
    if not (brief and criteria and submission):
        return jsonify({"error": "brief, criteria and a submission (text or upload) are required"}), 400
    job_id = _start(user_id, "grade", lambda progress: grade(brief, criteria, submission, user_id, progress))
    if not job_id:
        return jsonify({"error": "You already have jobs running. Wait for one to finish."}), 429
    return jsonify({"job_id": job_id})


@studio_bp.route("/api/studio/jobs/<job_id>", methods=["GET"])
@require_auth
def job_status(job_id):
    with _lock:
        job = dict(JOBS.get(job_id) or {})
    if not job or job["user_id"] != request.user["uid"]:
        return jsonify({"error": "Not found"}), 404
    job.pop("user_id", None)
    return jsonify(job)
