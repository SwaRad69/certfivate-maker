# Web App Deployment Guide

Deploy the Certificate Generator as a web application where users sign in with their Google account and generate certificates to their own Drive.

---

## Architecture Overview

**User Flow:**
1. User visits your website
2. Clicks "Sign In with Google"
3. Authorizes app to access their Drive
4. Uploads CSV file + provides template ID
5. App generates certificates to their Drive
6. User downloads PDFs from their Drive

**Key Benefits:**
- Decentralized storage (no server storage needed)
- User privacy (each user's data in their Drive)
- Scalable (no central bottleneck)
- Minimal server resources

---

## Part 1: Setup Google OAuth2

### Step 1: Create OAuth2 Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project (or create new)
3. Go to **APIs & Services** → **Credentials**
4. Click **+ CREATE CREDENTIALS** → **OAuth 2.0 Client ID**
5. Choose **Web application**
6. Fill in details:
   - **Name:** Certificate Generator
   - **Authorized JavaScript origins:**
     - `http://localhost:5000` (development)
     - `https://yourdomain.com` (production)
   - **Authorized redirect URIs:**
     - `http://localhost:5000/auth/callback` (dev)
     - `https://yourdomain.com/auth/callback` (prod)
7. Click **CREATE**
8. Download JSON → save as `client_secrets.json`

### Step 2: Place Credentials File

Place `client_secrets.json` in the `web/` directory:

```
certificate-maker/
└── web/
    ├── app.py
    ├── client_secrets.json     ← Place here
    └── requirements.txt
```

**Important:** Never commit `client_secrets.json` to Git.

---

## Part 2: Local Development Setup

### Installation

```bash
cd web
pip install -r requirements.txt
```

### Development Environment

Create a `.env` file in the `web/` directory:

```env
FLASK_ENV=development
FLASK_SECRET_KEY=your-super-secret-dev-key-change-in-production
GOOGLE_OAUTH_SECRETS=client_secrets.json
PORT=5000
```

### Run Locally

```bash
python app.py
```

Visit: `http://localhost:5000`

### Features to Test

1. Click "Sign In with Google"
2. Authorize the app
3. Upload sample CSV
4. Check certificates appear in Drive
5. Logout

---

## Part 3: Deploy to Production

Choose one of these hosting options:

### Option A: Heroku (Easiest)

**Cost:** Free-$7/month  
**Setup Time:** 15 minutes

1. **Install Heroku CLI:**
   ```bash
   # Windows: Download from https://devcenter.heroku.com/articles/heroku-cli
   heroku login
   ```

2. **Create Heroku app:**
   ```bash
   heroku create certificate-generator-app
   ```

3. **Create `Procfile` in root:**
   ```
   web: cd web && gunicorn app:app
   ```

4. **Create `.gitignore` at root:**
   ```
   client_secrets.json
   .env
   __pycache__/
   *.pyc
   ```

5. **Add credentials to Heroku:**
   ```bash
   heroku config:set GOOGLE_OAUTH_SECRETS=@client_secrets.json
   heroku config:set FLASK_SECRET_KEY=your-strong-random-key
   ```

6. **Deploy:**
   ```bash
   git push heroku main
   ```

Your app is now live at: `https://certificate-generator-app.herokuapp.com`

---

### Option B: Google Cloud Run (Scalable)

**Cost:** $0-20/month  
**Setup Time:** 20 minutes

1. **Create `Dockerfile` in web/ directory:**
   ```dockerfile
   FROM python:3.9-slim
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install -r requirements.txt
   COPY . .
   CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]
   ```

2. **Deploy with Cloud Run CLI:**
   ```bash
   gcloud run deploy certificate-generator \
     --source . \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated
   ```

3. **Set environment variables in Cloud Run:**
   - FLASK_SECRET_KEY
   - GOOGLE_OAUTH_SECRETS (JSON content)

---

### Option C: AWS Elastic Beanstalk

**Cost:** $5-20/month  
**Setup Time:** 30 minutes

1. **Install EB CLI:**
   ```bash
   pip install awsebcli
   ```

2. **Initialize:**
   ```bash
   eb init -p python-3.9 certificate-generator --region us-east-1
   ```

3. **Create `.ebextensions/python.config`:**
   ```yaml
   option_settings:
     aws:elasticbeanstalk:container:python:
       WSGIPath: web/app.py
   ```

4. **Create environment:**
   ```bash
   eb create production
   ```

5. **Set environment variables:**
   ```bash
   eb setenv FLASK_SECRET_KEY=your-key GOOGLE_OAUTH_SECRETS=@client_secrets.json
   ```

6. **Deploy:**
   ```bash
   eb deploy
   ```

---

### Option D: Your Own Server (Full Control)

**Cost:** $5-20/month (VPS)  
**Setup Time:** 1+ hour

1. **Rent VPS:** DigitalOcean, Linode, AWS EC2, etc.

2. **SSH into server:**
   ```bash
   ssh root@your-server-ip
   ```

3. **Install Python & dependencies:**
   ```bash
   apt update && apt install python3 python3-pip nginx supervisor
   pip3 install -r requirements.txt
   ```

4. **Create supervisor config** `/etc/supervisor/conf.d/certs.conf`:
   ```ini
   [program:certificate-generator]
   directory=/home/app/web
   command=/usr/bin/python3 -m gunicorn --workers 4 --bind 127.0.0.1:8000 app:app
   autostart=true
   autorestart=true
   stdout_logfile=/var/log/certs.log
   ```

5. **Configure nginx** `/etc/nginx/sites-available/default`:
   ```nginx
   server {
       listen 80;
       server_name yourdomain.com;

       location / {
           proxy_pass http://127.0.0.1:8000;
       }
   }
   ```

6. **Start services:**
   ```bash
   supervisorctl reread
   supervisorctl update
   systemctl restart nginx
   ```

---

## Part 4: Security Checklist

### Before Going Live

- [ ] Change FLASK_SECRET_KEY to strong random value
- [ ] Set GOOGLE_OAUTH_SECRETS environment variable on server
- [ ] Never commit client_secrets.json to Git
- [ ] Enable HTTPS/SSL (self-signed or Let's Encrypt)
- [ ] Add rate limiting to `/api/generate`
- [ ] Monitor server logs for errors
- [ ] Test OAuth flow with test account

### Environment Variables (Set on Server)

```
FLASK_ENV=production
FLASK_SECRET_KEY=<generate with: python -c 'import secrets; print(secrets.token_hex(32))'>
GOOGLE_OAUTH_SECRETS=<paste contents of client_secrets.json>
```

---

## Part 5: Production Monitoring

### Logging

Check logs for errors:

```bash
# Heroku
heroku logs --tail

# Google Cloud Run
gcloud run logs read certificate-generator --tail

# Your VPS
tail -f /var/log/certs.log
```

### Monitoring

Add monitoring tools:

- **Sentry** (error tracking): https://sentry.io/
- **Google Cloud Monitoring** (metrics)
- **Uptime Robot** (health checks): https://uptimerobot.com/

### Scaling

If traffic increases:

- **Heroku:** Upgrade dyno type
- **Cloud Run:** Auto-scales automatically
- **VPS:** Add more workers or upgrade instance

---

## Part 6: Custom Domain

### For Heroku:

```bash
heroku domains:add www.yourcertificates.com
# Follow DNS instructions
```

### For others:

1. Buy domain (GoDaddy, Namecheap, etc.)
2. Point DNS to your server
3. Setup SSL certificate (Let's Encrypt free)
4. Update OAuth redirect URIs in Google Cloud

---

## Part 7: Troubleshooting

### OAuth Error: "Redirect URI mismatch"

**Solution:**
1. Go to Google Cloud Console → Credentials
2. Edit OAuth client
3. Update **Authorized redirect URIs** to match your domain

### Certificates Not Saving to Drive

**Check:**
1. User authenticated successfully
2. Template ID is correct
3. CSV format is valid
4. Logs show no errors

### App Crashes on Deployment

**Debug:**
1. Check logs: `heroku logs --tail`
2. Verify all dependencies installed: `pip install -r requirements.txt`
3. Test locally first: `python app.py`

### SSL Certificate Error

**Fix:**
- Use certbot for Let's Encrypt (free):
  ```bash
  sudo apt install certbot python3-certbot-nginx
  sudo certbot --nginx -d yourdomain.com
  ```

---

## Part 8: Cost Estimates

| Service | Free Tier | Paid | Best For |
|---------|-----------|------|----------|
| **Heroku** | None (removed) | $7–50/mo | Simplest |
| **Google Cloud Run** | 2M requests/mo | $0.40 per M requests | Google ecosystem |
| **AWS Elastic Beanstalk** | 750 hrs/mo | $5–20/mo | AWS users |
| **Fly.io** | 3 shared-cpu-1x 256MB | $3–30/mo | Perfect balance |
| **Your VPS** | None | $5–20/mo | Full control |

**Recommendation:** Start with **Fly.io** or **Cloud Run** for best value.

---

## Part 9: Maintenance

### Regular Tasks

- [ ] Monitor server logs weekly
- [ ] Update dependencies monthly: `pip list --outdated`
- [ ] Rotate secrets quarterly
- [ ] Test OAuth flow monthly
- [ ] Monitor Google API quota

### Backup & Recovery

- Cloud storage handles user files
- App is stateless (no database)
- Redeploy anytime from Git

---

## Part 10: Documentation for Users

Create a landing page with:

1. **How it works video** (optional)
2. **Steps to use:**
   - Design in Canva
   - Add placeholders
   - Create CSV
   - Generate
3. **FAQ section**
4. **Contact support**

See [WEB_USER_GUIDE.md](WEB_USER_GUIDE.md) (to be created).

---

## Quick Deploy Checklist

- [ ] `client_secrets.json` downloaded from Google Cloud
- [ ] `client_secrets.json` in `web/` directory
- [ ] `.env` file created (or env vars set)
- [ ] Local test: `python web/app.py` → works
- [ ] Choose hosting platform
- [ ] Deploy using platform instructions
- [ ] Update Google OAuth redirect URIs
- [ ] Test OAuth on live site
- [ ] Test certificate generation
- [ ] Add SSL/HTTPS
- [ ] Setup monitoring

---

## Next Steps

1. **Test locally:** `python web/app.py`
2. **Choose hosting:** Heroku/Cloud Run/Fly.io
3. **Deploy:** Follow platform instructions
4. **Test on live:** Go to your domain, test workflow
5. **Share with users:** Add to your website/email signup

---

**Questions?** Check Flask/Google API docs or contact support.

Your app is now production-ready!
