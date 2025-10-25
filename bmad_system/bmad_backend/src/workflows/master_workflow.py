"""
Master Workflow Module for BMAD System

This module implements the master workflow orchestration logic that processes
user prompts and coordinates agent execution with detailed CLI-like logging.
Updated to use prompt references to reduce request size and avoid rate limiting.
"""

import asyncio
import json
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
from src.utils.logger import get_logger
from src.agents.agent_manager import AgentManager
from src.llm_clients.gemini_cli_client import GeminiCLIClient
from src.llm_clients.llxprt_cli_client import LlxprtCLIClient
from src.llm_clients.sure_cli_client import SureCliClient, SureCliError
from src.utils.token_meter import TokenMeter

logger = get_logger(__name__)

class MasterWorkflow:
    """Orchestrates the master workflow for BMAD system with CLI-like logging"""
    
    def __init__(self, agent_manager: AgentManager, gemini_client: GeminiCLIClient, token_meter: TokenMeter):
        self.agent_manager = agent_manager
        self.gemini_client = gemini_client
        self.token_meter = token_meter
        self.cli_logs = []  # Store CLI-like logs for frontend
        self.current_task_id: Optional[str] = None
        # Access shared llxprt client from routes module lazily to avoid cycles
        self._llxprt: Optional[LlxprtCLIClient] = None
        # Incremental sequence for CLI logs to support incremental fetching
        self._log_seq: int = 0
        # Lazy SureCli
        self._surecli: Optional[SureCliClient] = None
        
        # Initialize task manager
        from src.core.task_manager import TaskManager
        self.task_manager = TaskManager()
        
        # Set up CLI logging callback
        self.gemini_client.set_log_callback(self._handle_cli_log)
        
        # Runtime guards
        self._running_tasks: set[str] = set()
        self._cancel_flags: dict[str, bool] = {}

    def request_cancel(self, task_id: str):
        """Signal any running execution for this task to stop gracefully."""
        self._cancel_flags[task_id] = True
        logger.info(f"🚫 Cancel requested for task {task_id}")
        # Try to stop any ongoing CLI call immediately
        try:
            if hasattr(self.gemini_client, 'cancel_active'):
                self.gemini_client.cancel_active()
        except Exception:
            pass

    def clear_cancel(self, task_id: str):
        """Clear cancellation flag for a task."""
        try:
            if task_id in self._cancel_flags:
                del self._cancel_flags[task_id]
        except Exception:
            pass
    
    def _is_cancelled(self, task_id: str) -> bool:
        cancelled = bool(self._cancel_flags.get(task_id))
        if cancelled:
            logger.debug(f"🚫 Task {task_id} is marked for cancellation")
        return cancelled
    
    def force_cancel_task(self, task_id: str):
        """Force cancel a task by removing it from running tasks and setting status."""
        try:
            if task_id in self._running_tasks:
                self._running_tasks.remove(task_id)
                logger.info(f"🚫 Force removed task {task_id} from running tasks")
            
            # Set cancellation flag
            self._cancel_flags[task_id] = True
            # Force stop any running CLI call
            try:
                if hasattr(self.gemini_client, 'cancel_active'):
                    self.gemini_client.cancel_active()
            except Exception:
                pass
            
            # Update task status to cancelled
            try:
                from src.core.task_manager import TaskManager, TaskStatus
                task_manager = TaskManager()
                task_manager.update_task_status(task_id, TaskStatus.CANCELLED)
                logger.info(f"✅ Task {task_id} status set to cancelled")
            except Exception as e:
                logger.warning(f"⚠️ Could not update task {task_id} status: {e}")
                
        except Exception as e:
            logger.error(f"❌ Error force cancelling task {task_id}: {e}")
    
    def _handle_cli_log(self, level: str, message: str):
        """Handle CLI log messages and store them for frontend"""
        try:
            self._log_seq += 1
        except Exception:
            # Fallback if increment fails
            self._log_seq = (self._log_seq or 0) + 1
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
            "source": "gemini_cli",
            "task_id": self.current_task_id or "",
            "seq": self._log_seq
        }
        self.cli_logs.append(log_entry)
        
        # Also log to main logger
        if level == "INFO":
            logger.info(f"[Gemini CLI] {message}")
        elif level == "ERROR":
            logger.error(f"[Gemini CLI] {message}")
        elif level == "WARNING":
            logger.warning(f"[Gemini CLI] {message}")
        elif level == "DEBUG":
            logger.debug(f"[Gemini CLI] {message}")
    
    def get_cli_logs(self) -> List[Dict[str, Any]]:
        """Get all CLI logs for frontend display"""
        return self.cli_logs.copy()
    
    def clear_cli_logs(self):
        """Clear CLI logs"""
        self.cli_logs = []
    
    async def execute_workflow(self, task_id: str, user_prompt: str, workflow_sequence: Optional[List[str]] = None, 
                             custom_prompts: Optional[Dict[str, str]] = None, per_agent_models: Optional[List[str]] = None, per_agent_temperatures: Optional[List[Optional[float]]] = None, per_agent_clis: Optional[List[str]] = None, workflow_id: Optional[str] = None):
        """
        Execute the master workflow for a given task
        
        Args:
            task_id: The task identifier
            user_prompt: The user's input prompt
            workflow_sequence: Custom workflow sequence (optional)
            custom_prompts: Custom prompts for agents (optional)
            per_agent_models: Optional list of model names aligned to workflow_sequence
            per_agent_temperatures: Optional list of temperatures aligned to workflow_sequence
            
        Returns:
            Dict containing workflow execution results
        """
        # Check if this is an ignored task (for io8 workflows)
        if task_id.startswith("IGNORED:"):
            original_task_id = task_id.split(":", 1)[1]
            self._handle_cli_log("INFO", f"⏭️ Ignoring duplicate call for task {original_task_id} which is already in progress")
            return {'status': 'ignored', 'message': 'Duplicate call ignored - task already in progress', 'task_id': original_task_id}
        
        try:
            from src.core.task_manager import TaskManager, TaskStatus
            from src.llm_clients.gemini_cli_client import GeminiCLIError
            task_manager = TaskManager()
            
            # Prevent concurrent runs for the same task
            if task_id in self._running_tasks:
                self._handle_cli_log("WARNING", f"⚠️ Task {task_id} is already running; ignoring duplicate execute request")
                return {'status': 'ignored', 'error': 'already running'}
            
            # Clear any previous cancellation flags and add to running tasks
            self.clear_cancel(task_id)
            self._running_tasks.add(task_id)
            
            # Double-check that we're not cancelled after clearing
            if self._is_cancelled(task_id):
                self._handle_cli_log("ERROR", f"❌ Task {task_id} was cancelled immediately after clearing - this indicates a race condition")
                self._running_tasks.discard(task_id)
                return {'status': 'cancelled', 'error': 'race condition detected'}
            
            # Note: We no longer check API quota before starting workflow
            # Quota exhaustion will be detected during actual API calls when Gemini returns 429 errors
            # This prevents false positives and ensures accurate quota detection
            self._handle_cli_log("INFO", f"🚀 Starting workflow - API quota will be checked during actual calls")
            
            # Debug logging for workflow sequence
            logger.info(f"🔍 MasterWorkflow Debug - Received workflow_sequence: {workflow_sequence}")
            logger.info(f"🔍 MasterWorkflow Debug - Received workflow_sequence type: {type(workflow_sequence)}")
            logger.info(f"🔍 MasterWorkflow Debug - Received workflow_sequence length: {len(workflow_sequence) if isinstance(workflow_sequence, list) else 'N/A'}")
            
            # Resolve sequence, etc. (existing code)
            if workflow_sequence and len(workflow_sequence) > 0:
                agents_to_execute = workflow_sequence
                self._handle_cli_log("INFO", f"🎯 Using custom workflow sequence: {', '.join(agents_to_execute)}")
                self._handle_cli_log("INFO", f"📊 Total agents to execute: {len(agents_to_execute)}")
            else:
                agents_to_execute = self.agent_manager.get_default_workflow_sequence()
                self._handle_cli_log("INFO", f"🔄 Using default workflow sequence: {', '.join(agents_to_execute)}")
                self._handle_cli_log("INFO", f"📊 Total agents to execute: {len(agents_to_execute)}")

            # Check if this is a combined sequential workflow and handle as subworkflows
            is_sequential_io8 = False
            if workflow_id:
                try:
                    from src.models.workflow import Workflow
                    from src.models.user import db
                    workflow = Workflow.query.get(workflow_id)
                    self._handle_cli_log("DEBUG", f"🔍 Workflow ID: {workflow_id}")
                    if workflow:
                        self._handle_cli_log("DEBUG", f"🔍 Workflow name: '{workflow.name}'")
                        self._handle_cli_log("DEBUG", f"🔍 Workflow sequence: {workflow.agent_sequence}")
                        if workflow.name in ['End-to-End Plan + Execute', 'io8 Default']:
                            is_sequential_io8 = True
                            self._handle_cli_log("INFO", f"🔄 Detected combined workflow ('{workflow.name}') - will execute as sequential subworkflows")
                        else:
                            self._handle_cli_log("DEBUG", f"🔍 Not workflow3, using regular execution")
                    else:
                        self._handle_cli_log("WARNING", f"Workflow not found for ID: {workflow_id}")
                except Exception as e:
                    self._handle_cli_log("WARNING", f"Could not check workflow type: {e}")

            # Honor the user's chosen workflow exactly; no auto-fallback here.
            
            per_agent_models = per_agent_models or []
            if len(per_agent_models) < len(agents_to_execute):
                per_agent_models = per_agent_models + [None] * (len(agents_to_execute) - len(per_agent_models))
            per_agent_temperatures = per_agent_temperatures or []
            if len(per_agent_temperatures) < len(agents_to_execute):
                per_agent_temperatures = per_agent_temperatures + [None] * (len(agents_to_execute) - len(per_agent_temperatures))
            self.current_task_id = task_id
            
            # Save sequence to state (existing code)
            try:
                tm = TaskManager()
                state = tm.get_task_state(task_id)
                if state and isinstance(state.context, dict):
                    state.context['agent_sequence'] = agents_to_execute
                    state.context['agent_models'] = per_agent_models
                    state.context['agent_temperatures'] = per_agent_temperatures
                    if per_agent_clis:
                        state.context['agent_clis'] = per_agent_clis
                    tm.update_task_state(task_id, state)
            except Exception:
                pass

            # Initialize memory progress (existing code)
            try:
                self.task_manager.update_latest_memory_progress(task_id, [], list(agents_to_execute))
            except Exception:
                pass

            # Start logs and status
            self._handle_cli_log("INFO", f"🚀 Starting io8codermaster workflow execution")
            self._handle_cli_log("INFO", f"📋 Task ID: {task_id}")
            self._handle_cli_log("INFO", f"👥 Agents in sequence: {', '.join(agents_to_execute)}")
            self._handle_cli_log("INFO", f"💬 User prompt: {user_prompt[:100]}{'...' if len(user_prompt) > 100 else ''}")
            task_manager.update_task_status(task_id, TaskStatus.IN_PROGRESS)
            
            context = {'user_prompt': user_prompt, 'task_id': task_id}
            try:
                if workflow_id:
                    # Propagate workflow_id so sequential executor can determine variant (legacy vs io8)
                    context['workflow_id'] = workflow_id
            except Exception:
                pass
            
            # Handle combined workflows as sequential subworkflows
            if is_sequential_io8:
                # Reuse the existing sequential executor which already supports planning then execution phases
                return await self._execute_workflow3_sequential(task_id, user_prompt, context, custom_prompts, per_agent_models, per_agent_temperatures, per_agent_clis)
            
            # Regular workflow execution
            for i, agent_name in enumerate(agents_to_execute):
                # Check cooperative cancellation before each agent
                if self._is_cancelled(task_id):
                    self._handle_cli_log("WARNING", f"⛔ Task {task_id} canceled before executing {agent_name}")
                    self._handle_cli_log("DEBUG", f"🔍 Cancellation check: task_id={task_id}, cancel_flags={self._cancel_flags}")
                    return {'status': 'cancelled', 'agent': agent_name, 'step': i}
                try:
                    requested_model = per_agent_models[i] if i < len(per_agent_models) else None
                    requested_temperature = None
                    try:
                        requested_temperature = per_agent_temperatures[i] if i < len(per_agent_temperatures) else None
                    except Exception:
                        requested_temperature = None
                    # Defer model switching until after CLI selection
                    
                    start_progress = int((i / len(agents_to_execute)) * 100)
                    task_manager.update_task_progress(task_id, agent_name, start_progress)
                    
                    self._handle_cli_log("INFO", f"🤖 Executing agent {i+1}/{len(agents_to_execute)}: {agent_name}")
                    agent_prompt = custom_prompts[agent_name] if (custom_prompts and agent_name in custom_prompts) else self.agent_manager.get_agent_prompt(agent_name)
                    try:
                        info = self.agent_manager.get_agent_info(agent_name)
                        src = 'modified' if (info and info.get('is_modified')) else 'default'
                        preview = (agent_prompt or '')[:160].replace('\n', ' ')
                        self._handle_cli_log("DEBUG", f"🧩 Using {src} prompt for {agent_name}: {preview}{'...' if agent_prompt and len(agent_prompt) > 160 else ''}")
                    except Exception:
                        pass
                    if not agent_prompt:
                        raise Exception(f"Agent {agent_name} missing prompt")
                    agent_input = self._prepare_agent_input(user_prompt, context, agent_prompt, agent_name)
                    
                    # Explicitly log presence of memory blocks for observability
                    try:
                        if "=== MEMORY JSON (Latest) ===" in agent_input:
                            idx = agent_input.find("=== MEMORY JSON (Latest) ===")
                            snippet = agent_input[idx: idx + 800]
                            self._handle_cli_log("DEBUG", f"🧠 Memory JSON included for {agent_name}:\n{snippet}")
                        else:
                            self._handle_cli_log("WARNING", f"🧠 Memory JSON block not found in prompt for {agent_name}")
                        if "=== ACTIVE FILE FOR" in agent_input:
                            idx2 = agent_input.find("=== ACTIVE FILE FOR")
                            snip2 = agent_input[idx2: idx2 + 300]
                            self._handle_cli_log("DEBUG", f"📎 Active file hint included for {agent_name}:\n{snip2}")
                    except Exception:
                        pass
                    
                    # Decide which CLI to use per agent: default gemini; allow override via workflow state
                    agent_cli = None
                    try:
                        state = task_manager.get_task_state(task_id)
                        if state and isinstance(state.context, dict):
                            clis = state.context.get('agent_clis') or []
                            if clis and i < len(clis):
                                agent_cli = clis[i]
                    except Exception:
                        agent_cli = None
                    agent_cli = agent_cli or 'gemini'
                    # Force developer to use gemini for code generation fidelity
                    if agent_name in ['developer', 'io8developer'] and agent_cli != 'gemini':
                        self._handle_cli_log("WARNING", f"Developer step requires Gemini CLI; overriding selected '{agent_cli}' with 'gemini'")
                        agent_cli = 'gemini'
                    self._handle_cli_log("INFO", f"📤 Sending prompt via {agent_cli} CLI for {agent_name}")
                    self._handle_cli_log("DEBUG", f"📊 Input length: {len(agent_input)} characters")
                    
                    if agent_name in ['developer', 'io8developer']:
                        self._handle_cli_log("INFO", "ℹ️ Skipping generic chat response for developer; proceeding directly to code generation tasks")
                        response = "OK"
                    else:
                        if agent_cli == 'llxprt':
                            if self._llxprt is None:
                                try:
                                    from src.routes.bmad_api import llxprt_cli_client as _shared
                                    self._llxprt = _shared
                                    # mirror log callback
                                    self._llxprt.set_log_callback(self._handle_cli_log)
                                except Exception as _e:
                                    raise Exception(f"LLXPRT client unavailable: {_e}")
                            if requested_model:
                                try:
                                    self._llxprt.switch_model(requested_model)
                                    self._handle_cli_log("INFO", f"🎯 LLXPRT model set to {self._llxprt.get_model_info().get('model_name')}")
                                except Exception as _e:
                                    self._handle_cli_log("WARNING", f"LLXPRT model switch failed: {_e}")
                            else:
                                try:
                                    self._handle_cli_log("INFO", f"🎯 LLXPRT model (default): {self._llxprt.get_model_info().get('model_name')}")
                                except Exception:
                                    pass
                            response = await self._llxprt.send_message(agent_input, agent_name=agent_name)
                        elif agent_cli == 'surecli':
                            # Use SureCli (google.generativeai) for non-developer agents
                            if self._surecli is None:
                                try:
                                    self._surecli = SureCliClient()
                                    self._surecli.set_log_callback(self._handle_cli_log)
                                except Exception as _e:
                                    raise Exception(f"SureCli client unavailable: {_e}")
                            try:
                                self._handle_cli_log("INFO", f"🎯 SureCli model: {self._surecli.get_model_info().get('model_name')}")
                            except Exception:
                                pass
                            response = await self._surecli.send_message(agent_input, agent_name=agent_name, temperature=requested_temperature)
                        else:
                            # Using Gemini: switch Gemini model if requested
                            if requested_model:
                                try:
                                    self._handle_cli_log("INFO", f"🎯 Gemini model set to {requested_model}")
                                    self.gemini_client.switch_model(requested_model)
                                except Exception as _e:
                                    self._handle_cli_log("WARNING", f"Gemini model switch failed: {_e}")
                            response = await self.gemini_client.send_message(
                                agent_input,
                                context={
                                    "agent": agent_name,
                                    "task_id": task_id,
                                    "step": f"{i+1}/{len(agents_to_execute)}",
                                    "temperature": requested_temperature if requested_temperature is not None else ''
                                },
                                agent_name=agent_name,
                                temperature=requested_temperature
                            )
                        if response is None or (isinstance(response, str) and response.strip() == ""):
                            raise Exception("Empty response from selected CLI")
                    
                    # Track input tokens based on agent prompt sent
                    try:
                        if agent_cli == 'gemini':
                            model_used = (requested_model or getattr(self.gemini_client, 'model_name', None) or 'gemini-2.5-flash')
                        elif agent_cli == 'llxprt':
                            model_used = 'llxprt'
                        else:
                            model_used = self._surecli.get_model_info().get('model_name', 'surecli') if self._surecli else 'surecli'
                        # Rough estimate: tokens ~= words
                        estimated_input_tokens = len((agent_input or '').split())
                        self.token_meter.track_usage(task_id, estimated_input_tokens, 0, model_used)
                        self._handle_cli_log("DEBUG", f"🧮 Tracked input tokens for {agent_name}: {estimated_input_tokens}")
                    except Exception as _e:
                        self._handle_cli_log("WARNING", f"Token tracking (input) failed for {agent_name}: {_e}")
                    
                    output_file = await self._save_agent_output(task_id, agent_name, response)
                    self._handle_cli_log("INFO", f"✅ {agent_name} completed successfully")
                    self._handle_cli_log("INFO", f"💾 Output saved to: {os.path.basename(output_file)}")
                    context[f'{agent_name}_output'] = response
                    context[f'{agent_name}_file'] = output_file
                    
                    self._handle_cli_log("INFO", f"🔧 Executing tasks for {agent_name}...")
                    
                    # Execute agent tasks with automatic key rotation and restart on quota exhaustion
                    max_key_rotation_attempts = 3
                    key_rotation_attempt = 0
                    
                    while key_rotation_attempt < max_key_rotation_attempts:
                        # Check cancellation before each attempt
                        if self._is_cancelled(task_id):
                            self._handle_cli_log("WARNING", f"⛔ Task {task_id} canceled during {agent_name} execution")
                            return {'status': 'cancelled', 'agent': agent_name, 'step': i}
                        
                        try:
                            task_result = await self._execute_agent_tasks(task_id, agent_name, user_prompt)
                            
                            # Check if task execution failed due to quota exhaustion
                            if task_result.get('status') == 'failed':
                                error_msg = task_result.get('error', '')
                                if self._is_quota_exhaustion_error(error_msg):
                                    if self._handle_quota_exhaustion(agent_name, error_msg, context):
                                        key_rotation_attempt += 1
                                        continue
                                    else:
                                        break
                                else:
                                    # Not a quota error, break the retry loop
                                    break
                            else:
                                # Task succeeded, break the retry loop
                                break
                                
                        except Exception as task_error:
                            error_msg = str(task_error)
                            if self._is_quota_exhaustion_error(error_msg):
                                if self._handle_quota_exhaustion(agent_name, error_msg, context):
                                    key_rotation_attempt += 1
                                    continue
                                else:
                                    # Not a quota error, re-raise
                                    raise task_error
                    
                    # Update files created if task succeeded
                    try:
                        files_created = (task_result or {}).get('files_created') or []
                        if files_created:
                            self.task_manager.update_agent_artifacts(task_id, agent_name, files_created)
                        # Track output tokens based on files generated by CLI
                        try:
                            total_bytes = 0
                            for p in files_created:
                                try:
                                    abs_path = p if os.path.isabs(p) else os.path.join(os.path.dirname(output_file), '..', p)
                                    abs_path = os.path.abspath(abs_path)
                                    if os.path.exists(abs_path) and os.path.isfile(abs_path):
                                        total_bytes += os.path.getsize(abs_path)
                                except Exception:
                                    continue
                            # Fallback: include agent output markdown file itself
                            try:
                                if os.path.exists(output_file):
                                    total_bytes += os.path.getsize(output_file)
                            except Exception:
                                pass
                            # Approximate tokens from bytes (~4 chars per token)
                            estimated_output_tokens = int(max(0, total_bytes // 4))
                            if agent_cli == 'gemini':
                                model_used = (requested_model or getattr(self.gemini_client, 'model_name', None) or 'gemini-2.5-flash')
                            elif agent_cli == 'llxprt':
                                model_used = 'llxprt'
                            else:
                                model_used = self._surecli.get_model_info().get('model_name', 'surecli') if self._surecli else 'surecli'
                            if estimated_output_tokens > 0:
                                self.token_meter.track_usage(task_id, 0, estimated_output_tokens, model_used)
                                self._handle_cli_log("DEBUG", f"🧮 Tracked output tokens for {agent_name}: {estimated_output_tokens} (from {len(files_created)} files)")
                        except Exception as _e2:
                            self._handle_cli_log("WARNING", f"Token tracking (output) failed for {agent_name}: {_e2}")
                    except Exception:
                        pass
                    
                    # Check if the current agent failed due to quota exhaustion and prevent moving to next agent
                    if task_result.get('status') == 'failed':
                        error_msg = task_result.get('error', '')
                        if self._is_quota_exhaustion_error(error_msg):
                            self._handle_cli_log("ERROR", f"❌ {agent_name} failed due to quota exhaustion after key rotation attempts. Stopping workflow.")
                            return {
                                'status': 'failed',
                                'error': f'{agent_name} failed due to quota exhaustion: {task_result.get("error")}',
                                'agent': agent_name
                            }
                    
                    # Only execute developer continuation logic if developer is in the workflow sequence
                    if agent_name in ['developer', 'io8developer'] and agent_name in agents_to_execute:
                        remaining = task_result.get('remaining_subtasks', 0)
                        validation_issues = task_result.get('validation_issues', [])
                        total_completed = task_result.get('total_completed_tasks', 0)
                        
                        self._handle_cli_log("INFO", f"📊 Developer initial status: {remaining} remaining tasks, {len(validation_issues)} validation issues, {total_completed} completed tasks")
                        
                        attempt = 1
                        max_attempts = 5
                        quota_exhaustion_detected = False  # Track if quota exhaustion occurred
                        
                        # Note: We no longer check API quota before starting workflow
                        # Quota exhaustion will be detected during actual API calls when Gemini returns 429 errors
                        # This prevents false positives and ensures accurate quota detection
                        self._handle_cli_log("INFO", f"🚀 Starting developer continuation - API quota will be checked during actual calls")
                        
                        while (remaining > 0 or validation_issues) and attempt <= max_attempts:
                            # Check cooperative cancellation during long developer loop
                            if self._is_cancelled(task_id):
                                self._handle_cli_log("WARNING", f"⛔ Task {task_id} canceled during developer continuation")
                                return {'status': 'cancelled'}
                            self._handle_cli_log("INFO", f"🔁 Developer continuation attempt {attempt}/{max_attempts}. Remaining subtasks: {remaining}, Validation issues: {len(validation_issues)}")
                            
                            # Note: API quota will be checked during actual API calls when Gemini returns 429 errors
                            # This prevents false positives and ensures accurate quota detection
                            
                            # Execute developer tasks with automatic key rotation and restart on quota exhaustion
                            max_key_rotation_attempts = 3
                            key_rotation_attempt = 0
                            
                            while key_rotation_attempt < max_key_rotation_attempts:
                                try:
                                    next_result = await self._execute_agent_tasks(task_id, agent_name, user_prompt)
                                    
                                    # Check if task execution failed due to quota exhaustion
                                    if next_result.get('status') == 'failed':
                                        error_msg = next_result.get('error', '')
                                        if self._is_quota_exhaustion_error(error_msg):
                                            if self._handle_quota_exhaustion(agent_name, error_msg):
                                                key_rotation_attempt += 1
                                                continue
                                            else:
                                                # No more API keys available - stop developer agent
                                                quota_exhaustion_detected = True
                                                self._handle_cli_log("ERROR", f"❌ API quota exhausted and no more keys available for {agent_name}")
                                                self._handle_cli_log("ERROR", f"❌ Developer agent cannot continue. Stopping workflow.")
                                                self._handle_cli_log("ERROR", f"❌ User must add new API key and resume from developer agent.")
                                                # Update task status in database
                                                try:
                                                    from src.models.task import Task
                                                    from src.models.user import db
                                                    task = Task.query.get(task_id)
                                                    if task:
                                                        task.status = 'failed'
                                                        task.error_message = 'API quota exhausted and no more keys available. User must add new API key and resume from developer agent.'
                                                        db.session.commit()
                                                        self._handle_cli_log("INFO", f"✅ Task {task_id} status updated to failed in database")
                                                except Exception as db_error:
                                                    self._handle_cli_log("ERROR", f"❌ Failed to update task {task_id} status in database: {db_error}")
                                                
                                                return {
                                                    'status': 'failed',
                                                    'error': 'API quota exhausted and no more keys available. User must add new API key and resume from developer agent.',
                                                    'agent': agent_name,
                                                    'remaining_subtasks': remaining,
                                                    'validation_issues': validation_issues
                                                }
                                        else:
                                            # Not a quota error, break the retry loop
                                            break
                                    else:
                                        # Task succeeded, break the retry loop
                                        break
                                        
                                except Exception as task_error:
                                    error_msg = str(task_error)
                                    if self._is_quota_exhaustion_error(error_msg):
                                        if self._handle_quota_exhaustion(agent_name, error_msg):
                                            key_rotation_attempt += 1
                                            continue
                                        else:
                                            # No more API keys available - stop developer agent
                                            quota_exhaustion_detected = True
                                            self._handle_cli_log("ERROR", f"❌ API quota exhausted and no more keys available for {agent_name}")
                                            self._handle_cli_log("ERROR", f"❌ Developer agent cannot continue. Stopping workflow.")
                                            self._handle_cli_log("ERROR", f"❌ User must add new API key and resume from developer agent.")
                                            # Update task status in database
                                            try:
                                                from src.models.task import Task
                                                from src.models.user import db
                                                task = Task.query.get(task_id)
                                                if task:
                                                    task.status = 'failed'
                                                    task.error_message = 'API quota exhausted and no more keys available. User must add new API key and resume from developer agent.'
                                                    db.session.commit()
                                                    self._handle_cli_log("INFO", f"✅ Task {task_id} status updated to failed in database")
                                            except Exception as db_error:
                                                self._handle_cli_log("ERROR", f"❌ Failed to update task {task_id} status in database: {db_error}")
                                            
                                            return {
                                                'status': 'failed',
                                                'error': 'API quota exhausted and no more keys available. User must add new API key and resume from developer agent.',
                                                'agent': agent_name,
                                                'remaining_subtasks': remaining,
                                                'validation_issues': validation_issues
                                            }
                                    else:
                                        # Not a quota error, re-raise
                                        raise task_error
                            prev_remaining = remaining
                            prev_validation_issues = len(validation_issues)
                            
                            remaining = next_result.get('remaining_subtasks', remaining)
                            validation_issues = next_result.get('validation_issues', validation_issues)
                            total_completed = next_result.get('total_completed_tasks', total_completed)
                            
                            self._handle_cli_log("INFO", f"📊 After attempt {attempt}: {remaining} remaining tasks, {len(validation_issues)} validation issues, {total_completed} completed tasks")
                            
                            if isinstance(next_result.get('files_created'), list):
                                created_files = task_result.get('files_created', [])
                                created_files.extend(f for f in next_result['files_created'] if f not in created_files)
                                task_result['files_created'] = created_files
                            try:
                                self.task_manager.update_agent_artifacts(task_id, agent_name, task_result.get('files_created') or [])
                            except Exception:
                                pass
                            attempt += 1
                            
                            # Add delay if no improvement
                            if (remaining >= prev_remaining and len(validation_issues) >= prev_validation_issues):
                                await asyncio.sleep(3)
                                self._handle_cli_log("INFO", "⏳ No improvement detected, waiting before next attempt...")
                        
                        # Final status report and decision on whether to continue
                        if remaining == 0 and not validation_issues:
                            self._handle_cli_log("SUCCESS", f"✅ Developer completed all {total_completed} tasks successfully!")
                            self._handle_cli_log("INFO", "🚀 Proceeding to next agent...")
                        elif remaining == 0:
                            self._handle_cli_log("WARNING", f"⚠️ Developer marked all tasks complete but has {len(validation_issues)} validation issues")
                            self._handle_cli_log("INFO", "🚀 Proceeding to next agent despite validation issues...")
                        else:
                            self._handle_cli_log("WARNING", f"⚠️ Developer phase ended with {remaining} remaining tasks and {len(validation_issues)} validation issues")
                            
                            # Check if we should continue with developer or move to next agent
                            if attempt >= max_attempts:
                                # Check if the failure was due to API quota exhaustion
                                if quota_exhaustion_detected:
                                    self._handle_cli_log("ERROR", f"❌ Maximum attempts reached due to API quota exhaustion.")
                                    self._handle_cli_log("ERROR", f"❌ Developer agent cannot continue. Stopping workflow.")
                                    self._handle_cli_log("ERROR", f"❌ User must add new API key and resume from developer agent.")
                                    
                                    # Update task status in database
                                    try:
                                        from src.models.task import Task
                                        from src.models.user import db
                                        task = Task.query.get(task_id)
                                        if task:
                                            task.status = 'failed'
                                            task.error_message = 'API quota exhausted and no more keys available. User must add new API key and resume from developer agent.'
                                            db.session.commit()
                                            self._handle_cli_log("INFO", f"✅ Task {task_id} status updated to failed in database")
                                    except Exception as db_error:
                                        self._handle_cli_log("ERROR", f"❌ Failed to update task {task_id} status in database: {db_error}")
                                    
                                    return {
                                        'status': 'failed',
                                        'error': 'API quota exhausted and no more keys available. User must add new API key and resume from developer agent.',
                                        'agent': agent_name,
                                        'remaining_subtasks': remaining,
                                        'validation_issues': validation_issues
                                    }
                                else:
                                    # Do NOT advance to next agent if developer still has remaining work
                                    self._handle_cli_log("ERROR", f"❌ Maximum attempts ({max_attempts}) reached but developer still has {remaining} remaining tasks and {len(validation_issues)} validation issues. Stopping workflow at developer.")
                                    try:
                                        task_manager.update_task_status(task_id, TaskStatus.FAILED, current_agent=agent_name, error_message='incomplete_tasks_developer')
                                    except Exception:
                                        pass
                                    return {
                                        'status': 'failed',
                                        'error': 'incomplete_tasks_developer',
                                        'agent': agent_name,
                                        'remaining_subtasks': remaining,
                                        'validation_issues': validation_issues
                                    }
                            else:
                                self._handle_cli_log("ERROR", f"❌ Developer phase failed. Stopping workflow.")
                                return  # Stop the workflow if developer fails
                    elif agent_name == 'tester':
                        remaining_tests = task_result.get('remaining_tests', 0)
                        attempt = 1
                        max_attempts = 10
                        while remaining_tests and attempt <= max_attempts:
                            if self._is_cancelled(task_id):
                                self._handle_cli_log("WARNING", f"⛔ Task {task_id} canceled during tester continuation")
                                return {'status': 'cancelled'}
                            self._handle_cli_log("INFO", f"🔁 Tester continuation attempt {attempt}/{max_attempts}. Remaining subtests: {remaining_tests}")
                            
                            # Check API key availability before each attempt
                            try:
                                from src.routes.bmad_api import gemini_cli_client
                                available_keys = gemini_cli_client.api_key_manager.get_available_keys_count()
                                if available_keys <= 1:  # Only current key available or no keys
                                    self._handle_cli_log("ERROR", f"❌ No additional API keys available for {agent_name}. Stopping workflow.")
                                    self._handle_cli_log("ERROR", f"❌ User must add new API key and resume from tester agent.")
                                    # Update task status in database
                                    try:
                                        from src.models.task import Task
                                        from src.models.user import db
                                        task = Task.query.get(task_id)
                                        if task:
                                            task.status = 'failed'
                                            task.error_message = 'API quota exhausted. No additional API keys available. Please add a new API key and manually resume.'
                                            db.session.commit()
                                            self._handle_cli_log("INFO", f"✅ Task {task_id} status updated to failed in database")
                                    except Exception as db_error:
                                        self._handle_cli_log("ERROR", f"❌ Failed to update task {task_id} status in database: {db_error}")
                                    
                                    return {
                                        'status': 'failed',
                                        'error': 'API quota exhausted. No additional API keys available. Please add a new API key and manually resume.',
                                        'agent': agent_name,
                                        'remaining_subtasks': remaining,
                                        'validation_issues': validation_issues
                                    }
                            except Exception as key_check_error:
                                self._handle_cli_log("WARNING", f"⚠️ Could not check API key availability: {key_check_error}")
                            
                            # Execute tester tasks with automatic key rotation and restart on quota exhaustion
                            max_key_rotation_attempts = 3
                            key_rotation_attempt = 0
                            
                            while key_rotation_attempt < max_key_rotation_attempts:
                                try:
                                    next_result = await self._execute_agent_tasks(task_id, agent_name, user_prompt)
                                    
                                    # Check if task execution failed due to quota exhaustion
                                    if next_result.get('status') == 'failed':
                                        error_msg = next_result.get('error', '')
                                        if self._is_quota_exhaustion_error(error_msg):
                                            if self._handle_quota_exhaustion(agent_name, error_msg):
                                                key_rotation_attempt += 1
                                                continue
                                            else:
                                                # No more API keys available - stop tester agent
                                                self._handle_cli_log("ERROR", f"❌ API quota exhausted and no more keys available for {agent_name}")
                                                self._handle_cli_log("ERROR", f"❌ Tester agent cannot continue. Stopping workflow.")
                                                self._handle_cli_log("ERROR", f"❌ User must add new API key and resume from tester agent.")
                                                
                                                # Update task status in database
                                                try:
                                                    from src.models.task import Task
                                                    from src.models.user import db
                                                    task = Task.query.get(task_id)
                                                    if task:
                                                        task.status = 'failed'
                                                        task.error_message = 'API quota exhausted and no more keys available. User must add new API key and resume from tester agent.'
                                                        db.session.commit()
                                                        self._handle_cli_log("INFO", f"✅ Task {task_id} status updated to failed in database")
                                                except Exception as db_error:
                                                    self._handle_cli_log("ERROR", f"❌ Failed to update task {task_id} status in database: {db_error}")
                                                
                                                return {
                                                    'status': 'failed',
                                                    'error': 'API quota exhausted and no more keys available. User must add new API key and resume from tester agent.',
                                                    'agent': agent_name,
                                                    'remaining_tests': remaining_tests
                                                }
                                        else:
                                            # Not a quota error, break the retry loop
                                            break
                                    else:
                                        # Task succeeded, break the retry loop
                                        break
                                        
                                except Exception as task_error:
                                    error_msg = str(task_error)
                                    if self._is_quota_exhaustion_error(error_msg):
                                        if self._handle_quota_exhaustion(agent_name, error_msg):
                                            key_rotation_attempt += 1
                                            continue
                                        else:
                                            # No more API keys available - stop tester agent
                                            self._handle_cli_log("ERROR", f"❌ API quota exhausted and no more keys available for {agent_name}")
                                            self._handle_cli_log("ERROR", f"❌ Tester agent cannot continue. Stopping workflow.")
                                            self._handle_cli_log("ERROR", f"❌ User must add new API key and resume from tester agent.")
                                            
                                            # Update task status in database
                                            try:
                                                from src.models.task import Task
                                                from src.models.user import db
                                                task = Task.query.get(task_id)
                                                if task:
                                                    task.status = 'failed'
                                                    task.error_message = 'API quota exhausted and no more keys available. User must add new API key and resume from tester agent.'
                                                    db.session.commit()
                                                    self._handle_cli_log("INFO", f"✅ Task {task_id} status updated to failed in database")
                                            except Exception as db_error:
                                                self._handle_cli_log("ERROR", f"❌ Failed to update task {task_id} status in database: {db_error}")
                                            
                                            return {
                                                'status': 'failed',
                                                'error': 'API quota exhausted and no more keys available. User must add new API key and resume from tester agent.',
                                                'agent': agent_name,
                                                'remaining_tests': remaining_tests
                                            }
                                    else:
                                        # Not a quota error, re-raise
                                        raise task_error
                            prev_remaining = remaining_tests
                            remaining_tests = next_result.get('remaining_tests', remaining_tests)
                            if isinstance(next_result.get('files_created'), list):
                                created_files = task_result.get('files_created', [])
                                created_files.extend(f for f in next_result['files_created'] if f not in created_files)
                                task_result['files_created'] = created_files
                            try:
                                self.task_manager.update_agent_artifacts(task_id, agent_name, task_result.get('files_created') or [])
                            except Exception:
                                pass
                            attempt += 1
                    elif agent_name == 'devops':
                        # DevOps agent should not take multiple attempts - it completes deployment in one go
                        # Check if deployment was successful and auto-detect ports for zrok sharing
                        if task_result.get('status') == 'success':
                            self._handle_cli_log("INFO", "✅ DevOps deployment completed successfully")
                            self._handle_cli_log("INFO", "🔍 Auto-detecting frontend port from docker-compose.yml for zrok sharing")
                            
                            # Auto-detect frontend port and create deploy.json
                            try:
                                from src.utils.port_detector import PortDetector
                                project_dir = self.task_manager.get_task_output_directory(task_id)
                                if project_dir:
                                    frontend_port = PortDetector.auto_detect_and_create_deploy_json(project_dir)
                                    if frontend_port:
                                        self._handle_cli_log("INFO", f"✅ Auto-detected frontend port: {frontend_port}")
                                        self._handle_cli_log("INFO", f"📄 Created deploy.json with correct port for zrok sharing")
                                        
                                        # Automatically create zrok share after port detection
                                        try:
                                            from src.utils.zrok_utils import auto_create_zrok_share_for_task
                                            public_url = auto_create_zrok_share_for_task(task_id, project_dir, frontend_port)
                                            if public_url:
                                                self._handle_cli_log("INFO", f"✅ Auto-created zrok share: {public_url}")
                                            else:
                                                self._handle_cli_log("WARNING", "⚠️ Failed to create automatic zrok share")
                                        except Exception as e:
                                            self._handle_cli_log("WARNING", f"⚠️ Error creating automatic zrok share: {str(e)}")
                                    else:
                                        self._handle_cli_log("WARNING", "⚠️ Could not auto-detect frontend port from docker-compose.yml")
                            except Exception as e:
                                self._handle_cli_log("ERROR", f"❌ Error in port detection: {str(e)}")
                        else:
                            self._handle_cli_log("WARNING", f"⚠️ DevOps deployment status: {task_result.get('status', 'unknown')}")
                    
                    try:
                        completed = [a for a in agents_to_execute[:i+1]]
                        remaining = [a for a in agents_to_execute[i+1:]]
                        self.task_manager.update_latest_memory_progress(task_id, completed, remaining)
                    except Exception:
                        pass
                    
                    end_progress = int(((i + 1) / len(agents_to_execute)) * 100)
                    task_manager.update_task_progress(task_id, agent_name, end_progress)
                except GeminiCLIError as ge:
                    code = ge.code
                    msg = ge.message
                    self._handle_cli_log("ERROR", f"❌ Gemini API error [{code}] for agent {agent_name}: {msg}")
                    try:
                        self.task_manager.update_latest_memory_error(task_id, agent_name, code, msg)
                    except Exception:
                        pass
                    # Special handling for quota exhaustion with rotation: stop now so UI can auto-resume
                    if code == 'quota_exhausted_rotated':
                        self._handle_cli_log("WARNING", "🔁 Key rotated due to quota exhaustion. Stopping current run; please resume to continue with the next key.")
                        task_manager.update_task_status(task_id, TaskStatus.FAILED, current_agent=agent_name, error_message='quota_exhausted_rotated')
                        return { 'status': 'failed', 'error': 'quota_exhausted_rotated', 'agent': agent_name, 'message': msg }
                    if code == 'no_keys_available':
                        self._handle_cli_log("ERROR", "🛑 No additional API keys available. Stopping workflow.")
                        task_manager.update_task_status(task_id, TaskStatus.FAILED, current_agent=agent_name, error_message='no_keys_available')
                        return { 'status': 'failed', 'error': 'no_keys_available', 'agent': agent_name, 'message': msg }
                    # Default handling
                    task_manager.update_task_status(task_id, TaskStatus.FAILED, current_agent=agent_name, error_message=f"Gemini API error [{code}]")
                    return { 'status': 'failed', 'error': f'Gemini API error [{code}]', 'agent': agent_name, 'message': msg }
                except SureCliError as se:
                    code = getattr(se, 'code', 'error')
                    msg = getattr(se, 'message', str(se))
                    self._handle_cli_log("ERROR", f"❌ SureCLI error [{code}] for agent {agent_name}: {msg}")
                    try:
                        self.task_manager.update_latest_memory_error(task_id, agent_name, code, msg)
                    except Exception:
                        pass
                    if code == 'quota_exhausted_rotated':
                        self._handle_cli_log("WARNING", "🔁 Key rotated due to quota exhaustion (SureCLI). Stopping current run; please resume.")
                        task_manager.update_task_status(task_id, TaskStatus.FAILED, current_agent=agent_name, error_message='quota_exhausted_rotated')
                        return { 'status': 'failed', 'error': 'quota_exhausted_rotated', 'agent': agent_name, 'message': msg }
                    if code == 'no_keys_available':
                        self._handle_cli_log("ERROR", "🛑 No additional API keys available (SureCLI). Stopping workflow.")
                        task_manager.update_task_status(task_id, TaskStatus.FAILED, current_agent=agent_name, error_message='no_keys_available')
                        return { 'status': 'failed', 'error': 'no_keys_available', 'agent': agent_name, 'message': msg }
                    task_manager.update_task_status(task_id, TaskStatus.FAILED, current_agent=agent_name, error_message=f"SureCLI error [{code}]")
                    return { 'status': 'failed', 'error': f'SureCLI error [{code}]', 'agent': agent_name, 'message': msg }
                except Exception as e:
                    self._handle_cli_log("ERROR", f"Error executing agent {agent_name}: {str(e)}")
                    self._handle_cli_log("DEBUG", f"🔍 Exception details: {type(e).__name__}: {str(e)}")
                    self._handle_cli_log("DEBUG", f"🔍 Task state: task_id={task_id}, running_tasks={self._running_tasks}, cancel_flags={self._cancel_flags}")
                    task_manager.update_task_status(task_id, TaskStatus.FAILED, current_agent=agent_name, error_message=str(e))
                    return {'status': 'failed', 'agent': agent_name, 'error': str(e)}
            
            # Workflow completed successfully
            task_manager.update_task_progress(task_id, agents_to_execute[-1] if agents_to_execute else '', 100)
            task_manager.update_task_status(task_id, TaskStatus.COMPLETED)
            
            # Clean up running tasks
            self._running_tasks.discard(task_id)
            self.clear_cancel(task_id)
            
            return {'status': 'completed', 'message': 'Workflow completed successfully'}
        
        except Exception as e:
            logger.error(f"Error executing workflow for task {task_id}: {e}")
            return {'status': 'failed', 'error': str(e)}
        finally:
            # Clear running guard
            try:
                if task_id in self._running_tasks:
                    self._running_tasks.remove(task_id)
            except Exception:
                pass

    def _temperature_guidance(self, t: float) -> str:
        if t is None:
            return ""
        if t <= 0.15:
            return "Be strictly deterministic and concise. Avoid creativity; pick the most likely answer."
        if t <= 0.3:
            return "Be focused and precise. Prefer the most probable phrasing; minimize variation."
        if t <= 0.6:
            return "Balance determinism with small variation. Provide clear, relevant content."
        if t <= 0.8:
            return "Allow some creativity while staying relevant and structured."
        if t <= 1.0:
            return "Increase diversity slightly; offer alternative ideas if helpful."
        if t <= 1.5:
            return "Be creative; explore multiple directions while keeping coherence."
        return "Be very creative and exploratory; accept higher variance, but avoid illogical statements."

    def _prepare_agent_input(self, user_prompt: str, context: Dict[str, Any], 
                           agent_prompt: str, agent_name: str) -> str:
        """
        Prepare input for an agent with context from previous agents
        Now uses full agent prompts from AgentManager
        Also includes references to sequential documents created by previous agents
        
        Args:
            user_prompt: Original user prompt
            context: Context from previous agents
            agent_prompt: The agent's full prompt from AgentManager
            agent_name: Name of the current agent
            
        Returns:
            Formatted input string for the agent
        """
        # Special handling for FLF agent to ensure proper context
        if agent_name == "flf-save":
            logger.info(f"Preparing input for FLF agent with user prompt: {user_prompt}")
            
            # Ensure the user prompt contains the necessary information for FLF workflow
            # The frontend should have already formatted this as:
            # "First, clone the repository from {flfUrl}. Then, analyze the field patterns in {flfFolderName} using the Universal Field Analysis Context Guide"
            
            # Add explicit instructions for FLF agent if not already present
            if "clone the repository" not in user_prompt.lower() and "analyze the field patterns" not in user_prompt.lower():
                # This might be a direct prompt, add context
                user_prompt = f"{user_prompt}\n\nPlease analyze field patterns using the Universal Field Analysis Context Guide."
        
        # Build context from previous agents (limit to last 2 agents to keep size down)
        previous_work = ""
        context_keys = [key for key in context.keys() if key.endswith('_output') and key != 'user_prompt']
        # Only include last 2 agents' work to keep prompt size manageable
        recent_context_keys = context_keys[-2:] if len(context_keys) > 2 else context_keys
        
        for key in recent_context_keys:
            prev_agent = key.replace('_output', '')
            value = context[key]
            # Limit each agent's output to 500 characters to keep prompt size down
            truncated_value = value[:500] + "..." if len(value) > 500 else value
            previous_work += f"\n\n--- {prev_agent.upper()} OUTPUT ---\n{truncated_value}\n"
        
        # Include task memory summary (user prompts and agent progress only; no model responses)
        memory_block = ""
        active_file_block = ""
        memory_json_block = ""
        try:
            mem = self.task_manager.get_task_memory(context.get('task_id', ''))
            history = mem.get('history', [])[-3:]  # include last 3 runs for brevity
            if history:
                lines = ["=== MEMORY (Recent runs) ==="]
                for item in history:
                    ts = item.get('timestamp', '')
                    pr = item.get('prompt', '')
                    wf = item.get('workflow_id', '')
                    prog = item.get('agents_progress', {})
                    completed = ", ".join(prog.get('completed', []) or [])
                    remaining = ", ".join(prog.get('remaining', []) or [])
                    lines.append(f"- [{ts}] prompt: {pr}\n  workflow: {wf}\n  completed: {completed or '-'}\n  remaining: {remaining or '-'}")
                memory_block = "\n\n" + "\n".join(lines)
            # Latest entry JSON (prompt, progress, artifacts)
            latest = mem.get('history', [])[-1] if mem.get('history') else None
            if latest and isinstance(latest, dict):
                to_send = {
                    'prompt': latest.get('prompt'),
                    'workflow_id': latest.get('workflow_id'),
                    'agents_progress': latest.get('agents_progress', {}),
                    'agents_details': latest.get('agents_details', {}),
                }
                memory_json_block = "\n\n=== MEMORY JSON (Latest) ===\n" + json.dumps(to_send, indent=2)
                # Active file hint for current agent
                agents_details = latest.get('agents_details') or {}
                details = agents_details.get(agent_name) or {}
                in_progress_file = details.get('in_progress_file')
                if in_progress_file:
                    active_file_block = f"\n\n=== ACTIVE FILE FOR {agent_name.upper()} ===\nContinue from this file: @{in_progress_file}\n(If the file is missing, recreate it and resume where you left off.)"
                
                # Add resume context if this is a resumed workflow
                agents_progress = latest.get('agents_progress', {})
                completed_agents = agents_progress.get('completed', [])
                if completed_agents and agent_name not in completed_agents:
                    resume_context = f"\n\n=== RESUME CONTEXT ===\nThis workflow was resumed from agent '{agent_name}'. The following agents have already completed: {', '.join(completed_agents)}. Do not redo their work."
                    memory_json_block += resume_context
        except Exception:
            pass
        
        # Add references to sequential documents created by previous agents
        sequential_docs = ""
        try:
            from src.core.task_manager import TaskManager
            task_manager = TaskManager()
            project_dir = task_manager.get_task_output_directory(context.get('task_id', ''))
            
            if project_dir and os.path.exists(project_dir):
                # Define which documents each agent should reference
                doc_references = {
                    'architect': ['.sureai/analysis_document.md', '.sureai/requirements_document.md'],
                    'pm': ['.sureai/analysis_document.md', '.sureai/architecture_document.md'],
                    'sm': ['.sureai/prd_document.md', '.sureai/tasks_list.md'],
                    'developer': ['.sureai/tasks_list.md', '.sureai/architecture_document.md', '.sureai/tech_stack_document.md'],
                    'devops': ['.sureai/architecture_document.md'],
                    'tester': ['.sureai/architecture_document.md', 'backend/', 'frontend/'],
                    # FLF agent no longer needs the context file as it's included directly in the prompt
                    'flf-save': []
                }
                
                if agent_name in doc_references:
                    available_docs = []
                    for doc_name in doc_references[agent_name]:
                        doc_path = os.path.join(project_dir, doc_name)
                        if os.path.exists(doc_path):
                            try:
                                with open(doc_path, 'r', encoding='utf-8') as f:
                                    doc_content = f.read()
                                    # Limit document content to 300 characters
                                    truncated_doc = doc_content[:300] + "..." if len(doc_content) > 300 else doc_content
                                    available_docs.append(f"📄 {doc_name}:\n{truncated_doc}")
                            except Exception as e:
                                logger.warning(f"Could not read document {doc_name}: {e}")
                    
                    if available_docs:
                        sequential_docs = "\n\n=== SEQUENTIAL DOCUMENTS TO REFERENCE ===\n" + "\n\n".join(available_docs)
        except Exception as e:
            logger.warning(f"Could not load sequential documents: {e}")
        
        # Get agent-specific instructions from AgentManager
        agent_instructions = ""
        try:
            agent_instructions = self.agent_manager.get_agent_instructions(agent_name)
            if agent_instructions:
                agent_instructions = f"\n\n=== AGENT INSTRUCTIONS ===\n{agent_instructions}"
        except Exception as e:
            logger.warning(f"Could not load agent instructions for {agent_name}: {e}")

        # (Removed) Dynamic MCP/Git orchestration; handled via explicit UI buttons instead
        
        # Compose final input
        input_sections = [
            f"=== AGENT PROMPT ({agent_name}) ===\n{agent_prompt}",
            f"\n\n=== USER PROMPT ===\n{user_prompt}",
            previous_work,
            memory_block,
            memory_json_block,
            active_file_block,
            sequential_docs,
            agent_instructions
        ]
        final_input = "\n".join([s for s in input_sections if s])
        
        # Log the complete prompt for debugging
        logger.info(f"📝 Complete prompt for {agent_name} (length: {len(final_input)} characters)")
        if agent_name == "flf-save":
            # For FLF agent, log the full prompt for debugging
            logger.info(f"📝 FLF Agent Complete Prompt:\n{final_input}")
        else:
            # For other agents, log first 2000 characters
            logger.info(f"📝 Prompt preview: {final_input[:2000]}{'...' if len(final_input) > 2000 else ''}")
        
        return final_input

    async def _save_agent_output(self, task_id: str, agent_name: str, output: str) -> str:
        """
        Save agent output - now handled by SequentialDocumentBuilder
        
        Args:
            task_id: Task identifier
            agent_name: Name of the agent
            output: Agent's output text
            
        Returns:
            Path to the saved file
        """
        try:
            # Import here to avoid circular imports
            from src.core.task_manager import TaskManager
            task_manager = TaskManager()
            
            # Get task output directory with retry for potential race conditions
            project_dir = None
            for attempt in range(3):  # Try up to 3 times with small delays
                project_dir = task_manager.get_task_output_directory(task_id)
                if project_dir:
                    break
                if attempt < 2:  # Don't sleep on the last attempt
                    import time
                    time.sleep(0.1)  # Small delay to allow database commit
            
            if not project_dir:
                # If no project directory found after retries, this is an error condition
                # The TaskManager should have created the directory during task creation
                self._handle_cli_log("ERROR", f"⚠️ No project directory found for task {task_id} after retries. Task may not have been created properly.")
                return f"/tmp/.{agent_name}_{task_id}.md"
            
            # Create .sureai directory if it doesn't exist
            sureai_dir = os.path.join(project_dir, ".sureai")
            os.makedirs(sureai_dir, exist_ok=True)
            
            # Create filename with dot prefix (hidden file)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f".{agent_name}_{timestamp}.md"
            file_path = os.path.join(sureai_dir, filename)
            
            # Agent output files are now created by SequentialDocumentBuilder via Gemini CLI
            # This method just returns the expected path for logging purposes
            self._handle_cli_log("INFO", f"💾 Agent output will be saved by SequentialDocumentBuilder to {file_path}")
            return file_path
            
        except Exception as e:
            self._handle_cli_log("ERROR", f"Failed to prepare agent output path: {e}")
            # Return a fallback path
            return f"/tmp/.{agent_name}_{task_id}.md"

    async def _execute_agent_tasks(self, task_id: str, agent_name: str, user_prompt: str) -> Dict[str, Any]:
        """Execute tasks for a specific agent based on the user prompt"""
        try:
            from src.core.sequential_document_builder import SequentialDocumentBuilder
            
            # Get project directory with retry for potential race conditions
            project_dir = None
            for attempt in range(3):  # Try up to 3 times with small delays
                project_dir = self.task_manager.get_task_output_directory(task_id)
                if project_dir:
                    break
                if attempt < 2:  # Don't sleep on the last attempt
                    import time
                    time.sleep(0.1)  # Small delay to allow database commit
            
            if not project_dir:
                self._handle_cli_log("WARNING", f"⚠️ No project directory found for task {task_id} after retries")
                return {
                    'status': 'skipped',
                    'reason': 'No project directory available'
                }
            
            # Initialize sequential document builder only
            doc_builder = SequentialDocumentBuilder()
            
            # Execute sequential document builder with the user prompt
            # This will create the agent-specific prompts and documents
            doc_result = doc_builder.execute_sequential_phase(task_id, agent_name, user_prompt, project_dir)
            
            # Return the document builder result
            return {
                'status': doc_result['status'],
                'document_building': doc_result,
                'files_created': doc_result.get('files_created', []),
                'remaining_subtasks': doc_result.get('remaining_subtasks', 0),
                'remaining_tests': doc_result.get('remaining_tests', 0)
            }
            
        except Exception as e:
            self._handle_cli_log("ERROR", f"❌ Task execution error for {agent_name}: {str(e)}")
            return {
                'status': 'failed',
                'error': str(e)
            }

    async def _execute_project_generation(self, task_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute project generation based on agent outputs"""
        try:
            # Extract agent outputs from context
            agent_outputs = {}
            for key, value in context.items():
                if key.endswith('_output'):
                    agent_name = key.replace('_output', '')
                    agent_outputs[agent_name] = value
            
            if not agent_outputs:
                self._handle_cli_log("WARNING", "⚠️ No agent outputs found for project generation")
                return {
                    'status': 'skipped',
                    'reason': 'No agent outputs available'
                }
            
            # Project generation is now handled by SequentialDocumentBuilder
            # The DevOps agent creates all deployment files directly
            self._handle_cli_log("INFO", f"📋 Project generation handled by SequentialDocumentBuilder")
            self._handle_cli_log("INFO", f"✅ All files created by Gemini CLI via terminal commands")
            
            return {
                'status': 'completed',
                'message': 'Project generation handled by SequentialDocumentBuilder and Gemini CLI',
                'files_created': 'All files created by Gemini CLI via terminal commands'
            }
            
        except Exception as e:
            self._handle_cli_log("ERROR", f"❌ Project execution error: {str(e)}")
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    def _handle_quota_exhaustion(self, agent_name: str, error_message: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Handle quota exhaustion by attempting key rotation
        
        Args:
            agent_name: Name of the agent that encountered the error
            error_message: The error message containing quota exhaustion details
            context: Optional context to update with restart information
            
        Returns:
            True if key rotation was successful, False otherwise
        """
        try:
            from src.routes.bmad_api import gemini_cli_client
            
            # Check if gemini_cli_client is available
            if gemini_cli_client is None:
                self._handle_cli_log("ERROR", f"❌ Gemini CLI client not available for key rotation")
                return False
                
            # Check if api_key_manager is available
            if gemini_cli_client.api_key_manager is None:
                self._handle_cli_log("ERROR", f"❌ API key manager not available for key rotation")
                return False
            
            # Get current key status before rotation
            current_status = gemini_cli_client.api_key_manager.get_key_status()
            current_key_index = current_status.get('current_key_index', 0)
            current_key_id = f"key{current_key_index + 1}"
            
            self._handle_cli_log("WARNING", f"🔄 Quota exhaustion detected for {agent_name} using {current_key_id}, attempting automatic key rotation...")
            
            # Attempt key rotation
            if gemini_cli_client.handle_api_error(error_message):
                # Key rotation was successful - get new key status
                new_status = gemini_cli_client.api_key_manager.get_key_status()
                new_key_index = new_status.get('current_key_index', 0)
                new_key_id = f"key{new_key_index + 1}"
                
                self._handle_cli_log("SUCCESS", f"✅ Key rotation successful: {current_key_id} → {new_key_id} for {agent_name}")
                self._handle_cli_log("INFO", f"🔄 Restarting {agent_name} with new API key...")
                
                # Update context if provided
                if context:
                    context[f'{agent_name}_output'] = f"Key rotated from {current_key_id} to {new_key_id} and agent restarted"
                
                return True
            else:
                # No keys available for rotation - workflow must stop
                available_keys = gemini_cli_client.api_key_manager.get_available_keys_count()
                total_keys = len(gemini_cli_client.api_key_manager.api_keys)
                
                self._handle_cli_log("ERROR", f"❌ No additional API keys available for rotation (total keys: {total_keys})")
                self._handle_cli_log("ERROR", f"❌ All API keys exhausted - workflow must be terminated")
                self._handle_cli_log("ERROR", f"❌ User must add new API key and manually restart workflow")
                return False
                
        except Exception as rotation_error:
            self._handle_cli_log("ERROR", f"❌ Key rotation error for {agent_name}: {rotation_error}")
            return False
    
    def _is_quota_exhaustion_error(self, error_message: str) -> bool:
        """
        Check if an error message indicates quota exhaustion
        
        Args:
            error_message: The error message to check
            
        Returns:
            True if the error indicates quota exhaustion
        """
        error_lower = error_message.lower()
        quota_indicators = [
            'quota exceeded', 'quota exhausted', 'resource_exhausted', 
            '429', 'rate limit exceeded', 'quota limit', 'exceeded your current quota'
        ]
        return any(quota_indicator in error_lower for quota_indicator in quota_indicators)
    
    def get_workflow_status(self, task_id: str) -> Dict[str, Any]:
        """Get the current status of a workflow"""
        return {
            'task_id': task_id,
            'cli_logs': self.get_cli_logs(),
            'gemini_model': self.gemini_client.get_model_info()
        }
    
    async def _execute_workflow3_sequential(self, task_id: str, user_prompt: str, context: Dict[str, Any], 
                                          custom_prompts: Optional[Dict[str, str]] = None, per_agent_models: Optional[List[str]] = None, 
                                          per_agent_temperatures: Optional[List[Optional[float]]] = None, per_agent_clis: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Execute combined workflow as sequential subworkflows
        
        For legacy name 'End-to-End Plan + Execute':
          Phase 1: Planning Phase (SureCLI) - directory_structure → io8codermaster → analyst → architect → pm
          Phase 2: Execution Phase (Gemini) - sm → developer → devops
        
        For 'io8 Default':
          Phase 1: io8 Plan (SureCLI) - io8_mcp_project → io8directory_structure → io8codermaster → io8analyst → io8architect → io8pm
          Phase 2: io8 Develop (Gemini) - io8sm → io8developer
          Phase 3: io8 Deploy (Gemini) - io8devops
        """
        try:
            from src.core.task_manager import TaskManager, TaskStatus
            task_manager = TaskManager()
            
            # Provide default values for optional parameters
            custom_prompts = custom_prompts or {}
            per_agent_models = per_agent_models or []
            per_agent_temperatures = per_agent_temperatures or []
            per_agent_clis = per_agent_clis or []
            
            # Determine workflow by name from DB if available
            workflow_name = None
            try:
                from src.models.workflow import Workflow
                wf = Workflow.query.get(context.get('workflow_id')) if context and context.get('workflow_id') else None
                if wf:
                    workflow_name = wf.name
            except Exception:
                workflow_name = None

            # Define subworkflows
            if workflow_name in ['io8 Default', 'io8 Plan', 'io8plan']:
                # Ensure io8_mcp_project runs first in planning and uses Gemini CLI
                planning_agents = ['io8_mcp_project', 'io8directory_structure', 'io8codermaster', 'io8analyst', 'io8architect', 'io8pm']
                development_agents = ['io8sm', 'io8developer']
                deployment_agents = ['io8devops']
                # Define these variables to avoid "possibly unbound" errors
                execution_agents = []
            else:
                planning_agents = ['directory_structure', 'io8codermaster', 'analyst', 'architect', 'pm']
                execution_agents = ['sm', 'developer', 'devops']
                # Define these variables to avoid "possibly unbound" errors
                development_agents = []
                deployment_agents = []
            
            # Check if this is a resume operation by looking at task current agent
            current_agent = None
            skip_planning = False
            skip_development = False
            skip_deployment = False
            
            try:
                task = task_manager.get_task(task_id)
                if task:
                    if isinstance(task, dict):
                        current_agent = task.get('current_agent')
                    else:
                        current_agent = getattr(task, 'current_agent', None)
                    
                    if current_agent:
                        self._handle_cli_log("INFO", f"🔄 Resume detected - current agent: {current_agent}")
                        
                        # Check if current agent is in development or deployment phase
                        if current_agent in deployment_agents:
                            skip_planning = True
                            skip_development = True
                            self._handle_cli_log("INFO", f"🔄 Skipping planning and development phases - resuming from deployment phase")
                        elif current_agent in development_agents:
                            skip_planning = True
                            self._handle_cli_log("INFO", f"🔄 Skipping planning phase - resuming from development phase")
                        elif current_agent in execution_agents:
                            skip_planning = True
                            self._handle_cli_log("INFO", f"🔄 Skipping planning phase - resuming from execution phase")
                        elif current_agent in planning_agents:
                            # Current agent is in planning phase, continue from there
                            # Filter planning agents to start from current agent
                            current_index = planning_agents.index(current_agent)
                            planning_agents = planning_agents[current_index:]
                            self._handle_cli_log("INFO", f"🔄 Resuming planning phase from agent: {current_agent}")
            except Exception as e:
                self._handle_cli_log("WARNING", f"Could not determine resume context: {e}")
            
            # Phase 1: Planning Phase (SureCLI) - only if not skipping
            phase1_result = {'status': 'completed'}  # Default to completed if skipping
            if not skip_planning:
                self._handle_cli_log("INFO", f"🚀 Starting Phase 1: Planning Phase (SureCLI)")
                self._handle_cli_log("INFO", f"📋 Planning agents: {', '.join(planning_agents)}")
                
                phase1_result = await self._execute_workflow_phase(
                    task_id, user_prompt, context, planning_agents, 
                    custom_prompts, per_agent_models, per_agent_temperatures, per_agent_clis,
                    phase_name="Planning Phase (SureCLI)", phase_number=1
                )
                
                if phase1_result.get('status') != 'completed':
                    self._handle_cli_log("ERROR", f"❌ Phase 1 (Planning) failed: {phase1_result.get('error', 'Unknown error')}")
                    return phase1_result
                
                self._handle_cli_log("SUCCESS", f"✅ Phase 1 (Planning) completed successfully!")
            else:
                self._handle_cli_log("INFO", f"⏭️ Skipping Phase 1 (Planning) - resuming from execution phase")
            
            # Auto-commit to Gitea after PM agent completes in io8 planning phase
            try:
                # Only for io8-style planning where 'io8pm' is last agent
                if 'io8pm' in planning_agents and planning_agents[-1] == 'io8pm':
                    from src.core.task_manager import TaskManager
                    import os
                    import subprocess
                    import threading

                    tm = TaskManager()
                    project_dir = tm.get_task_output_directory(task_id)
                    if project_dir and os.path.exists(project_dir):
                        project_name = os.path.basename(project_dir.rstrip(os.sep)) or 'project'
                        repo_url = f"http://157.66.191.31:3000/risadmin_prod/{project_name}.git"
                        username = 'risadmin_prod'
                        password = 'adminprod1234'

                        def _run_cmd(cmd, cwd=None, env=None, timeout=180):
                            try:
                                proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
                                out, err = proc.communicate(timeout=timeout)
                                return proc.returncode, out or '', err or ''
                            except Exception as e:
                                return 1, '', str(e)

                        def _with_creds(url: str, user: str, pwd: str) -> str:
                            if url.startswith('http://') or url.startswith('https://'):
                                scheme, rest = url.split('://', 1)
                                return f"{scheme}://{user}:{pwd}@{rest}"
                            return url

                        def _commit_and_push():
                            try:
                                self._handle_cli_log("INFO", f"🔁 Auto-commit: preparing git repo in {project_dir}")
                                # Init if missing
                                if not os.path.exists(os.path.join(project_dir, '.git')):
                                    code, out, err = _run_cmd(['git', 'init'], cwd=project_dir)
                                    if code != 0:
                                        self._handle_cli_log("ERROR", f"Auto-commit: git init failed: {err}")
                                        return
                                # main branch and config
                                _run_cmd(['git', 'checkout', '-B', 'main'], cwd=project_dir)
                                _run_cmd(['git', 'config', 'user.name', 'user'], cwd=project_dir)
                                _run_cmd(['git', 'config', 'user.email', 'user@gmail.com'], cwd=project_dir)
                                # remote origin
                                _run_cmd(['git', 'remote', 'remove', 'origin'], cwd=project_dir)
                                url_with_creds = _with_creds(repo_url, username, password)
                                code, out, err = _run_cmd(['git', 'remote', 'add', 'origin', url_with_creds], cwd=project_dir)
                                if code != 0 and 'already exists' not in (err or '').lower():
                                    self._handle_cli_log("ERROR", f"Auto-commit: git remote add failed: {err}")
                                    return
                                # Try to reconcile with remote main if it exists
                                _run_cmd(['git', 'fetch', 'origin', 'main'], cwd=project_dir)
                                _run_cmd(['git', 'branch', '-u', 'origin/main', 'main'], cwd=project_dir)
                                _run_cmd(['git', 'pull', 'origin', 'main', '--allow-unrelated-histories'], cwd=project_dir)
                                # stage and commit if there are changes
                                _run_cmd(['git', 'add', '.'], cwd=project_dir)
                                code, out, err = _run_cmd(['git', 'diff', '--cached', '--quiet'], cwd=project_dir)
                                if code != 0:
                                    _run_cmd(['git', 'commit', '-m', 'Initial commit of io8 project'], cwd=project_dir)
                                # push (retry with lease if first fails)
                                code, out, err = _run_cmd(['git', 'push', '-u', 'origin', 'main'], cwd=project_dir)
                                if code != 0:
                                    self._handle_cli_log("WARNING", f"Auto-commit: initial git push failed, retrying with --force-with-lease: {err}")
                                    code2, out2, err2 = _run_cmd(['git', 'push', '-u', 'origin', 'main', '--force-with-lease'], cwd=project_dir)
                                    if code2 != 0:
                                        self._handle_cli_log("ERROR", f"Auto-commit: git push failed after retry: {err2}")
                                        return
                                self._handle_cli_log("SUCCESS", f"✅ Auto-commit: code pushed to Gitea repo {repo_url}")
                            except Exception as e:
                                self._handle_cli_log("ERROR", f"Auto-commit error: {e}")

                        # Run in background to avoid blocking workflow transition
                        threading.Thread(target=_commit_and_push, name=f"auto-commit-{task_id}", daemon=True).start()
                        self._handle_cli_log("INFO", f"🚀 Auto-commit to Gitea triggered for {project_name}")
            except Exception as ac_err:
                self._handle_cli_log("WARNING", f"Auto-commit hook skipped due to error: {ac_err}")
            
            # Phase 2: Development Phase (Gemini) - only for io8 Default
            if workflow_name in ['io8 Default', 'io8 Plan', 'io8plan']:
                phase2_result = {'status': 'completed'}  # Default to completed if skipping
                if not skip_development:
                    self._handle_cli_log("INFO", f"🚀 Starting Phase 2: Development Phase (Gemini)")
                    self._handle_cli_log("INFO", f"📋 Development agents: {', '.join(development_agents)}")
                    # Skip preflight Gemini CLI availability check since we know it's installed
                    # This prevents timeout issues when the CLI is slow to respond to --version
                    '''
                    try:
                        import subprocess
                        check = subprocess.run(['gemini', '--version'], capture_output=True, text=True, timeout=10)
                        if check.returncode != 0:
                            self._handle_cli_log("ERROR", f"❌ Gemini CLI preflight failed (non-zero exit). Stderr: {check.stderr.strip()}")
                            return {'status': 'error', 'error': 'Gemini CLI not available for Development Phase'}
                    except Exception as e:
                        self._handle_cli_log("ERROR", f"❌ Gemini CLI preflight failed: {str(e)}")
                        return {'status': 'error', 'error': 'Gemini CLI not available for Development Phase'}
                    '''
                    
                    # Handle development phase resume if needed
                    if skip_planning and current_agent in development_agents:
                        # Filter development agents to start from current agent
                        current_index = development_agents.index(current_agent)
                        development_agents = development_agents[current_index:]
                        self._handle_cli_log("INFO", f"🔄 Resuming development phase from agent: {current_agent}")
                    
                    phase2_result = await self._execute_workflow_phase(
                        task_id, user_prompt, context, development_agents, 
                        custom_prompts, per_agent_models, per_agent_temperatures, per_agent_clis,
                        phase_name="Development Phase (Gemini)", phase_number=2
                    )
                    
                    if phase2_result.get('status') != 'completed':
                        self._handle_cli_log("ERROR", f"❌ Phase 2 (Development) failed: {phase2_result.get('error', 'Unknown error')}")
                        return phase2_result
                    
                    self._handle_cli_log("SUCCESS", f"✅ Phase 2 (Development) completed successfully!")
                else:
                    self._handle_cli_log("INFO", f"⏭️ Skipping Phase 2 (Development) - resuming from deployment phase")
                
                # Phase 3: Deployment Phase (Gemini) - only for io8 Default
                phase3_result = {'status': 'completed'}  # Default to completed if skipping
                if not skip_deployment:
                    self._handle_cli_log("INFO", f"🚀 Starting Phase 3: Deployment Phase (Gemini)")
                    self._handle_cli_log("INFO", f"📋 Deployment agents: {', '.join(deployment_agents)}")
                    
                    # Handle deployment phase resume if needed
                    if skip_development and current_agent in deployment_agents:
                        # Filter deployment agents to start from current agent
                        current_index = deployment_agents.index(current_agent)
                        deployment_agents = deployment_agents[current_index:]
                        self._handle_cli_log("INFO", f"🔄 Resuming deployment phase from agent: {current_agent}")
                    
                    phase3_result = await self._execute_workflow_phase(
                        task_id, user_prompt, context, deployment_agents, 
                        custom_prompts, per_agent_models, per_agent_temperatures, per_agent_clis,
                        phase_name="Deployment Phase (Gemini)", phase_number=3
                    )
                    
                    if phase3_result.get('status') != 'completed':
                        self._handle_cli_log("ERROR", f"❌ Phase 3 (Deployment) failed: {phase3_result.get('error', 'Unknown error')}")
                        return phase3_result
                    
                    self._handle_cli_log("SUCCESS", f"✅ Phase 3 (Deployment) completed successfully!")
                else:
                    self._handle_cli_log("INFO", f"⏭️ Skipping Phase 3 (Deployment) - already completed")
                
                self._handle_cli_log("SUCCESS", f"🎉 io8 Default workflow completed successfully!")
                
                # Update final status
                task_manager.update_task_progress(task_id, deployment_agents[-1] if deployment_agents else '', 100)
                task_manager.update_task_status(task_id, TaskStatus.COMPLETED)
                
                # Clean up running tasks
                self._running_tasks.discard(task_id)
                self.clear_cancel(task_id)
                
                return {'status': 'completed', 'message': 'io8 Default workflow completed successfully with sequential subworkflows'}
            else:
                # Legacy workflow: Phase 2: Execution Phase (Gemini)
                self._handle_cli_log("INFO", f"🚀 Starting Phase 2: Execution Phase (Gemini)")
                self._handle_cli_log("INFO", f"📋 Execution agents: {', '.join(execution_agents)}")
                # Skip preflight Gemini CLI availability check since we know it's installed
                # This prevents timeout issues when the CLI is slow to respond to --version
                '''
                try:
                    import subprocess
                    check = subprocess.run(['gemini', '--version'], capture_output=True, text=True, timeout=10)
                    if check.returncode != 0:
                        self._handle_cli_log("ERROR", f"❌ Gemini CLI preflight failed (non-zero exit). Stderr: {check.stderr.strip()}")
                        return {'status': 'error', 'error': 'Gemini CLI not available for Execution Phase'}
                except Exception as e:
                    self._handle_cli_log("ERROR", f"❌ Gemini CLI preflight failed: {str(e)}")
                    return {'status': 'error', 'error': 'Gemini CLI not available for Execution Phase'}
                '''
                
                # Handle execution phase resume if needed
                if skip_planning and current_agent in execution_agents:
                    # Filter execution agents to start from current agent
                    current_index = execution_agents.index(current_agent)
                    execution_agents = execution_agents[current_index:]
                    self._handle_cli_log("INFO", f"🔄 Resuming execution phase from agent: {current_agent}")
                
                phase2_result = await self._execute_workflow_phase(
                    task_id, user_prompt, context, execution_agents, 
                    custom_prompts, per_agent_models, per_agent_temperatures, per_agent_clis,
                    phase_name="Execution Phase (Gemini)", phase_number=2
                )
                
                if phase2_result.get('status') != 'completed':
                    self._handle_cli_log("ERROR", f"❌ Phase 2 (Execution) failed: {phase2_result.get('error', 'Unknown error')}")
                    return phase2_result
                
                self._handle_cli_log("SUCCESS", f"✅ Phase 2 (Execution) completed successfully!")
                self._handle_cli_log("SUCCESS", f"🎉 Combined sequential workflow completed successfully!")
                
                # Update final status
                task_manager.update_task_progress(task_id, execution_agents[-1] if execution_agents else '', 100)
                task_manager.update_task_status(task_id, TaskStatus.COMPLETED)
                
                # Clean up running tasks
                self._running_tasks.discard(task_id)
                self.clear_cancel(task_id)
                
                return {'status': 'completed', 'message': 'Combined workflow completed successfully with sequential subworkflows'}
            
        except Exception as e:
            self._handle_cli_log("ERROR", f"❌ Error in workflow3 sequential execution: {str(e)}")
            return {'status': 'failed', 'error': str(e)}
    
    async def _execute_workflow_phase(self, task_id: str, user_prompt: str, context: Dict[str, Any], 
                                    agents: List[str], custom_prompts: Optional[Dict[str, str]] = None, 
                                    per_agent_models: Optional[List[str]] = None, per_agent_temperatures: Optional[List[Optional[float]]] = None, 
                                    per_agent_clis: Optional[List[str]] = None, phase_name: str = "", phase_number: int = 1) -> Dict[str, Any]:
        """
        Execute a single phase of workflow3
        
        Args:
            task_id: Task identifier
            user_prompt: User's input prompt
            context: Context from previous phases
            agents: List of agents to execute in this phase
            custom_prompts: Custom prompts for agents
            per_agent_models: Model overrides per agent
            per_agent_temperatures: Temperature overrides per agent
            per_agent_clis: CLI overrides per agent
            phase_name: Name of the phase for logging
            phase_number: Phase number for logging
            
        Returns:
            Dict containing phase execution results
        """
        try:
            from src.core.task_manager import TaskManager, TaskStatus
            task_manager = TaskManager()
            
            # Provide default values for optional parameters
            custom_prompts = custom_prompts or {}
            per_agent_models = per_agent_models or []
            per_agent_temperatures = per_agent_temperatures or []
            per_agent_clis = per_agent_clis or []
            
            # Align arrays to phase length
            phase_models = list(per_agent_models[:len(agents)]) if per_agent_models else [None] * len(agents)
            phase_temperatures = list(per_agent_temperatures[:len(agents)]) if per_agent_temperatures else [None] * len(agents)
            phase_clis = list(per_agent_clis[:len(agents)]) if per_agent_clis else ['surecli' if phase_number == 1 else 'gemini'] * len(agents)
            # Enforce gemini CLI for io8_mcp_project
            phase_clis = [cli for cli in phase_clis]  # Convert to list
            for idx, name in enumerate(agents):
                if name == 'io8_mcp_project':
                    phase_clis[idx] = 'gemini'
            
            # Pad arrays if needed
            while len(phase_models) < len(agents):
                phase_models.append(None)
            while len(phase_temperatures) < len(agents):
                phase_temperatures.append(None)
            while len(phase_clis) < len(agents):
                phase_clis.append('surecli' if phase_number == 1 else 'gemini')
            
            self._handle_cli_log("INFO", f"🔄 Executing {phase_name} with {len(agents)} agents")
            
            for i, agent_name in enumerate(agents):
                # Check cooperative cancellation before each agent
                if self._is_cancelled(task_id):
                    self._handle_cli_log("WARNING", f"⛔ Task {task_id} canceled before executing {agent_name} in {phase_name}")
                    return {'status': 'cancelled', 'agent': agent_name, 'phase': phase_number}
                
                try:
                    requested_model = phase_models[i] if i < len(phase_models) else None
                    requested_temperature = phase_temperatures[i] if i < len(phase_temperatures) else None
                    agent_cli = phase_clis[i] if i < len(phase_clis) else ('surecli' if phase_number == 1 else 'gemini')
                    if agent_name == 'io8_mcp_project' and agent_cli != 'gemini':
                        self._handle_cli_log("WARNING", "io8_mcp_project requires Gemini CLI; overriding to 'gemini'")
                        agent_cli = 'gemini'
                    
                    start_progress = int((i / len(agents)) * 100)
                    task_manager.update_task_progress(task_id, agent_name, start_progress)
                    
                    self._handle_cli_log("INFO", f"🤖 Executing {phase_name} agent {i+1}/{len(agents)}: {agent_name}")
                    agent_prompt = custom_prompts[agent_name] if (custom_prompts and agent_name in custom_prompts) else self.agent_manager.get_agent_prompt(agent_name)
                    
                    if not agent_prompt:
                        raise Exception(f"Agent {agent_name} missing prompt")
                    
                    agent_input = self._prepare_agent_input(user_prompt, context, agent_prompt, agent_name)
                    
                    self._handle_cli_log("INFO", f"📤 Sending prompt via {agent_cli} CLI for {agent_name}")
                    
                    # Execute agent based on CLI type
                    if agent_cli == 'llxprt':
                        if self._llxprt is None:
                            try:
                                from src.routes.bmad_api import llxprt_cli_client as _shared
                                self._llxprt = _shared
                                self._llxprt.set_log_callback(self._handle_cli_log)
                            except Exception as _e:
                                raise Exception(f"LLXPRT client unavailable: {_e}")
                        if requested_model:
                            try:
                                self._llxprt.switch_model(requested_model)
                                self._handle_cli_log("INFO", f"🎯 LLXPRT model set to {self._llxprt.get_model_info().get('model_name')}")
                            except Exception as _e:
                                self._handle_cli_log("WARNING", f"LLXPRT model switch failed: {_e}")
                        response = await self._llxprt.send_message(agent_input, agent_name=agent_name)
                    elif agent_cli == 'surecli':
                        if self._surecli is None:
                            try:
                                self._surecli = SureCliClient()
                                self._surecli.set_log_callback(self._handle_cli_log)
                            except Exception as _e:
                                raise Exception(f"SureCli client unavailable: {_e}")
                        response = await self._surecli.send_message(agent_input, agent_name=agent_name, temperature=requested_temperature)
                    else:
                        # Using Gemini
                        if requested_model:
                            try:
                                self._handle_cli_log("INFO", f"🎯 Gemini model set to {requested_model}")
                                self.gemini_client.switch_model(requested_model)
                            except Exception as _e:
                                self._handle_cli_log("WARNING", f"Gemini model switch failed: {_e}")
                        response = await self.gemini_client.send_message(
                            agent_input,
                            context={
                                "agent": agent_name,
                                "task_id": task_id,
                                "step": f"{i+1}/{len(agents)}",
                                "phase": phase_name,
                                "temperature": requested_temperature if requested_temperature is not None else ''
                            },
                            agent_name=agent_name,
                            temperature=requested_temperature
                        )
                    
                    if response is None or (isinstance(response, str) and response.strip() == ""):
                        raise Exception("Empty response from selected CLI")
                    
                    # Execute agent tasks
                    task_result = await self._execute_agent_tasks(task_id, agent_name, user_prompt)

                    # Special handling: developer must complete all tasks before advancing.
                    if agent_name in ['developer', 'io8developer']:
                        attempt = 1
                        max_attempts = 5
                        while ((task_result or {}).get('status') != 'success') and attempt <= max_attempts:
                            tr_status = (task_result or {}).get('status', '')
                            error_msg = (task_result or {}).get('error', '')
                            remaining = (task_result or {}).get('remaining_subtasks', None)
                            validation_issues = (task_result or {}).get('validation_issues', [])
                            self._handle_cli_log("INFO", f"🔁 Developer retry {attempt}/{max_attempts} — status={tr_status or 'unknown'}, remaining_subtasks={remaining if remaining is not None else ''}, validation_issues={len(validation_issues)}")

                            # If quota exhaustion, try rotation and then STOP to let UI resume
                            if self._is_quota_exhaustion_error(error_msg or ''):
                                if not self._handle_quota_exhaustion(agent_name, error_msg or '', context):
                                    return {
                                        'status': 'failed',
                                        'error': f'{agent_name} failed due to quota exhaustion: {error_msg}',
                                        'agent': agent_name,
                                        'phase': phase_number,
                                        'remaining_subtasks': remaining if remaining is not None else ''
                                    }
                                # Key rotated: stop developer run here; UI will resume with new key
                                return {
                                    'status': 'failed',
                                    'error': 'quota_exhausted_rotated',
                                    'agent': agent_name,
                                    'phase': phase_number,
                                    'remaining_subtasks': remaining if remaining is not None else ''
                                }

                            # Retry developer tasks (no quota exhaustion)
                            task_result = await self._execute_agent_tasks(task_id, agent_name, user_prompt)
                            attempt += 1

                        # After retries, if not success, stop and surface details
                        if (task_result or {}).get('status') != 'success':
                            tr_status = (task_result or {}).get('status', '')
                            error_msg = (task_result or {}).get('error', '')
                            remaining = (task_result or {}).get('remaining_subtasks', None)
                            return {
                                'status': 'failed',
                                'error': f'developer {tr_status or "failed"}: {error_msg or "Pending tasks remain"}',
                                'agent': agent_name,
                                'phase': phase_number,
                                'remaining_subtasks': remaining if remaining is not None else ''
                            }

                    else:
                        # Non-developer: Treat any non-success status as a stop condition (do not advance)
                        tr_status = (task_result or {}).get('status', '')
                        if tr_status != 'success':
                            error_msg = task_result.get('error', '')
                            remaining = task_result.get('remaining_subtasks', None)
                            if self._is_quota_exhaustion_error(error_msg):
                                if not self._handle_quota_exhaustion(agent_name, error_msg, context):
                                    return {
                                        'status': 'failed',
                                        'error': f'{agent_name} failed due to quota exhaustion: {error_msg}',
                                        'agent': agent_name,
                                        'phase': phase_number,
                                        'remaining_subtasks': remaining if remaining is not None else ''
                                    }
                            return {
                                'status': 'failed',
                                'error': f'{agent_name} {tr_status or "failed"}: {error_msg or "Agent did not complete successfully"}',
                                'agent': agent_name,
                                'phase': phase_number,
                                'remaining_subtasks': remaining if remaining is not None else ''
                            }
                    
                    output_file = await self._save_agent_output(task_id, agent_name, response)
                    self._handle_cli_log("INFO", f"✅ {agent_name} completed successfully in {phase_name}")
                    self._handle_cli_log("INFO", f"💾 Output saved to: {os.path.basename(output_file)}")
                    context[f'{agent_name}_output'] = response
                    context[f'{agent_name}_file'] = output_file
                    
                    # Update memory progress
                    try:
                        completed = [a for a in agents[:i+1]]
                        remaining = [a for a in agents[i+1:]]
                        self.task_manager.update_latest_memory_progress(task_id, completed, remaining)
                    except Exception:
                        pass
                    
                    end_progress = int(((i + 1) / len(agents)) * 100)
                    task_manager.update_task_progress(task_id, agent_name, end_progress)
                    
                except Exception as e:
                    self._handle_cli_log("ERROR", f"Error executing {phase_name} agent {agent_name}: {str(e)}")
                    return {'status': 'failed', 'agent': agent_name, 'phase': phase_number, 'error': str(e)}
            
            return {'status': 'completed', 'phase': phase_number, 'message': f'{phase_name} completed successfully'}
            
        except Exception as e:
            self._handle_cli_log("ERROR", f"Error in {phase_name} execution: {str(e)}")
            return {'status': 'failed', 'phase': phase_number, 'error': str(e)} 