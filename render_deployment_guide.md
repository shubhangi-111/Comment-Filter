# Complete Render Production Deployment Guide: Creator Safety Shield

This guide details how to securely deploy **Creator Safety Shield** (`Comment-Filter`) to **Render** using Neon PostgreSQL, Firebase Authentication, and Razorpay payments without committing secrets or credential files to GitHub.

---

## 1. Important Concepts: Secrets & API Keys Explained

### A. What is `GOOGLE_APPLICATION_CREDENTIALS` & How to Pass Firebase Keys Securely?
- **The Problem**: Never commit your Firebase service account `.json` key file to GitHub or git repositories.
- **The Solution**: `app.py` is engineered to handle your Firebase key securely in two ways without committing files to git:

#### Method 1: Raw JSON String in Environment Variable (Recommended & Simplest)
Paste the entire contents of your downloaded Firebase service account `.json` file directly into Render's `GOOGLE_APPLICATION_CREDENTIALS` environment variable as a single JSON string:
```json
{"type":"service_account","project_id":"your-project-id","private_key_id":"...","private_key":"-----BEGIN PRIVATE KEY-----\nMIIEvg...","client_email":"..."}
```
*`app.py` detects that `GOOGLE_APPLICATION_CREDENTIALS` starts with `{`, parses the JSON directly in memory, and authenticates securely without touching disk!*

#### Method 2: Render Secret Files Feature
Render has a feature called **Secret Files**:
1. In Render Dashboard, go to **Environment** $\rightarrow$ **Secret Files**.
2. Upload your `firebase-key.json` file. Set filename as `firebase-key.json`.
3. Render securely mounts this file at `/etc/secrets/firebase-key.json` inside your running web container.
4. Set `GOOGLE_APPLICATION_CREDENTIALS=/etc/secrets/firebase-key.json` in Render's environment variables.

---

### B. What is `API_KEY` & Can It Be Anything?
- **What is it?**: `API_KEY` is your master system key. It allows system administrators, automated cron scripts, or backend-to-backend services to invoke your API endpoints (via `X-API-Key: <your_key>`) with `system_admin` privileges without needing a Firebase user account.
- **Can it be anything?**: **YES!** It can be any secret string you decide (e.g., `sk_prod_safety_shield_998234` or a random UUID).
- **How to choose one**: Generate a strong random string (e.g., using Python: `python -c "import secrets; print(secrets.token_hex(24))"`).

---

## 2. Step-by-Step Render Setup Protocol

### Step 1: Create a Render Web Service
1. Go to **[dashboard.render.com](https://dashboard.render.com)**.
2. Click **New +** $\rightarrow$ Select **Web Service**.
3. Connect your GitHub repository (`Comment-Filter`).

### Step 2: Configure Service Build Settings
- **Name**: `creator-safety-shield` (or your preferred service name)
- **Region**: Choose the region closest to your users (e.g., `Singapore` or `Frankfurt`)
- **Branch**: `main`
- **Runtime**: `Python 3` (or `Docker`)
- **Build Command**:
  ```bash
  pip install -r requirements.txt
  ```
- **Start Command**:
  ```bash
  gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 2 app:app
  ```

---

### Step 3: Add Environment Variables in Render

In Render Dashboard $\rightarrow$ **Environment**, add the following environment variables:

| Variable Name | Value Description | Example / Format |
| :--- | :--- | :--- |
| `FLASK_ENV` | Environment mode | `production` |
| `API_KEY` | Master system secret (any string you choose) | `sk_prod_safety_shield_998234` |
| `DATABASE_URL` | Neon Serverless PostgreSQL URL | `postgresql://user:password@ep-xyz.neon.tech/dbname?sslmode=require` |
| `RAZORPAY_KEY_ID` | Your Live/Test Razorpay Key ID | `rzp_live_xxxxxxxxxxxx` |
| `RAZORPAY_KEY_SECRET` | Your Live/Test Razorpay Key Secret | `your_razorpay_secret_key` |
| `GOOGLE_APPLICATION_CREDENTIALS` | Firebase Service Account (Raw JSON string or file path) | `{"type":"service_account","project_id":"..."}` |

---

### Step 4: Keep Render Warm 24/7 (Zero Cold Starts)

Render free instances sleep after 15 minutes of zero traffic. Keep your instance awake 24/7 with zero cold starts using a free ping:

1. Copy your Render service URL (e.g., `https://creator-safety-shield.onrender.com`).
2. Go to a free monitor service like **[UptimeRobot](https://uptimerobot.com)** or **[cron-job.org](https://cron-job.org)**.
3. Create a new Monitor / Cron Job:
   - **URL**: `https://creator-safety-shield.onrender.com/health`
   - **Method**: `GET`
   - **Interval**: **Every 10 minutes**
4. **Result**: Render receives a `/health` HTTP ping every 10 minutes, returning `{"status":"healthy","service":"creator-safety-shield-api"}` and keeping the Python process permanently warm in memory!

---

## 3. Post-Deployment Verification

Once Render finishes deploying your Web Service, test your live endpoints:

```bash
# 1. Health Verification
curl -i https://creator-safety-shield.onrender.com/health
# Response: HTTP 200 OK {"service":"creator-safety-shield-api","status":"healthy"}

# 2. Test Batch Endpoint with System API Key
curl -i -X POST https://creator-safety-shield.onrender.com/v1/moderate/batch \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk_prod_safety_shield_998234" \
  -d '{"comments":[{"comment":"Awesome video!"},{"comment":"kys"}]}'
# Response: HTTP 200 OK {"count":2,"status":"success"}
```

Your app is now live on Render with Neon PostgreSQL, Firebase Auth, Razorpay Payments, and zero cold starts!
