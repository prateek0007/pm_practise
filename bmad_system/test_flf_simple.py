#!/usr/bin/env python3
"""
Simple test to verify FLF workflow changes
"""

def test_flf_prompt_inclusion():
    """Test that the FLF prompt includes the context guide directly"""
    # Read the flf-save.chatmode.md file
    with open('bmad_backend/src/agents/flf-save.chatmode.md', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check that it contains the context guide content
    assert '# Universal Field Analysis Context Guide' in content
    assert 'Universal Field Analysis Process' in content
    assert 'Standardized Keywords' in content
    
    # Check that it no longer references the external file
    assert '@.sureai/UNIVERSAL_FIELD_ANALYSIS_CONTEXT.md' not in content
    
    print("✅ FLF prompt correctly includes context guide directly")

def test_workflow_references():
    """Test that the workflow no longer references the external context file"""
    # Read the master_workflow.py file
    with open('bmad_backend/src/workflows/master_workflow.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check that flf-save has an empty list of document references
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if "'flf-save':" in line and i < len(lines) - 1:
            next_line = lines[i + 1].strip()
            if next_line == '[]' or '[]  # FLF agent no longer needs' in next_line:
                print("✅ Workflow correctly removes external context file reference")
                return
    
    # If we get here, check if it's on the same line
    if "'flf-save': []" in content:
        print("✅ Workflow correctly removes external context file reference")
        return
    
    raise AssertionError("Workflow still references external context file")

if __name__ == "__main__":
    print("Testing FLF workflow changes...")
    test_flf_prompt_inclusion()
    test_workflow_references()
    print("All tests passed! 🎉")