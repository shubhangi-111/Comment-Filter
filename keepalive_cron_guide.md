# Complete Keep-Alive Cron Job Guide (Zero Cold Starts)

To ensure **Creator Safety Shield** (`Comment-Filter`) remains instantly responsive with **zero cold starts** (whether hosted on Render or Vercel), set up an automated ping job to hit the `/health` endpoint every 10 minutes.

---

## Option 1: Native Render Cron Job Setup

Render allows you to run scheduled Cron Jobs directly inside your Render project dashboard.

### Step-by-Step Instructions:

1. Go to your **[Render Dashboard](https://dashboard.render.com)**.
2. Click **New +** in the top right corner $\rightarrow$ Select **Cron Job**.
3. Fill in the configuration details:
   - **Name**: `creator-shield-keepalive-ping`
   - **Environment**: `Starter` / `Free`
   - **Region**: Same region as your primary Web Service (e.g., `Singapore` or `Frankfurt`).
   - **Schedule (Cron Expression)**:
     ```cron
     */10 * * * *
     ```
     *(This runs the job every 10 minutes, 24/7).*
   - **Command**:
     ```bash
     curl -s -f https://your-app-name.onrender.com/health || echo "Health check failed"
     ```
     *(Replace `https://your-app-name.onrender.com` with your actual Render or Vercel app URL).*

4. Click **Create Cron Job**.

---

## Option 2: Free GitHub Actions Workflow (Automated Pinger)

If you use GitHub, you can set up a **100% free GitHub Action** that pings your endpoint every 10-15 minutes automatically without spending any Render credits or external service limits.

A pre-built workflow has been created in your repository at `.github/workflows/keepalive.yml`:

```yaml
name: Endpoint Keep-Alive Ping

on:
  schedule:
    # Runs every 10 minutes
    - cron: '*/10 * * * *'
  workflow_dispatch: # Allows manual trigger from GitHub UI

jobs:
  ping-health:
    runs-on: ubuntu-latest
    steps:
      - name: Ping Health Endpoint
        run: |
          URL="${{ secrets.APP_HEALTH_URL }}"
          if [ -z "$URL" ]; then
            URL="https://creator-safety-shield.onrender.com/health"
          fi
          echo "Pinging $URL..."
          HTTP_STATUS=$(curl -o /dev/null -s -w "%{http_code}" "$URL")
          echo "HTTP Status Code: $HTTP_STATUS"
          if [ "$HTTP_STATUS" -ne 200 ]; then
            echo "::error::Health check ping failed with status $HTTP_STATUS"
            exit 1
          fi
```

### Setup Instructions for GitHub Action:
1. Push `.github/workflows/keepalive.yml` to your GitHub repo.
2. Go to **GitHub Repo** $\rightarrow$ **Settings** $\rightarrow$ **Secrets and variables** $\rightarrow$ **Actions**.
3. Add a new Repository Secret:
   - **Name**: `APP_HEALTH_URL`
   - **Value**: `https://your-app.onrender.com/health` (or `https://your-app.vercel.app/health`)
4. Done! GitHub Actions will ping your server every 10 minutes.

---

## Option 3: External Free Monitoring Services (Simple 2-Minute Setup)

If you don't want to use Render Cron or GitHub Actions, these free 3rd-party services require zero code:

### A. UptimeRobot (Recommended & Free)
1. Register at **[uptimerobot.com](https://uptimerobot.com)**.
2. Click **Add New Monitor**:
   - **Monitor Type**: `HTTP(s)`
   - **Friendly Name**: `Creator Safety Shield Health`
   - **URL / IP**: `https://your-app.onrender.com/health` (or `https://your-app.vercel.app/health`)
   - **Monitoring Interval**: `Every 5 minutes`
3. Click **Create Monitor**.

### B. Cron-Job.org (Free)
1. Register at **[cron-job.org](https://cron-job.org)**.
2. Create a new Cron Job:
   - **Title**: `Creator Shield Keepalive`
   - **Address**: `https://your-app.onrender.com/health`
   - **Execution Schedule**: `Every 10 minutes`
3. Click **Save**.

---

## Verification

When the cron job executes, the `/health` endpoint will respond with:

```json
{
  "service": "creator-safety-shield-api",
  "status": "healthy",
  "version": "1.0.0"
}
```

This keeps your Python process hot in memory, preventing cold-start latency for your web users and API clients!
