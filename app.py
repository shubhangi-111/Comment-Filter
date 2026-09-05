import os
from flask import Flask, request, jsonify, render_template
from model.predict import predict_comment_detail, predict_batch

app = Flask(__name__)

# Optional API Key check helper for SaaS monetization hook
API_KEY = os.environ.get("API_KEY", None)

def verify_api_key(req):
    if not API_KEY:
        return True  # If no API key configured, open access
    key_provided = req.headers.get("X-API-Key") or req.args.get("api_key")
    return key_provided == API_KEY

@app.route("/", methods=["GET", "POST"])
def home():
    result = None
    comment_text = ""

    if request.method == "POST":
        # Handle form submission or JSON request on root
        if request.is_json:
            data = request.get_json() or {}
            comment_text = data.get("comment", "")
        else:
            comment_text = request.form.get("comment", "")

        if comment_text:
            result = predict_comment_detail(comment_text)

    return render_template("index.html", result=result, comment=comment_text)

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "service": "comment-moderation-api",
        "version": "1.0.0"
    }), 200

@app.route("/v1/moderate", methods=["POST"])
def api_moderate_single():
    if not verify_api_key(request):
        return jsonify({"error": "Unauthorized", "message": "Invalid or missing X-API-Key"}), 401

    data = request.get_json(silent=True)
    if not data or "comment" not in data:
        return jsonify({"error": "Bad Request", "message": "Missing 'comment' field in JSON payload"}), 400

    comment = data.get("comment")
    if not isinstance(comment, str):
        return jsonify({"error": "Bad Request", "message": "'comment' must be a string"}), 400

    prediction = predict_comment_detail(comment)
    return jsonify({
        "status": "success",
        "data": prediction
    }), 200

@app.route("/v1/moderate/batch", methods=["POST"])
def api_moderate_batch():
    if not verify_api_key(request):
        return jsonify({"error": "Unauthorized", "message": "Invalid or missing X-API-Key"}), 401

    data = request.get_json(silent=True)
    if not data or "comments" not in data:
        return jsonify({"error": "Bad Request", "message": "Missing 'comments' list in JSON payload"}), 400

    comments = data.get("comments")
    if not isinstance(comments, list):
        return jsonify({"error": "Bad Request", "message": "'comments' must be a list of strings"}), 400

    if len(comments) > 500:
        return jsonify({"error": "Payload Too Large", "message": "Maximum batch size is 500 comments"}), 413

    predictions = predict_batch(comments)
    return jsonify({
        "status": "success",
        "count": len(predictions),
        "data": predictions
    }), 200

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") == "development"
    app.run(host=host, port=port, debug=debug)