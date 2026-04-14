# Certificate Generator - Deploy to Production
# This script helps prepare your code for deployment to Render

# Stop on any error
$ErrorActionPreference = "Stop"

Write-Host "=========================================="
Write-Host "  Certificate Generator"
Write-Host "  Production Deployment Helper"
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check if git is installed
try {
    $gitVersion = git --version 2>&1
    Write-Host "✓ Git found: $gitVersion"
} catch {
    Write-Host "✗ Git not found! Install from: https://git-scm.com/download/win" -ForegroundColor Red
    exit 1
}

# Check if already a git repo
if (-not (Test-Path ".git")) {
    Write-Host "✗ Not a Git repository. Run: git init" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== DEPLOYMENT CHECKLIST ===" -ForegroundColor Yellow
Write-Host ""

# Check for committed changes
Write-Host "1. Checking for uncommitted changes..."
$status = git status --porcelain
if ($status) {
    Write-Host "   ✗ You have uncommitted changes:" -ForegroundColor Yellow
    Write-Host $status
    Write-Host ""
    Write-Host "   Commit them with:" -ForegroundColor Cyan
    Write-Host "   git add ."
    Write-Host "   git commit -m 'your message'"
    Write-Host ""
} else {
    Write-Host "   ✓ All changes committed" -ForegroundColor Green
}

# Check for secrets in git history
Write-Host ""
Write-Host "2. Checking for secrets in code..."
$secrets = @("client_secrets", "credentials.json", "FLASK_SECRET_KEY", "private_key")
$found = $false
foreach ($secret in $secrets) {
    $matches = git log --all --full-history -S $secret --oneline 2>&1 | Select-Object -First 3
    if ($matches) {
        Write-Host "   ⚠ Found '$secret' in git history:" -ForegroundColor Yellow
        Write-Host "   $matches"
        $found = $true
    }
}
if (-not $found) {
    Write-Host "   ✓ No obvious secrets found" -ForegroundColor Green
}

# Check .gitignore
Write-Host ""
Write-Host "3. Checking .gitignore..."
$gitignore = Get-Content ".gitignore" -ErrorAction SilentlyContinue
if ($gitignore -match "client_secrets.json") {
    Write-Host "   ✓ client_secrets.json is in .gitignore" -ForegroundColor Green
} else {
    Write-Host "   ✗ client_secrets.json NOT in .gitignore!" -ForegroundColor Red
}

if ($gitignore -match "\.env") {
    Write-Host "   ✓ .env is in .gitignore" -ForegroundColor Green
} else {
    Write-Host "   ✗ .env NOT in .gitignore!" -ForegroundColor Red
}

# Check for necessary files
Write-Host ""
Write-Host "4. Checking deployment files..."
$deploymentFiles = @(
    ("Procfile", "Render configuration"),
    ("runtime.txt", "Python version"),
    ("web/requirements.txt", "Dependencies"),
    ("DEPLOYMENT_GUIDE.md", "Deployment guide")
)

foreach ($file, $description in $deploymentFiles) {
    if (Test-Path $file) {
        Write-Host "   ✓ $file ($description)" -ForegroundColor Green
    } else {
        Write-Host "   ✗ Missing: $file" -ForegroundColor Red
    }
}

# Check git remote
Write-Host ""
Write-Host "5. Checking Git remote..."
$remote = git remote -v
if ($remote) {
    Write-Host "   ✓ Git remote configured:"
    $remote | ForEach-Object { Write-Host "     $_" }
} else {
    Write-Host "   ✗ No Git remote configured" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "   Add your GitHub repo:" -ForegroundColor Cyan
    Write-Host "   git remote add origin https://github.com/YOUR_USERNAME/certfivate-maker.git"
    Write-Host "   git branch -M main"
    Write-Host "   git push -u origin main"
}

# Summary
Write-Host ""
Write-Host "=== NEXT STEPS ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Read: DEPLOYMENT_GUIDE.md (complete guide)" -ForegroundColor Yellow
Write-Host "2. Read: DEPLOYMENT_CHECKLIST.md (verification steps)" -ForegroundColor Yellow
Write-Host ""
Write-Host "Quick deployment flow:" -ForegroundColor Cyan
Write-Host "  a) Generate secret key:"
Write-Host "     python -c ""import secrets; print(secrets.token_hex(32))"""
Write-Host ""
Write-Host "  b) Create GitHub repo and push:" -ForegroundColor Cyan
Write-Host "     git remote add origin https://github.com/YOUR_USERNAME/certfivate-maker.git"
Write-Host "     git branch -M main"
Write-Host "     git push -u origin main"
Write-Host ""
Write-Host "  c) Connect to Render.com"
Write-Host "     - Sign up at https://render.com"
Write-Host "     - Connect your GitHub account"
Write-Host "     - Create new Web Service"
Write-Host "     - Follow DEPLOYMENT_GUIDE.md for configuration"
Write-Host ""

Write-Host "Questions? See:" -ForegroundColor Yellow
Write-Host "  - DEPLOYMENT_GUIDE.md" -ForegroundColor Cyan
Write-Host "  - GETTING_STARTED.md" -ForegroundColor Cyan
Write-Host "  - DEPLOYMENT_CHECKLIST.md" -ForegroundColor Cyan
