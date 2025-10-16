# Agent Instructions Implementation

## Overview

This document describes the implementation of agent-specific instructions functionality in the BMAD system. The instructions are now editable from the frontend and are automatically sent to the Gemini CLI when agents are executed, just like agent prompts.

## What Was Implemented

### 1. Frontend Changes

#### AgentManager.jsx
- **Added Instructions Field**: Added a "Specific Instructions" textarea field to the AgentEditor component
- **Instructions Preview**: Added instructions preview in the AgentCard component showing the first 100 characters
- **Instructions State Management**: Added state management for instructions in the AgentEditor
- **API Integration**: Updated the handleSaveAgent function to send instructions updates to the backend

#### Key Frontend Features:
- Instructions are editable for both built-in and custom agents
- Instructions are displayed in agent cards with a preview
- Instructions are saved along with agent prompts when updating agents
- Instructions are copied when duplicating agents

### 2. Backend Changes

#### Agent Manager (agent_manager.py)
- **get_agent_instructions()**: Method to retrieve instructions for any agent
- **update_agent_instructions()**: Method to update instructions for built-in agents
- **Built-in Instructions**: Default instructions for each agent type
- **Custom Agent Support**: Instructions support for custom agents via database

#### API Endpoints (bmad_api.py)
- **PUT /api/agents/instructions/{agent_name}**: Endpoint to update agent instructions
- **Instructions in Agent Data**: Instructions are included in the agent prompts response

#### Master Workflow (master_workflow.py)
- **Dynamic Instructions**: Replaced hardcoded developer instructions with dynamic agent instructions
- **Agent Instructions Integration**: Instructions are now loaded from AgentManager and included in prompts sent to Gemini CLI

#### Sequential Document Builder (sequential_document_builder.py)
- **Instructions Support**: Added _get_agent_instructions() method
- **Prompt Augmentation**: Instructions are appended to agent prompts before sending to Gemini CLI

#### Orchestrator (orchestrator.py)
- **Instructions Loading**: Added _load_agent_instructions() method
- **Prompt Creation**: Updated _create_full_prompt() to include agent instructions
- **CLI Integration**: Instructions are sent to Gemini CLI via the orchestrator

### 3. Data Flow

```
Frontend (AgentEditor) 
    ↓ (User edits instructions)
Backend API (/api/agents/instructions/{agent_name})
    ↓ (Updates stored instructions)
AgentManager (update_agent_instructions)
    ↓ (Stores in config file)
AgentManager (get_agent_instructions)
    ↓ (Retrieves when needed)
Master Workflow / Sequential Builder / Orchestrator
    ↓ (Includes in prompt)
Gemini CLI
```

## How It Works

### 1. Editing Instructions
1. User opens the Agent Manager in the frontend
2. User clicks "Edit" on any agent
3. User can edit both the agent prompt and specific instructions
4. When saved, both prompt and instructions are updated via API calls

### 2. Instructions Storage
- **Built-in Agents**: Instructions are stored in the custom config file
- **Custom Agents**: Instructions are stored in the database with the agent record

### 3. Instructions Usage
When an agent is executed:
1. The system loads the agent's prompt from AgentManager
2. The system loads the agent's instructions from AgentManager
3. Both are combined into a single prompt sent to Gemini CLI
4. The instructions appear as "=== AGENT INSTRUCTIONS ===" section in the prompt

### 4. Default Instructions
Each agent type has built-in default instructions:
- **Developer**: Code generation instructions with terminal command format
- **Tester**: Testing instructions with Selenium/E2E guidance
- **Analyst**: Analysis and requirements gathering instructions
- **Architect**: Architecture and tech stack planning instructions
- And more for each agent type...

## API Endpoints

### Update Agent Instructions
```
PUT /api/agents/instructions/{agent_name}
Content-Type: application/json

{
  "instructions": "New instructions content"
}
```

### Get Agent Data (includes instructions)
```
GET /api/agents/prompts
```

Response includes instructions for each agent:
```json
{
  "agents": {
    "developer": {
      "name": "developer",
      "display_name": "Developer",
      "instructions": "Agent-specific instructions...",
      "prompt": "Agent prompt...",
      ...
    }
  }
}
```

## Testing

A comprehensive test script (`test_instructions.py`) was created to verify:
1. Instructions are included in agent data
2. Instructions can be updated via API
3. Instructions are properly stored and retrieved
4. AgentManager methods work correctly
5. Instructions can be reset to defaults

## Benefits

1. **Flexibility**: Users can customize how each agent behaves
2. **Consistency**: Instructions are automatically included in all agent executions
3. **User-Friendly**: Instructions are editable through the same interface as prompts
4. **Backward Compatibility**: Default instructions are provided for all agents
5. **Integration**: Instructions work seamlessly with the existing Gemini CLI integration

## Future Enhancements

1. **Instruction Templates**: Pre-built instruction templates for common use cases
2. **Instruction Validation**: Validate instruction format and content
3. **Instruction History**: Track changes to instructions over time
4. **Instruction Sharing**: Share instruction sets between users
5. **Instruction Categories**: Organize instructions by type or purpose

## Files Modified

### Frontend
- `bmad_frontend/src/components/AgentManager.jsx`

### Backend
- `bmad_backend/src/agents/agent_manager.py`
- `bmad_backend/src/routes/bmad_api.py`
- `bmad_backend/src/workflows/master_workflow.py`
- `bmad_backend/src/core/sequential_document_builder.py`
- `bmad_backend/src/core/orchestrator.py`

### Testing
- `bmad_backend/test_instructions.py`

## Conclusion

The agent instructions functionality has been successfully implemented and integrated into the BMAD system. Users can now edit agent-specific instructions through the frontend, and these instructions are automatically included in all agent executions sent to the Gemini CLI, providing greater control and customization over agent behavior.
