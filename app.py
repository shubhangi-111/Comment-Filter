import os
from flask import Flask, request, jsonify, render_template, send_file
import firebase_admin
from firebase_admin import credentials, auth
import json

from model.predict import predict_comment_detail
from db.connection import (
    init_db,
    log_moderation_event,
    get_recent_moderation_logs,
    get_usage_stats,
    increment_usage_count,
    get_user_usage
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
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "rzp_test_CreatorSafetyShield99")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "test_secret_key_12345")

# 3-Tier Quota Limits
LIMIT_GUEST = 5          # 5 free tests (local browser cache)
LIMIT_FREE_USER = 50     # 50 comments / week (Signed-in Unpaid)
LIMIT_PAID_PRO = 3000    # 3,000 comments / month (₹99/mo Paid Subscriber)

def get_authenticated_user(req):
    """
    Returns user_id if authenticated, else None.
    1. System API Key
    2. X-User-Id Header (Extension Sync)
    3. Firebase Bearer Token
    """
    key_provided = req.headers.get("X-API-Key") or req.args.get("api_key")
    if API_KEY and key_provided == API_KEY:
        return "system_admin"

    user_id = req.headers.get("X-User-Id")
    if user_id:
        return user_id

    auth_header = req.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            decoded_token = auth.verify_id_token(token)
            return decoded_token.get("uid")
        except Exception:
            pass
            
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
                    log_moderation_event(username, name, comment_text, result, platform=platform)
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
    log_moderation_event(author_username, author_name, comment, prediction, platform=platform)
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

    results = []
    platform = data.get("platform", "Extension/Batch")

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
            pred = predict_comment_detail(text)
            pred["author_username"] = user
            pred["author_name"] = name
            results.append(pred)
            log_moderation_event(user, name, text, pred, platform=platform)

    increment_usage_count(user_id, len(results), plan)

    return jsonify({
        "status": "success",
        "count": len(results),
        "data": results
    }), 200

@app.route("/api/logs", methods=["GET"])
def api_get_logs():
    logs = get_recent_moderation_logs(limit=100)
    return jsonify({
        "status": "success",
        "count": len(logs),
        "data": logs
    }), 200

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
    return jsonify({
        "status": "success",
        "order_id": "order_test_rzp_99_plan",
        "amount": 9900,
        "currency": "INR",
        "key_id": RAZORPAY_KEY_ID,
        "plan_name": "Creator Pro Safety Shield (₹99/mo)"
    }), 200

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") == "development"
    app.run(host=host, port=port, debug=debug)