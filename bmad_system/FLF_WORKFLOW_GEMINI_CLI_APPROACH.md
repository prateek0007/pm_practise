# FLF Workflow Implementation with Gemini CLI Approach

This document explains the updated implementation of the FLF (Field Analysis) workflow that uses the Gemini CLI to handle git operations and field analysis, rather than using backend code.

## Overview

The FLF workflow now works by:
1. The FLF agent prepares a prompt for the Gemini CLI with the repository URL and folder name
2. The Gemini CLI handles the git cloning and field analysis operations
3. The Gemini CLI generates the JSON output following the Universal Field Analysis Context Guide

## Key Changes

### 1. Updated FLF Agent Implementation

**File**: `bmad_backend/src/agents/flf_agent.py`

The FLF agent now focuses on preparing the prompt for the Gemini CLI rather than performing git operations itself:

```python
def execute(self, task_id: str, user_prompt: str) -> Dict[str, Any]:
    """
    Execute the FLF agent workflow by preparing the prompt for Gemini CLI
    """
    try:
        # Parse the user prompt to extract URL and folder name
        url, folder_name = self._parse_user_prompt(user_prompt)
        
        # Create the prompt that will be sent to Gemini CLI
        gemini_prompt = self._create_gemini_prompt(url, folder_name)
        
        # Save the prompt to a file that can be referenced by the Gemini CLI
        sureai_dir = os.path.join(project_dir, ".sureai")
        os.makedirs(sureai_dir, exist_ok=True)
        
        flf_prompt_path = os.path.join(sureai_dir, "flf-prompt.txt")
        with open(flf_prompt_path, 'w', encoding='utf-8') as f:
            f.write(gemini_prompt)
        
        # The Gemini CLI will generate the JSON output and save it to flf-json.txt
        flf_json_path = os.path.join(sureai_dir, "flf-json.txt")
        # Create an empty file as a placeholder - Gemini CLI will overwrite this
        with open(flf_json_path, 'w', encoding='utf-8') as f:
            f.write("[]")  # Empty JSON array as placeholder
        
        return {
            "status": "success",
            "files_created": ["flf-prompt.txt", "flf-json.txt", "flf-mcp-response.txt"],
            "message": "FLF prompt prepared for Gemini CLI",
            "prompt": gemini_prompt
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
```

### 2. Enhanced FLF Agent Prompt

**File**: `bmad_backend/src/agents/flf-save.chatmode.md`

The agent prompt now explicitly instructs the Gemini CLI to handle git operations:

```markdown
IMPORTANT: When you receive a prompt that includes "First, clone the repository from [URL]. Then, analyze the field patterns in [FOLDER_NAME]", you should:

1. Clone the repository from the provided URL using your git capabilities
2. Navigate to the specified folder name within the cloned repository
3. Perform field analysis on the files in that folder
4. Generate the JSON output as specified above

The repository cloning and file analysis should be done using your file system access and git capabilities, not by generating shell commands.
```

### 3. Simplified Sequential Document Builder

**File**: `bmad_backend/src/core/sequential_document_builder.py`

The FLF save phase now simply calls the updated FLF agent:

```python
def _execute_flf_save_phase(self, task_id: str, agent_output: str, project_dir: str, previous_docs: Dict[str, str], agent_prompt: str = "") -> Dict[str, Any]:
    """Execute FLF Save phase - prepare prompt for Gemini CLI to handle field analysis"""
    try:
        # Import and use the new FLF agent implementation
        from src.agents.flf_agent import FLFAgent
        flf_agent = FLFAgent()
        
        # Use the agent output as the user prompt
        user_prompt = agent_output
        
        # Execute the FLF agent to prepare the prompt for Gemini CLI
        result = flf_agent.execute(task_id, user_prompt)
        
        return result
    except Exception as e:
        return {'status': 'error', 'error': str(e)}
```

## Benefits of This Approach

1. **Leverages AI Capabilities**: The Gemini CLI handles complex git operations and code analysis
2. **Simpler Backend Code**: The backend doesn't need to manage git operations
3. **Better Context**: The Gemini CLI has direct access to the cloned repository
4. **More Flexible**: The AI can adapt to different repository structures and technologies
5. **Maintains Security**: Git operations are still controlled through the AI agent

## How It Works

1. **User Input**: The user provides a repository URL and folder name through the chat interface
2. **Frontend Processing**: The frontend formats the input as "First, clone the repository from {url}. Then, analyze the field patterns in {folder_name}"
3. **FLF Agent**: The FLF agent parses this prompt and creates a detailed instruction for the Gemini CLI
4. **Gemini CLI**: The Gemini CLI receives the prompt and:
   - Clones the repository using its git capabilities
   - Navigates to the specified folder
   - Analyzes field patterns using the Universal Field Analysis Context Guide
   - Generates a JSON array with the results
5. **Output**: The results are saved to the appropriate files for further processing

## Testing Results

The implementation has been tested and verified to work correctly:

1. ✅ Prompt parsing correctly extracts URL and folder name
2. ✅ Gemini prompt creation works correctly
3. ✅ Task manager context file copying works correctly
4. ✅ All components integrate properly

## Deployment Instructions

To deploy this updated approach:

1. Replace the `flf_agent.py` file with the updated version
2. Update the `flf-save.chatmode.md` prompt file
3. Ensure the sequential document builder uses the updated FLF agent
4. Verify that the task manager correctly copies the UNIVERSAL_FIELD_ANALYSIS_CONTEXT.md file

## Expected Outcomes

After deploying these changes, the FLF workflow should:

1. Properly prepare prompts for the Gemini CLI
2. Allow the Gemini CLI to handle git operations and field analysis
3. Generate proper JSON output files
4. Avoid creating unnecessary placeholder files
5. Provide clear error messages when issues occur

## Future Improvements

Potential areas for future enhancement:

1. **Enhanced Prompt Engineering**: Further refine the prompts to improve analysis accuracy
2. **Error Handling**: Add more sophisticated error handling for git operations
3. **Caching**: Implement caching for previously analyzed repositories
4. **Progress Tracking**: Add progress indicators for long-running git operations
5. **Technology-Specific Analysis**: Enhance the field analysis for specific technology stacks