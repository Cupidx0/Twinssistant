import os
from functools import wraps
from flask import request, jsonify
from firebase_admin import auth as fb_auth
from firebase_admin import credentials, firestore, initialize_app, get_app
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
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
OWNER_UIDS = {u.strip() for u in os.getenv("OWNER_UIDS", "").split(",") if u.strip()}

def require_owner(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if request.user.get("uid") not in OWNER_UIDS:
            return jsonify({"error": "This feature is only available to the owner."}), 403
        return f(*args, **kwargs)
    return wrapper
def init_firebase():
    """Initialize the default Firebase app once and reuse it across reloads."""
    cred = credentials.Certificate(os.path.join(BASE_DIR, "tw.json"))
    try:
        firebase_app = get_app()
    except ValueError:
        firebase_app = initialize_app(cred)
    return firebase_app, firestore.client(app=firebase_app)