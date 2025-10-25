"""
FLF Agent Implementation

This module provides the FLF agent implementation that performs
repository cloning and field analysis directly.
"""

import os
import json
import logging
import re
from typing import Dict, Any
from src.core.task_manager import TaskManager

logger = logging.getLogger(__name__)

class FLFAgent:
    """FLF Agent that performs git operations and field analysis directly"""
    
    def __init__(self):
        self.task_manager = TaskManager()
    
    def execute(self, task_id: str, user_prompt: str) -> Dict[str, Any]:
        """
        Execute the FLF agent workflow by performing git operations and field analysis
        
        Args:
            task_id: The task identifier
            user_prompt: The user prompt containing URL and folder name
            
        Returns:
            Dict containing execution results
        """
        try:
            logger.info(f"Executing FLF agent for task {task_id}")
            logger.info(f"User prompt: {user_prompt}")
            
            # Parse the user prompt to extract URL and folder name
            # Expected format: "First, clone the repository from {url}. Then, analyze the field patterns in {folder_name}"
            url, folder_name = self._parse_user_prompt(user_prompt)
            
            if not url or not folder_name:
                logger.error("Could not extract URL and folder name from user prompt")
                return {"status": "error", "error": "Invalid user prompt format. Expected: 'First, clone the repository from {url}. Then, analyze the field patterns in {folder_name}'"}
            
            logger.info(f"Extracted URL: {url}, Folder: {folder_name}")
            
            # Get task output directory
            project_dir = self.task_manager.get_task_output_directory(task_id)
            if not project_dir:
                logger.error("Could not get task output directory")
                return {"status": "error", "error": "Task output directory not found"}
            
            # Create sureai directory if it doesn't exist
            sureai_dir = os.path.join(project_dir, ".sureai")
            os.makedirs(sureai_dir, exist_ok=True)
            
            # Import git operations module
            from src.core.git_operations import clone_repository, analyze_field_patterns
            
            # Clone the repository
            clone_dir = os.path.join(project_dir, "cloned_repo")
            if not clone_repository(url, clone_dir):
                logger.error(f"Failed to clone repository from {url}")
                return {"status": "error", "error": f"Failed to clone repository from {url}"}
            
            logger.info(f"Successfully cloned repository to {clone_dir}")
            
            # Analyze field patterns in the specified folder
            field_patterns = analyze_field_patterns(clone_dir, folder_name)
            
            # Convert field patterns to JSON
            field_patterns_json = json.dumps(field_patterns, indent=2)
            
            # Save the JSON output to flf-json.txt
            flf_json_path = os.path.join(sureai_dir, "flf-json.txt")
            try:
                with open(flf_json_path, 'w', encoding='utf-8') as f:
                    f.write(field_patterns_json)
                logger.info(f"Saved field patterns to {flf_json_path}")
            except Exception as e:
                logger.error(f"Failed to save field patterns to {flf_json_path}: {e}")
                return {"status": "error", "error": f"Failed to save field patterns: {e}"}
            
            # Create a simple MCP response
            mcp_response = {"status": "success", "message": "Field patterns analyzed and saved successfully"}
            mcp_response_json = json.dumps(mcp_response, indent=2)
            
            # Save the MCP response to flf-mcp-response.txt
            flf_mcp_response_path = os.path.join(sureai_dir, "flf-mcp-response.txt")
            try:
                with open(flf_mcp_response_path, 'w', encoding='utf-8') as f:
                    f.write(mcp_response_json)
                logger.info(f"Saved MCP response to {flf_mcp_response_path}")
            except Exception as e:
                logger.error(f"Failed to save MCP response to {flf_mcp_response_path}: {e}")
                return {"status": "error", "error": f"Failed to save MCP response: {e}"}
            
            return {
                "status": "success",
                "files_created": ["flf-json.txt", "flf-mcp-response.txt"],
                "message": "FLF field analysis completed successfully",
                "field_patterns": field_patterns_json,
                "mcp_response": mcp_response_json
            }
            
        except Exception as e:
            logger.error(f"Error executing FLF agent: {e}", exc_info=True)
            return {"status": "error", "error": f"FLF agent execution failed: {str(e)}"}
    
    def _parse_user_prompt(self, user_prompt: str) -> tuple:
        """
        Parse the user prompt to extract URL and folder name
        
        Args:
            user_prompt: The user prompt string
            
        Returns:
            Tuple of (url, folder_name) or (None, None) if not found
        """
        try:
            # Handle the format: "First, clone the repository from {url}. Then, analyze the field patterns in {folder_name}"
            url_pattern = r"clone the repository from\s+([^\s]+)"
            url_match = re.search(url_pattern, user_prompt)
            url = url_match.group(1) if url_match else None
            
            # Handle different folder name formats:
            # 1. "analyze the field patterns in ad9"
            # 2. "analyze the field patterns in Folder: ad9"
            folder_patterns = [
                r"analyze the field patterns in\s+Folder:\s*([^\s.,;]+)",
                r"analyze the field patterns in\s+([^\s.,;]+)"
            ]
            
            folder_name = None
            for pattern in folder_patterns:
                folder_match = re.search(pattern, user_prompt)
                if folder_match:
                    folder_name = folder_match.group(1)
                    break
            
            # Clean up the extracted values
            if url:
                url = url.rstrip('.,;')
            if folder_name:
                folder_name = folder_name.rstrip('.,;')
            
            return url, folder_name
        except Exception as e:
            logger.error(f"Error parsing user prompt: {e}")
            return None, None

# Global instance for other modules to import
flf_agent = FLFAgent()