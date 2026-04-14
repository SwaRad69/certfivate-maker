# Web App Quick Start

Get the Certificate Generator web app running locally in 5 minutes.

---

## Prerequisites

- Python 3.8+
- Google Cloud Project with Drive & Slides APIs enabled
- OAuth2 Client ID (JSON) from Google Cloud Console

**Don't have these?** Follow [WEB_DEPLOYMENT_GUIDE.md](WEB_DEPLOYMENT_GUIDE.md) Part 1 first.

---

## Step 1: Get OAuth2 Credentials (5 min)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. **APIs & Services** → **Credentials** → **+ CREATE CREDENTIALS**
3. Select **OAuth 2.0 Client ID** → **Web application**
4. Add authorized URIs:
   - Authorized JavaScript origin: `http://localhost:5000`
   - Authorized redirect URI: `http://localhost:5000/auth/callback`
5. Click **CREATE**
6. Click **DOWNLOAD JSON**
7. Save as `client_secrets.json` in the `web/` folder

```
certificate-maker/
└── web/
    ├── app.py
    ├── client_secrets.json    ← Place here
    └── requirements.txt
```

---

## Step 2: Install Dependencies (1 min)

```bash
cd web
pip install -r requirements.txt
```

---

## Step 3: Create .env File (1 min)

Create `web/.env`:

```env
FLASK_ENV=development
FLASK_SECRET_KEY=dev-secret-key
GOOGLE_OAUTH_SECRETS=client_secrets.json
PORT=5000
```

---

## Step 4: Run the App (1 min)

```bash
python app.py
```

**Output:**
```
 * Running on http://127.0.0.1:5000
```

---

## Step 5: Test It

1. Open browser: `http://localhost:5000`
2. Click "Sign In with Google"
3. Authorize the app
4. Upload a sample CSV file
5. Enter your template ID
6. Click "Generate"
7. Check your Google Drive for certificates

---

## Testing Checklist

- [ ] App runs without errors
- [ ] OAuth login works
- [ ] Dashboard loads after login
- [ ] Can upload CSV file
- [ ] Template ID accepted
- [ ] Generation starts/completes
- [ ] Certificates appear in Drive

---

## File Structure

```
web/
├── app.py                      # Flask application
├── static/
│   ├── style.css              # Styling
│   └── main.js                # JavaScript
├── templates/
│   ├── base.html              # Base template
│   ├── login.html             # Login page
│   ├── dashboard.html         # Main interface
│   ├── help.html              # Help page
│   ├── 404.html               # Error pages
│   └── 500.html
├── client_secrets.json        # OAuth credentials (Git ignored)
├── .env                       # Environment variables (Git ignored)
└── requirements.txt           # Python dependencies
```

---

## Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `FLASK_ENV` | Development or production | `development` |
| `FLASK_SECRET_KEY` | Session encryption key | Long random string |
| `GOOGLE_OAUTH_SECRETS` | Path to OAuth JSON | `client_secrets.json` |
| `PORT` | Port to run on | `5000` |

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'flask'"

**Fix:** Install dependencies
```bash
pip install -r requirements.txt
```

### "FileNotFoundError: client_secrets.json"

**Fix:** Download from Google Cloud Console and place in `web/` folder

### OAuth redirect URI mismatch error

**Fix:** 
1. Check URL matches: `http://localhost:5000`
2. Update in Google Cloud Console if different
3. Wait 5 min for changes to sync

### "Permission denied" generating certificates

**Fix:**
1. Verify template is shared with your Google account
2. Try refreshing Google Drive browser tab
3. Check template permissions (should be "Editor")

### App crashes after login

**Check logs:**
1. Look for errors in console
2. Verify CSV file format
3. Verify template ID is correct

---

## Common Issues

**Q: Certificates not appearing in Drive**
- A: Check output folder name (default: "Certificate Generator")
- A: Refresh Google Drive (F5)
- A: Check generation log for errors

**Q: "Invalid template ID"**
- A: ID should be 26+ characters
- A: Copy full ID from Google Slides URL
- A: Must be a Slides presentation, not Docs/Sheets

**Q: CSV validation error**
- A: Column names must match placeholders exactly (case-sensitive)
- A: Example: `{{Name}}` requires "Name" column in CSV

---

## Next: Deploy to Production

When ready to deploy:

1. See [WEB_DEPLOYMENT_GUIDE.md](WEB_DEPLOYMENT_GUIDE.md)
2. Choose hosting (Heroku, Cloud Run, Fly.io, etc.)
3. Follow deployment steps
4. Update Google OAuth redirect URIs
5. Test on live URL

---

## Development Tips

**Enable Debug Mode:**

Edit `app.py`:
```python
if __name__ == '__main__':
    app.run(debug=True)  # Auto-reload on changes
```

**Test With Sample Data:**

Use `sample_participants.csv` from root:
```bash
# Copy to web folder
cp sample_participants.csv web/
```

**Monitor Requests:**

Add logging to see what's happening:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## Local Development Workflow

1. **Make code changes**
2. **Save file** (auto-reload if debug mode)
3. **Test in browser** (refresh page)
4. **Check console** for errors
5. **Commit changes**: `git add . && git commit -m "message"`

---

**Ready?** Start the app: `python app.py` 🚀
