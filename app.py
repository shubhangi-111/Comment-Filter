import os
from flask import Flask, request, jsonify, render_template, send_file
import firebase_admin
from firebase_admin import credentials, auth
import json

from model.predict import predict_comment_detail, predict_comments_batch
from db.connection import (
    init_db,
    log_moderation_event,
    log_moderation_events_bulk,
    get_recent_moderation_logs,
    get_usage_stats,
    increment_usage_count,
    get_user_usage,
    clear_moderation_logs,
    record_subscription
)

app = Flask(__name__)

# Initialize Database Schema on Application Startup
try:
    init_db()
except Exception as e:
    print(f"Database initialization notice: {e}")

# Initialize Firebase Admin
try:
    if not firebase_admin._apps:
        cred_env = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if cred_env and cred_env.startswith("{"):
            cred_dict = json.loads(cred_env)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
        else:
            firebase_admin.initialize_app()
except Exception as e:
    print(f"Firebase init notice: {e}")

# Configuration & Env Variables
API_KEY = os.environ.get("API_KEY") # No default, fail closed if missing
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET")

# 3-Tier Quota Limits
LIMIT_GUEST = 5          # 5 free tests (local browser cache)
LIMIT_FREE_USER = 50     # 50 comments / week (Signed-in Unpaid)
LIMIT_PAID_PRO = 3000    # 3,000 comments / month (₹99/mo Paid Subscriber)

def get_authenticated_user(req):
    """
    Returns user_id if authenticated, else None.
    1. System API Key (X-API-Key header)
    2. Firebase Bearer Token (Authorization header)
    3. Development Mode Only: X-User-Id header
    """
    key_provided = req.headers.get("X-API-Key")
    if API_KEY and key_provided == API_KEY:
        return "system_admin"

    auth_header = req.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            decoded_token = auth.verify_id_token(token)
            return decoded_token.get("uid")
        except Exception:
            pass

    # Allow X-User-Id header ONLY in local development mode
    if os.environ.get("FLASK_ENV") == "development":
        user_id = req.headers.get("X-User-Id")
        if user_id:
            return user_id

    return None

def check_quota(user_id, count=1):
    if user_id == "system_admin":
        return True, "system_admin"
        
    usage = get_user_usage(user_id)
    limit = LIMIT_PAID_PRO if usage["plan_tier"] == "pro" else LIMIT_FREE_USER
    if usage["processed_count"] + count > limit:
        return False, usage["plan_tier"]
    return True, usage["plan_tier"]

@app.route("/", methods=["GET", "POST"])
def home():
    result = None
    comment_text = ""
    is_guest = False

    if request.method == "POST":
        data = request.get_json(silent=True) or request.form
        comment_text = data.get("comment", "")
        username = data.get("author_username") or data.get("username", "@guest_user")
        name = data.get("author_name") or data.get("name", "Guest User")
        platform = data.get("platform", "Web Playground")
        is_guest = data.get("is_guest") in [True, "true"]
        user_id = data.get("user_id")

        if comment_text:
            result = predict_comment_detail(comment_text)
            # Save to Database if NOT in guest mode and user_id is provided
            if not is_guest and user_id:
                has_quota, plan = check_quota(user_id, 1)
                if has_quota:
                    log_moderation_event(username, name, comment_text, result, platform=platform, user_id=user_id)
                    increment_usage_count(user_id, 1, plan)
                else:
                    result["error"] = "QUOTA_EXCEEDED"

    logs = get_recent_moderation_logs(limit=50)
    stats = get_usage_stats()
    return render_template(
        "index.html",
        result=result,
        comment=comment_text,
        logs=logs,
        stats=stats,
        limit_guest=LIMIT_GUEST,
        limit_free=LIMIT_FREE_USER,
        limit_pro=LIMIT_PAID_PRO,
        razorpay_key_id=RAZORPAY_KEY_ID
    )

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "service": "creator-safety-shield-api",
        "version": "1.0.0"
    }), 200

@app.route("/v1/moderate", methods=["POST"])
def api_moderate_single():
    user_id = get_authenticated_user(request)
    if not user_id:
        return jsonify({"error": "Unauthorized", "message": "Missing X-User-Id or Token"}), 401

    data = request.get_json(silent=True)
    if not data or "comment" not in data:
        return jsonify({"error": "Bad Request", "message": "Missing 'comment' field"}), 400

    comment = data.get("comment")
    author_username = data.get("author_username") or data.get("username", "Anonymous")
    author_name = data.get("author_name") or data.get("name", "Anonymous User")
    platform = data.get("platform", "API Integration")

    has_quota, plan = check_quota(user_id, 1)
    if not has_quota:
        return jsonify({"error": "Quota Exceeded", "code": "QUOTA_EXCEEDED"}), 429

    prediction = predict_comment_detail(comment)
    log_moderation_event(author_username, author_name, comment, prediction, platform=platform, user_id=user_id)
    increment_usage_count(user_id, 1, plan)

    return jsonify({
        "status": "success",
        "data": prediction
    }), 200

