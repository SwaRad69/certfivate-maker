# Getting Started - Certificate Generator

## For Local Development

### Quick Start (Windows PowerShell)

```powershell
# 1. Navigate to the project
cd "C:\Users\hebba_sglgqoe\Desktop\silly projects\certfivate maker"

# 2. Activate virtual environment
.\.venv\Scripts\Activate.ps1

# 3. Go to web directory
cd web

# 4. Start the app
python app.py
```

Then open http://localhost:5000/ in your browser.

---

## For Production Deployment

### Prerequisites Checklist
- [ ] Git installed
- [ ] GitHub account
- [ ] Render.com account  
- [ ] Google Cloud Console with OAuth2 credentials

### Deployment Steps

1. **Create `.gitignore`** (already created)
2. **Initialize Git** (you've already done this)
3. **Read [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)** - Complete step-by-step guide
4. **Follow the 8 steps in the guide:**
   - Step 1: Prepare repo (done)
   - Step 2: Generate secret key
   - Step 3: Push to GitHub
   - Step 4: Create Render service
   - Step 5: Upload credentials
   - Step 6: Update Google OAuth
   - Step 7: Deploy
   - Step 8: Test

### Essential Files for Deployment

The following files are already created:
- `Procfile` - Tells Render how to run your app
- `runtime.txt` - Specifies Python version
- `.gitignore` - Excludes secret files
- `DEPLOYMENT_GUIDE.md` - Complete deployment instructions
- `requirements.txt` - All Python dependencies

### Never Commit to Git

These files are in `.gitignore` and should NEVER be committed:
- `client_secrets.json` - Your OAuth2 credentials
- `credentials.json` - Service account credentials
- `.env` - Local environment variables
- `.venv/` - Virtual environment

---

## Troubleshooting

### "ModuleNotFoundError" when running locally
```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Flask won't start
- Make sure you're in the `web/` directory before running `python app.py`
- Check that port 5000 isn't in use: `netstat -ano | findstr :5000`

### Google authentication errors
- Verify `client_secrets.json` exists in `web/` directory
- Check that redirect URI in Google Cloud Console matches `http://localhost:5000/auth/callback`

### "FLASK_ENV not recognized" 
- It's normal in development - Flask defaults to development mode if not set

---

## File Structure

```
certfivate maker/
├── web/
│   ├── app.py                 # Main Flask application
│   ├── generator.py           # Certificate generation logic
│   ├── file_converter.py      # Multi-format file conversion
│   ├── config.py              # Configuration
│   ├── templates/             # HTML templates
│   ├── static/                # CSS & JavaScript
│   ├── requirements.txt        # Python dependencies
│   └── client_secrets.json    # (NOT in Git - add manually)
├── generator.py               # CLI certificate generator
├── config.py                  # CLI configuration
├── .env                       # (NOT in Git - copy from .env.example)
├── .env.example              # Environment template
├── .gitignore                # Git ignore rules
├── Procfile                  # Render deployment config
├── runtime.txt               # Python version
├── requirements.txt          # Root dependencies (symlinked to web/)
├── DEPLOYMENT_GUIDE.md       # Production deployment guide
├── QUICK_START.md            # Quick start guide
└── README.md                 # Project overview
```

---

## Next Steps

1. **Test locally**: Run the app locally first to make sure everything works
2. **Read DEPLOYMENT_GUIDE.md**: For complete deployment instructions
3. **Push to GitHub**: When ready to deploy
4. **Deploy to Render**: Follow steps in DEPLOYMENT_GUIDE.md

---

## Support

If you hit issues:
1. Check the logs (Render shows them in the dashboard)
2. Review DEPLOYMENT_GUIDE.md troubleshooting section
3. Verify all environment variables are set correctly
4. Ensure client_secrets.json is uploaded properly
