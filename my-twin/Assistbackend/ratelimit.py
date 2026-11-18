"""Per-user sliding-window rate limit (in memory, single process)."""
import threading
import time
from collections import defaultdict, deque
from functools import wraps

from flask import jsonify, request

_hits = defaultdict(deque)
_lock = threading.Lock()

LIMITS = {"chat": (20, 60), "upload": (30, 60), "studio": (6, 600)}


def allow(user_id, bucket="chat"):
    limit, window = LIMITS.get(bucket, (20, 60))
    now = time.time()
    with _lock:
        q = _hits[(user_id, bucket)]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True


def rate_limited(bucket):
    """Decorator for routes that already ran @require_auth."""
    def deco(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not allow(request.user["uid"], bucket):
                return jsonify({"error": "Too many requests. Please slow down."}), 429
            return f(*args, **kwargs)
        return wrapper
    return deco
