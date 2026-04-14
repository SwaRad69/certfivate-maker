#!/usr/bin/env python
"""
Quick setup and development server startup script for Certificate Generator
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    """Setup and start the development server"""
    
    project_root = Path(__file__).parent
    venv_path = project_root / '.venv'
    web_dir = project_root / 'web'
    
    print("=" * 60)
    print("🎓 Certificate Generator - Development Setup")
    print("=" * 60)
    
    # Step 1: Check if venv exists
    if not venv_path.exists():
        print("\n❌ Virtual environment not found!")
        print("\nCreate one with:")
        print(f"  python -m venv .venv")
        print(f"  .venv\\Scripts\\activate  (Windows)")
        return 1
    
    # Step 2: Ensure .env exists
    env_file = project_root / '.env'
    env_example = project_root / '.env.example'
    
    if not env_file.exists() and env_example.exists():
        print(f"\n⚠️  No .env file found. Creating from .env.example...")
        with open(env_example) as src:
            with open(env_file, 'w') as dst:
                dst.write(src.read())
        print("✅ Created .env - Update with your actual values")
    
    # Step 3: Check for client_secrets.json
    client_secrets = web_dir / 'client_secrets.json'
    credentials_example = project_root / 'credentials.json.example'
    
    if not client_secrets.exists():
        print(f"\n❌ Missing client_secrets.json!")
        print("\nTo get it:")
        print("1. Go to Google Cloud Console: https://console.cloud.google.com/")
        print("2. Create OAuth 2.0 credentials (Desktop application)")
        print("3. Download the JSON file")
        print("4. Save as: web/client_secrets.json")
        print("\n⚠️  Cannot start server without this file")
        return 1
    
    # Step 4: Install dependencies
    print("\n📦 Checking dependencies...")
    requirements = web_dir / 'requirements.txt'
    
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '-q', '-r', str(requirements)],
            cwd=str(web_dir),
            capture_output=True,
            timeout=60
        )
        if result.returncode == 0:
            print("✅ Dependencies installed")
        else:
            print("⚠️  Dependency installation had warnings")
    except Exception as e:
        print(f"❌ Failed to install dependencies: {e}")
        return 1
    
    # Step 5: Start the server
    print("\n" + "=" * 60)
    print("🚀 Starting Flask development server...")
    print("=" * 60)
    print("\n📍 Server running at: http://localhost:5000/")
    print("🛑 Press Ctrl+C to stop\n")
    
    os.chdir(str(web_dir))
    
    try:
        subprocess.run([sys.executable, 'app.py'])
    except KeyboardInterrupt:
        print("\n\n✅ Server stopped")
        return 0
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
