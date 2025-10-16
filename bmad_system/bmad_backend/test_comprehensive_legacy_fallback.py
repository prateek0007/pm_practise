#!/usr/bin/env python3
"""
Comprehensive test script to verify all legacy filename fallback scenarios
"""
import os
import tempfile
import sys
from pathlib import Path

# Add the src directory to the path so we can import the modules
sys.path.insert(0, str(Path(__file__).parent))

from src.core.sequential_document_builder import SequentialDocumentBuilder


def test_comprehensive_legacy_fallback():
    """Test all legacy filename fallback scenarios"""
    
    # Create a temporary directory structure for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create project directory structure
        project_dir = Path(temp_dir) / "test_project"
        sureai_dir = project_dir / ".sureai"
        sureai_dir.mkdir(parents=True)
        
        # Create mock CLI client with the correct class name
        class SureCliClient:
            pass
        
        cli_client = SureCliClient()
        builder = SequentialDocumentBuilder()
        
        # Test 1: Breakdown file fallback
        print("Test 1: Breakdown file fallback")
        legacy_breakdown = sureai_dir / ".io8coder_breakdown.md"
        legacy_breakdown.write_text("# Legacy Breakdown")
        
        prompt = "@.sureai/.io8codermaster_breakdown.md"
        result = builder._inject_document_contents(prompt, str(project_dir), cli_client)
        assert "# Legacy Breakdown" in result
        legacy_breakdown.unlink()  # Clean up
        print("✓ Breakdown file fallback works")
        
        # Test 2: Plan file fallback
        print("Test 2: Plan file fallback")
        legacy_plan = sureai_dir / ".io8coder_plan.md"
        legacy_plan.write_text("# Legacy Plan")
        
        prompt = "@.sureai/.io8codermaster_plan.md"
        result = builder._inject_document_contents(prompt, str(project_dir), cli_client)
        assert "# Legacy Plan" in result
        legacy_plan.unlink()  # Clean up
        print("✓ Plan file fallback works")
        
        # Test 3: Agent file fallback
        print("Test 3: Agent file fallback")
        legacy_agent = sureai_dir / ".io8coder_agent_test_123.md"
        legacy_agent.write_text("# Legacy Agent Content")
        
        prompt = "@.sureai/.io8codermaster_agent_test_123.md"
        result = builder._inject_document_contents(prompt, str(project_dir), cli_client)
        assert "# Legacy Agent Content" in result
        legacy_agent.unlink()  # Clean up
        print("✓ Agent file fallback works")
        
        # Test 4: New files take precedence over legacy files
        print("Test 4: New files take precedence")
        legacy_breakdown = sureai_dir / ".io8coder_breakdown.md"
        legacy_breakdown.write_text("# Legacy Breakdown Content")
        
        new_breakdown = sureai_dir / ".io8codermaster_breakdown.md"
        new_breakdown.write_text("# New Breakdown Content")
        
        prompt = "@.sureai/.io8codermaster_breakdown.md"
        result = builder._inject_document_contents(prompt, str(project_dir), cli_client)
        assert "# New Breakdown Content" in result
        assert "# Legacy Breakdown Content" not in result
        legacy_breakdown.unlink()  # Clean up
        new_breakdown.unlink()  # Clean up
        print("✓ New files take precedence over legacy files")
        
        # Test 5: Multiple references in one prompt
        print("Test 5: Multiple references")
        legacy_breakdown = sureai_dir / ".io8coder_breakdown.md"
        legacy_breakdown.write_text("# Legacy Breakdown")
        
        legacy_plan = sureai_dir / ".io8coder_plan.md"
        legacy_plan.write_text("# Legacy Plan")
        
        prompt = "References:\n@.sureai/.io8codermaster_breakdown.md\n@.sureai/.io8codermaster_plan.md"
        result = builder._inject_document_contents(prompt, str(project_dir), cli_client)
        assert "# Legacy Breakdown" in result
        assert "# Legacy Plan" in result
        legacy_breakdown.unlink()  # Clean up
        legacy_plan.unlink()  # Clean up
        print("✓ Multiple references work correctly")
        
        print("\n🎉 All comprehensive tests passed!")


if __name__ == "__main__":
    test_comprehensive_legacy_fallback()