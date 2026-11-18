"""Per-request token and cost logging, monthly totals, budget guard and /api/costs.

Every LLM call and paid service call goes through log_usage / log_service so
the dashboard shows the real monthly spend.
"""
import threading
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from auth_utils import require_auth
from services import db, env_float

costs_bp = Blueprint("costs", __name__)

# USD per million tokens: (input, output, cache_read, cache_write_5m).
# Verify against the official pricing pages before relying on these.
PRICES_USD_PER_MTOK = {
    "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125),
    "claude-sonnet-5-5": (2.00, 10.00, 0.10, 2.50),
    "claude-opus-5-5": (4.00, 20.00, 0.20, 5.00),
    "claude-sonnet-5": (2.00, 10.00, 0.20, 2.50),
    "claude-opus-4-8": (5.00, 25.00, 0.50, 6.25),
    "claude-sonnet-4-6": (3.00, 15.00, 0.30, 3.75),
    "gpt-4o-mini": (0.15, 0.60, 0.075, 0.0),
    "gemini-3.1-flash-lite": (0.10, 0.40, 0.025, 0.0),
    "text-embedding-3-small": (0.02, 0.0, 0.0, 0.0),
}

# Flat prices for non-token services (USD per unit). Rough figures; adjust to your plan.
SERVICE_PRICES_USD = {
    "tavily_search": 0.008,        # per basic search
    "elevenlabs_chars": 0.00018,   # per character (flash models)
    "whisper_minutes": 0.006,      # per audio minute
}

CLAUDE_PRO_GBP = 18.0


def price_for(model):
    if model in PRICES_USD_PER_MTOK:
        return PRICES_USD_PER_MTOK[model]
    # Snapshot or suffixed IDs: use the longest matching known prefix.
    for known in sorted(PRICES_USD_PER_MTOK, key=len, reverse=True):
        if model and model.startswith(known):
            return PRICES_USD_PER_MTOK[known]
    return PRICES_USD_PER_MTOK["claude-sonnet-5-5"]


def _field(u, name):
    if u is None:
        return 0
    if isinstance(u, dict):
        return u.get(name) or 0
    return getattr(u, name, 0) or 0


def usage_cost_usd(model, u):
    """Cost of one call from an Anthropic-style usage object (or dict with the same keys)."""
    p_in, p_out, p_cr, p_cw = price_for(model)
    inp = _field(u, "input_tokens")
    out = _field(u, "output_tokens")
    cr = _field(u, "cache_read_input_tokens")
    cw = _field(u, "cache_creation_input_tokens")
    usd = (inp * p_in + out * p_out + cr * p_cr + cw * p_cw) / 1e6
    return usd, {"input": inp, "output": out, "cache_read": cr, "cache_write": cw}


def usd_to_gbp(usd):
    return usd * env_float("USD_TO_GBP", 0.76)


def _month_key(now=None):
    now = now or datetime.now(timezone.utc)
    return now.strftime("%Y-%m")


def _safe_key(k):
    return str(k).replace(".", "_").replace("/", "_")


def _record(user_id, model, feature, usd, tokens, extra=None):
    """Write the usage row and bump the monthly totals doc. Never raises."""
    if not user_id:
        return
    from firebase_admin import firestore

    now = datetime.now(timezone.utc)
    gbp = usd_to_gbp(usd)
    month = _month_key(now)
    day = now.strftime("%Y-%m-%d")
    try:
        store = db()
        store.collection("usage").add({
            "user_id": user_id, "model": model, "feature": feature,
            **tokens, **(extra or {}),
            "usd": usd, "gbp": gbp, "month": month, "day": day,
            "ts": firestore.SERVER_TIMESTAMP,
        })
        inc = firestore.Increment
        store.collection("usage_totals").document(f"{user_id}_{month}").set({
            "user_id": user_id, "month": month,
            "usd": inc(usd), "gbp": inc(gbp), "requests": inc(1),
            "by_model": {_safe_key(model): inc(gbp)},
            "by_feature": {_safe_key(feature): inc(gbp)},
            "by_day": {day: inc(gbp)},
            "updated_at": firestore.SERVER_TIMESTAMP,
        }, merge=True)
    except Exception as e:
        print(f"Usage logging failed: {e}")


def log_usage(user_id, model, u, feature="chat", background=True):
    """Log one LLM call. `u` is response.usage (Anthropic) or a dict with the same keys."""
    usd, tokens = usage_cost_usd(model, u)
    if background:
        threading.Thread(target=_record, args=(user_id, model, feature, usd, tokens), daemon=True).start()
    else:
        _record(user_id, model, feature, usd, tokens)
    return usd


def log_service(user_id, service, units, feature=None):
    """Log a non-LLM paid call (Tavily search, ElevenLabs characters, Whisper minutes)."""
    usd = SERVICE_PRICES_USD.get(service, 0.0) * units
    threading.Thread(
        target=_record,
        args=(user_id, service, feature or service, usd,
              {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}, {"units": units}),
        daemon=True,
    ).start()
    return usd


def month_totals(user_id, month=None):
    try:
        snap = db().collection("usage_totals").document(f"{user_id}_{month or _month_key()}").get()
        return (snap.to_dict() or {}) if snap.exists else {}
    except Exception as e:
        print(f"Could not read usage totals: {e}")
        return {}


def budget_status(user_id):
    budget = env_float("MONTHLY_BUDGET_GBP", 12.0)
    spent = float(month_totals(user_id).get("gbp", 0.0) or 0.0)
    return {"spent_gbp": round(spent, 4), "budget_gbp": budget, "over_budget": spent >= budget}


@costs_bp.route("/api/costs", methods=["GET"])
@require_auth
def costs():
    user_id = request.user["uid"]
    month = request.args.get("month") or _month_key()
    totals = month_totals(user_id, month)
    status = budget_status(user_id)
    return jsonify({
        "month": month,
        "total_gbp": round(float(totals.get("gbp", 0.0) or 0.0), 4),
        "total_usd": round(float(totals.get("usd", 0.0) or 0.0), 4),
        "requests": int(totals.get("requests", 0) or 0),
        "by_model": totals.get("by_model", {}),
        "by_feature": totals.get("by_feature", {}),
        "by_day": dict(sorted((totals.get("by_day") or {}).items())),
        "budget_gbp": status["budget_gbp"],
        "over_budget": status["over_budget"],
        "claude_pro_gbp": CLAUDE_PRO_GBP,
    })
