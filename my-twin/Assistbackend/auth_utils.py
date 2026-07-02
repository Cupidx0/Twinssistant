from functools import wraps

from flask import request, jsonify
from firebase_admin import auth as fb_auth


def require_auth(f):
    """Reject the request unless it carries a valid Firebase ID token.

    On success the decoded token is attached as `request.user`
    (use `request.user["uid"]` instead of trusting a userId from the body).
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        token = header.removeprefix("Bearer ").strip()
        if not token:
            return jsonify({"error": "Missing Authorization token"}), 401
        try:
            request.user = fb_auth.verify_id_token(token)
        except Exception:
            return jsonify({"error": "Invalid or expired token"}), 401
        return f(*args, **kwargs)
    return wrapper
