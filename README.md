# 🛡️ CommentModerator AI — High-Speed Comment Moderation API

An AI-powered, high-throughput comment moderation microservice & REST API that classifies text as Toxic or Non-Toxic with confidence probability scores.

---

## 📌 Overview

This project provides automated content moderation for forums, blogs, e-commerce reviews, and community platforms. It combines pre-compiled NLP regex cleaning with an in-memory TF-IDF vectorizer and Logistic Regression model for ultra-low latency (<5ms) text classification.

---

## ⚙️ Features

- ⚡ **Ultra-Fast Sub-5ms CPU Inference**: In-memory pickled TF-IDF model, no expensive GPUs required.
- 🎯 **Confidence Scores**: Returns probability score (`0.0 - 1.0`) alongside classification label.
- 📦 **Batch Moderation Endpoint**: Moderates up to 500 comments in a single HTTP request.
- 🐳 **Containerized & WSGI-Ready**: Dockerized with Gunicorn multi-worker concurrency.
- 🔑 **API Key Authentication Hook**: Ready for SaaS monetization and rate-limiting integration.
- 💻 **Interactive Playground UI**: Modern dark-mode web tester for manual testing.

---

## 🔌 API Endpoints & Usage

### 1. Health Check
```bash
GET /health
```
**Response:**
```json
{
  "service": "comment-moderation-api",
  "status": "healthy",
  "version": "1.0.0"
}
```

---

### 2. Single Comment Moderation
```bash
POST /v1/moderate
Content-Type: application/json
```
**Payload:**
```json
{
  "comment": "Thank you for the wonderful tutorial!"
}
```
**Response:**
```json
{
  "status": "success",
  "data": {
    "comment": "Thank you for the wonderful tutorial!",
    "is_toxic": false,
    "label": "Non-Toxic",
    "confidence": 0.9642
  }
}
```

---

### 3. Batch Comment Moderation
```bash
POST /v1/moderate/batch
Content-Type: application/json
```
**Payload:**
```json
{
  "comments": [
    "Great article, super helpful!",
    "You are an absolute idiot",
    "Can you clarify step 2?"
  ]
}
```
**Response:**
```json
{
  "status": "success",
  "count": 3,
  "data": [
    {
      "comment": "Great article, super helpful!",
      "is_toxic": false,
      "label": "Non-Toxic",
      "confidence": 0.9812
    },
    {
      "comment": "You are an absolute idiot",
      "is_toxic": true,
      "label": "Toxic",
      "confidence": 0.9415
    },
    {
      "comment": "Can you clarify step 2?",
      "is_toxic": false,
      "label": "Non-Toxic",
      "confidence": 0.9901
    }
  ]
}
```

---

## 🚀 Running Locally

### Option A: Direct Python Execution
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the application server
python app.py
```
Open [http://localhost:5000](http://localhost:5000) in your browser.

---

### Option B: Docker Container Deployment
```bash
# 1. Build Docker image
docker build -t comment-moderator-api .

# 2. Run container
docker run -p 5000:5000 comment-moderator-api
```

---

## 📈 SaaS Scaling Roadmap

| Level | Architecture Upgrade | Trigger |
| :--- | :--- | :--- |
| **Phase 1 (Current)** | Flask + Gunicorn + In-Memory sklearn model on Cloud Run | 0 – 1M requests/mo |
| **Phase 2** | Redis Rate Limiter + PostgreSQL (API Keys & Usage Metering) + Stripe | 1M – 10M requests/mo |
| **Phase 3** | Export model to ONNX runtime (5x speedup) + Async Celery Queue for bulk moderation | 10M+ requests/mo |