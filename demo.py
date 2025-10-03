#!/usr/bin/env python3
"""
Demo script showing how to use the OpenAI Vector Store CLI Tool
"""

import subprocess
import sys
import os

def run_command(cmd, description):
    """Run a command and display the result"""
    print(f"\n🔧 {description}")
    print(f"Command: {cmd}")
    print("-" * 50)
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(f"Error: {result.stderr}")
        return result.returncode == 0
    except Exception as e:
        print(f"Error running command: {e}")
        return False

def main():
    """Demo main function"""
    print("🎯 OpenAI Vector Store CLI Tool Demo")
    print("=" * 50)
    
    # Check if .env exists
    if not os.path.exists(".env"):
        print("❌ .env file not found. Please run setup.py first.")
        sys.exit(1)
    
    # Demo commands
    demos = [
        ("python cli.py --help", "Show main help"),
        ("python cli.py upload --help", "Show upload help"),
        ("python cli.py qna --help", "Show QnA help"),
        ("python cli.py clear --help", "Show clear help"),
        ("python cli.py list --help", "Show list help"),
    ]
    
    for cmd, description in demos:
        success = run_command(cmd, description)
        if not success:
            print("❌ Command failed")
        else:
            print("✅ Command successful")
    
    print("\n📚 Example Usage:")
    print("1. Upload documents: python cli.py upload ./data --name 'my_knowledge_base'")
    print("2. List files: python cli.py list")
    print("3. Ask questions: python cli.py qna 'Is the contract approved?'")
    print("4. Clear store: python cli.py clear --vector-store-id vs_your_id")
    
    print("\n💡 Note: Make sure to set your OPENAI_API_KEY in .env file before using upload/qna commands")

if __name__ == "__main__":
    main()
