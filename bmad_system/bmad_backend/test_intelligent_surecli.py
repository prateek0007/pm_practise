#!/usr/bin/env python3
"""
Test script for the Intelligent SureCli System

This script demonstrates the new intelligent file operations capabilities
of SureCli that can understand AI responses and autonomously perform:
- File writing (create/overwrite)
- File appending 
- File deletion
- File searching
- Directory creation
"""

import os
import sys
import tempfile
import shutil
import json
from typing import List, Dict

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from src.llm_clients.sure_cli_client import SureCliClient
    print("✅ Successfully imported SureCliClient")
except ImportError as e:
    print(f"❌ Failed to import SureCliClient: {e}")
    sys.exit(1)


class MockLogHandler:
    """Mock log handler to capture SureCli logs during testing"""
    
    def __init__(self):
        self.logs: List[tuple] = []
    
    def log_callback(self, level: str, message: str):
        self.logs.append((level, message))
        print(f"[{level}] {message}")
    
    def get_logs_by_level(self, level: str) -> List[str]:
        return [msg for lvl, msg in self.logs if lvl == level]


def test_structured_file_operations():
    """Test the new structured file_operations JSON format"""
    print("\n🧪 Testing Structured File Operations...")
    
    # Create temporary directory for testing
    test_dir = tempfile.mkdtemp(prefix="surecli_test_")
    print(f"📁 Test directory: {test_dir}")
    
    try:
        # Create SureCli client and set up logging
        client = SureCliClient()
        log_handler = MockLogHandler()
        client.set_log_callback(log_handler.log_callback)
        
        # Test JSON with structured file_operations array
        test_response = json.dumps({
            "file_operations": [
                {
                    "filename": "test_app.py",
                    "operation": "write",
                    "content": "#!/usr/bin/env python3\nprint('Hello, Intelligent SureCli!')\n"
                },
                {
                    "filename": "README.md",
                    "operation": "write", 
                    "content": "# Test Project\n\nThis is a test project created by Intelligent SureCli.\n"
                },
                {
                    "filename": "data/",
                    "operation": "create_dir"
                },
                {
                    "filename": "data/config.json",
                    "operation": "write",
                    "content": '{"app_name": "SureCliTest", "version": "1.0.0"}'
                }
            ]
        })
        
        # Execute file operations
        success = client._parse_and_execute_file_operations(test_response, test_dir)
        
        # Verify results
        assert success, "File operations should succeed"
        assert os.path.exists(os.path.join(test_dir, "test_app.py")), "Python file should be created"
        assert os.path.exists(os.path.join(test_dir, "README.md")), "README should be created"
        assert os.path.exists(os.path.join(test_dir, "data")), "Data directory should be created"
        assert os.path.exists(os.path.join(test_dir, "data", "config.json")), "Config file should be created"
        
        # Check file contents
        with open(os.path.join(test_dir, "test_app.py"), "r") as f:
            content = f.read()
            assert "Hello, Intelligent SureCli!" in content, "Python file should contain expected content"
        
        # Check logs
        info_logs = log_handler.get_logs_by_level("INFO")
        assert any("SureCli Intelligent CLI: Analyzing AI response" in log for log in info_logs), "Should log analysis start"
        assert any("Found structured file_operations array" in log for log in info_logs), "Should detect structured format"
        assert any("File created: test_app.py" in log for log in info_logs), "Should log file creation"
        
        print("✅ Structured file operations test passed!")
        return True
        
    finally:
        # Clean up
        shutil.rmtree(test_dir, ignore_errors=True)