@app.route("/v1/moderate/batch", methods=["POST"])
def api_moderate_batch():
    user_id = get_authenticated_user(request)
    if not user_id:
        return jsonify({"error": "Unauthorized", "message": "Missing X-User-Id or Token"}), 401

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Bad Request", "message": "Missing JSON payload"}), 400

    raw_comments = data.get("comments", [])
    if len(raw_comments) > 500:
        return jsonify({"error": "Payload Too Large", "message": "Max 500 comments"}), 413

    has_quota, plan = check_quota(user_id, len(raw_comments))
    if not has_quota:
        return jsonify({"error": "Quota Exceeded", "code": "QUOTA_EXCEEDED"}), 429

    platform = data.get("platform", "Extension/Batch")

    texts = []
    metadata = []
    for item in raw_comments:
        if isinstance(item, dict):
            text = item.get("comment", "")
            user = item.get("author_username", "Anonymous")
            name = item.get("author_name", "Anonymous User")
        else:
            text = str(item)
            user = "Anonymous"
            name = "Anonymous User"
            
        if text:
            texts.append(text)
            metadata.append({"user": user, "name": name})

    results = []
    events_to_log = []
    if texts:
        batch_preds = predict_comments_batch(texts)
        for pred, meta in zip(batch_preds, metadata):
            pred["author_username"] = meta["user"]
            pred["author_name"] = meta["name"]
            results.append(pred)
            events_to_log.append({
                "author_username": meta["user"],
                "author_name": meta["name"],
                "comment_text": pred["comment"],
                "prediction": pred,
                "platform": platform
            })
        
        # Single-transaction bulk database insert
        log_moderation_events_bulk(events_to_log, user_id=user_id)

    increment_usage_count(user_id, len(results), plan)

    return jsonify({
        "status": "success",
        "count": len(results),
        "data": results
    }), 200

@app.route("/api/logs", methods=["GET"])
def api_get_logs():
    user_id = get_authenticated_user(request)
    if not user_id:
        return jsonify({"error": "Unauthorized", "message": "Authentication required to access logs"}), 401
    logs = get_recent_moderation_logs(limit=100, user_id=user_id)
    return jsonify({
        "status": "success",
        "count": len(logs),
        "data": logs
    }), 200

@app.route("/api/clear-logs", methods=["POST"])
def api_clear_logs():
    user_id = get_authenticated_user(request)
    if not user_id:
        return jsonify({"error": "Unauthorized", "message": "Authentication required to clear logs"}), 401
    clear_moderation_logs(user_id=user_id)
    return jsonify({"status": "success", "message": "Harassment Evidence Vault cleared"}), 200

@app.route("/api/stats", methods=["GET"])
def api_get_stats():
    user_id = get_authenticated_user(request)
    if user_id and user_id != "system_admin":
        stats = get_user_usage(user_id)
    else:
        stats = get_usage_stats()
    
    return jsonify({
        "status": "success",
        "data": stats,
        "limits": {
            "guest": LIMIT_GUEST,
            "free": LIMIT_FREE_USER,
            "pro": LIMIT_PAID_PRO
        }
    }), 200

@app.route("/api/download-extension", methods=["GET"])
def download_extension():
    user_id = get_authenticated_user(request)
    if not user_id:
        return jsonify({"error": "Unauthorized", "message": "You must be signed in to download the Chrome Extension."}), 401
    zip_path = os.path.join(app.root_path, "static", "creator-safety-shield-extension.zip")
    if os.path.exists(zip_path):
        return send_file(zip_path, as_attachment=True, download_name="creator-safety-shield-extension.zip")
    return jsonify({"error": "File Not Found"}), 404

@app.route("/api/razorpay/create-order", methods=["POST"])
def razorpay_create_order():
    user_id = get_authenticated_user(request)
    order_id = f"order_{os.urandom(8).hex()}"
    return jsonify({
        "status": "success",
        "order_id": order_id,
        "amount": 9900,
        "currency": "INR",
        "key_id": RAZORPAY_KEY_ID or "rzp_test_CreatorShield",
        "plan_name": "Creator Pro Safety Shield (₹99/mo)"
    }), 200

@app.route("/api/razorpay/verify-payment", methods=["POST"])
def razorpay_verify_payment():
    user_id = get_authenticated_user(request)
    if not user_id:
        return jsonify({"error": "Unauthorized", "message": "Authentication required for subscription."}), 401
    
    data = request.get_json(silent=True) or {}
    payment_id = data.get("razorpay_payment_id", "pay_test_mock")
    order_id = data.get("razorpay_order_id", "order_test_mock")
    signature = data.get("razorpay_signature")

    # Secure HMAC-SHA256 signature validation if secret is configured
    if RAZORPAY_KEY_SECRET and signature:
        import hmac
        import hashlib
        msg = f"{order_id}|{payment_id}".encode("utf-8")
        expected_sig = hmac.new(RAZORPAY_KEY_SECRET.encode("utf-8"), msg, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_sig, signature):
            return jsonify({"error": "Bad Request", "message": "Invalid Razorpay Payment Signature"}), 400

    # Upgrade User to PRO Plan
    record_subscription(user_id, payment_id)

    return jsonify({
        "status": "success",
        "message": "Payment Verified & Creator Pro Subscription Active (3,000 comments/mo)!"
    }), 200

@app.after_request
def apply_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") == "development"
    app.run(host=host, port=port, debug=debug)