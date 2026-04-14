# Environment Setup Guide

## Overview

Your project uses environment variables to manage sensitive credentials (API keys, secrets) and configuration. These should **never be committed to Git**.

---

## What's New

### Root Level (`/`)
- **`.env`** - Your actual development environment variables (ignored by Git)
- **`.env.example`** - Template showing what variables to set (safe to commit)
- **`.gitignore`** - Updated to exclude `.env` and credential files

### Web App Level (`/web`)
- **`web/.env`** - Your actual web app environment variables (ignored by Git)
- **`web/.env.example`** - Template for web app variables (safe to commit)

---

## Setup Instructions

### 1. Get Your Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. **APIs & Services** → **Credentials**
3. Click **+ CREATE CREDENTIALS** → **OAuth 2.0 Client ID**
4. Select **Web application**
5. Add authorized redirect URIs:
   - `http://localhost:5000/auth/callback` (development)
6. Click **CREATE**
7. Click the download button (⬇️) to download as JSON
8. Save as `client_secrets.json` in the `web/` folder

```
certificate-maker/
└── web/
    ├── app.py
    ├── client_secrets.json    ← Place here
    ├── .env                   ← Create from .env.example
    └── requirements.txt
```

### 2. Create Your `.env` File

**Root level (optional for CLI):**
```bash
cp .env.example .env
```

**Web level (required for web app):**
```bash
cd web
cp .env.example .env
```

### 3. Edit `.env` File

Update the values in `web/.env`:

```env
FLASK_ENV=development
FLASK_SECRET_KEY=your-super-secret-dev-key-change-in-production
GOOGLE_OAUTH_SECRETS=client_secrets.json
PORT=5000
```

- `FLASK_SECRET_KEY`: Change to something random (for session encryption)
- `GOOGLE_OAUTH_SECRETS`: Should be filename of your credentials (or set to actual JSON path)
- Other values: Usually fine as-is for development

### 4. Verify `.gitignore`

Make sure these lines are in `.gitignore`:

```
# Environment variables
.env
.env.local
.env.*.local

# Credentials & Secrets
credentials.json
client_secrets.json
*.key
*.pem
```

### 5. Test It Works

```bash
cd web
python app.py
```

Visit `http://localhost:5000` and test the login flow.

---

## For Production Deployment

When deploying to Heroku, Google Cloud Run, AWS, etc., you don't use `.env` files. Instead:

### Set Environment Variables on Your Server

**Heroku:**
```bash
heroku config:set FLASK_SECRET_KEY=<strong-random-key>
heroku config:set GOOGLE_OAUTH_SECRETS=@client_secrets.json
```

**Google Cloud Run:**
- Set via Cloud Console or `gcloud` CLI
- Don't commit secrets to repository

**AWS Elastic Beanstalk:**
- Set via `.ebextensions/` config files or console

See [WEB_DEPLOYMENT_GUIDE.md](WEB_DEPLOYMENT_GUIDE.md) for platform-specific instructions.

---

## What to Commit vs. Ignore

### ✅ Safe to Commit to Git
- `.env.example` - Shows structure, no real secrets
- `credentials.json.example` - Template only
- Source code files
- Documentation

### ❌ NEVER Commit to Git
- `.env` - Contains your actual secret key
- `client_secrets.json` - Your OAuth credentials
- `credentials.json` - Service account credentials
- Any file with API keys or tokens

---

## Troubleshooting

### Error: "No module named 'dotenv'"

The Flask app loads `.env` automatically. If you get this error:

1. Make sure you're in the `web/` directory
2. Install requirements: `pip install -r requirements.txt`
3. Restart Python

### Error: "client_secrets.json not found"

1. Download from Google Cloud Console
2. Place in `web/` folder with exact filename `client_secrets.json`
3. Update `GOOGLE_OAUTH_SECRETS=client_secrets.json` in `.env`

### Environment Variables Not Loading

1. Verify `.env` exists in current directory: `ls -la .env`
2. Restart Flask: `Ctrl+C` and `python app.py`
3. Check `.env` format (no spaces around `=`)

---

## Environment Variable Reference

| Variable | Purpose | Example |
|----------|---------|---------|
| `FLASK_ENV` | Flask mode | `development` or `production` |
| `FLASK_SECRET_KEY` | Session encryption | 32+ random characters |
| `GOOGLE_OAUTH_SECRETS` | OAuth credentials file | `client_secrets.json` |
| `PORT` | Server port | `5000` (development), `8080` (production) |

---

## Next Steps

1. [Download OAuth credentials](#get-your-google-oauth-credentials)
2. [Create `.env` file](#create-your-env-file)
3. [Test locally](WEB_QUICK_START.md)
4. [Deploy to production](WEB_DEPLOYMENT_GUIDE.md)

---

**Questions?** Check [WEB_QUICK_START.md](WEB_QUICK_START.md) for the 5-minute setup guide.
