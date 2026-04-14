# Production Deployment Guide

## Overview
This guide covers deploying the Certificate Generator to **Render** (free tier with 0.5 CPU, 512MB RAM, stops after 15 minutes of inactivity).

For higher reliability, upgrade to a paid plan or use Google Cloud Run.

---

## Step 1: Prepare Your Repository for Git

```powershell
cd "c:\Users\hebba_sglgqoe\Desktop\silly projects\certfivate maker"
git init
git add .
git commit -m "Initial commit - certificate generator"
```

Create a `.gitignore` file to exclude sensitive files:

```
.env
.venv
__pycache__
*.pyc
*.pyo
*.egg-info/
.DS_Store
client_secrets.json
```

---

## Step 2: Generate a Secure Secret Key

Run this in PowerShell to generate a secure key:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Copy the output - you'll need this in Step 4.

---

## Step 3: Push to GitHub

Create a GitHub repo and push your code:

```powershell
git remote add origin https://github.com/YOUR_USERNAME/certfivate-maker.git
git branch -M main
git push -u origin main
```

---

## Step 4: Deploy on Render

### 4a. Create Render Account
1. Go to https://render.com
2. Sign up with GitHub account
3. Accept OAuth permissions

### 4b. Create New Web Service
1. Click "New +" → "Web Service"
2. Select your `certfivate-maker` repository
3. Configure:
   - **Name**: `certfivate-maker` (or your choice)
   - **Environment**: `Python 3`
   - **Region**: Choose closest to your users
   - **Branch**: `main`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `cd web && gunicorn -w 4 -b 0.0.0.0:$PORT app:app`
   - **Plan**: `Free` (recommended to start)

### 4c. Add Environment Variables
In Render dashboard, go to your service → "Environment"

Add these variables:
```
FLASK_ENV=production
FLASK_SECRET_KEY=<paste the key from Step 2>
GOOGLE_OAUTH_SECRETS=client_secrets.json
YOUTUBE_EMBED=<optional: YouTube embed code>
```

---

## Step 5: Upload Google OAuth Credentials

You need to upload `client_secrets.json` to Render securely:

### Option A: Store as Environment Variable (Recommended)
1. Download `client_secrets.json` from Google Cloud Console
2. Convert it to a string and add as environment variable:

```powershell
$content = Get-Content "client_secrets.json" -Raw
$encoded = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($content))
Write-Host $encoded
```

3. In Render, add environment variable:
```
GOOGLE_OAUTH_SECRETS_BASE64=<paste the encoded string>
```

4. Update `app.py` to decode it:
```python
import base64

if os.environ.get('GOOGLE_OAUTH_SECRETS_BASE64'):
    decoded = base64.b64decode(os.environ['GOOGLE_OAUTH_SECRETS_BASE64'])
    GOOGLE_OAUTH_CLIENT_SECRETS = '/tmp/client_secrets.json'
    with open(GOOGLE_OAUTH_CLIENT_SECRETS, 'w') as f:
        f.write(decoded.decode('utf-8'))
else:
    GOOGLE_OAUTH_CLIENT_SECRETS = os.environ.get('GOOGLE_OAUTH_SECRETS', 'client_secrets.json')
```

### Option B: Store in Render Secret Files
1. In Render dashboard, add a Secret File:
   - **Filename**: `client_secrets.json`
   - **Contents**: Paste contents of your `client_secrets.json`
2. Directory: `/etc/secrets`

---

## Step 6: Update Google OAuth Configuration

In Google Cloud Console, update your OAuth 2.0 Authorized Redirect URIs:

1. Go to Google Cloud Console → Credentials
2. Edit your OAuth 2.0 Client ID
3. Add Authorized Redirect URIs:
   ```
   https://certfivate-maker.onrender.com/auth/callback
   ```
   (Replace with your actual Render app URL)

4. Also add localhost for development:
   ```
   http://localhost:5000/auth/callback
   ```

---

## Step 7: Deploy

1. Render auto-deploys when you push to GitHub
2. Check deployment status in Render dashboard
3. View logs: Dashboard → Service → "Logs" tab

---

## Step 8: Test Your Deployment

1. Visit `https://certfivate-maker.onrender.com` (will be your actual URL)
2. You should see the landing page
3. Click "Get Started with Google"
4. Authenticate with your Google account
5. Test a certificate generation

---

## Troubleshooting

### "Module not found" errors
- Check `requirements.txt` is in root directory
- Verify all imports are installed

### OAuth redirect error
- Confirm redirect URI matches exactly in Google Cloud Console
- Check FLASK_ENV is set to `production`

### "client_secrets.json not found"
- Verify the base64 encoding method worked
- Or use Secret Files method in Render

### Out of memory
- Reduce gunicorn workers: Change `-w 4` to `-w 2`
- Free plan has 512MB RAM

### App goes idle after 15 minutes
- Free tier stops after inactivity
- Upgrade to paid plan ($7/month) for always-on
- Or add a simple uptime monitor (services like UptimeRobot can ping periodically)

---

## Production Checklist

- [ ] `FLASK_SECRET_KEY` is set to a strong random value
- [ ] `FLASK_ENV=production` configured
- [ ] `client_secrets.json` uploaded securely
- [ ] Google OAuth redirect URI updated
- [ ] `.env` file is in `.gitignore`
- [ ] All environment variables are set in Render
- [ ] Test landing page loads
- [ ] Test Google authentication works
- [ ] Test certificate generation works
- [ ] Check logs for errors

---

## Upgrading Later

If you need better performance:

1. **Upgrade Render Plan**: $7/month for Standard (always on, 2GB RAM)
2. **Use Google Cloud Run**: Free tier includes 180,000 vCPU-seconds/month
3. **Use Railway**: Free tier with $5 credit/month

For now, free Render is perfect for testing!
