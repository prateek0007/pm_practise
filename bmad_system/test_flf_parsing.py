#!/usr/bin/env python3
"""
Test to verify FLF agent prompt parsing improvements
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bmad_backend'))

def test_flf_prompt_parsing():
    """Test that the FLF agent can parse different prompt formats"""
    
    # Import the FLF agent
    from src.agents.flf_agent import FLFAgent
    flf_agent = FLFAgent()
    
    # Test case 1: Original format
    prompt1 = "First, clone the repository from http://157.66.191.31:3000/risadmin_prod/testnew17oct.git. Then, analyze the field patterns in ad9 using the Universal Field Analysis Context Guide"
    url1, folder1 = flf_agent._parse_user_prompt(prompt1)
    assert url1 == "http://157.66.191.31:3000/risadmin_prod/testnew17oct.git"
    assert folder1 == "ad9"
    print("✅ Test case 1 passed: Original format")
    
    # Test case 2: New format with "Folder:" prefix
    prompt2 = "First, clone the repository from http://157.66.191.31:3000/risadmin_prod/testnew17oct.git. Then, analyze the field patterns in Folder: ad9 using the Universal Field Analysis Context Guide. First search for this folder in the cloned repo then follow the universal field guide."
    url2, folder2 = flf_agent._parse_user_prompt(prompt2)
    assert url2 == "http://157.66.191.31:3000/risadmin_prod/testnew17oct.git"
    assert folder2 == "ad9"
    print("✅ Test case 2 passed: New format with 'Folder:' prefix")
    
    # Test case 3: Edge case with punctuation
    prompt3 = "First, clone the repository from http://example.com/repo.git. Then, analyze the field patterns in Folder: test-folder."
    url3, folder3 = flf_agent._parse_user_prompt(prompt3)
    assert url3 == "http://example.com/repo.git"
    assert folder3 == "test-folder"
    print("✅ Test case 3 passed: Edge case with punctuation")

if __name__ == "__main__":
    print("Testing FLF prompt parsing improvements...")
    test_flf_prompt_parsing()
    print("All parsing tests passed! 🎉")