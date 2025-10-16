#!/usr/bin/env python3
"""
Test script to verify the legacy filename fallback functionality in SequentialDocumentBuilder
"""
import os
import tempfile
import sys
from pathlib import Path

# Add the src directory to the path so we can import the modules
sys.path.insert(0, str(Path(__file__).parent))

from src.core.sequential_document_builder import SequentialDocumentBuilder


def test_legacy_filename_fallback():
    """Test that the _inject_document_contents method handles legacy filenames correctly"""
    
    # Create a temporary directory structure for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create project directory structure
        project_dir = Path(temp_dir) / "test_project"
        sureai_dir = project_dir / ".sureai"
        sureai_dir.mkdir(parents=True)
        
        # Create a legacy filename document (old naming convention)
        legacy_file = sureai_dir / ".io8coder_breakdown.md"
        legacy_content = "# Legacy Breakdown Content\nThis is content from the legacy file."
        legacy_file.write_text(legacy_content)
        
        # Create a new filename document (new naming convention)
        new_file = sureai_dir / ".io8codermaster_breakdown.md"
        new_content = "# New Breakdown Content\nThis is content from the new file."
        new_file.write_text(new_content)
        
        # Create a test prompt with @ references
        prompt = "Please analyze the following documents:\n\n@.sureai/.io8codermaster_breakdown.md\n\nProvide insights."
        
        # Create a mock CLI client with the correct class name
        class SureCliClient:
            pass
        
        cli_client = SureCliClient()
        
        # Create SequentialDocumentBuilder instance
        builder = SequentialDocumentBuilder()
        
        # Test the injection with new filename (should find the new file)
        result = builder._inject_document_contents(prompt, str(project_dir), cli_client)
        
        # Verify that the new file content was injected
        assert "New Breakdown Content" in result, "New file content should be injected"
        assert "Legacy Breakdown Content" not in result, "Legacy file content should not be injected when new file exists"
        print("✓ Test 1 passed: New filename correctly injected when file exists")
        
        # Remove the new file and test fallback to legacy
        new_file.unlink()
        
        # Test the injection again (should fall back to legacy file)
        result = builder._inject_document_contents(prompt, str(project_dir), cli_client)
        
        # Verify that the legacy file content was injected
        assert "Legacy Breakdown Content" in result, "Legacy file content should be injected when new file doesn't exist"
        assert "New Breakdown Content" not in result, "New file content should not be injected when file doesn't exist"
        print("✓ Test 2 passed: Legacy filename fallback works correctly")
        
        # Test with a file that doesn't exist at all
        prompt_missing = "Please analyze the following documents:\n\n@.sureai/missing_file.md\n\nProvide insights."
        result = builder._inject_document_contents(prompt_missing, str(project_dir), cli_client)
        
        # Verify that the missing file is marked as not found
        assert "missing_file.md (NOT FOUND)" in result, "Missing file should be marked as NOT FOUND"
        print("✓ Test 3 passed: Missing file correctly marked as NOT FOUND")
        
        print("\n🎉 All tests passed! Legacy filename fallback is working correctly.")


if __name__ == "__main__":
    test_legacy_filename_fallback()