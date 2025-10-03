#!/usr/bin/env python3
"""
Setup script for OpenAI Vector Store CLI Tool
"""

import os
import sys
import subprocess
from pathlib import Path

def check_python_version():
    """Check if Python version is 3.8 or higher"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        sys.exit(1)
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")

def install_requirements():
    """Install required packages"""
    print("📦 Installing required packages...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Requirements installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install requirements: {e}")
        sys.exit(1)

def create_env_file():
    """Create .env file if it doesn't exist"""
    env_file = Path(".env")
    if not env_file.exists():
        print("📝 Creating .env file...")
        with open(env_file, "w") as f:
            f.write("# OpenAI Configuration\n")
            f.write("DIRECT_OPENAI_API_KEY=your_openai_api_key_here\n")
            f.write("OPENAI_MODEL=gpt-4o\n\n")
            f.write("# Vector Store Configuration (optional)\n")
            f.write("VECTOR_STORE_ID=vs_your_vector_store_id_here\n")
        print("✅ .env file created. Please edit it with your API key.")
    else:
        print("ℹ️ .env file already exists")

def make_cli_executable():
    """Make CLI executable"""
    cli_file = Path("cli.py")
    if cli_file.exists():
        os.chmod(cli_file, 0o755)
        print("✅ CLI made executable")

def main():
    """Main setup function"""
    print("🚀 Setting up OpenAI Vector Store CLI Tool")
    print("=" * 50)
    
    check_python_version()
    install_requirements()
    create_env_file()
    make_cli_executable()
    
    print("\n🎉 Setup complete!")
    print("\nNext steps:")
    print("1. Edit .env file with your OpenAI API key")
    print("2. Run: python cli.py --help")
    print("3. Upload documents: python cli.py upload ./data")
    print("4. Ask questions: python cli.py qna 'Your question here'")

if __name__ == "__main__":
    main()
