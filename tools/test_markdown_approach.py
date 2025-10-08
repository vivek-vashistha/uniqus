#!/usr/bin/env python3
"""
Test script for the new markdown-based ASC 606 analysis approach
"""

import os
import sys
from pathlib import Path

# Add the tools directory to the path
sys.path.append(str(Path(__file__).parent))

def test_template_loading():
    """Test if we can load the markdown templates"""
    print("🧪 Testing template loading...")
    
    try:
        from asc606_markdown_filler import load_markdown_template
        
        for step in range(1, 6):
            step_name = f"step{step}"
            template = load_markdown_template(step_name)
            print(f"  ✅ {step_name}: {len(template)} characters")
            
            # Check for placeholders
            placeholder_count = template.count("{")
            print(f"     📝 Found {placeholder_count} placeholders")
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False
    
    return True

def test_context_building():
    """Test context building functionality"""
    print("\n🧪 Testing context building...")
    
    try:
        from asc606_markdown_filler import build_context_for_step
        
        # Create a test output directory
        test_dir = Path("test_output")
        test_dir.mkdir(exist_ok=True)
        
        # Create some dummy step files
        for i in range(1, 4):
            step_file = test_dir / f"step{i}_filled.md"
            with open(step_file, "w") as f:
                f.write(f"# Step {i} Results\n\nThis is dummy content for step {i}.\n")
        
        # Test context building
        context = build_context_for_step(4, str(test_dir))
        print(f"  ✅ Context length: {len(context)} characters")
        print(f"  📄 Context preview: {context[:200]}...")
        
        # Cleanup
        import shutil
        shutil.rmtree(test_dir)
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False
    
    return True

def test_requirements():
    """Test if all required dependencies are available"""
    print("\n🧪 Testing requirements...")
    
    try:
        import openai
        print("  ✅ openai package available")
    except ImportError:
        print("  ❌ openai package not found")
        return False
    
    try:
        from dotenv import load_dotenv
        print("  ✅ python-dotenv available")
    except ImportError:
        print("  ❌ python-dotenv not found")
        return False
    
    # Check for API key
    api_key = os.getenv("DIRECT_OPENAI_API_KEY")
    if api_key:
        print("  ✅ OPENAI_API_KEY found")
    else:
        print("  ⚠️  OPENAI_API_KEY not found in environment")
    
    return True

def main():
    """Run all tests"""
    print("🚀 Testing ASC 606 Markdown Filler")
    print("=" * 50)
    
    tests = [
        test_requirements,
        test_template_loading,
        test_context_building,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The markdown approach is ready to use.")
        print("\n📖 Usage:")
        print("1. Ingest files: python asc606_markdown_filler.py ingest --contract_id C-001 --files contract.pdf")
        print("2. Analyze: python asc606_markdown_filler.py analyze --contract_id C-001 --output_dir ./output")
    else:
        print("❌ Some tests failed. Please check the errors above.")

if __name__ == "__main__":
    main()
