# 🛡️ Creator Safety Shield — Product Walkthrough, System Flowcharts & Vercel Deployment Guide

**Creator Safety Shield** is a production-ready AI SaaS platform designed to protect content creators from online harassment, misogynistic slurs, stealth euphemisms (e.g. *R-word*), death threats, and creepy solicitations across **Instagram Reels** and **YouTube Shorts**.

---

## 📑 Executive Summary of Features Built

1. **Multi-Lingual Creator Protection Safety Engine** ([model/predict.py](file:///e:/hackathons/slavic/Comment-Filter/model/predict.py)):
   * Combined TF-IDF + Logistic Regression Machine Learning model trained on **288,668 balanced comments** (86.3% cross-validation accuracy).
   * **Hinglish & Hindi Misogyny Shield**: Detects terms like `chinaar`, `bhadwi`, `kitne me degi`, `kiske sath soti hai`, `itne bade`, `ek baar dilade`, `nude bhejo`, `रंडी`, `छिनार`, etc.
   * **Slur Euphemisms & Leetspeak Normalizer**: Detects `R-word`, `F-word`, `N-word`, `r@ndi`, `b!tch`, `a$$hole`.
   * **Threat & Violence Detector**: Detects `mar dunga`, `jaan se maar`, `acid phek`, `kys`, `kill yourself`, `goli maar`, `ghar aake`.

2. **3-Tier Quota & Pricing System** ([app.py](file:///e:/hackathons/slavic/Comment-Filter/app.py)):
   * **Tier 1 (Guest Mode - Unauthenticated)**: 5 free comment tests. Results cached strictly in browser `localStorage` (bypasses DB).
   * **Tier 2 (Registered Free User - Firebase / Google Signed-In)**: 50 free comments/week + unlocked Chrome Extension download + unlocked Harassment Evidence Vault (Neon DB).
   * **Tier 3 (Creator Pro Subscriber - ₹99/mo)**: 3,000 comments/month + Razorpay UPI payment integration + unlocked Extension & Vault.

3. **Offender Harassment Evidence Vault (Neon DB)** ([db/connection.py](file:///e:/hackathons/slavic/Comment-Filter/db/connection.py)):
   * Archives offender handle (`@username`), author name, comment text, classification label, category tag, platform, and timestamp into Neon Serverless PostgreSQL (with local SQLite fallback).

4. **Chrome Browser Extension** ([extension/](file:///e:/hackathons/slavic/Comment-Filter/extension)):
   * Ready-to-load Manifest V3 extension. Automatically extracts comments & handles on YouTube & Instagram, hides toxic comments, and archives offenders in the DB.

---

## 📐 System Architecture & User Flowcharts

### 1. User Journey & Conversion Funnel Flowchart

```mermaid
flowchart TD
    Start[User Visits Creator Safety Shield Website] --> CheckAuth{Is User Signed In?}
    
    CheckAuth -->|No: Guest Mode| GuestLimit{Guest Test Count < 5?}
    GuestLimit -->|Yes| GuestTest[Process Comment in Playground]
    GuestTest --> GuestCache[Cache Result in LocalStorage - No DB]
    GuestTest --> IncGuest[Increment Guest Count]
    
    GuestLimit -->|No: Reached 5| LockGuest[Lock Playground & Show Auth Modal]
    LockGuest --> GoogleAuth[Sign In with Google / Firebase]
    
    CheckAuth -->|Yes: Signed In| CheckPlan{Is Paid Pro Subscriber?}
    GoogleAuth --> CheckPlan
    
    CheckPlan -->|No: Free Registered| FreeQuota{Weekly Count < 50?}
    FreeQuota -->|Yes| FullAccess[Unlock Extension Download & Evidence Vault]
    FreeQuota -->|No: Reached 50| UpgradePrompt[Prompt ₹99/mo Razorpay Upgrade]
    
    CheckPlan -->|Yes: Pro Plan| ProQuota{Monthly Count < 3000?}
    ProQuota -->|Yes| FullAccess
    ProQuota -->|No| TopupPrompt[Prompt Refill / Upgrade]
    
    UpgradePrompt --> RazorpayCheckout[Razorpay UPI Autopay ₹99]
    RazorpayCheckout --> ProActive[Activate Pro Plan: 3000 Comments/mo]
```

---

### 2. Multi-Lingual Moderation & Threat Detection Pipeline

```mermaid
flowchart LR
    Input[Incoming Comment Text] --> Normalize[Leetspeak & Evasion Normalization]
    Normalize --> RuleCheck{Rule Engine Match?}
    
    RuleCheck -->|Slur Placeholder| EuphemismTag[Tag: Harassment / Slur Euphemism R-word]
    RuleCheck -->|Death / Acid Threat| ThreatTag[Tag: Severe Threat / Violence]
    RuleCheck -->|Hinglish Abuse| MisogynyTag[Tag: Sexual Harassment / Slur]
    
    RuleCheck -->|No Rule Match| MLModel[TF-IDF + Logistic Regression ML Model]
    MLModel --> MLResult{Confidence >= Threshold?}
    
    MLResult -->|Toxic| GeneralToxic[Tag: General Toxicity]
    MLResult -->|Non-Toxic| SafeTag[Tag: Safe]
    
    EuphemismTag --> CheckDBLogging{Is Guest User?}
    ThreatTag --> CheckDBLogging
    MisogynyTag --> CheckDBLogging
    GeneralToxic --> CheckDBLogging
    SafeTag --> CheckDBLogging
    
    CheckDBLogging -->|Yes: Guest| LocalCache[Store in Browser LocalStorage]
    CheckDBLogging -->|No: Authenticated| SaveDB[Archive to Neon PostgreSQL Database]
```

---

### 3. Chrome Extension Real-Time Moderation Flowchart

```mermaid
sequenceDiagram
    autonumber
    actor Creator
    participant Browser as Chrome Browser (YouTube/Instagram)
    participant Extension as Content Script (content.js)
    participant API as Flask API (/v1/moderate/batch)
    participant DB as Neon PostgreSQL DB

    Creator->>Browser: Opens YouTube Video or IG Reel
    Browser->>Extension: DOM Comments Loaded
    Extension->>Extension: Scrape Comment Text, Handle (@user) & Author Name
    Extension->>API: POST /v1/moderate/batch (Payload with Handles & Comments)
    API->>API: Execute NLP Model & Hinglish Safety Shield
    API->>DB: Log Toxic Offender Metadata (Username, Name, Comment)
    API-->>Extension: Returns Classification & Category Payload
    Extension->>Browser: Blur Toxic Comments & Inject Red Shield Alert Badge
    Extension->>Creator: Displays Filtered Comment Feed
```

---

## ☁️ Step-by-Step Vercel + Neon DB Deployment Guide

Follow these simple steps to host **Creator Safety Shield** live on **Vercel** with a **Neon PostgreSQL** database.

### Step 1: Create a Free Serverless Database on Neon
1. Go to **[https://neon.tech](https://neon.tech)** and sign up for a free account.
2. Click **"Create Project"** and name it `creator-safety-shield`.
3. In the project dashboard, copy your **Connection String** (PostgreSQL URI). It looks like this:
   ```text
   postgres://username:password@ep-xyz.aws.neon.tech/neondb?sslmode=require
   ```

---

### Step 2: Push Repository to GitHub
In your terminal, commit and push your code to GitHub:
```bash
git add .
git commit -m "Deploying Creator Safety Shield SaaS"
git push origin main
```

---

### Step 3: Import Project into Vercel
1. Go to **[https://vercel.com](https://vercel.com)** and log in.
2. Click **"Add New..."** $\rightarrow$ **"Project"**.
3. Select your GitHub repository (`Comment-Filter` or `creator-safety-shield`).
4. Framework Preset: **Other** (Vercel automatically detects `vercel.json` and `app.py`).

---

### Step 4: Configure Environment Variables in Vercel
Before clicking Deploy, expand **Environment Variables** and add the following keys:

| Environment Variable Key | Value Example | Purpose |
| :--- | :--- | :--- |
| `DATABASE_URL` | `postgres://username:password@ep-xyz.aws.neon.tech/neondb?sslmode=require` | Connects Flask to Neon Postgres DB |
| `RAZORPAY_KEY_ID` | `rzp_test_YourRazorpayKey` | Enables ₹99 subscription modal |
| `RAZORPAY_KEY_SECRET` | `YourRazorpaySecret` | Razorpay payment validation |
| `API_KEY` | *(Optional, leave empty for open API)* | Authenticates API headers |

---

### Step 5: Deploy & Initialize Database
1. Click **"Deploy"**. Vercel will build and deploy your application in ~45 seconds.
2. Once deployed, open your live Vercel URL (e.g. `https://creator-safety-shield.vercel.app`).
3. On first load, `app.py` automatically initializes the `moderation_logs`, `usage_tracker`, and `subscriptions` tables on Neon DB!

---

### Step 6: Load Chrome Extension in Browser
1. In Chrome, navigate to `chrome://extensions`.
2. Enable **Developer Mode** in the top right.
3. Click **"Load unpacked"** and select the [`extension/`](file:///e:/hackathons/slavic/Comment-Filter/extension) directory.
4. If your app is live on Vercel, update `API_SERVER` in [`extension/content.js`](file:///e:/hackathons/slavic/Comment-Filter/extension/content.js#L3) to your Vercel URL:
   ```javascript
   const API_SERVER = "https://creator-safety-shield.vercel.app/v1/moderate/batch";
   ```

---

## 🧪 Local Testing Checklist

```bash
# 1. Start application
python app.py

# 2. Test endpoints
# Visit http://localhost:5000 in your browser
```

* 🟢 **Test 1**: Enter 5 comments in Guest Mode. Verify that after 5 tests, the Guest Lock Card appears asking you to Sign In.
* 🟢 **Test 2**: Click **"Sign In with Google"** to claim 50 free comments/week and unlock the **"Download Extension (.zip)"** button.
* 🟢 **Test 3**: Test `"chinaar"`, `"bhadwi"`, `"kitne me degi"`, or `"mar dunga"`. Verify that offender handle and name are recorded in the **Harassment Evidence Vault** tab!
* 🟢 **Test 4**: Click **"⚡ Upgrade (₹99/mo)"** to verify the Razorpay test payment modal.
