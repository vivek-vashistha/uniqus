#!/usr/bin/env python3
"""
Test script to verify the real implementation integration
"""

import os
import sys
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

def test_openai_connection():
    """Test OpenAI API connection"""
    api_key = os.getenv("DIRECT_OPENAI_API_KEY")
    if not api_key:
        print("❌ DIRECT_OPENAI_API_KEY is missing in .env")
        return False
    
    try:
        client = OpenAI(api_key=api_key)
        # Test with a simple API call
        response = client.models.list()
        print("✅ OpenAI API connection successful")
        return True
    except Exception as e:
        print(f"❌ OpenAI API connection failed: {e}")
        return False

def test_vector_store_creation():
    """Test vector store creation"""
    api_key = os.getenv("DIRECT_OPENAI_API_KEY")
    if not api_key:
        print("❌ DIRECT_OPENAI_API_KEY is missing in .env")
        return False
    
    try:
        client = OpenAI(api_key=api_key)
        # Create a test vector store
        vs = client.vector_stores.create(name="test_integration")
        print(f"✅ Vector store created: {vs.id}")
        
        # Clean up
        client.vector_stores.delete(vector_store_id=vs.id)
        print("✅ Vector store cleaned up")
        return True
    except Exception as e:
        print(f"❌ Vector store creation failed: {e}")
        return False

def test_file_upload():
    """Test file upload to OpenAI"""
    api_key = os.getenv("DIRECT_OPENAI_API_KEY")
    if not api_key:
        print("❌ DIRECT_OPENAI_API_KEY is missing in .env")
        return False
    
    try:
        client = OpenAI(api_key=api_key)
        
        # Create a test file
        test_content = b"This is a test contract document for ASC-606 analysis."
        test_file = ("test_contract.txt", test_content)
        
        # Upload file
        created = client.files.create(file=test_file, purpose="assistants")
        print(f"✅ File uploaded: {created.id}")
        
        # Clean up
        client.files.delete(created.id)
        print("✅ File cleaned up")
        return True
    except Exception as e:
        print(f"❌ File upload failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Testing Contract→606 Intelligence Integration")
    print("=" * 50)
    
    tests = [
        ("OpenAI API Connection", test_openai_connection),
        ("Vector Store Creation", test_vector_store_creation),
        ("File Upload", test_file_upload)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🔍 Testing: {test_name}")
        if test_func():
            passed += 1
        else:
            print(f"❌ {test_name} failed")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("✅ All tests passed! Integration is ready.")
        return True
    else:
        print("❌ Some tests failed. Check your configuration.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
