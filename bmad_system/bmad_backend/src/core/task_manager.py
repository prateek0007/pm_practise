"""
Task Manager Module for BMAD System

This module manages the lifecycle of tasks, including creation, status tracking,
pausing, resuming, and persistence. It interacts with the SQLite database for
state management.
"""

import json
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, asdict
from src.models.user import db
from src.models.task import Task
from src.utils.logger import get_logger
from sqlalchemy import text

logger = get_logger(__name__)

class TaskStatus(Enum):
    RECEIVED = "received"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class TaskState:
    """Represents the current state of a task"""
    current_task_id: str
    completed_tasks: List[str]
    agent_sequence_index: int
    debug_attempts: int
    current_agent: str
    progress_percentage: float
    context: Dict[str, Any]

class TaskManager:
    """Manages task lifecycle and state persistence"""
    
    def __init__(self):
        self.output_directory = "/tmp/bmad_output"
        os.makedirs(self.output_directory, exist_ok=True)
        # Ensure DB schema has required columns without full migrations (SQLite-safe)
        try:
            engine = db.engine
            with engine.connect() as conn:
                try:
                    result = conn.execute(text("PRAGMA table_info(tasks)"))
                    cols = [row[1] for row in result]
                    if 'workflow_id' not in cols:
                        conn.execute(text("ALTER TABLE tasks ADD COLUMN workflow_id VARCHAR(36)"))
                    if 'memory_json' not in cols:
                        conn.execute(text("ALTER TABLE tasks ADD COLUMN memory_json TEXT"))
                except Exception:
                    # Ignore if PRAGMA not supported or table missing; created elsewhere
                    pass
        except Exception:
            # DB might not be initialized yet; ignore
            pass
    
    def create_task(self, prompt: str, files: Optional[List[str]] = None, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Create a new task and return the task ID
        
        Args:
            prompt: The user's input prompt
            files: List of uploaded files
            metadata: Additional task metadata (custom workflow, agent prompts, etc.)
            
        Returns:
            Task ID string
        """
        task_id = str(uuid.uuid4())

        # Check if there's an existing task with the same workflow_id and prompt that is still in progress
        # This prevents multiple task creations for the same workflow execution
        try:
            if isinstance(metadata, dict) and metadata.get('workflow_id'):
                wf_id = metadata.get('workflow_id')
                # Normalize the prompt for comparison
                normalized_prompt = (prompt or '').strip()
                
                # Check if this is an io8 workflow
                is_io8_workflow = False
                try:
                    from src.models.workflow import Workflow
                    workflow = Workflow.query.get(wf_id)
                    if workflow and 'io8' in workflow.name.lower():
                        is_io8_workflow = True
                        logger.info(f"🔍 Task reuse check - Identified as io8 workflow: {workflow.name}")
                except Exception as e:
                    logger.warning(f"Could not determine workflow type: {e}")
                
                # For io8 workflows, we want to reuse tasks even if they failed or were cancelled, 
                # as they're part of the same workflow execution
                if is_io8_workflow:
                    logger.info(f"🔍 Task reuse check - Looking for existing tasks with workflow_id: {wf_id}, prompt: '{normalized_prompt}'")
                    
                    # Only consider tasks created within the last 5 minutes to avoid reusing very old tasks
                    five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
                    
                    # First, get all tasks with the same workflow_id within the time window
                    all_workflow_tasks = (
                        db.session.query(Task)
                        .filter(Task.workflow_id == wf_id)
                        .filter(Task.created_at >= five_minutes_ago)
                        .order_by(Task.created_at.desc())
                        .all()
                    )
                    
                    logger.info(f"🔍 Task reuse check - Found {len(all_workflow_tasks)} tasks with workflow_id {wf_id} within last 5 minutes")
                    
                    # Filter tasks with matching prompts
                    matching_tasks = []
                    for task in all_workflow_tasks:
                        task_prompt = (task.user_prompt or '').strip()
                        logger.info(f"🔍 Task reuse check - Comparing prompts: '{normalized_prompt}' vs '{task_prompt}' for task {task.id}")
                        if task_prompt == normalized_prompt:
                            matching_tasks.append(task)
                    
                    # Log debugging information
                    logger.info(f"🔍 Task reuse check - Found {len(matching_tasks)} tasks with matching prompts")
                    for task in matching_tasks:
                        logger.info(f"🔍 Task reuse check - Matching task {task.id} with status: {task.status}, created_at: {task.created_at}")
                    
                    if matching_tasks:
                        # Use the most recent task instead of creating a new one
                        existing_task_id = matching_tasks[0].id
                        logger.info(f"🔄 Found existing task {existing_task_id} for workflow_id {wf_id} with same prompt, reusing it")
                        
                        # For io8 workflows, we want to ensure that only the third call (the correct one) proceeds
                        # Check if this is a duplicate call that should be ignored
                        existing_task = matching_tasks[0]
                        if existing_task.status in ['received', 'in_progress']:
                            logger.info(f"⏭️ Ignoring duplicate call for task {existing_task_id} which is already in progress")
                            # Return the existing task ID but indicate this call should be ignored
                            return f"IGNORED:{str(existing_task_id)}"
                        else:
                            return str(existing_task_id)
                    else:
                        logger.info(f"🔍 Task reuse check - No matching tasks found, creating new task")
                else:
                    # For non-io8 workflows, use the original logic
                    # Find tasks with same workflow_id and prompt that are still in progress
                    existing_tasks = (
                        db.session.query(Task)
                        .filter(Task.workflow_id == wf_id)
                        .filter(Task.user_prompt == prompt)
                        .filter(Task.status.in_(['received', 'in_progress']))
                        .order_by(Task.created_at.desc())
                        .all()
                    )
                    
                    if existing_tasks:
                        # Use the most recent in-progress task instead of creating a new one
                        existing_task_id = existing_tasks[0].id
                        logger.info(f"🔄 Found existing in-progress task {existing_task_id} for workflow_id {wf_id} with same prompt, reusing it")
                        return str(existing_task_id)
            else:
                logger.info("🔍 Task reuse check - No workflow_id provided, skipping task reuse check")
        except Exception as e:
            logger.warning(f"Error checking for existing tasks: {e}")

        # Reuse existing project directory for same workflow (planning → execution)
        reuse_project_path: Optional[str] = None
        try:
            if isinstance(metadata, dict) and metadata.get('workflow_id'):
                wf_id = metadata.get('workflow_id')
                logger.info(f"🔍 Looking for existing project path for workflow_id: {wf_id}")
                # Find most recent task with same workflow_id
                prev = (
                    db.session.query(Task)
                    .filter(Task.workflow_id == wf_id)
                    .order_by(Task.created_at.desc())
                    .first()
                )
                if prev:
                    logger.info(f"📋 Found previous task {prev.id} with workflow_id {wf_id}")
                    logger.info(f"📁 Previous project_path: {prev.project_path}")
                    logger.info(f"📝 Previous prompt: '{prev.user_prompt}'")
                    logger.info(f"📝 Current prompt: '{prompt}'")
                    
                # Handle SQLAlchemy column types properly
                if prev is not None:
                    # Convert SQLAlchemy columns to strings safely
                    prev_project_path = str(getattr(prev, 'project_path')) if getattr(prev, 'project_path') else None
                    prev_user_prompt = str(getattr(prev, 'user_prompt')) if getattr(prev, 'user_prompt') else ''
                    
                    if prev_project_path and os.path.exists(prev_project_path):
                        # For io8 workflows, always reuse the folder for subworkflows
                        try:
                            if prev_user_prompt.strip().lower() == (prompt or '').strip().lower():
                                reuse_project_path = prev_project_path
                                logger.info(f"✅ Reusing project path due to matching prompts: {reuse_project_path}")
                            else:
                                # Check if this is a subworkflow continuation (different task ID but same workflow)
                                # For io8 workflows, reuse even with different prompts if same workflow
                                try:
                                    from src.models.workflow import Workflow
                                    workflow = Workflow.query.get(wf_id)
                                    if workflow and 'io8' in workflow.name.lower():
                                        reuse_project_path = prev_project_path
                                        logger.info(f"✅ Reusing project path for io8 subworkflow: {reuse_project_path}")
                                    else:
                                        logger.info(f"⏭️ Not reusing path - different prompts and not io8 workflow")
                                except Exception as wf_err:
                                    logger.warning(f"Could not check workflow type: {wf_err}")
                                    # Fallback to prompt comparison
                                    reuse_project_path = prev_project_path
                                    logger.info(f"✅ Reusing project path as fallback: {reuse_project_path}")
                        except Exception:
                            reuse_project_path = prev_project_path
                            logger.info(f"✅ Reusing project path (exception fallback): {reuse_project_path}")
                    else:
                        if not prev_project_path:
                            logger.info(f"ℹ️ Previous task has no project_path")
                        elif not os.path.exists(prev_project_path):
                            logger.info(f"ℹ️ Previous project path does not exist: {prev_project_path}")
                else:
                    logger.info(f"ℹ️ No previous task found for workflow_id {wf_id}")
        except Exception as e:
            logger.warning(f"Error checking for reusable project path: {e}")
            reuse_project_path = None

        # Create project directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Robustly derive first three words slug from prompt: alphanumeric only, single underscores
        try:
            import re
            words = re.findall(r"[A-Za-z0-9]+", str(prompt))
            if words:
                first_three = words[:3]
                first_three_words = "_".join(w.lower() for w in first_three)
            else:
                first_three_words = "project"
        except Exception:
            first_three_words = "project"
        project_name = f"{first_three_words}_{timestamp}"
        # If there is already a task created recently with same prompt & timestamp second,
        # prefer to reuse that folder path to avoid double creation under subworkflow calls.
        if reuse_project_path:
            project_path = reuse_project_path
            # Ensure exists
            os.makedirs(project_path, exist_ok=True)
        else:
            project_path = os.path.join(self.output_directory, project_name)
            try:
                # Look back for existing folders with same project_name
                if os.path.exists(self.output_directory):
                    candidates = [d for d in os.listdir(self.output_directory) if d == project_name]
                    if candidates:
                        project_path = os.path.join(self.output_directory, project_name)
            except Exception:
                pass
            os.makedirs(project_path, exist_ok=True)
        
        # Create enhanced directory structure only when not reusing an existing project
        if not reuse_project_path:
            self._create_project_directory_structure(project_path)
        else:
            # Even when reusing a project, ensure the UNIVERSAL_FIELD_ANALYSIS_CONTEXT.md file exists
            self._ensure_universal_field_analysis_context(project_path)
        
        # Create .io8project directory
        io8_project_path = os.path.join(project_path, ".io8project")
        os.makedirs(io8_project_path, exist_ok=True)
        
        # Determine initial current agent based on workflow type
        initial_current_agent = "architect"  # Default for legacy workflows
        try:
            if isinstance(metadata, dict) and metadata.get('workflow_id'):
                from src.models.workflow import Workflow
                workflow = Workflow.query.get(metadata['workflow_id'])
                if workflow and workflow.name in ['io8 Default', 'io8 Plan', 'io8plan']:
                    initial_current_agent = "io8project_builder"  # First agent in io8 workflows
                elif workflow and workflow.name == 'End-to-End Plan + Execute':
                    initial_current_agent = "directory_structure"  # First agent in End-to-End workflow
        except Exception as e:
            logger.warning(f"Could not determine initial current agent: {e}")
        
        # Initialize task state
        initial_state = TaskState(
            current_task_id=task_id,
            completed_tasks=[],
            agent_sequence_index=0,
            debug_attempts=0,
            current_agent=initial_current_agent,
            progress_percentage=0.0,
            context={
                "uploaded_files": files or [],
                "project_path": project_path,
                "io8_project_path": io8_project_path
            }
        )
        
        # Initialize memory: seed with first user prompt entry
        initial_memory = {
            "history": [
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "prompt": prompt,
                    "workflow_id": metadata.get('workflow_id') if isinstance(metadata, dict) else None,
                    "agents_progress": {"completed": [], "remaining": []},
                    "agents_details": {}
                }
            ]
        }
        
        # Save to database
        task_data = {
            'id': task_id,
            'user_prompt': prompt,
            'status': TaskStatus.RECEIVED.value,
            'project_path': project_path,
            'current_agent': initial_current_agent,
            'progress_percentage': 0,
            'state_json': json.dumps(asdict(initial_state)),
            'memory_json': json.dumps(initial_memory)
        }
        
        # Add workflow_id if present in metadata
        if isinstance(metadata, dict) and metadata.get('workflow_id'):
            task_data['workflow_id'] = metadata.get('workflow_id')
        
        task = Task(**task_data)
        
        db.session.add(task)
        db.session.commit()
        
        # Save state to project directory
        self._save_state_to_project(project_path, initial_state)
        
        return task_id
    
    def _create_project_directory_structure(self, project_path: str):
        # Creates standard project directory structure with .io8project and .sureai folders
        """Create the complete project directory structure"""
        directories = [
            os.path.join(project_path, ".io8project"),
            os.path.join(project_path, ".sureai"),
            os.path.join(project_path, ".sureai", "uploads"),
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
        
        # Copy the UNIVERSAL_FIELD_ANALYSIS_CONTEXT.md file to the task's .sureai directory
        self._copy_universal_field_analysis_context(project_path)
    
    def _ensure_universal_field_analysis_context(self, project_path: str):
        """Ensure the UNIVERSAL_FIELD_ANALYSIS_CONTEXT.md file exists in the project's .sureai directory"""
        dest_context_file = os.path.join(project_path, ".sureai", "UNIVERSAL_FIELD_ANALYSIS_CONTEXT.md")
        
        # Check if the file already exists and contains real content
        if os.path.exists(dest_context_file):
            try:
                with open(dest_context_file, 'r', encoding='utf-8') as f:
                    content = f.read(200)  # Read only first 200 chars to check
                    if "placeholder file" not in content:
                        # File exists and contains real content, no need to copy
                        return
            except Exception as read_err:
                logger.warning(f"Could not verify existing file content: {read_err}")
        
        # File doesn't exist or is a placeholder, copy it
        self._copy_universal_field_analysis_context(project_path)
    
    def _copy_universal_field_analysis_context(self, project_path: str):
        """Copy the UNIVERSAL_FIELD_ANALYSIS_CONTEXT.md file to the task's .sureai directory"""
        # This is required by the FLF agent to reference the context guide
        try:
            dest_context_file = os.path.join(project_path, ".sureai", "UNIVERSAL_FIELD_ANALYSIS_CONTEXT.md")
            
            # In Docker container, the source file should be at a known location
            # No need to search multiple paths - use the correct source path directly
            source_context_file = None
            
            # According to user feedback, we know exactly where the file will be in Docker
            # It will be under .sureai directory of the newly created folder under bmad_output
            # So we can directly copy from the source location to the destination
            # First check the Docker container path
            docker_source_path = "/app/.sureai/UNIVERSAL_FIELD_ANALYSIS_CONTEXT.md"
            # Also check the development environment path
            workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
            dev_source_path = os.path.join(workspace_root, ".sureai", "UNIVERSAL_FIELD_ANALYSIS_CONTEXT.md")
            
            # Check if the source file exists in either location
            source_context_file = None
            if os.path.exists(docker_source_path):
                source_context_file = docker_source_path
                logger.info(f"Found UNIVERSAL_FIELD_ANALYSIS_CONTEXT.md at known Docker location: {docker_source_path}")
            elif os.path.exists(dev_source_path):
                source_context_file = dev_source_path
                logger.info(f"Found UNIVERSAL_FIELD_ANALYSIS_CONTEXT.md at development location: {dev_source_path}")
            else:
                # Try to find the file in the current workspace
                current_file_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                workspace_source_path = os.path.join(current_file_path, "..", ".sureai", "UNIVERSAL_FIELD_ANALYSIS_CONTEXT.md")
                workspace_source_path = os.path.abspath(workspace_source_path)
                if os.path.exists(workspace_source_path):
                    source_context_file = workspace_source_path
                    logger.info(f"Found UNIVERSAL_FIELD_ANALYSIS_CONTEXT.md at workspace location: {workspace_source_path}")
                else:
                    logger.warning(f"UNIVERSAL_FIELD_ANALYSIS_CONTEXT.md not found at any expected location. Docker: {docker_source_path}, Dev: {dev_source_path}, Workspace: {workspace_source_path}")
            
            # Copy the file if found
            if source_context_file and os.path.exists(source_context_file):
                import shutil
                shutil.copy2(source_context_file, dest_context_file)
                logger.info(f"Successfully copied UNIVERSAL_FIELD_ANALYSIS_CONTEXT.md from {source_context_file} to {dest_context_file}")
                
                # Verify the copied file is not a placeholder
                try:
                    with open(dest_context_file, 'r', encoding='utf-8') as f:
                        content = f.read(200)  # Read only first 200 chars to check
                        if "placeholder file" in content.lower():
                            logger.warning(f"Warning: Copied file appears to be a placeholder: {dest_context_file}")
                        else:
                            logger.info(f"Verified copied file contains real content: {dest_context_file}")
                except Exception as read_err:
                    logger.warning(f"Could not verify copied file content: {read_err}")
            else:
                logger.error("UNIVERSAL_FIELD_ANALYSIS_CONTEXT.md not found in expected locations")
                
                # Create an empty file as a fallback so the agent doesn't fail
                logger.warning("Creating empty placeholder file as fallback")
                with open(dest_context_file, 'w') as f:
                    f.write("# Universal Field Analysis Context Guide\n\nThis is a placeholder file. The actual context guide was not found during task initialization.\n")
                logger.info(f"Created placeholder file at {dest_context_file}")
        except Exception as e:
            logger.error(f"Error copying UNIVERSAL_FIELD_ANALYSIS_CONTEXT.md: {e}")
            # Create an empty file as a fallback so the agent doesn't fail
            try:
                dest_context_file = os.path.join(project_path, ".sureai", "UNIVERSAL_FIELD_ANALYSIS_CONTEXT.md")
                with open(dest_context_file, 'w') as f:
                    f.write("# Universal Field Analysis Context Guide\n\nThis is a placeholder file. An error occurred during file copying: " + str(e) + "\n")
                logger.info(f"Created error placeholder file at {dest_context_file}")
            except Exception as fallback_err:
                logger.error(f"Failed to create fallback file: {fallback_err}")
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task information by ID"""
        task = Task.query.get(task_id)
        if task:
            return task.to_dict()
        return None
    
    def update_task_status(self, task_id: str, status: TaskStatus, 
                          current_agent: Optional[str] = None, progress: Optional[float] = None,
                          error_message: Optional[str] = None) -> bool:
        """Update task status and related information"""
        task = Task.query.get(task_id)
        if not task:
            return False
        
        task.status = status.value
        task.updated_at = datetime.utcnow()
        
        if current_agent:
            task.current_agent = current_agent
        if progress is not None:
            task.progress_percentage = int(progress)
        if error_message:
            task.error_message = error_message
        
        db.session.commit()
        return True
    
    def update_task_progress(self, task_id: str, current_agent: str, progress: float) -> bool:
        """Update task progress and current agent"""
        task = Task.query.get(task_id)
        if not task:
            return False
        
        task.current_agent = current_agent
        task.progress_percentage = int(progress)
        task.updated_at = datetime.utcnow()
        
        db.session.commit()
        return True
    
    def pause_task(self, task_id: str) -> bool:
        """Pause a running task"""
        return self.update_task_status(task_id, TaskStatus.PAUSED)
    
    def resume_task(self, task_id: str) -> bool:
        """Resume a paused task"""
        return self.update_task_status(task_id, TaskStatus.IN_PROGRESS)
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a task"""
        return self.update_task_status(task_id, TaskStatus.CANCELLED)
    
    def get_task_state(self, task_id: str) -> Optional[TaskState]:
        """Get the current state of a task"""
        task = Task.query.get(task_id)
        if not task or not task.state_json:
            return None
        
        try:
            state_dict = json.loads(task.state_json)
            return TaskState(**state_dict)
        except (json.JSONDecodeError, TypeError):
            return None
    
    def update_task_state(self, task_id: str, state: TaskState) -> bool:
        """Update the task state"""
        task = Task.query.get(task_id)
        if not task:
            return False
        
        task.state_json = json.dumps(asdict(state))
        task.current_agent = state.current_agent
        task.progress_percentage = int(state.progress_percentage)
        task.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Also save to project directory
        if task.project_path:
            self._save_state_to_project(task.project_path, state)
        
        return True
    
    def ensure_project_directory(self, task_id: str, prompt: str) -> Optional[str]:
        """Ensure an existing task has a project directory. Create if missing.
        Returns absolute project path or None on failure.
        """
        try:
            from src.models.task import Task as TaskModel
            task = TaskModel.query.get(task_id)
            if not task:
                return None
            # If exists and present on disk, return
            if task.project_path and os.path.exists(task.project_path):
                return task.project_path
            # If task has a recorded project_path but the directory is missing,
            # recreate the SAME path (do NOT mint a new timestamped folder)
            if task.project_path and not os.path.exists(task.project_path):
                project_path = task.project_path
                os.makedirs(project_path, exist_ok=True)
                # Create structure and state folder
                self._create_project_directory_structure(project_path)
                # Ensure the UNIVERSAL_FIELD_ANALYSIS_CONTEXT.md file exists
                self._ensure_universal_field_analysis_context(project_path)
                io8_project_path = os.path.join(project_path, ".io8project")
                os.makedirs(io8_project_path, exist_ok=True)
                # Persist minimal state if available
                try:
                    state = self.get_task_state(task_id)
                    if state:
                        self._save_state_to_project(project_path, state)
                except Exception:
                    pass
                return project_path
            # No recorded project_path: create new directory similar to create_task naming
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            try:
                import re
                words = re.findall(r"[A-Za-z0-9]+", str(prompt))
                first_three_words = "_".join([w.lower() for w in words[:3]]) if words else "project"
            except Exception:
                first_three_words = "project"
            project_name = f"{first_three_words}_{timestamp}"
            project_path = os.path.join(self.output_directory, project_name)
            os.makedirs(project_path, exist_ok=True)
            # Create structure and state folder
            self._create_project_directory_structure(project_path)
            # Ensure the UNIVERSAL_FIELD_ANALYSIS_CONTEXT.md file exists
            self._ensure_universal_field_analysis_context(project_path)
            io8_project_path = os.path.join(project_path, ".io8project")
            os.makedirs(io8_project_path, exist_ok=True)
            # Update DB
            task.project_path = project_path
            db.session.commit()
            # Persist minimal state if available
            try:
                state = self.get_task_state(task_id)
                if state:
                    self._save_state_to_project(project_path, state)
            except Exception:
                pass
            return project_path
        except Exception:
            return None
    
    def _save_state_to_project(self, project_path: str, state: TaskState):
        # Persists task state to .state.json file in project directory for recovery
        """Save state to .state.json in project directory"""
        state_file = os.path.join(project_path, ".io8project", ".state.json")
        with open(state_file, 'w') as f:
            json.dump(asdict(state), f, indent=2)
    
    def load_state_from_project(self, project_path: str) -> Optional[TaskState]:
        # Loads task state from .state.json file in project directory for recovery
        """Load state from .state.json in project directory"""
        state_file = os.path.join(project_path, ".io8project", ".state.json")
        if not os.path.exists(state_file):
            return None
        
        try:
            with open(state_file, 'r') as f:
                state_dict = json.load(f)
            return TaskState(**state_dict)
        except (json.JSONDecodeError, FileNotFoundError, TypeError):
            return None
    
    def list_tasks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List all tasks with pagination"""
        tasks = Task.query.order_by(Task.created_at.desc()).limit(limit).all()
        return [task.to_dict() for task in tasks]
    
    def get_active_tasks(self) -> List[Dict[str, Any]]:
        """Get all active (in-progress) tasks"""
        tasks = Task.query.filter(
            Task.status.in_([TaskStatus.IN_PROGRESS.value, TaskStatus.RECEIVED.value])
        ).all()
        return [task.to_dict() for task in tasks]
    
    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """Get all tasks"""
        tasks = Task.query.order_by(Task.created_at.desc()).all()
        return [task.to_dict() for task in tasks]
    
    def get_task_output_directory(self, task_id: str) -> Optional[str]:
        """Get the output directory for a task"""
        task = Task.query.get(task_id)
        if task and task.project_path:
            return task.project_path
        return None
    
    # ----- Memory helpers -----
    def get_task_memory(self, task_id: str) -> Dict[str, Any]:
        # Retrieves task memory from database including history and agent progress
        task = Task.query.get(task_id)
        if not task:
            return {"history": []}
        try:
            if task.memory_json:
                return json.loads(task.memory_json)
        except Exception:
            pass
        return {"history": []}
    
    def append_memory_entry(self, task_id: str, prompt: str, workflow_id: Optional[str], agents_completed: List[str], agents_remaining: List[str]) -> bool:
        # Adds new memory entry to task history with agent progress tracking
        task = Task.query.get(task_id)
        if not task:
            return False
        mem = self.get_task_memory(task_id)
        mem.setdefault("history", []).append({
            "timestamp": datetime.utcnow().isoformat(),
            "prompt": prompt,
            "workflow_id": workflow_id,
            "agents_progress": {"completed": agents_completed, "remaining": agents_remaining},
            "agents_details": {}
        })
        task.memory_json = json.dumps(mem)
        task.updated_at = datetime.utcnow()
        db.session.commit()
        return True
    
    def update_latest_memory_progress(self, task_id: str, agents_completed: List[str], agents_remaining: List[str]) -> bool:
        # Updates the latest memory entry with current agent progress status
        task = Task.query.get(task_id)
        if not task:
            return False
        mem = self.get_task_memory(task_id)
        history = mem.setdefault("history", [])
        if not history:
            return False
        history[-1]["agents_progress"] = {"completed": agents_completed, "remaining": agents_remaining}
        task.memory_json = json.dumps(mem)
        task.updated_at = datetime.utcnow()
        db.session.commit()
        return True
    
    def update_agent_artifacts(self, task_id: str, agent_name: str, files_created: List[str]) -> bool:
        # Updates latest history with per-agent files and computes in-progress file hint
        """Update latest history with per-agent files and compute in-progress file hint."""
        task = Task.query.get(task_id)
        if not task:
            return False
        mem = self.get_task_memory(task_id)
        history = mem.setdefault("history", [])
        if not history:
            return False
        entry = history[-1]
        agents_details = entry.setdefault("agents_details", {})
        details = agents_details.setdefault(agent_name, {})
        
        # Filter artifacts by agent-known outputs to avoid cross-attribution
        agent_outputs: Dict[str, List[str]] = {
            "io8codermaster": [".sureai/.io8codermaster_breakdown.md", ".sureai/.io8codermaster_plan.md"],
            "analyst": [".sureai/analysis_document.md", ".sureai/requirements_document.md"],
            "architect": [".sureai/architecture_document.md", ".sureai/tech_stack_document.md"],
            "pm": [".sureai/prd_document.md", ".sureai/project_plan.md"],
            "sm": [".sureai/tasks_list.md", ".sureai/sprint_plan.md"],
            "developer": [".sureai/tasks_list.md", "backend/", "frontend/"],
            "devops": ["deployment_config.yml", "Dockerfile.backend", "Dockerfile.frontend", "docker-compose.yml", "nginx.conf"],
            "tester": [".sureai/test-list.md"],
            "directory_structure": ["frontend", "backend", ".io8project", ".sureai"],
        }
        allowed = agent_outputs.get(agent_name, [])
        filtered: List[str] = []
        for p in files_created or []:
            norm = p.replace('\\', '/')
            # keep exact path if it matches or is under allowed dir prefix
            if any(norm == a or norm.startswith(a) for a in allowed) or not allowed:
                filtered.append(norm)
        
        details["files_created"] = filtered
        details["last_updated"] = datetime.utcnow().isoformat()
        
        # Heuristic to choose in-progress file
        in_progress = None
        # Prefer .md under .sureai
        md_files = [
            f for f in filtered
            if (f.endswith('.md') and (f.startswith('.sureai/') or '/.sureai/' in f))
        ]
        if agent_name in ["developer", "sm"]:
            # Prefer tasks_list.md
            for f in filtered:
                if f.endswith('tasks_list.md'):
                    in_progress = f
                    break
        if agent_name == "tester" and not in_progress:
            for f in filtered:
                if f.endswith('test-list.md'):
                    in_progress = f
                    break
        if not in_progress and md_files:
            in_progress = md_files[0]
        # Avoid directories as in-progress file (no dot suggests directory)
        if in_progress and ("/" not in in_progress and "." not in in_progress):
            in_progress = None
        details["in_progress_file"] = in_progress
        agents_details[agent_name] = details
        entry["agents_details"] = agents_details
        task.memory_json = json.dumps(mem)
        task.updated_at = datetime.utcnow()
        db.session.commit()
        return True
    
    def update_latest_memory_error(self, task_id: str, agent_name: str, code: str, message: str) -> bool:
        # Records an error for the latest run in memory for debugging and recovery
        """Record an error for the latest run in memory."""
        task = Task.query.get(task_id)
        if not task:
            return False
        mem = self.get_task_memory(task_id)
        history = mem.setdefault("history", [])
        if not history:
            return False
        entry = history[-1]
        entry["error"] = {
            "timestamp": datetime.utcnow().isoformat(),
            "agent": agent_name,
            "code": code,
            "message": message
        }
        task.memory_json = json.dumps(mem)
        task.updated_at = datetime.utcnow()
        db.session.commit()
        return True