def test_legacy_files_format():
    """Test backward compatibility with legacy files array format"""
    print("\n🧪 Testing Legacy Files Format...")
    
    test_dir = tempfile.mkdtemp(prefix="surecli_legacy_test_")
    print(f"📁 Test directory: {test_dir}")
    
    try:
        client = SureCliClient()
        log_handler = MockLogHandler()
        client.set_log_callback(log_handler.log_callback)
        
        # Test legacy files array format
        test_response = json.dumps({
            "files": [
                {
                    "path": "legacy_app.py",
                    "content": "print('Legacy format works!')"
                },
                {
                    "path": "docs/",
                    "is_dir": true
                },
                {
                    "path": "docs/guide.md",
                    "content": "# Legacy Documentation\n\nThis tests legacy compatibility."
                }
            ]
        })
        
        success = client._parse_and_execute_file_operations(test_response, test_dir)
        
        # Verify results
        assert success, "Legacy format should work"
        assert os.path.exists(os.path.join(test_dir, "legacy_app.py")), "Legacy Python file should be created"
        assert os.path.exists(os.path.join(test_dir, "docs")), "Docs directory should be created"
        assert os.path.exists(os.path.join(test_dir, "docs", "guide.md")), "Guide file should be created"
        
        # Check logs
        info_logs = log_handler.get_logs_by_level("INFO")
        assert any("Found legacy files array" in log for log in info_logs), "Should detect legacy format"
        
        print("✅ Legacy files format test passed!")
        return True
        
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_auto_detection():
    """Test auto-detection of file operations from content keys"""
    print("\n🧪 Testing Auto-Detection...")
    
    test_dir = tempfile.mkdtemp(prefix="surecli_autodetect_test_")
    print(f"📁 Test directory: {test_dir}")
    
    try:
        client = SureCliClient()
        log_handler = MockLogHandler()
        client.set_log_callback(log_handler.log_callback)
        
        # Test auto-detection from simple key-value pairs
        test_response = json.dumps({
            "main.py": "def main():\n    print('Auto-detected!')\n\nif __name__ == '__main__':\n    main()",
            "requirements.txt": "flask>=2.0.0\nrequests>=2.25.0",
            "README.md": "# Auto-Detected Project\n\nThis was detected automatically!",
            "config.json": '{"auto_detected": true, "version": "1.0"}'
        })
        
        success = client._parse_and_execute_file_operations(test_response, test_dir)
        
        # Verify results
        assert success, "Auto-detection should work"
        assert os.path.exists(os.path.join(test_dir, "main.py")), "Main.py should be created"
        assert os.path.exists(os.path.join(test_dir, "requirements.txt")), "Requirements should be created"
        assert os.path.exists(os.path.join(test_dir, "README.md")), "README should be created"
        assert os.path.exists(os.path.join(test_dir, "config.json")), "Config should be created"
        
        # Check logs
        info_logs = log_handler.get_logs_by_level("INFO")
        assert any("auto-detecting from content keys" in log for log in info_logs), "Should use auto-detection"
        assert any("Auto-detected" in log for log in info_logs), "Should log auto-detection"
        
        print("✅ Auto-detection test passed!")
        return True
        
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_append_operations():
    """Test file append operations"""
    print("\n🧪 Testing Append Operations...")
    
    test_dir = tempfile.mkdtemp(prefix="surecli_append_test_")
    print(f"📁 Test directory: {test_dir}")
    
    try:
        client = SureCliClient()
        log_handler = MockLogHandler()
        client.set_log_callback(log_handler.log_callback)
        
        # First, create a base file
        base_file = os.path.join(test_dir, "log.txt")
        with open(base_file, "w") as f:
            f.write("Initial log entry\n")
        
        # Test append operation
        test_response = json.dumps({
            "file_operations": [
                {
                    "filename": "log.txt",
                    "operation": "append",
                    "content": "Appended log entry\nAnother appended line\n"
                }
            ]
        })
        
        success = client._parse_and_execute_file_operations(test_response, test_dir)
        
        # Verify results
        assert success, "Append operation should succeed"
        
        with open(base_file, "r") as f:
            content = f.read()
            assert "Initial log entry" in content, "Original content should remain"
            assert "Appended log entry" in content, "Appended content should be added"
            assert "Another appended line" in content, "Multiple appended lines should work"
        
        # Check logs
        info_logs = log_handler.get_logs_by_level("INFO")
        assert any("Content appended: log.txt" in log for log in info_logs), "Should log append operation"
        
        print("✅ Append operations test passed!")
        return True
        
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def run_all_tests():
    """Run all tests for the Intelligent SureCli System"""
    print("🚀 Starting Intelligent SureCli System Tests")
    print("=" * 60)
    
    tests = [
        test_structured_file_operations,
        test_legacy_files_format,
        test_auto_detection,
        test_append_operations
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
                print(f"❌ {test.__name__} failed")
        except Exception as e:
            failed += 1
            print(f"❌ {test.__name__} failed with error: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed! Intelligent SureCli System is working correctly!")
        return True
    else:
        print("⚠️ Some tests failed. Please check the implementation.")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)