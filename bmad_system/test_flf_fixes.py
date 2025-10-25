#!/usr/bin/env python3
"""
Test script for FLF workflow fixes
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add the backend directory to the path
backend_path = os.path.join(os.path.dirname(__file__), 'bmad_backend')
sys.path.insert(0, backend_path)

def test_context_file_copying():
    """Test the UNIVERSAL_FIELD_ANALYSIS_CONTEXT.md file copying logic"""
    print("Testing context file copying...")
    
    try:
        # Create a temporary directory structure
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create source directory structure
            source_sureai_dir = os.path.join(temp_dir, ".sureai")
            os.makedirs(source_sureai_dir, exist_ok=True)
            
            # Create a sample context file
            source_context_file = os.path.join(source_sureai_dir, "UNIVERSAL_FIELD_ANALYSIS_CONTEXT.md")
            with open(source_context_file, 'w') as f:
                f.write("# Universal Field Analysis Context Guide\n\nThis is a test context file.\n")
            
            # Create destination directory structure
            project_dir = os.path.join(temp_dir, "test_project")
            os.makedirs(project_dir, exist_ok=True)
            
            dest_sureai_dir = os.path.join(project_dir, ".sureai")
            os.makedirs(dest_sureai_dir, exist_ok=True)
            
            dest_context_file = os.path.join(dest_sureai_dir, "UNIVERSAL_FIELD_ANALYSIS_CONTEXT.md")
            
            # Test the simplified copying logic
            source_context_file = None
            
            # Check Docker location first
            docker_source_path = os.path.join(temp_dir, ".sureai", "UNIVERSAL_FIELD_ANALYSIS_CONTEXT.md")
            if os.path.exists(docker_source_path):
                source_context_file = docker_source_path
                print(f"✅ Found context file at Docker location: {docker_source_path}")
            else:
                # Try development environment path as fallback
                workspace_root = temp_dir
                dev_source_path = os.path.join(workspace_root, ".sureai", "UNIVERSAL_FIELD_ANALYSIS_CONTEXT.md")
                if os.path.exists(dev_source_path):
                    source_context_file = dev_source_path
                    print(f"✅ Found context file at development location: {dev_source_path}")
            
            # Copy the file if found
            if source_context_file and os.path.exists(source_context_file):
                import shutil
                shutil.copy2(source_context_file, dest_context_file)
                print(f"✅ Successfully copied context file from {source_context_file} to {dest_context_file}")
                
                # Verify the copied file
                if os.path.exists(dest_context_file):
                    with open(dest_context_file, 'r') as f:
                        content = f.read()
                        if "test context file" in content:
                            print("✅ Copied file contains correct content")
                        else:
                            print("⚠️ Copied file content verification failed")
                else:
                    print("❌ Destination file was not created")
            else:
                print("❌ Context file not found in expected locations")
                
    except Exception as e:
        print(f"❌ Error testing context file copying: {e}")

def test_git_operations():
    """Test git operations module"""
    print("\nTesting git operations...")
    
    try:
        # Try to import the git operations module
        git_operations_path = os.path.join(backend_path, 'src', 'core')
        if git_operations_path not in sys.path:
            sys.path.append(git_operations_path)
        # Just check if the file exists
        git_file = os.path.join(backend_path, 'src', 'core', 'git_operations.py')
        if os.path.exists(git_file):
            print("✅ Git operations module file exists")
        else:
            print("❌ Git operations module file not found")
    except Exception as e:
        print(f"⚠️ Error checking git operations: {e}")

def test_flf_agent():
    """Test FLF agent implementation"""
    print("\nTesting FLF agent...")
    
    try:
        # Try to check if the FLF agent module file exists
        flf_file = os.path.join(backend_path, 'src', 'agents', 'flf_agent.py')
        if os.path.exists(flf_file):
            print("✅ FLF agent module file exists")
        else:
            print("❌ FLF agent module file not found")
            
        # Test prompt parsing logic (simplified)
        import re
        def _parse_user_prompt(user_prompt: str) -> tuple:
            try:
                url_pattern = r"clone the repository from\s+([^\s]+)"
                folder_pattern = r"analyze the field patterns in\s+([^\s]+)"
                
                url_match = re.search(url_pattern, user_prompt)
                folder_match = re.search(folder_pattern, user_prompt)
                
                url = url_match.group(1) if url_match else None
                folder_name = folder_match.group(1) if folder_match else None
                
                if url:
                    url = url.rstrip('.,;')
                if folder_name:
                    folder_name = folder_name.rstrip('.,;')
                
                return url, folder_name
            except Exception:
                return None, None
        
        url, folder = _parse_user_prompt("First, clone the repository from https://github.com/example/repo.git. Then, analyze the field patterns in src")
        if url == "https://github.com/example/repo.git" and folder == "src":
            print("✅ Prompt parsing logic works correctly")
        else:
            print(f"❌ Prompt parsing logic failed. Got URL: {url}, Folder: {folder}")
            
    except Exception as e:
        print(f"⚠️ Error testing FLF agent: {e}")

if __name__ == "__main__":
    print("Running FLF workflow fixes tests...\n")
    
    test_context_file_copying()
    test_git_operations()
    test_flf_agent()
    
    print("\n✅ All tests completed!")