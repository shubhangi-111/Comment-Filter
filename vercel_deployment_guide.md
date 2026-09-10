# Complete Vercel Production Deployment Guide: Creator Safety Shield

This guide provides step-by-step instructions to deploy **Creator Safety Shield** (`Comment-Filter`) fully on **Vercel** with a free external **Neon PostgreSQL** database, **Firebase Authentication**, and **Razorpay Payments**.

---

## 1. Prerequisites

Before starting, ensure you have:
1. A **Vercel Account** ([vercel.com](https://vercel.com)).
2. A free **Neon PostgreSQL Database** ([neon.tech](https://neon.tech)) or **Supabase** ([supabase.com](https://supabase.com)) — *Required because Vercel serverless functions have a read-only filesystem, so persistent data cannot use local SQLite.*
3. Your **Firebase Service Account JSON** (or project credentials).
4. Your **Razorpay API Keys** (Test or Live mode).

---

## 2. Step 1: Provision Free Serverless PostgreSQL (Neon.tech)

1. Sign up at **[neon.tech](https://neon.tech)** and create a new project named `creator-safety-shield`.
2. Copy your connection string from the Neon dashboard. It will look like:
   ```text
   postgresql://alex:password123@ep-cool-shield-123456.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
3. Save this connection string for the `DATABASE_URL` environment variable.

---

## 3. Step 2: Verify Configuration Files in Repository

Ensure your repository has `vercel.json` in the project root:

### `vercel.json`
```json
{
  "version": 2,
  "builds": [
    {
      "src": "app.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "app.py"
    }
  ]
}
```

---

## 4. Step 3: Deploy to Vercel

### Option A: Via Vercel Dashboard (Recommended)

1. Push your latest code to your **GitHub** repository.
2. Go to **[vercel.com/new](https://vercel.com/new)**.
3. Import your GitHub repository (`Comment-Filter`).
4. Keep the Framework Preset as **Other**.
5. Open the **Environment Variables** section and add the required variables (listed in Step 4 below).
6. Click **Deploy**.

---

### Option B: Via Vercel CLI

If you prefer deploying from your terminal:

```bash
# 1. Install Vercel CLI (if not already installed)
npm install -g vercel

# 2. Login to Vercel
vercel login

# 3. Deploy to production
vercel --prod
```

---

## 5. Step 4: Configure Environment Variables in Vercel

In Vercel Dashboard $\rightarrow$ **Project Settings** $\rightarrow$ **Environment Variables**, add the following:

| Variable Name | Description | Example / Format |
| :--- | :--- | :--- |
| `FLASK_ENV` | Mode setting | `production` |
| `DATABASE_URL` | Neon/Supabase PostgreSQL connection string | `postgresql://user:pass@ep-xyz.neon.tech/neondb?sslmode=require` |
| `API_KEY` | Secret master system key for admin/API usage | `sk_prod_safety_shield_998234` |
| `GOOGLE_APPLICATION_CREDENTIALS` | Firebase Service Account Raw JSON string | `{"type":"service_account","project_id":"..."}` |
| `RAZORPAY_KEY_ID` | Razorpay Key ID | `rzp_live_xxxxxxxxxxxx` |
| `RAZORPAY_KEY_SECRET` | Razorpay Secret Key | `your_razorpay_secret_key` |
| `LIMIT_FREE_USER` | Free user weekly comment limit | `50` |
| `LIMIT_PAID_PRO` | Pro user monthly comment limit | `3000` |

> 💡 **Tip for `GOOGLE_APPLICATION_CREDENTIALS`**: Open your downloaded Firebase `.json` key file, copy the entire raw JSON text, and paste it into the Vercel variable value. `app.py` is pre-configured to detect raw JSON strings starting with `{` and parse them in-memory without needing a file path!

---

## 6. Step 5: Post-Deployment Verification

Once Vercel completes building and deploying, test your live Vercel URL (e.g. `https://your-app.vercel.app`):

### 1. Test Health Endpoint
```bash
curl -i https://your-app.vercel.app/health
```
**Expected Response**: `HTTP 200 OK`
```json
{
  "service": "creator-safety-shield-api",
  "status": "healthy",
  "version": "1.0.0"
}
```

### 2. Test Single Comment Moderation API
```bash
curl -i -X POST https://your-app.vercel.app/v1/moderate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk_prod_safety_shield_998234" \
  -d '{"comment": "Loved your video!"}'
```

### 3. Test Batch Moderation API
```bash
curl -i -X POST https://your-app.vercel.app/v1/moderate/batch \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk_prod_safety_shield_998234" \
  -d '{"comments":[{"comment":"Great job!"},{"comment":"kys"}]}'
```

---

## 7. Notes on Vercel Behavior

- **Database Automatic Initialization**: On the first request, SQLAlchemy connects to Neon PostgreSQL and automatically creates the required tables (`moderation_logs`, `usage_tracker`, `subscriptions`).
- **Serverless Warmup**: Vercel functions scale to zero when idle. To avoid cold-start delays on initial requests, use the Keep-Alive Cron setup below.
