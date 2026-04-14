# Certificate Generator - Documentation Index

Welcome! All documentation for the Certificate Generator project is organized here. Choose which guide to read based on your needs.

---

## Quick Start (5 minutes)

**New to the project?** Start here!

- **[WEB_QUICK_START.md](WEB_QUICK_START.md)** — Get the web app running locally in 5 minutes
- **[QUICK_START.md](QUICK_START.md)** — Get the CLI tool running locally

---

## Setup & Configuration

**Setting up for the first time?**

- **[ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md)** — How to create `.env` files and manage secrets
- **[SETUP_GUIDE.md](SETUP_GUIDE.md)** — Complete setup guide for Google Cloud credentials
- **[TEMPLATE_DESIGN_GUIDE.md](TEMPLATE_DESIGN_GUIDE.md)** — How to design certificates in Canva and set up Google Slides templates

---

## Usage Guides

**Ready to generate certificates?**

- **[README.md](README.md)** — Complete reference for the CLI tool with all command options
- **[WEB_QUICK_START.md](WEB_QUICK_START.md)** — How to use the web interface

---

## Deployment

**Ready to deploy to production?**

- **[WEB_DEPLOYMENT_GUIDE.md](WEB_DEPLOYMENT_GUIDE.md)** — Deploy to Heroku, Google Cloud Run, AWS, or your own server
- **[WEB_APP_COMPLETE.md](WEB_APP_COMPLETE.md)** — Web app features and architecture

---

## Project Information

**Want to understand the project structure?**

- **[PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)** — File organization and code modules
- **[IMPLEMENTATION_COMPLETE.md](IMPLEMENTATION_COMPLETE.md)** — What was built and completed
- **[COMPLETE_SUMMARY.md](COMPLETE_SUMMARY.md)** — Full project summary and features

---

## Documentation by Role

### For Users
1. Read [TEMPLATE_DESIGN_GUIDE.md](TEMPLATE_DESIGN_GUIDE.md) — Design your certificate
2. Follow [WEB_QUICK_START.md](WEB_QUICK_START.md) — Use the web app
3. Check [README.md](README.md) — Troubleshooting & reference

### For Developers
1. Read [ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md) — Setup environment
2. Check [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) — Understand code organization
3. Follow [SETUP_GUIDE.md](SETUP_GUIDE.md) — Configure Google Cloud

### For DevOps/Deployment
1. Read [WEB_DEPLOYMENT_GUIDE.md](WEB_DEPLOYMENT_GUIDE.md) — Choose your platform
2. Check [ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md) — Manage secrets
3. Follow platform-specific instructions (Heroku, GCP, AWS, etc.)

---

## Quick Links

| Document | Purpose | Duration |
|----------|---------|----------|
| WEB_QUICK_START.md | Run web app locally | 5 min |
| SETUP_GUIDE.md | Configure Google Cloud | 15 min |
| TEMPLATE_DESIGN_GUIDE.md | Design certificates | 20 min |
| ENVIRONMENT_SETUP.md | Manage .env files | 5 min |
| WEB_DEPLOYMENT_GUIDE.md | Deploy to production | 30 min |
| README.md | CLI reference | Reference |
| PROJECT_STRUCTURE.md | Code organization | Reference |

---

## ❓ Common Tasks

### "I want to generate certificates locally"
→ Read [QUICK_START.md](QUICK_START.md)

### "I want to use the web app"
→ Read [WEB_QUICK_START.md](WEB_QUICK_START.md)

### "I need to set up Google Cloud credentials"
→ Read [SETUP_GUIDE.md](SETUP_GUIDE.md)

### "I want to deploy the app online"
→ Read [WEB_DEPLOYMENT_GUIDE.md](WEB_DEPLOYMENT_GUIDE.md)

### "How do I design the certificate?"
→ Read [TEMPLATE_DESIGN_GUIDE.md](TEMPLATE_DESIGN_GUIDE.md)

### "What environment variables do I need?"
→ Read [ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md)

### "What files are in this project?"
→ Read [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)

---

## 📞 Need Help?

1. **Check the relevant guide** — Most answers are in the documentation above
2. **Review error logs** — Check `certificate_generator.log` or browser console
3. **Check credentials** — Verify `client_secrets.json` or `credentials.json` exists
4. **Run with `--verbose`** — Get detailed debug output: `python main.py --csv file.csv --template ID --verbose`

---

**Start with [WEB_QUICK_START.md](WEB_QUICK_START.md) if you're unsure!
