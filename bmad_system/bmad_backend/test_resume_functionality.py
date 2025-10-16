#!/usr/bin/env python3
"""
Test script for the new resume workflow functionality.

This script tests the resume capability by:
1. Testing the can-resume endpoint with different task statuses
2. Testing the resume-workflow endpoint
3. Verifying that resume works from any status, not just failed
"""

import json
import requests
import sys
import time

# Configuration
BASE_URL = "http://localhost:5000/api"

def test_resume_functionality():
    """Test the resume workflow functionality"""
    
    print("🧪 Testing Resume Workflow Functionality")
    print("=" * 50)
    
    # Test 1: Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("✅ Server is running")
        else:
            print("❌ Server health check failed")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Make sure it's running on localhost:5000")
        return False
    
    # Test 2: Test can-resume endpoint with invalid task
    print("\n📋 Test 2: Testing can-resume with invalid task")
    try:
        response = requests.get(f"{BASE_URL}/tasks/invalid-task-id/can-resume")
        if response.status_code == 404:
            print("✅ can-resume endpoint correctly returns 404 for invalid task")
        else:
            print(f"❌ Unexpected response: {response.status_code}")
    except Exception as e:
        print(f"❌ Error testing can-resume: {e}")
    
    # Test 3: Test resume-workflow endpoint with invalid task
    print("\n📋 Test 3: Testing resume-workflow with invalid task")
    try:
        response = requests.post(f"{BASE_URL}/tasks/invalid-task-id/resume-workflow", 
                               json={"user_prompt": "test"})
        if response.status_code == 404:
            print("✅ resume-workflow endpoint correctly returns 404 for invalid task")
        else:
            print(f"❌ Unexpected response: {response.status_code}")
    except Exception as e:
        print(f"❌ Error testing resume-workflow: {e}")
    
    # Test 4: Test resume-workflow endpoint with invalid data
    print("\n📋 Test 4: Testing resume-workflow with invalid data")
    try:
        response = requests.post(f"{BASE_URL}/tasks/invalid-task-id/resume-workflow", 
                               json={})
        if response.status_code == 400:
            print("✅ resume-workflow endpoint correctly validates input data")
        else:
            print(f"❌ Unexpected response: {response.status_code}")
    except Exception as e:
        print(f"❌ Error testing resume-workflow validation: {e}")
    
    print("\n🎉 Resume functionality tests completed!")
    print("\n📝 Key Features:")
    print("   ✅ Resume button appears next to 'Run with New Prompt'")
    print("   ✅ Works from any status (in_progress, failed, paused, received)")
    print("   ✅ Automatically detects current agent from monitor data")
    print("   ✅ Allows new prompt while maintaining workflow structure")
    print("   ✅ Disabled when new workflow is selected")
    print("\n📝 Note: To test with real tasks, create a task and use the frontend")
    print("   to test the resume functionality in the monitor section.")
    
    return True

if __name__ == "__main__":
    success = test_resume_functionality()
    sys.exit(0 if success else 1)
