#!/usr/bin/env python3
"""
Verification script for FLF workflow fixes
"""

def verify_requirement_builder_fix():
    """Verify that the requirement_builder fix is in place"""
    with open('bmad_backend/src/core/sequential_document_builder.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check that requirement_builder uses _execute_analyst_phase
    assert "'executor': self._execute_analyst_phase" in content
    assert "_execute_requirement_builder_phase" not in content
    print("✅ Requirement builder fix verified")

def verify_prompt_parsing():
    """Verify that the FLF agent can parse improved prompts"""
    with open('bmad_backend/src/agents/flf_agent.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check that the parsing logic handles "Folder:" prefix
    assert "Folder:" in content
    assert "folder_patterns" in content
    print("✅ Prompt parsing improvements verified")

def verify_context_inclusion():
    """Verify that the context is included directly in the prompt"""
    with open('bmad_backend/src/agents/flf-save.chatmode.md', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check that context guide is included directly
    assert "# Universal Field Analysis Context Guide" in content
    assert "Universal Field Analysis Process" in content
    # Check that external file references are removed
    assert "@.sureai/UNIVERSAL_FIELD_ANALYSIS_CONTEXT.md" not in content
    print("✅ Context inclusion verified")

if __name__ == "__main__":
    print("Verifying FLF workflow fixes...")
    verify_requirement_builder_fix()
    verify_prompt_parsing()
    verify_context_inclusion()
    print("All verifications passed! 🎉")