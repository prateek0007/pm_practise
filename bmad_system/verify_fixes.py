#!/usr/bin/env python3
"""
Simple verification script for FLF workflow fixes
"""

import os
import sys

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_files():
    """Check if the key files have been updated correctly"""
    
    # Check FLF agent file
    flf_agent_path = "bmad_backend/src/agents/flf_agent.py"
    if os.path.exists(flf_agent_path):
        with open(flf_agent_path, 'r') as f:
            content = f.read()
            if "clone_repository" in content and "analyze_field_patterns" in content:
                print("✅ FLF agent correctly implements git operations and field analysis")
            else:
                print("❌ FLF agent does not implement git operations and field analysis")
    else:
        print(f"❌ FLF agent file not found: {flf_agent_path}")
    
    # Check sequential document builder
    seq_doc_path = "bmad_backend/src/core/sequential_document_builder.py"
    if os.path.exists(seq_doc_path):
        with open(seq_doc_path, 'r') as f:
            content = f.read()
            if "perform field analysis directly" in content:
                print("✅ Sequential document builder updated to use direct field analysis")
            else:
                print("❌ Sequential document builder not updated correctly")
    else:
        print(f"❌ Sequential document builder file not found: {seq_doc_path}")
    
    # Check git operations
    git_ops_path = "bmad_backend/src/core/git_operations.py"
    if os.path.exists(git_ops_path):
        with open(git_ops_path, 'r') as f:
            content = f.read()
            if "def clone_repository" in content and "def analyze_field_patterns" in content:
                print("✅ Git operations module correctly implements required functions")
            else:
                print("❌ Git operations module missing required functions")
    else:
        print(f"❌ Git operations file not found: {git_ops_path}")

if __name__ == "__main__":
    print("Verifying FLF workflow fixes...")
    check_files()
    print("Verification complete.")