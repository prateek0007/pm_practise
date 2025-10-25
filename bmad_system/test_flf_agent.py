#!/usr/bin/env python3
"""
Test script for the FLF agent to verify it's working correctly
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add the backend directory to the path so we can import the modules
backend_path = Path(__file__).parent / "bmad_backend"
sys.path.insert(0, str(backend_path))

def test_flf_agent():
    """Test the FLF agent with a simple repository"""
    try:
        # Create a temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            print(f"Created temporary directory: {temp_dir}")
            
            # Create a mock task ID
            task_id = "test_flf_task_123"
            
            # Create the task directory structure
            project_dir = Path(temp_dir) / f"test_flf_{task_id}"
            project_dir.mkdir()
            
            # Create the .sureai directory
            sureai_dir = project_dir / ".sureai"
            sureai_dir.mkdir()
            
            # Copy the UNIVERSAL_FIELD_ANALYSIS_CONTEXT.md file to the test directory
            source_context_file = Path(__file__).parent / ".sureai" / "UNIVERSAL_FIELD_ANALYSIS_CONTEXT.md"
            if source_context_file.exists():
                dest_context_file = sureai_dir / "UNIVERSAL_FIELD_ANALYSIS_CONTEXT.md"
                shutil.copy2(source_context_file, dest_context_file)
                print(f"Copied context file to: {dest_context_file}")
            else:
                print(f"Source context file not found: {source_context_file}")
                # Create a simple placeholder
                with open(sureai_dir / "UNIVERSAL_FIELD_ANALYSIS_CONTEXT.md", "w") as f:
                    f.write("# Universal Field Analysis Context Guide\n\nThis is a test context file.\n")
            
            # Test user prompt
            user_prompt = "First, clone the repository from http://157.66.191.31:3000/risadmin_prod/testnew17oct.git. Then, analyze the field patterns in ad9."
            
            # Import and test the FLF agent
            from src.agents.flf_agent import FLFAgent
            flf_agent = FLFAgent()
            
            # Mock the task manager to return our test directory
            original_get_task_output_directory = flf_agent.task_manager.get_task_output_directory
            flf_agent.task_manager.get_task_output_directory = lambda x: str(project_dir)
            
            print("Executing FLF agent...")
            result = flf_agent.execute(task_id, user_prompt)
            
            # Restore the original method
            flf_agent.task_manager.get_task_output_directory = original_get_task_output_directory
            
            print(f"FLF agent result: {result}")
            
            # Check if the expected files were created
            flf_json_path = sureai_dir / "flf-json.txt"
            flf_mcp_response_path = sureai_dir / "flf-mcp-response.txt"
            
            print(f"FLF JSON file exists: {flf_json_path.exists()}")
            print(f"FLF MCP response file exists: {flf_mcp_response_path.exists()}")
            
            if flf_json_path.exists():
                with open(flf_json_path, 'r') as f:
                    content = f.read()
                    print(f"FLF JSON content: {content[:200]}...")
            
            if flf_mcp_response_path.exists():
                with open(flf_mcp_response_path, 'r') as f:
                    content = f.read()
                    print(f"FLF MCP response content: {content[:200]}...")
            
            return result
            
    except Exception as e:
        print(f"Error testing FLF agent: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}

if __name__ == "__main__":
    print("Testing FLF agent...")
    result = test_flf_agent()
    print(f"Test result: {result}")