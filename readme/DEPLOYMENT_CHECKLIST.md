# 🚀 Production Deployment Checklist

Use this checklist to ensure everything is ready for deployment to Render.

## Pre-Deployment (Local)

- [ ] All code committed to Git locally
- [ ] `.env` file created (from `.env.example`)
- [ ] `client_secrets.json` exists in `web/` directory
- [ ] App runs locally without errors: `python web/app.py`
- [ ] Google authentication works locally
- [ ] Certificate generation tested locally
- [ ] No hardcoded secrets in code
- [ ] `.gitignore` has `client_secrets.json` and `.env` entries

## GitHub Setup

- [ ] GitHub account created
- [ ] New repository created named `certfivate-maker`
- [ ] Git initialized locally (`git init`)
- [ ] Remote added: `git remote add origin https://github.com/YOUR_USERNAME/certfivate-maker.git`
- [ ] All files committed: `git add .` then `git commit -m "Initial commit"`
- [ ] Pushed to GitHub: `git push -u origin main`
- [ ] Repository is public (for Render to access)

## Google Cloud Setup

- [ ] Google Cloud Console project created
- [ ] OAuth 2.0 credentials created (Desktop application)
- [ ] `client_secrets.json` downloaded
- [ ] OAuth scope includes: `drive`, `presentations`, `spreadsheets.readonly`
- [ ] Initial authorized redirect URI: `http://localhost:5000/auth/callback`

## Render Setup

### Create Account & Service
- [ ] Render account created (https://render.com)
- [ ] Signed up with GitHub
- [ ] GitHub repository connected
- [ ] New Web Service created
- [ ] Environment set to `Python 3`
- [ ] Build command: `pip install -r requirements.txt`
- [ ] Start command: `cd web && gunicorn -w 4 -b 0.0.0.0:$PORT app:app`
- [ ] Plan: `Free`

### Environment Variables
- [ ] `FLASK_ENV` = `production`
- [ ] `FLASK_SECRET_KEY` = [strong random 32-byte key]
- [ ] `GOOGLE_OAUTH_SECRETS_BASE64` = [base64-encoded client_secrets.json content]
  - OR `GOOGLE_OAUTH_SECRETS` = `client_secrets.json` + upload as Secret File
- [ ] `YOUTUBE_EMBED` = [optional YouTube embed code]

### Credentials Upload
- [ ] Chose method for uploading `client_secrets.json`:
  - [ ] Option A: Encoded as `GOOGLE_OAUTH_SECRETS_BASE64` environment variable
  - [ ] Option B: Uploaded as Secret File in Render
- [ ] Verified credentials are not in Git history

## Google OAuth Configuration

- [ ] Added Render app URL to Google Cloud authorized redirect URIs
  - Example: `https://certfivate-maker.onrender.com/auth/callback`
- [ ] Kept `http://localhost:5000/auth/callback` for local development
- [ ] OAuth 2.0 Client ID is unrestricted (or added Render domain)

## Production Code Changes

- [ ] `app.py` has proper environment handling for FLASK_ENV
- [ ] `OAUTHLIB_INSECURE_TRANSPORT` only set in development mode
- [ ] Secret key is pulled from environment variable
- [ ] All API keys and credentials use environment variables
- [ ] No console.log() or debug print statements left in
- [ ] Logging is configured for production

## Deployment

- [ ] All local commits pushed to GitHub
- [ ] Render deployment triggered (automatic or manual)
- [ ] Deployment logs show no errors
- [ ] Build completed successfully
- [ ] Service is running (not in build or crash loop)

## Post-Deployment Testing

- [ ] App loads at `https://certfivate-maker.onrender.com/` (actual URL will differ)
- [ ] Landing page displays correctly
- [ ] "Get Started with Google" button works
- [ ] Google OAuth redirect works without errors
- [ ] Dashboard loads after authentication
- [ ] Can select Google Drive files
- [ ] Can upload CSV files
- [ ] Can select Google Slides template
- [ ] Certificate generation completes
- [ ] PDFs save to Google Drive successfully
- [ ] No sensitive data in browser logs
- [ ] HTTPS is enabled (automatic with Render)

## Troubleshooting

If deployment fails:

- [ ] Check Render deployment logs for errors
- [ ] Verify environment variables are set correctly
- [ ] Confirm `client_secrets.json` is uploaded properly
- [ ] Check Google OAuth redirect URI matches exactly
- [ ] Try reducing gunicorn workers: `-w 2` instead of `-w 4`
- [ ] Check for missing Python dependencies

If OAuth fails in production:

- [ ] Verify Render app URL in Google Cloud Console
- [ ] Check that domain isn't blocked by browser
- [ ] Clear browser cache and cookies
- [ ] Try in incognito/private window

## Performance Tuning (Optional)

Once fully working, consider:

- [ ] Upgrade to Render Standard plan ($7/month) for always-on service
- [ ] Add UptimeRobot monitoring to keep app alive on free plan
- [ ] Optimize for faster cold starts if needed
- [ ] Monitor logs for performance issues

---

## Need Help?

1. Check [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) for detailed steps
2. Review [GETTING_STARTED.md](./GETTING_STARTED.md) for local setup
3. Check Render logs: Dashboard → Service → Logs tab
4. Google Cloud Console: Check OAuth credentials and authorized URIs

**Remember**: Never commit `client_secrets.json` or `.env` to Git!
