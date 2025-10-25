"""
BMAD API Routes Module

This module defines the API endpoints for the BMAD system, including task management,
file operations, system configuration, agent management, and real-time updates.

NEW FEATURE: Resume Workflow Capability
- When a workflow fails due to API quota issues, users can now resume from the last agent
- The resume functionality preserves memory and context from previous agents
- Users can optionally provide a new prompt when resuming
- The system automatically skips completed agents and continues from where it left off
- Memory JSON is passed to maintain context about what agents have already completed
"""

import os
import asyncio
from flask import Blueprint, request, jsonify, send_file
from flask_cors import cross_origin
from werkzeug.utils import secure_filename
from typing import Dict, Any, List
import json
import uuid
from datetime import datetime
from pathlib import Path
import threading

from src.core.task_manager import TaskManager, TaskStatus
from src.core.orchestrator import Orchestrator
from src.core.file_parser import FileParser
from src.mcp_handlers.file_io_handler import FileIOHandler
from src.utils.logger import get_logger, get_task_logs
from src.utils.token_meter import TokenMeter
from src.agents.agent_manager import AgentManager
from src.llm_clients.gemini_cli_client import GeminiCLIClient
from src.llm_clients.llxprt_cli_client import LlxprtCLIClient
from src.llm_clients.sure_cli_client import SureCliClient
from src.workflows.master_workflow import MasterWorkflow
from src.models.workflow import Workflow
from src.models.user import db
from src.models.mcp import MCPServer
from sqlalchemy import text
import subprocess
import shutil
import time

logger = get_logger(__name__)

# Create Blueprint
bmad_bp = Blueprint('bmad', __name__)

# Initialize components
task_manager = TaskManager()
orchestrator = Orchestrator()
file_parser = FileParser()
file_handler = FileIOHandler()
token_meter = TokenMeter()
agent_manager = AgentManager()

# Initialize CLI clients
gemini_cli_client = GeminiCLIClient()
llxprt_cli_client = LlxprtCLIClient()
sure_cli_client = SureCliClient()
master_workflow = MasterWorkflow(agent_manager, gemini_cli_client, token_meter)
# ---------- Zrok helpers ----------
from src.utils.zrok_utils import zrok_configured as _zrok_configured, ensure_zrok_enabled as _ensure_zrok_enabled, zrok_share_http as _zrok_share_http

# ---- Lightweight schema guard for SQLite (adds tasks.workflow_id if missing) ----
def _ensure_tasks_schema():
	try:
		engine = db.engine
		with engine.connect() as conn:
			try:
				result = conn.execute(text("PRAGMA table_info(tasks)"))
				cols = [row[1] for row in result]
				if 'workflow_id' not in cols:
					conn.execute(text("ALTER TABLE tasks ADD COLUMN workflow_id VARCHAR(36)"))
					logger.info("Added missing column tasks.workflow_id")
				# New: memory_json column
				if 'memory_json' not in cols:
					conn.execute(text("ALTER TABLE tasks ADD COLUMN memory_json TEXT"))
					logger.info("Added missing column tasks.memory_json")
			except Exception as e:
				logger.warning(f"Schema guard failed to inspect/add column: {e}")
	except Exception as e:
		logger.warning(f"Schema guard could not acquire engine: {e}")

# ---- Lightweight schema guard for SQLite (adds workflows.agent_models if missing) ----
def _ensure_workflows_schema():
	try:
		engine = db.engine
		with engine.connect() as conn:
			try:
				result = conn.execute(text("PRAGMA table_info(workflows)"))
				cols = [row[1] for row in result]
				if 'agent_models' not in cols:
					conn.execute(text("ALTER TABLE workflows ADD COLUMN agent_models TEXT"))
					logger.info("Added missing column workflows.agent_models")
				# New: add temperatures column
				if 'agent_temperatures' not in cols:
					conn.execute(text("ALTER TABLE workflows ADD COLUMN agent_temperatures TEXT"))
					logger.info("Added missing column workflows.agent_temperatures")
				# New: add agent_clis column
				if 'agent_clis' not in cols:
					conn.execute(text("ALTER TABLE workflows ADD COLUMN agent_clis TEXT"))
					logger.info("Added missing column workflows.agent_clis")
			except Exception as e:
				logger.warning(f"Workflows schema guard failed: {e}")
	except Exception as e:
		logger.warning(f"Workflows schema guard could not acquire engine: {e}")

# Configuration
UPLOAD_FOLDER = '/tmp/bmad_uploads'
ALLOWED_EXTENSIONS = {
	'txt', 'md', 'json', 'csv', 'docx', 'pdf', 'xlsx', 'pptx',
	'png', 'jpg', 'jpeg', 'gif', 'webp', 'mp4', 'webm'
}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
	"""Check if file extension is allowed"""
	return '.' in filename and \
			   filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Health Check
@bmad_bp.route('/api/health', methods=['GET'])
@cross_origin()
def health_check():
	"""System health check"""
	try:
		# Check component status
		components = {
			'task_manager': 'operational',
			'orchestrator': 'operational',
			'file_parser': 'operational',
			'token_meter': 'operational',
			'agent_manager': f"{len(agent_manager.get_agent_names())} agents loaded",
			'gemini_cli': 'operational' if gemini_cli_client.get_model_info()['api_key_configured'] else 'not configured',
			'llxprt': 'operational',
			'surecli': 'operational' if sure_cli_client.get_model_info()['api_key_configured'] else 'not configured'
		}
		
		return jsonify({
			'status': 'healthy',
			'message': 'BMAD system is running',
			'components': components
		})
		
	except Exception as e:
		logger.error(f"Health check failed: {e}")
		return jsonify({
			'status': 'unhealthy',
			'message': str(e)
		}), 500

# Task Management
@bmad_bp.route('/api/tasks', methods=['POST'])
@cross_origin()
def create_task():
	"""Create a new task with master workflow"""
	try:
		_ensure_tasks_schema()
		_ensure_workflows_schema()
		data = request.get_json()
		
		if not data:
			return jsonify({'error': 'No data provided'}), 400
		
		# Accept both 'user_prompt' and 'prompt' field names
		user_prompt = data.get('user_prompt') or data.get('prompt')
		if not user_prompt:
			return jsonify({'error': 'user_prompt or prompt is required'}), 400
		
		# Optional parameters - accept both naming conventions
		custom_workflow = data.get('custom_workflow') or data.get('workflow_sequence') or []
		custom_agent_prompts = data.get('custom_agent_prompts') or data.get('agent_specific_prompts') or {}
		workflow_id = data.get('workflow_id')  # New: support workflow selection by ID
		per_agent_models = data.get('agent_models') or []
		per_agent_temperatures = data.get('agent_temperatures') or []
		agent_clis = data.get('agent_clis', [])
		phase = data.get('phase')
		
		# Removed base project cloning parameters for io8 default; workflow should run directly
		base_project = None
		base_project_url = None
		base_project_branch = None
		
		# Debug logging for workflow sequence
		logger.info(f"🔍 API Debug - Received custom_workflow: {custom_workflow}")
		logger.info(f"🔍 API Debug - Received workflow_id: {workflow_id}")
		logger.info(f"🔍 API Debug - Received custom_agent_prompts keys: {list(custom_agent_prompts.keys()) if custom_agent_prompts else 'None'}")
		
		# If workflow_id is provided, get the workflow sequence from the database
		agent_clis_from_wf = []  # Initialize to avoid undefined variable error
		if workflow_id:
			workflow = Workflow.query.get(workflow_id)
			if workflow and workflow.is_active:
				wf_dict = workflow.to_dict()
				custom_workflow = wf_dict['agent_sequence']
				per_agent_models = wf_dict.get('agent_models', [])
				per_agent_temperatures = wf_dict.get('agent_temperatures', [])
				agent_clis_from_wf = wf_dict.get('agent_clis', [])
				logger.info(f"🔍 API Debug - Resolved workflow_id {workflow_id} to sequence: {custom_workflow}")
			else:
				return jsonify({'error': 'Invalid workflow ID'}), 400
		
		# Final debug logging
		logger.info(f"🔍 API Debug - Final custom_workflow to be passed: {custom_workflow}")
		logger.info(f"🔍 API Debug - Final custom_workflow type: {type(custom_workflow)}")
		logger.info(f"🔍 API Debug - Final custom_workflow length: {len(custom_workflow) if isinstance(custom_workflow, list) else 'N/A'}")
		
		# Optional: per-agent CLI selection (gemini | llxprt)
		agent_clis = data.get('agent_clis') or []
		# Prefer clis from workflow if selected
		if not agent_clis:
			try:
				agent_clis = agent_clis_from_wf  # may be undefined
			except Exception:
				agent_clis = []
		
		# Create task
		md = {'workflow_id': workflow_id} if workflow_id else {}
		if phase:
			md['phase'] = phase
		task_id = task_manager.create_task(user_prompt, metadata=md if md else None)
		
		# Check if this is an ignored task (for io8 workflows)
		if isinstance(task_id, str) and task_id.startswith("IGNORED:"):
			original_task_id = task_id.split(":", 1)[1]
			logger.info(f"⏭️ Ignoring duplicate call for task {original_task_id} which is already in progress")
			return jsonify({
				'task_id': original_task_id,
				'status': 'ignored',
				'message': 'Duplicate call ignored - task already in progress'
			}), 200
		
		# If workflow_id provided, set it early to avoid stale sequence usage
		if workflow_id:
			try:
				from src.models.task import Task as TaskModel
				from src.models.user import db as _db
				t = TaskModel.query.get(task_id)
				if t and hasattr(t, 'workflow_id'):
					t.workflow_id = workflow_id
					_db.session.commit()
			except Exception as _e:
				logger.warning(f"Deferred workflow_id set failed for {task_id}: {_e}")
		
		# Start token tracking
		token_meter.start_build_timer(task_id)
		
		# Clear previous CLI logs for new task
		master_workflow.clear_cli_logs()
		
		# Get the Flask app instance from the current request context
		from flask import current_app
		app = current_app._get_current_object()
		
		# Start master workflow execution in a separate thread
		import threading
		
		def run_workflow(flask_app, task_id, user_prompt, custom_workflow, custom_agent_prompts, per_agent_models, per_agent_temperatures):
			"""Run workflow in a separate thread with proper Flask app context"""
			import asyncio
			
			# Create new event loop for this thread
			loop = asyncio.new_event_loop()
			asyncio.set_event_loop(loop)
			
			try:
				# Create Flask app context for the thread
				with flask_app.app_context():
					try:
						# Execute the workflow
						result = loop.run_until_complete(
							master_workflow.execute_workflow(
								task_id, user_prompt, custom_workflow, custom_agent_prompts, per_agent_models, per_agent_temperatures, agent_clis, workflow_id
							)
						)
						
						# Update task with workflow result
						from src.models.task import Task
						from src.models.user import db
                        
						task = Task.query.get(task_id)
						if task:
							if result.get('status') in ['completed', 'success']:
								task.status = 'completed'
								logger.info(f"Task {task_id} completed successfully")
							else:
								task.status = 'failed'
								logger.warning(f"Task {task_id} failed: {result.get('error', 'Unknown error')}")
                            
							db.session.commit()
							logger.info(f"Task {task_id} status updated to: {task.status}")
						else:
							logger.error(f"Task {task_id} not found in database")
                            
					except Exception as e:
						logger.error(f"Workflow execution error for task {task_id}: {e}")
                        
						# Update task status to failed
						try:
							from src.models.task import Task
							from src.models.user import db
                            
							task = Task.query.get(task_id)
							if task:
								task.status = 'failed'
								db.session.commit()
								logger.info(f"Task {task_id} status set to failed due to exception")
							else:
								logger.error(f"Task {task_id} not found when trying to set failed status")
						except Exception as db_error:
							logger.error(f"Failed to update task {task_id} status to failed: {db_error}")
                            
			except Exception as context_error:
				logger.error(f"Error in workflow thread context for task {task_id}: {context_error}")
			finally:
				# Clean up the event loop
				try:
					loop.close()
				except Exception as loop_error:
					logger.error(f"Error closing event loop for task {task_id}: {loop_error}")
        
		# Start the thread with the Flask app instance
		thread = threading.Thread(
			target=run_workflow,
			args=(app, task_id, user_prompt, custom_workflow, custom_agent_prompts, per_agent_models, per_agent_temperatures),
			name=f"workflow-{task_id}"
		)
		thread.daemon = True  # Thread will die when main thread dies
		thread.start()
        
		logger.info(f"Created new task with master workflow: {task_id}")
        
		return jsonify({
			'task_id': task_id,
			'status': 'received',
			'message': 'Task created successfully and master workflow initiated'
		}), 201
        
	except Exception as e:
		logger.error(f"Error creating task: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/tasks/<task_id>/memory', methods=['GET'])
@cross_origin()
def get_task_memory(task_id):
	try:
		_ensure_tasks_schema()
		mem = task_manager.get_task_memory(task_id)
		return jsonify(mem)
	except Exception as e:
		logger.error(f"Error getting memory for task {task_id}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/tasks/<task_id>/memory', methods=['PUT'])
@cross_origin()
def update_task_memory(task_id):
	try:
		_ensure_tasks_schema()
		data = request.get_json() or {}
		if 'history' not in data or not isinstance(data['history'], list):
			return jsonify({'error': 'history array required'}), 400
		from src.models.task import Task as TaskModel
		t = TaskModel.query.get(task_id)
		if not t:
			return jsonify({'error': 'Task not found'}), 404
		
		# Preserve existing memory structure instead of overwriting
		existing_memory = {}
		if t.memory_json:
			try:
				existing_memory = json.loads(t.memory_json)
			except Exception:
				existing_memory = {}
		
		# Update only the history while preserving other memory fields
		existing_memory['history'] = data['history']
		t.memory_json = json.dumps(existing_memory)
		db.session.commit()
		
		logger.info(f"Memory updated for task {task_id}: {len(data['history'])} history entries")
		return jsonify({'message': 'Memory updated'})
	except Exception as e:
		logger.error(f"Error updating memory for task {task_id}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/tasks', methods=['GET'])
@cross_origin()
def get_tasks():
	"""Get all tasks"""
	try:
		_ensure_tasks_schema()
		tasks = task_manager.get_all_tasks()
		return jsonify({'tasks': tasks})
		
	except Exception as e:
		logger.error(f"Error getting tasks: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/tasks/<task_id>', methods=['GET'])
@cross_origin()
def get_task(task_id):
	"""Get details for a specific task with accurate current agent and progress"""
	try:
		data = _compute_monitor_data(task_id)
		if isinstance(data, tuple):
			# Already a (response, status) tuple
			return data
		return jsonify(data)
	except Exception as e:
		logger.error(f"Error getting task {task_id}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/tasks/<task_id>/cli-logs', methods=['GET'])
@cross_origin()
def get_task_cli_logs(task_id):
	"""Get CLI logs for a specific task"""
	try:
		# Get CLI logs from master workflow
		cli_logs = master_workflow.get_cli_logs()
		
		# Filter logs for this task using the task_id field we tag in logs
		task_logs = [log for log in cli_logs if log.get('task_id') == task_id]
		
		# Optional pagination and ordering
		try:
			limit = int(request.args.get('limit', '200'))
			offset = int(request.args.get('offset', '0'))
			after_seq = int(request.args.get('after_seq', '0'))
			if limit < 0:
				limit = 0
			if offset < 0:
				offset = 0
			if after_seq < 0:
				after_seq = 0
		except Exception:
			limit = 200
			offset = 0
			after_seq = 0
		
		# Ensure chronological order by timestamp/seq if present
		try:
			task_logs.sort(key=lambda x: (x.get('seq', 0), x.get('timestamp', '')))
		except Exception:
			pass
		# Apply incremental filtering if requested
		if after_seq:
			task_logs = [l for l in task_logs if int(l.get('seq') or 0) > after_seq]
		total_logs = len(task_logs)
		sliced = task_logs[offset: offset + limit] if limit else task_logs[offset:]
		
		return jsonify({
			'task_id': task_id,
			'cli_logs': sliced,
			'total_logs': total_logs,
			'offset': offset,
			'limit': limit,
			'has_more': (offset + len(sliced)) < total_logs,
			'last_seq': (sliced[-1]['seq'] if sliced and 'seq' in sliced[-1] else after_seq)
		})
		
	except Exception as e:
		logger.error(f"Error getting CLI logs for task {task_id}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/tasks/<task_id>/monitor', methods=['GET'])
@cross_origin()
def get_task_monitor_data(task_id):
	"""Get comprehensive task monitoring data including logs and progress"""
	try:
		data = _compute_monitor_data(task_id)
		if isinstance(data, tuple):
			return data
		return jsonify(data)
	except Exception as e:
		logger.error(f"Error getting monitor data for task {task_id}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

# ---- Git utilities ----
def _run_cmd(cmd: list[str], cwd: str | None = None, env: dict | None = None, timeout: int = 120) -> tuple[int, str, str]:
	proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
	try:
		out, err = proc.communicate(timeout=timeout)
	except subprocess.TimeoutExpired:
		proc.kill()
		out, err = proc.communicate()
	return proc.returncode, out or '', err or ''

def _safe_repo_url_with_creds(repo_url: str, username: str, password: str) -> str:
	# Inject credentials into http(s) URL: http://user:pass@host/path
	if repo_url.startswith('http://') or repo_url.startswith('https://'):
		scheme, rest = repo_url.split('://', 1)
		return f"{scheme}://{username}:{password}@{rest}"
	return repo_url

@bmad_bp.route('/api/tasks/<task_id>/gemini/single', methods=['POST'])
@cross_origin()
def gemini_single_prompt(task_id: str):
	"""Execute a single Gemini CLI prompt directly in the task's project directory.

	This bypasses the master workflow and agent prompts entirely. It simply runs the
	provided prompt using the Gemini CLI with the task's project directory as the
	working directory, allowing the model to create or modify files there.

	Request JSON:
	- prompt (required): The single prompt to execute
	- agent_name (optional): For timeout profile; defaults to 'developer'
	"""
	try:
		data = request.get_json() or {}
		prompt = data.get('prompt') or data.get('user_prompt')
		if not prompt:
			return jsonify({'error': 'prompt or user_prompt is required'}), 400

		project_dir = task_manager.get_task_output_directory(task_id)
		if not project_dir:
			return jsonify({'error': 'Project folder not found for task'}), 404
		os.makedirs(project_dir, exist_ok=True)

		agent_name = (data.get('agent_name') or 'developer')

		def _run_single():
			try:
				# Echo prompt to task logs
				logger.info(f"[Gemini CLI] ▶ Single-prompt input (first 500 chars) =>\n{(prompt or '')[:500]}", extra={'task_id': task_id})
				logger.info(f"[Gemini CLI] ▶ Running single prompt for task {task_id} in {project_dir}", extra={'task_id': task_id})
				
				# Use direct gemini CLI command with -p flag (arg mode) for MCP compatibility
				import subprocess
				import os
				
				# Build the exact command that works manually
				cmd = ['gemini', '--yolo', '-p', prompt]
				logger.info(f"[Gemini CLI] 🔧 Executing: gemini --yolo -p <prompt>", extra={'task_id': task_id})
				
				# Set environment
				env = dict(os.environ)
				# Ensure CLI can find config (MCP settings) inside container
				env.setdefault('HOME', '/root')
				env.setdefault('XDG_CONFIG_HOME', '/root/.config')
				if gemini_cli_client.api_key_manager.get_current_key():
					env['GEMINI_API_KEY'] = gemini_cli_client.api_key_manager.get_current_key()
				elif os.getenv('GEMINI_API_KEY'):
					env['GEMINI_API_KEY'] = os.getenv('GEMINI_API_KEY')
				
				# Execute command
				result = subprocess.run(
					cmd,
					cwd=project_dir,
					env=env,
					capture_output=True,
					text=True,
					timeout=300
				)
				
				if result.returncode == 0:
					response_text = result.stdout or result.stderr or "OK"
					logger.info(f"[Gemini CLI] ✅ Single prompt completed for task {task_id}", extra={'task_id': task_id})
				else:
					response_text = f"Error: {result.stderr or 'Unknown error'}"
					logger.error(f"[Gemini CLI] ❌ Single prompt failed for task {task_id}: {result.stderr}", extra={'task_id': task_id})
				
				# Log response to task logs
				preview = (response_text or '')[:800]
				logger.info(f"[Gemini CLI] 📝 Single-prompt response (first 800 chars) =>\n{preview}", extra={'task_id': task_id})
				
			except Exception as e:
				logger.error(f"[Gemini CLI] ❌ Single prompt error for task {task_id}: {e}", extra={'task_id': task_id})

		thread = threading.Thread(target=_run_single, name=f"gemini-single-{task_id}")
		thread.daemon = True
		thread.start()

		return jsonify({'message': 'Gemini single prompt started', 'task_id': task_id}), 202
	except Exception as e:
		logger.error(f"Error starting Gemini single prompt for task {task_id}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/tasks/<task_id>/git/commit', methods=['POST'])
@cross_origin()
def git_commit_task(task_id: str):
	"""Initialize repo if needed, add/commit/push to main for this task's project folder."""
	try:
		project_dir = task_manager.get_task_output_directory(task_id)
		if not project_dir or not os.path.exists(project_dir):
			return jsonify({'error': 'Project folder not found for task'}), 404
		data = request.get_json() or {}
		repo_url = data.get('repo_url')
		commit_message = data.get('commit_message') or 'first commit'
		username = data.get('username') or 'risadmin_prod'
		password = data.get('password') or 'adminprod1234'
		if not repo_url:
			return jsonify({'error': 'repo_url required'}), 400
		# Init repo if missing
		if not os.path.exists(os.path.join(project_dir, '.git')):
			code, out, err = _run_cmd(['git', 'init'], cwd=project_dir)
			if code != 0:
				return jsonify({'error': f'git init failed', 'stderr': err}), 500
		# Set default branch main
		_run_cmd(['git', 'checkout', '-B', 'main'], cwd=project_dir)
		# Set config
		_run_cmd(['git', 'config', 'user.name', 'user'], cwd=project_dir)
		_run_cmd(['git', 'config', 'user.email', 'user@gmail.com'], cwd=project_dir)
		# Add remote origin (replace if exists)
		_run_cmd(['git', 'remote', 'remove', 'origin'], cwd=project_dir)
		url_with_creds = _safe_repo_url_with_creds(repo_url, username, password)
		code, out, err = _run_cmd(['git', 'remote', 'add', 'origin', url_with_creds], cwd=project_dir)
		if code != 0 and 'already exists' not in (err or '').lower():
			return jsonify({'error': 'git remote add failed', 'stderr': err}), 500
		# Add all and commit (only if staged changes exist)
		_run_cmd(['git', 'add', '.'], cwd=project_dir)
		code, out, err = _run_cmd(['git', 'diff', '--cached', '--quiet'], cwd=project_dir)
		if code != 0:
			_run_cmd(['git', 'commit', '-m', commit_message], cwd=project_dir)
		# Push to main
		code, out, err = _run_cmd(['git', 'push', '-u', 'origin', 'main'], cwd=project_dir)
		if code != 0:
			return jsonify({'error': 'git push failed', 'stderr': err}), 500
		return jsonify({'message': 'Commit and push successful'})
	except Exception as e:
		logger.error(f"Git commit error for task {task_id}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/tasks/<task_id>/git/clone-if-missing', methods=['POST'])
@cross_origin()
def git_clone_if_missing(task_id: str):
	"""Clone repo into the task's project folder if it's empty or missing code."""
	try:
		project_dir = task_manager.get_task_output_directory(task_id)
		if not project_dir:
			return jsonify({'error': 'Project folder not found for task'}), 404
		os.makedirs(project_dir, exist_ok=True)
		data = request.get_json() or {}
		repo_url = data.get('repo_url')
		username = data.get('username') or 'risadmin_prod'
		password = data.get('password') or 'adminprod1234'
		if not repo_url:
			return jsonify({'error': 'repo_url required'}), 400
		# If folder appears empty, clone
		has_entries = False
		try:
			for entry in os.scandir(project_dir):
				if entry.name not in ['.', '..']:
					has_entries = True
					break
		except Exception:
			has_entries = False
		if has_entries and os.path.exists(os.path.join(project_dir, '.git')):
			return jsonify({'message': 'Project already present'}), 200
		# Clone into temp and move contents in
		tmp_parent = os.path.dirname(project_dir.rstrip(os.sep)) or '/tmp'
		tmp_dir = os.path.join(tmp_parent, f'.clone_{task_id}')
		if os.path.exists(tmp_dir):
			shutil.rmtree(tmp_dir, ignore_errors=True)
		url_with_creds = _safe_repo_url_with_creds(repo_url, username, password)
		code, out, err = _run_cmd(['git', 'clone', url_with_creds, tmp_dir], cwd=tmp_parent, timeout=300)
		if code != 0:
			return jsonify({'error': 'git clone failed', 'stderr': err}), 500
		for entry in os.listdir(tmp_dir):
			src = os.path.join(tmp_dir, entry)
			dst = os.path.join(project_dir, entry)
			if os.path.exists(dst):
				continue
			shutil.move(src, dst)
		shutil.rmtree(tmp_dir, ignore_errors=True)
		return jsonify({'message': 'Clone successful'})
	except Exception as e:
		logger.error(f"Git clone error for task {task_id}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

def _compute_monitor_data(task_id: str):
	"""Compute monitor data used by both /tasks/<id> and /tasks/<id>/monitor"""
	# Get task details
	task = task_manager.get_task(task_id)
	if not task:
		return jsonify({'error': 'Task not found'}), 404

	# Handle both Task model objects and dictionaries
	if isinstance(task, dict):
		task_status = task.get('status', 'unknown')
		task_created_at = task.get('created_at')
		task_updated_at = task.get('updated_at')
		task_workflow_id = task.get('workflow_id')  # May not exist in older tasks
		task_current_agent = task.get('current_agent')
		task_progress_percentage = task.get('progress_percentage', 0)
	else:
		# Task model object
		task_status = task.status if hasattr(task, 'status') else 'unknown'
		task_created_at = task.created_at if hasattr(task, 'created_at') else None
		task_updated_at = task.updated_at if hasattr(task, 'updated_at') else None
		task_workflow_id = getattr(task, 'workflow_id', None)  # May not exist in older tasks
		task_current_agent = task.current_agent if hasattr(task, 'current_agent') else None
		task_progress_percentage = task.progress_percentage if hasattr(task, 'progress_percentage') else 0

	# Get CLI logs from master workflow
	cli_logs = master_workflow.get_cli_logs()
	# Filter logs for this specific task
	task_logs = [log for log in cli_logs if log.get('task_id') == task_id]
	current_agent_from_logs = None
	completed_agents = []

	# Extract current and completed agents from logs
	for log in task_logs:
		message = log.get('message', '').lower()
		if 'executing agent' in message:
			import re
			agent_match = re.search(r'executing agent \d+/\d+: (\w+)', message)
			if agent_match:
				current_agent_from_logs = agent_match.group(1)
		if 'completed successfully' in message and 'agent' in message:
			import re
			agent_match = re.search(r'(\w+) completed successfully', message)
			if agent_match:
				completed_agent = agent_match.group(1)
				if completed_agent not in completed_agents:
					completed_agents.append(completed_agent)

	# Check memory for previously completed agents (important for resumed workflows)
	try:
		memory = task_manager.get_task_memory(task_id)
		if memory and 'history' in memory and memory['history']:
			# Look at the latest memory entry for agent progress
			latest_entry = memory['history'][-1]
			if 'agents_progress' in latest_entry:
				memory_completed = latest_entry['agents_progress'].get('completed', [])
				# Add memory-based completed agents to the list
				for agent in memory_completed:
					if agent not in completed_agents:
						completed_agents.append(agent)
				logger.debug(f"Memory-based completed agents for task {task_id}: {memory_completed}")
	except Exception as e:
		logger.warning(f"Could not get memory for task {task_id}: {e}")

	# Prefer DB task fields updated by MasterWorkflow for status
	progress_data = {
		'current_agent': task_current_agent,
		'progress_percentage': task_progress_percentage
	}

	# Resolve workflow sequence
	workflow_sequence = []
	try:
		if task_workflow_id:
			from src.models.workflow import Workflow
			workflow = Workflow.query.get(task_workflow_id)
			if workflow:
				# Parse JSON stored agent_sequence into a Python list
				try:
					import json
					seq = workflow.agent_sequence
					if isinstance(seq, str):
						workflow_sequence = json.loads(seq)
					elif isinstance(seq, list):
						workflow_sequence = seq
					else:
						workflow_sequence = []
				except Exception:
					workflow_sequence = []
	except Exception as e:
		logger.warning(f"Could not get workflow sequence for task {task_id}: {e}")

	# If still empty, try to peek the TaskState context for any saved agent sequence
	if not workflow_sequence:
		try:
			state = task_manager.get_task_state(task_id)
			if state and isinstance(state.context, dict):
				seq = state.context.get('agent_sequence')
				if isinstance(seq, list) and seq:
					workflow_sequence = seq
		except Exception:
			pass

	# Fallback to default agent manager sequence when unknown/empty
	if not workflow_sequence:
		try:
			workflow_sequence = agent_manager.get_default_workflow_sequence()
		except Exception:
			workflow_sequence = []

	# Handle datetime conversion safely
	def safe_isoformat(dt):
		if dt is None:
			return None
		if isinstance(dt, str):
			return dt  # Already a string
		try:
			return dt.isoformat()
		except:
			return str(dt)

	# Calculate progress percentage based on completed agents and workflow sequence
	progress_percentage = progress_data.get('progress_percentage', 0)
	if workflow_sequence:
		completed_count = len(completed_agents) if completed_agents else 0
		total_agents = len(workflow_sequence)
		if total_agents > 0:
			# For resumed workflows, ensure we show the correct progress
			calculated_progress = int((completed_count / total_agents) * 100)
			progress_percentage = max(progress_percentage, calculated_progress)
			
			# Log progress calculation for debugging
			logger.debug(f"Progress calculation for task {task_id}: {completed_count}/{total_agents} = {calculated_progress}%, final: {progress_percentage}%")

	# Use the most accurate current agent
	current_agent = current_agent_from_logs or progress_data.get('current_agent')
	if not current_agent and workflow_sequence:
		completed_count = len(completed_agents) if completed_agents else 0
		if completed_count < len(workflow_sequence):
			current_agent = workflow_sequence[completed_count]
	
	# For resumed workflows, ensure current agent is set correctly
	if not current_agent and workflow_sequence and completed_agents:
		# Find the next agent after the last completed one
		for agent in workflow_sequence:
			if agent not in completed_agents:
				current_agent = agent
				break

	# Debug logging for resumed workflows
	if completed_agents and workflow_sequence:
		logger.debug(f"Monitor data for task {task_id}:")
		logger.debug(f"  - Workflow sequence: {workflow_sequence}")
		logger.debug(f"  - Completed agents: {completed_agents}")
		logger.debug(f"  - Current agent: {current_agent}")
		logger.debug(f"  - Progress: {progress_percentage}%")
	else:
		logger.debug(f"Monitor data for task {task_id}:")
		logger.debug(f"  - Workflow sequence: {workflow_sequence}")
		logger.debug(f"  - Completed agents: {completed_agents}")
		logger.debug(f"  - Current agent: {current_agent}")
		logger.debug(f"  - Progress: {progress_percentage}%")

	return {
		'task_id': task_id,
		'status': task_status,
		'progress_percentage': progress_percentage,
		'current_agent': current_agent,
		'workflow_sequence': workflow_sequence,
		'completed_agents': completed_agents,
		'cli_logs': task_logs,
		'total_logs': len(task_logs),
		'created_at': safe_isoformat(task_created_at),
		'updated_at': safe_isoformat(task_updated_at),
		# Project folder path for UI buttons (folder name display and git actions)
		'project_path': _resolve_project_dir(task_id),
		# Optional: surfaced deployed frontend URL if present
		'frontend_url': _read_deployed_frontend_url(task_id)
	}

def _read_deployed_frontend_url(task_id: str):
	"""Best-effort read of a previously recorded deployed frontend URL for a task.
	Looks for .sureai/deploy.json in the task's project output directory.
	"""
	try:
		project_dir = _resolve_project_dir(task_id)
		if not project_dir:
			return None
		deploy_path = os.path.join(project_dir, '.sureai', 'deploy.json')
		if os.path.exists(deploy_path):
			with open(deploy_path, 'r', encoding='utf-8') as f:
				data = json.load(f)
				return data.get('frontend_url')
	except Exception:
		pass
	return None

@bmad_bp.route('/api/tasks/<task_id>/pause', methods=['POST'])
@cross_origin()
def pause_task(task_id):
	"""Pause a running task"""
	try:
		success = task_manager.pause_task(task_id)
		
		if not success:
			return jsonify({'error': 'Task not found or cannot be paused'}), 404
		
		return jsonify({'message': 'Task paused successfully'})
		
	except Exception as e:
		logger.error(f"Error pausing task {task_id}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/tasks/<task_id>/resume', methods=['POST'])
@cross_origin()
def resume_task(task_id):
	"""Resume a paused task"""
	try:
		success = task_manager.resume_task(task_id)
		
		if not success:
			return jsonify({'error': 'Task not found or cannot be resumed'}), 404
		
		return jsonify({'message': 'Task resumed successfully'})
		
	except Exception as e:
		logger.error(f"Error resuming task {task_id}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/tasks/<task_id>/resume-workflow', methods=['POST'])
@cross_origin()
def resume_workflow_from_agent(task_id):
	"""
	Resume a workflow from a specific agent where it was interrupted due to API quota issues.
	This endpoint is designed for immediate execution and should be called directly,
	not through JobPro queue management. It handles:
	1. Cancelling any currently running workflow
	2. Resuming execution from the current agent
	3. Bypassing queue delays for immediate response
	
	This endpoint allows resuming from the last agent that was running when the API error occurred.
	"""
	try:
		_ensure_tasks_schema()
		data = request.get_json()
		if not data:
			return jsonify({'error': 'No data provided'}), 400

		# Accept optional agent-specific prompt overrides
		custom_agent_prompts = data.get('custom_agent_prompts') or data.get('agent_specific_prompts') or {}

		# Optional new prompt - if provided, use it; otherwise use the original prompt
		user_prompt = data.get('user_prompt') or data.get('prompt')
		
		# Get the task to check its current status and find the last agent
		task = task_manager.get_task(task_id)
		if not task:
			return jsonify({'error': 'Task not found'}), 404

		# Check if task can be resumed (should be failed due to API error)
		task_status = None
		if isinstance(task, dict):
			task_status = task.get('status')
		else:
			task_status = getattr(task, 'status', None)

		# Allow resuming from any status where there's a current agent
		# This enables resuming from in_progress, failed, paused, etc.
		if task_status not in ['failed', 'in_progress', 'paused', 'received']:
			return jsonify({'error': f'Task cannot be resumed from status: {task_status}. Cannot resume from this status.'}), 400

		# Get the current agent from the task or monitor data
		current_agent = None
		if isinstance(task, dict):
			current_agent = task.get('current_agent')
		else:
			current_agent = getattr(task, 'current_agent', None)

		# If no current agent found, try to get it from monitor data
		if not current_agent:
			try:
				monitor_data = _compute_monitor_data(task_id)
				# Some implementations may return (data, status). Normalize to dict.
				if isinstance(monitor_data, tuple) and len(monitor_data) > 0:
					monitor_data = monitor_data[0]
				if isinstance(monitor_data, dict):
					current_agent = monitor_data.get('current_agent')
			except Exception:
				pass

		# If still no current agent, try TaskState snapshot (more reliable than logs)
		if not current_agent:
			try:
				st = task_manager.get_task_state(task_id)
				if st and isinstance(st, object):
					# Prefer explicit resume hint saved earlier
					if isinstance(st.context, dict) and st.context.get('resume_current_agent'):
						current_agent = st.context.get('resume_current_agent')
					elif getattr(st, 'current_agent', None):
						current_agent = st.current_agent
			except Exception:
				pass

		# If still no current agent, try to determine from workflow sequence and completed agents
		if not current_agent:
			try:
				monitor_data = _compute_monitor_data(task_id)
				if isinstance(monitor_data, tuple) and len(monitor_data) > 0:
					monitor_data = monitor_data[0]
				if isinstance(monitor_data, dict):
					workflow_sequence = monitor_data.get('workflow_sequence', [])
					completed_agents = monitor_data.get('completed_agents', [])
					if workflow_sequence and completed_agents:
						# Find the next agent after the last completed one
						for agent in workflow_sequence:
							if agent not in completed_agents:
								current_agent = agent
								break
			except Exception:
				pass

		# Final fallback: infer from memory's latest remaining agents
		if not current_agent:
			try:
				mem = task_manager.get_task_memory(task_id)
				if mem and isinstance(mem, dict) and mem.get('history'):
					latest = mem['history'][-1] or {}
					remaining = ((latest.get('agents_progress') or {}).get('remaining')) or []
					if isinstance(remaining, list) and remaining:
						current_agent = remaining[0]
			except Exception:
				pass

		# If still no current agent, try to determine from workflow sequence and completed agents
		if not current_agent:
			try:
				monitor_data = _compute_monitor_data(task_id)
				if isinstance(monitor_data, tuple) and len(monitor_data) > 0:
					monitor_data = monitor_data[0]
				if isinstance(monitor_data, dict):
					workflow_sequence = monitor_data.get('workflow_sequence', [])
					completed_agents = monitor_data.get('completed_agents', [])
					if workflow_sequence and completed_agents:
						# Find the next agent after the last completed one
						for agent in workflow_sequence:
							if agent not in completed_agents:
								current_agent = agent
								break
			except Exception:
				pass

		if not current_agent:
			return jsonify({'error': 'Could not determine the current agent'}), 400

		# Get the original prompt if no new prompt provided
		if not user_prompt:
			if isinstance(task, dict):
				user_prompt = task.get('user_prompt') or task.get('prompt', '')
			else:
				user_prompt = getattr(task, 'user_prompt', '') or getattr(task, 'prompt', '')

		if not user_prompt:
			return jsonify({'error': 'No user prompt available for resume'}), 400

		# Get workflow sequence and configuration
		workflow_id = None
		if isinstance(task, dict):
			workflow_id = task.get('workflow_id')
		else:
			workflow_id = getattr(task, 'workflow_id', None)

		# Resolve workflow sequence strictly from DB/state/monitor (avoid falling back to manager default when resuming)
		workflow_sequence = []
		per_agent_models = []
		per_agent_temperatures = []
		per_agent_clis = []

		# Prefer persisted workflow_id
		if workflow_id:
			workflow = Workflow.query.get(workflow_id)
			if workflow and workflow.is_active:
				wf_dict = workflow.to_dict()
				workflow_sequence = wf_dict.get('agent_sequence', [])
				per_agent_models = wf_dict.get('agent_models', [])
				per_agent_temperatures = wf_dict.get('agent_temperatures', [])
				per_agent_clis = wf_dict.get('agent_clis', [])
				logger.info(f"🔍 Resume Debug - Resolved workflow_id {workflow_id} to sequence: {workflow_sequence}")
			else:
				return jsonify({'error': 'Invalid workflow ID'}), 400

		# If still empty, try TaskState context
		if not workflow_sequence:
			try:
				st = task_manager.get_task_state(task_id)
				if st and isinstance(st.context, dict):
					seq = st.context.get('agent_sequence') or []
					if isinstance(seq, list) and seq:
						workflow_sequence = seq
			except Exception:
				pass

		# If still empty, try monitor snapshot (does not change order)
		if not workflow_sequence:
			try:
				mon = _compute_monitor_data(task_id)
				if not isinstance(mon, tuple):
					seq = mon.get('workflow_sequence') or []
					if isinstance(seq, list) and seq:
						workflow_sequence = seq
			except Exception:
				pass

		if not workflow_sequence:
			return jsonify({'error': 'No workflow sequence available to resume'}), 400

		# Find the index of the current agent in the workflow sequence
		if current_agent not in workflow_sequence:
			return jsonify({'error': f'Agent {current_agent} not found in workflow sequence'}), 400

		start_index = workflow_sequence.index(current_agent)
		
		# Check if this is a sequential workflow (io8 Default or End-to-End Plan + Execute)
		is_sequential_workflow = False
		workflow_name = None
		try:
			if workflow_id:
				workflow = Workflow.query.get(workflow_id)
				if workflow:
					workflow_name = workflow.name
					if workflow_name in ['io8 Default', 'End-to-End Plan + Execute']:
						is_sequential_workflow = True
						logger.info(f"🔍 Resume Debug - Detected sequential workflow: {workflow_name}")
		except Exception as e:
			logger.warning(f"Could not check workflow type for resume: {e}")
		
		# Handle sequential workflows with subworkflows
		if is_sequential_workflow and workflow_name:
			# Define phase boundaries for sequential workflows
			if workflow_name in ['io8 Default', 'io8 Plan', 'io8plan']:
				planning_agents = ['io8_mcp_project', 'io8directory_structure', 'io8codermaster', 'io8analyst', 'io8architect', 'io8pm']
				development_agents = ['io8sm', 'io8developer']
				deployment_agents = ['io8devops']
			else:  # End-to-End Plan + Execute
				planning_agents = ['directory_structure', 'io8codermaster', 'analyst', 'architect', 'pm']
				execution_agents = ['sm', 'developer', 'devops']
			
			# Determine which phase the current agent is in
			if workflow_name in ['io8 Default', 'io8 Plan', 'io8plan']:
				# io8 workflows: 3 phases
				if current_agent in planning_agents:
					# Resume from current agent in planning phase
					phase_start_index = planning_agents.index(current_agent)
					resume_sequence = planning_agents[phase_start_index:] + development_agents + deployment_agents
					logger.info(f"🔍 Resume Debug - Resuming from planning phase agent {current_agent}")
				elif current_agent in development_agents:
					# Resume from current agent in development phase
					phase_start_index = development_agents.index(current_agent)
					resume_sequence = development_agents[phase_start_index:] + deployment_agents
					logger.info(f"🔍 Resume Debug - Resuming from development phase agent {current_agent}")
				elif current_agent in deployment_agents:
					# Resume from current agent in deployment phase
					phase_start_index = deployment_agents.index(current_agent)
					resume_sequence = deployment_agents[phase_start_index:]
					logger.info(f"🔍 Resume Debug - Resuming from deployment phase agent {current_agent}")
				else:
					# Fallback to linear resume if agent not found in defined phases
					resume_sequence = workflow_sequence[start_index:]
					logger.warning(f"🔍 Resume Debug - Agent {current_agent} not in defined phases, using linear resume")
			else:
				# Legacy workflows: 2 phases
				if current_agent in planning_agents:
					# Resume from current agent in planning phase
					phase_start_index = planning_agents.index(current_agent)
					resume_sequence = planning_agents[phase_start_index:] + execution_agents
					logger.info(f"🔍 Resume Debug - Resuming from planning phase agent {current_agent}")
				elif current_agent in execution_agents:
					# Resume from current agent in execution phase
					phase_start_index = execution_agents.index(current_agent)
					resume_sequence = execution_agents[phase_start_index:]
					logger.info(f"🔍 Resume Debug - Resuming from execution phase agent {current_agent}")
				else:
					# Fallback to linear resume if agent not found in defined phases
					resume_sequence = workflow_sequence[start_index:]
					logger.warning(f"🔍 Resume Debug - Agent {current_agent} not in defined phases, using linear resume")
			
			# Align models, temperatures, and CLIs based on the resume sequence
			# Map resume sequence back to original sequence indices for proper alignment
			resume_models = []
			resume_temperatures = []
			resume_clis = []
			
			for agent in resume_sequence:
				if agent in workflow_sequence:
					agent_index = workflow_sequence.index(agent)
					resume_models.append(per_agent_models[agent_index] if agent_index < len(per_agent_models) else None)
					resume_temperatures.append(per_agent_temperatures[agent_index] if agent_index < len(per_agent_temperatures) else None)
					resume_clis.append(per_agent_clis[agent_index] if agent_index < len(per_agent_clis) else 'gemini')
				else:
					resume_models.append(None)
					resume_temperatures.append(None)
					resume_clis.append('gemini')
		else:
			# Standard linear workflow resume
			resume_sequence = workflow_sequence[start_index:]
			resume_models = per_agent_models[start_index:] if per_agent_models else []
			resume_temperatures = per_agent_temperatures[start_index:] if per_agent_temperatures else []
			resume_clis = per_agent_clis[start_index:] if per_agent_clis else []

		# Align arrays to the resume sequence length
		if len(resume_models) < len(resume_sequence):
			resume_models = resume_models + [None] * (len(resume_sequence) - len(resume_models))
		if len(resume_temperatures) < len(resume_sequence):
			resume_temperatures = resume_temperatures + [None] * (len(resume_sequence) - len(resume_temperatures))
		if len(resume_clis) < len(resume_sequence):
			resume_clis = resume_clis + ['gemini'] * (len(resume_sequence) - len(resume_clis))

		logger.info(f"🔍 Resume Debug - Resuming from agent {current_agent} (index {start_index})")
		logger.info(f"🔍 Resume Debug - Resume sequence: {resume_sequence}")
		logger.info(f"🔍 Resume Debug - Original sequence: {workflow_sequence}")
		logger.info(f"🔍 Resume Debug - Is sequential workflow: {is_sequential_workflow}")
		if is_sequential_workflow:
			logger.info(f"🔍 Resume Debug - Workflow name: {workflow_name}")

		# Cancel any existing run for this task (cooperative)
		try:
			from src.workflows.master_workflow import master_workflow as _mw_singleton  # may not exist; handle via imported instance
		except Exception:
			_mw_singleton = None
		
		# Check if task is actually running before cancelling
		task_is_running = False
		try:
			if master_workflow and hasattr(master_workflow, '_running_tasks'):
				task_is_running = task_id in master_workflow._running_tasks
				logger.info(f"Task {task_id} running status: {task_is_running}")
		except Exception as e:
			logger.warning(f"Could not check task running status: {e}")
		
		# Only cancel if task is actually running
		if task_is_running:
			try:
				# Use our module level master_workflow instance
				if master_workflow and hasattr(master_workflow, 'request_cancel'):
					master_workflow.request_cancel(task_id)
					logger.info(f"Issued cancel signal for task {task_id} before resume")
					
					# Also try force cancel for immediate effect
					if hasattr(master_workflow, 'force_cancel_task'):
						master_workflow.force_cancel_task(task_id)
						logger.info(f"Force cancelled task {task_id} for immediate effect")
			except Exception as e:
				logger.warning(f"Error cancelling task {task_id}: {e}")
		else:
			logger.info(f"Task {task_id} not running, skipping cancellation")

		# Short grace period for prior loop to exit (only if we cancelled)
		if task_is_running:
			try:
				import time
				time.sleep(0.5)  # Grace period for cancellation
				
				# Check if task is still running after grace period
				if master_workflow and hasattr(master_workflow, '_running_tasks'):
					still_running = task_id in master_workflow._running_tasks
					if still_running:
						logger.warning(f"⚠️ Task {task_id} still running after grace period, proceeding anyway")
					else:
						logger.info(f"✅ Task {task_id} stopped successfully after cancellation")
			except Exception:
				pass

		# Get memory to pass to the workflow
		memory = {}
		try:
			memory = task_manager.get_task_memory(task_id)
		except Exception as e:
			logger.warning(f"Could not get memory for task {task_id}: {e}")

		# Clear any existing cancellation flags for this task before resuming
		try:
			if master_workflow and hasattr(master_workflow, 'clear_cancel'):
				master_workflow.clear_cancel(task_id)
				logger.info(f"🔍 Resume Debug - Cleared cancellation flags for task {task_id}")
		except Exception as e:
			logger.warning(f"Could not clear cancellation flags: {e}")
		
		# Update task status to in_progress
		task_manager.update_task_status(task_id, TaskStatus.IN_PROGRESS)
		# Calculate correct progress percentage based on completed agents
		completed_count = start_index  # start_index represents the number of completed agents
		progress_percentage = int((completed_count / len(workflow_sequence)) * 100)
		task_manager.update_task_progress(task_id, current_agent, progress_percentage)

		# Persist the detected current agent so sequential workflows can resume correctly
		try:
			from src.models.task import Task as TaskModel
			t = TaskModel.query.get(task_id)
			if t:
				t.current_agent = current_agent
				# Optional: store completed agents snapshot using latest monitor data if available
				try:
					mon = _compute_monitor_data(task_id)
					if isinstance(mon, tuple) and len(mon) > 0:
						mon = mon[0]
					completed_snapshot = []
					if isinstance(mon, dict):
						completed_snapshot = mon.get('completed_agents') or workflow_sequence[:start_index]
					else:
						completed_snapshot = workflow_sequence[:start_index]
					setattr(t, 'completed_agents', json.dumps(list(completed_snapshot)))
				except Exception:
					pass
				db.session.commit()
		except Exception as persist_err:
			logger.warning(f"Could not persist current_agent during resume: {persist_err}")
		
		logger.info(f"🔍 Resume Debug - Updated task progress: {completed_count}/{len(workflow_sequence)} = {progress_percentage}%")

		# Update memory with this resume attempt
		try:
			completed = workflow_sequence[:start_index]
			remaining = resume_sequence
			task_manager.append_memory_entry(task_id, user_prompt, workflow_id, completed, remaining)
			logger.info(f"🔍 Resume Debug - Memory updated: completed={completed}, remaining={remaining}")
		except Exception as e:
			logger.warning(f"Could not update memory for resume: {e}")

		# Run in background thread
		from flask import current_app
		app = current_app._get_current_object()

		import threading, asyncio

		def run_resume_workflow(flask_app, task_id, user_prompt, resume_sequence, custom_agent_prompts, resume_models, resume_temperatures, resume_clis):
			loop = asyncio.new_event_loop()
			asyncio.set_event_loop(loop)
			try:
				with flask_app.app_context():
					try:
						# 🔑 CRITICAL: Check if API key rotation is possible before resuming workflow
						logger.info(f"🔄 Resuming workflow for task {task_id} - checking API key availability")
						try:
							# Check if there are available keys for rotation
							available_keys_count = gemini_cli_client.api_key_manager.get_available_keys_count()
							total_keys_count = len(gemini_cli_client.api_key_manager.api_keys)
							
							logger.info(f"🔍 API Key Status: {available_keys_count} available out of {total_keys_count} total keys")
							
							# Note: We no longer check API quota before starting workflow
							# Quota exhaustion will be detected during actual API calls when Gemini returns 429 errors
							# This prevents false positives and ensures accurate quota detection
							logger.info(f"🚀 Starting resume workflow - API quota will be checked during actual calls")
							
							# Get current key status for logging
							current_status = gemini_cli_client.get_api_key_status()
							current_key = current_status.get('current_key')
							
							if current_key:
								# Get current key index for logging
								current_key_index = current_status.get('current_key_index', 0)
								current_key_id = f"key{current_key_index + 1}"
								logger.info(f"🔄 Resuming workflow with {current_key_id} (no rotation needed unless quota exhausted)")
								
								# Note: We no longer check API quota before starting workflow
								# Quota exhaustion will be detected during actual API calls when Gemini returns 429 errors
								# This prevents false positives and ensures accurate quota detection
								logger.info(f"🚀 Proceeding with resume workflow - API quota will be checked during actual calls")
							else:
								logger.warning(f"⚠️ No current API key found, proceeding without key verification")
						except Exception as rotation_error:
							logger.error(f"❌ API key rotation check failed during resume: {rotation_error}")
							# Mark task as failed since we can't determine key availability
							from src.models.task import Task as TaskModel
							t = TaskModel.query.get(task_id)
							if t:
								t.status = 'failed'
								t.error_message = f'API key rotation check failed: {rotation_error}. Manual intervention required.'
								db.session.commit()
								logger.info(f"✅ Task {task_id} marked as failed due to rotation check error")
							return

							# Stash arrays into TaskState for accurate routing (and a resume hint)
							try:
								st = task_manager.get_task_state(task_id)
								if st and isinstance(st.context, dict):
									st.context['agent_sequence'] = resume_sequence
									st.context['agent_models'] = resume_models
									st.context['agent_temperatures'] = resume_temperatures
									st.context['agent_clis'] = resume_clis
									st.context['resume_current_agent'] = resume_sequence[0] if isinstance(resume_sequence, list) and len(resume_sequence) > 0 else None
									task_manager.update_task_state(task_id, st)
							except Exception:
								pass

						# Execute the workflow from the resume point
						# Check if this is a sequential workflow that needs special handling
						is_sequential_workflow_resume = False
						try:
							if workflow_id:
								workflow = Workflow.query.get(workflow_id)
								if workflow and workflow.name in ['io8 Default', 'End-to-End Plan + Execute']:
									is_sequential_workflow_resume = True
						except Exception:
							pass
						
						if is_sequential_workflow_resume:
							# For sequential workflows, we need to use the sequential execution method
							# but we need to handle the resume context properly
							context = {'workflow_id': workflow_id}
							result = loop.run_until_complete(
								master_workflow._execute_workflow3_sequential(
									task_id, user_prompt, context, custom_agent_prompts, resume_models, resume_temperatures, resume_clis
								)
							)
						else:
							# Regular workflow execution for non-sequential workflows
							result = loop.run_until_complete(
								master_workflow.execute_workflow(
									task_id, user_prompt, resume_sequence, custom_agent_prompts, resume_models, resume_temperatures, resume_clis, workflow_id
								)
							)

						# Update task status based on result
						from src.models.task import Task as TaskModel
						t = TaskModel.query.get(task_id)
						if t:
							t.status = 'completed' if result.get('status') in ['completed', 'success'] else 'failed'
							db.session.commit()
					except Exception as e:
						logger.error(f"Resume workflow error for task {task_id}: {e}")
						try:
							from src.models.task import Task as TaskModel
							t = TaskModel.query.get(task_id)
							if t:
								t.status = 'failed'
								db.session.commit()
						except Exception as db_error:
							logger.error(f"Failed to set task {task_id} to failed after error: {db_error}")
			finally:
				try:
					loop.close()
				except Exception as loop_error:
					logger.error(f"Error closing event loop for task {task_id}: {loop_error}")

		thread = threading.Thread(
			target=run_resume_workflow,
			args=(app, task_id, user_prompt, resume_sequence, custom_agent_prompts, resume_models, resume_temperatures, resume_clis),
			name=f"workflow-resume-{task_id}"
		)
		thread.daemon = True
		thread.start()

		return jsonify({
			'task_id': task_id,
			'status': 'in_progress',
			'message': f'Workflow resumed successfully from agent {current_agent}',
			'resume_agent': current_agent,
			'resume_sequence': resume_sequence,
			'original_sequence': workflow_sequence,
			'workflow_sequence': workflow_sequence,  # Return full sequence for frontend display
			'completed_agents': workflow_sequence[:start_index]  # Return completed agents for frontend
		}), 202

	except Exception as e:
		logger.error(f"Error resuming workflow for task {task_id}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/tasks/<task_id>/cancel', methods=['POST'])
@cross_origin()
def cancel_task(task_id):
	"""Cancel a task"""
	try:
		success = task_manager.cancel_task(task_id)
		
		if not success:
			return jsonify({'error': 'Task not found or cannot be cancelled'}), 404
		
		return jsonify({'message': 'Task cancelled successfully'})
		
	except Exception as e:
		logger.error(f"Error cancelling task {task_id}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/tasks/<task_id>/reexecute', methods=['POST'])
@cross_origin()
def reexecute_task(task_id):
	"""
	Re-execute a workflow on an existing task in the same project folder.
	This endpoint is designed for immediate execution and should be called directly,
	not through JobPro queue management. It handles:
	1. Cancelling any currently running workflow
	2. Starting a new execution with the new prompt
	3. Bypassing queue delays for immediate response
	
	Accepts a new user prompt, an optional custom workflow sequence or workflow_id,
	and an optional starting agent to begin from within the sequence.
	"""
	try:
		_ensure_tasks_schema()
		data = request.get_json()
		if not data:
			return jsonify({'error': 'No data provided'}), 400
 
		# New prompt to drive modifications/fixes
		user_prompt = data.get('user_prompt') or data.get('prompt')
		if not user_prompt:
			return jsonify({'error': 'user_prompt or prompt is required'}), 400
 
		# Optional: custom workflow by id or explicit sequence
		custom_workflow = data.get('custom_workflow') or data.get('workflow_sequence') or []
		workflow_id = data.get('workflow_id')
		start_agent = data.get('start_agent')  # e.g., 'developer', 'tester'
		custom_agent_prompts = data.get('custom_agent_prompts') or data.get('agent_specific_prompts') or {}
		per_agent_models = data.get('agent_models') or []
		per_agent_temperatures = data.get('agent_temperatures') or []
		per_agent_clis = data.get('agent_clis') or []
 
		# Extract base project data for io8 Default workflow
		base_project = data.get('base_project')
		base_project_url = data.get('base_project_url')
		base_project_branch = data.get('base_project_branch', 'main')

		# Validate task exists
		task = task_manager.get_task(task_id)
		if not task:
			return jsonify({'error': 'Task not found'}), 404

		# 🔑 CRITICAL: Cancel any existing run for this task before starting re-execution
		try:
			from src.workflows.master_workflow import master_workflow as _mw_singleton
		except Exception:
			_mw_singleton = None
		
		# Check if task is actually running before cancelling
		task_is_running = False
		try:
			if master_workflow and hasattr(master_workflow, '_running_tasks'):
				task_is_running = task_id in master_workflow._running_tasks
				logger.info(f"Task {task_id} running status: {task_is_running}")
		except Exception as e:
			logger.warning(f"Could not check task running status: {e}")
		
		# Cancel if task is actually running
		if task_is_running:
			try:
				# Use our module level master_workflow instance
				if master_workflow and hasattr(master_workflow, 'request_cancel'):
					master_workflow.request_cancel(task_id)
					logger.info(f"Issued cancel signal for task {task_id} before re-execution")
					
					# Also try force cancel for immediate effect
					if hasattr(master_workflow, 'force_cancel_task'):
						master_workflow.force_cancel_task(task_id)
						logger.info(f"Force cancelled task {task_id} for immediate effect")
			except Exception as e:
				logger.warning(f"Error cancelling task {task_id}: {e}")
		else:
			logger.info(f"Task {task_id} not running, skipping cancellation")

		# Short grace period for prior loop to exit (only if we cancelled)
		if task_is_running:
			try:
				import time
				time.sleep(0.5)  # Grace period for cancellation
			except Exception:
				pass
 
		# If no workflow_id provided, fallback to the task's persisted workflow_id
		if not workflow_id:
			try:
				persisted_wf = task.get('workflow_id') if isinstance(task, dict) else getattr(task, 'workflow_id', None)
				if persisted_wf:
					workflow_id = persisted_wf
			except Exception:
				workflow_id = None
 
				# Resolve workflow sequence if workflow_id is provided
		if workflow_id and not custom_workflow:
			wf = Workflow.query.get(workflow_id)
			if wf and wf.is_active:
				wf_dict = wf.to_dict()
				custom_workflow = wf_dict.get('agent_sequence', [])
				per_agent_models = wf_dict.get('agent_models', [])
				per_agent_temperatures = wf_dict.get('agent_temperatures', [])
				per_agent_clis = wf_dict.get('agent_clis', [])
				logger.info(f"🔍 Re-execute Debug - Resolved workflow_id {workflow_id} to sequence: {custom_workflow}")
			else:
				return jsonify({'error': 'Invalid workflow ID'}), 400

		# Fallback to default sequence if none provided
		if not custom_workflow:
			try:
				custom_workflow = agent_manager.get_default_workflow_sequence()
				logger.info(f"🔍 Re-execute Debug - Using default workflow sequence: {custom_workflow}")
			except Exception:
				custom_workflow = []
				logger.warning(f"🔍 Re-execute Debug - Failed to get default workflow sequence, using empty list")
 
		# Align arrays to workflow length if they were not supplied
		if not isinstance(per_agent_models, list) or len(per_agent_models) != len(custom_workflow):
			per_agent_models = [None] * len(custom_workflow)
		if not isinstance(per_agent_temperatures, list) or len(per_agent_temperatures) != len(custom_workflow):
			per_agent_temperatures = [None] * len(custom_workflow)
		if not isinstance(per_agent_clis, list) or len(per_agent_clis) != len(custom_workflow):
			per_agent_clis = ['gemini'] * len(custom_workflow)
 
		# If a starting agent is provided and present in the sequence, slice from there
		if start_agent and isinstance(custom_workflow, list) and start_agent in custom_workflow:
			start_index = custom_workflow.index(start_agent)
			# Store the full sequence for frontend display
			full_workflow_sequence = custom_workflow.copy()
			# Slice only for execution
			custom_workflow = custom_workflow[start_index:]
			per_agent_models = per_agent_models[start_index:]
			per_agent_temperatures = per_agent_temperatures[start_index:]
			per_agent_clis = per_agent_clis[start_index:]
			logger.info(f"🔍 Re-execute Debug - Sliced workflow from {start_agent} (index {start_index}): {custom_workflow}")
		else:
			logger.info(f"🔍 Re-execute Debug - No start_agent slicing, using full sequence: {custom_workflow}")
			full_workflow_sequence = custom_workflow.copy()
 
		# Persist selected workflow on the existing task for accurate monitor sequence
		if workflow_id:
			try:
				from src.models.task import Task as TaskModel
				t = TaskModel.query.get(task_id)
				if t and hasattr(t, 'workflow_id'):
					setattr(t, 'workflow_id', workflow_id)
					db.session.commit()
			except Exception as _e:
				logger.warning(f"Could not persist workflow_id on task {task_id} during re-execution: {_e}")

		# Update memory with this new prompt and reset agent progress for this run
		try:
			completed = []
			remaining = list(custom_workflow) if isinstance(custom_workflow, list) else []
			task_manager.append_memory_entry(task_id, user_prompt, workflow_id, completed, remaining)
		except Exception:
			pass

		# Ensure project directory exists for this task before starting rerun
		try:
			proj = task_manager.ensure_project_directory(task_id, user_prompt)
			if proj:
				logger.info(f"🔧 Re-execute - Project directory ensured at: {proj}")
			else:
				logger.warning(f"⚠️ Re-execute - Failed to ensure project directory for task {task_id}")
		except Exception as _e:
			logger.warning(f"⚠️ Re-execute - Error ensuring project directory for {task_id}: {_e}")

		# Update task status to in_progress and reset progress
		task_manager.update_task_status(task_id, TaskStatus.IN_PROGRESS)
		task_manager.update_task_progress(task_id, custom_workflow[0] if custom_workflow else (task.get('current_agent') if isinstance(task, dict) else None) or 'unknown', 0)
 
		# Do NOT clear CLI logs here to preserve historical runs; frontend filters by task_id
 
		# Run in background thread similar to create_task
		from flask import current_app
		app = current_app._get_current_object()
 
		import threading, asyncio
 
		def run_rerun_workflow(flask_app, task_id, user_prompt, custom_workflow, custom_agent_prompts, per_agent_models, per_agent_temperatures, per_agent_clis, base_project_data):
			loop = asyncio.new_event_loop()
			asyncio.set_event_loop(loop)
			try:
				with flask_app.app_context():
					try:
						# 🔑 CRITICAL: Check if API key rotation is possible before re-executing workflow
						logger.info(f"🔄 Re-executing workflow for task {task_id} - checking API key availability")
						try:
							# Check if there are available keys for rotation
							available_keys_count = gemini_cli_client.api_key_manager.get_available_keys_count()
							total_keys_count = len(gemini_cli_client.api_key_manager.api_keys)
							
							logger.info(f"🔍 API Key Status: {available_keys_count} available out of {total_keys_count} total keys")
							
							# Note: We no longer check API quota before starting workflow
							# Quota exhaustion will be detected during actual API calls when Gemini returns 429 errors
							# This prevents false positives and ensures accurate quota detection
							logger.info(f"🚀 Starting reexecute workflow - API quota will be checked during actual calls")
							
							# Get current key status for logging
							current_status = gemini_cli_client.get_api_key_status()
							current_key = current_status.get('current_key')
							
							if current_key:
								# Get current key index for logging
								current_key_index = current_status.get('current_key_index', 0)
								current_key_id = f"key{current_key_index + 1}"
								logger.info(f"🔄 Re-executing workflow with {current_key_id} (no rotation needed unless quota exhausted)")
								
								# Note: We no longer check API quota before starting workflow
								# Quota exhaustion will be detected during actual API calls when Gemini returns 429 errors
								# This prevents false positives and ensures accurate quota detection
								logger.info(f"🚀 Proceeding with re-execute workflow - API quota will be checked during actual calls")
							else:
								logger.warning(f"⚠️ No current API key found, proceeding without key verification")
						except Exception as rotation_error:
							logger.error(f"❌ API key rotation check failed during re-execute: {rotation_error}")
							# Mark task as failed since we can't determine key availability
							from src.models.task import Task as TaskModel
							t = TaskModel.query.get(task_id)
							if t:
								t.status = 'failed'
								t.error_message = f'API key rotation check failed: {rotation_error}. Manual intervention required.'
								db.session.commit()
								logger.info(f"✅ Task {task_id} marked as failed due to rotation check error")
							return

						# Stash arrays into TaskState for accurate routing
						try:
							st = task_manager.get_task_state(task_id)
							if st and isinstance(st.context, dict):
								st.context['agent_sequence'] = custom_workflow
								st.context['agent_models'] = per_agent_models
								st.context['agent_temperatures'] = per_agent_temperatures
								st.context['agent_clis'] = per_agent_clis
								# Store base project data if provided
								if base_project:
									st.context['base_project'] = base_project
								if base_project_url:
									st.context['base_project_url'] = base_project_url
								if base_project_branch:
									st.context['base_project_branch'] = base_project_branch
								task_manager.update_task_state(task_id, st)
						except Exception:
							pass
						logger.info(f"🔍 Re-execute Debug - Calling master_workflow.execute_workflow with sequence: {custom_workflow}")
						result = loop.run_until_complete(
							master_workflow.execute_workflow(
								task_id, user_prompt, custom_workflow, custom_agent_prompts, per_agent_models, per_agent_temperatures, per_agent_clis, workflow_id
							)
						)
						# Update task status based on result
						from src.models.task import Task as TaskModel
						t = TaskModel.query.get(task_id)
						if t:
							t.status = 'completed' if result.get('status') in ['completed', 'success'] else 'failed'
							db.session.commit()
					except Exception as e:
						logger.error(f"Re-execution workflow error for task {task_id}: {e}")
						try:
							from src.models.task import Task as TaskModel
							t = TaskModel.query.get(task_id)
							if t:
								t.status = 'failed'
								db.session.commit()
						except Exception as db_error:
							logger.error(f"Failed to set task {task_id} to failed after error: {db_error}")
			finally:
				try:
					loop.close()
				except Exception as loop_error:
					logger.error(f"Error closing event loop for task {task_id}: {loop_error}")
 
		# Start the rerun thread with base project data
		base_project_data = {
			'base_project': base_project,
			'base_project_url': base_project_url,
			'base_project_branch': base_project_branch
		} if base_project else {}
		
		thread = threading.Thread(
			target=run_rerun_workflow,
			args=(app, task_id, user_prompt, custom_workflow, custom_agent_prompts, per_agent_models, per_agent_temperatures, per_agent_clis, base_project_data),
			name=f"workflow-rerun-{task_id}"
		)
		thread.daemon = True
		thread.start()
 
		return jsonify({
			'task_id': task_id,
			'status': 'in_progress',
			'message': 'Re-execution started successfully',
			'workflow_sequence': full_workflow_sequence,  # Return full sequence for frontend
			'execution_sequence': custom_workflow  # Return execution sequence for debugging
		}), 202
 
	except Exception as e:
		logger.error(f"Error re-executing task {task_id}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

# Configuration Management
@bmad_bp.route('/api/config', methods=['GET'])
@cross_origin()
def get_config():
	"""Get system configuration"""
	try:
		gemini_info = gemini_cli_client.get_model_info()
		
		config = {
			'gemini_api_key_configured': gemini_info['api_key_configured'],
			'current_model': gemini_info['model_name'],
			'available_models': ['gemini-2.5-flash', 'gemini-2.5-pro', 'gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-1.0-pro'],
			'gemini_api_keys_status': gemini_cli_client.get_api_key_status(),
			'llxprt': llxprt_cli_client.get_model_info(),
			'max_cost_per_day': float(os.getenv('MAX_COST_PER_DAY', 100.0)),
			'max_requests_per_day': int(os.getenv('MAX_REQUESTS_PER_DAY', 1000)),
			'max_tokens_per_day': int(os.getenv('MAX_TOKENS_PER_DAY', 1000000)),
			'upload_folder': UPLOAD_FOLDER,
			'allowed_extensions': list(ALLOWED_EXTENSIONS),
			'max_file_size': MAX_FILE_SIZE
		}
		
		return jsonify(config)
		
	except Exception as e:
		logger.error(f"Error getting config: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/config', methods=['PUT'])
@cross_origin()
def update_config():
	"""Update system configuration"""
	try:
		data = request.get_json()
		
		if not data:
			return jsonify({'error': 'No data provided'}), 400
		
		# Update Gemini API key
		if 'gemini_api_key' in data:
			gemini_cli_client.update_api_key(data['gemini_api_key'])
		
		# Update model
		if 'current_model' in data:
			gemini_cli_client.switch_model(data['current_model'])

		# Update llxprt settings
		if 'llxprt' in data and isinstance(data['llxprt'], dict):
			cfg = data['llxprt']
			api_key = cfg.get('api_key') or cfg.get('OPENROUTER_API_KEY')
			model = cfg.get('model') or cfg.get('model_name')
			base_url = cfg.get('base_url') or cfg.get('OPENROUTER_BASE_URL')
			provider = cfg.get('provider')
			if api_key or base_url or provider:
				llxprt_cli_client.update_api_config(api_key=api_key, base_url=base_url, provider=provider)
			if model:
				llxprt_cli_client.switch_model(model)
		
		return jsonify({'message': 'Configuration updated successfully'})
		
	except Exception as e:
		logger.error(f"Error updating config: {e}")
		return jsonify({'error': 'Internal server error'}), 500

# Gemini API Key Management
@bmad_bp.route('/api/config/gemini/keys', methods=['GET'])
@cross_origin()
def get_gemini_api_keys():
	"""Get all Gemini API keys status"""
	try:
		keys_status = gemini_cli_client.get_api_key_status()
		return jsonify(keys_status)
		
	except Exception as e:
		logger.error(f"Error getting Gemini API keys: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/config/gemini/keys', methods=['POST'])
@cross_origin()
def add_gemini_api_key():
	"""Add a new Gemini API key or update at specific position"""
	try:
		data = request.get_json()
		
		if not data or 'api_key' not in data:
			return jsonify({'error': 'API key is required'}), 400
		
		# Check if position is specified for updating
		if 'position' in data:
			position = data['position']
			if not isinstance(position, int) or position < 0 or position > 2:
				return jsonify({'error': 'Position must be 0, 1, or 2'}), 400
			
			success = gemini_cli_client.update_api_key_at_position(data['api_key'], position)
			if success:
				position_names = ["primary", "other1", "other2"]
				return jsonify({'message': f'{position_names[position]} API key updated successfully'})
			else:
				return jsonify({'error': f'Failed to update {position_names[position]} API key'}), 400
		else:
			# Legacy behavior - add new key
			success = gemini_cli_client.add_api_key(data['api_key'])
			if success:
				return jsonify({'message': 'API key added successfully'})
			else:
				return jsonify({'error': 'Failed to add API key'}), 400
		
	except Exception as e:
		logger.error(f"Error adding/updating Gemini API key: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/config/gemini/keys/<api_key>', methods=['DELETE'])
@cross_origin()
def remove_gemini_api_key(api_key):
	"""Remove a Gemini API key"""
	try:
		success = gemini_cli_client.remove_api_key(api_key)
		
		if success:
			return jsonify({'message': 'API key removed successfully'})
		else:
			return jsonify({'error': 'Failed to remove API key'}), 404
		
	except Exception as e:
		logger.error(f"Error removing Gemini API key: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/config/gemini/keys/reset', methods=['POST'])
@cross_origin()
def reset_gemini_exhausted_keys():
	"""Reset all exhausted Gemini API keys"""
	try:
		gemini_cli_client.reset_exhausted_keys()
		return jsonify({'message': 'Exhausted keys reset successfully'})
		
	except Exception as e:
		logger.error(f"Error resetting exhausted keys: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/config/gemini/keys/rotate', methods=['POST'])
@cross_origin()
def rotate_gemini_api_key():
	"""Manually rotate to the next available Gemini API key"""
	try:
		# Get current status
		current_status = gemini_cli_client.get_api_key_status()
		
		# Mark current key as exhausted to force rotation
		current_key = current_status.get('current_key')
		if current_key:
			current_key_index = current_status.get('current_key_index', 0)
			current_key_id = f"key{current_key_index + 1}"
			
			logger.info(f"🔄 Manual rotation requested for {current_key_id}")
			gemini_cli_client.api_key_manager.mark_key_exhausted(current_key, "manual_rotation")
			
			# Get new key status after rotation
			new_status = gemini_cli_client.api_key_manager.get_key_status()
			new_key_index = new_status.get('current_key_index', 0)
			new_key_id = f"key{new_key_index + 1}"
			
			# Restart session with new key
			gemini_cli_client.restart_session_with_new_key()
			
			logger.info(f"✅ Manual rotation successful: {current_key_id} → {new_key_id}")
			return jsonify({'message': f'API key rotated successfully from {current_key_id} to {new_key_id}'})
		else:
			return jsonify({'error': 'No current API key to rotate'}), 400
		
	except Exception as e:
		logger.error(f"Error rotating Gemini API key: {e}")
		return jsonify({'error': 'Internal server error'}), 500

# Agent Management
@bmad_bp.route('/api/agents/prompts', methods=['GET'])
@cross_origin()
def get_agent_prompts():
	"""Get all agent prompts (built-in and custom)"""
	try:
		agents = agent_manager.get_all_agents()
		
		# Add current_prompt field for compatibility
		for agent_name, agent_info in agents.items():
			if 'current_prompt' not in agent_info:
				agent_info['current_prompt'] = agent_manager.get_agent_prompt(agent_name)
		
		return jsonify({'agents': agents})
		
	except Exception as e:
		logger.error(f"Error getting agent prompts: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/agents/prompts/<agent_name>', methods=['PUT'])
@cross_origin()
def update_agent_prompt(agent_name):
	"""Update an agent's prompt"""
	try:
		data = request.get_json()
		
		if not data or 'prompt' not in data:
			return jsonify({'error': 'Prompt is required'}), 400
		
		success = agent_manager.update_agent_prompt(agent_name, data['prompt'])
		
		if not success:
			return jsonify({'error': 'Agent not found'}), 404
		
		return jsonify({'message': f'Agent {agent_name} prompt updated successfully'})
		
	except Exception as e:
		logger.error(f"Error updating agent prompt for {agent_name}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/agents/prompts/<agent_name>/reset', methods=['POST'])
@cross_origin()
def reset_agent_prompt(agent_name):
	"""Reset an agent's prompt to default"""
	try:
		success = agent_manager.reset_agent_prompt(agent_name)
		
		if not success:
			return jsonify({'error': 'Agent not found'}), 404
		
		return jsonify({'message': f'Agent {agent_name} prompt reset to default'})
		
	except Exception as e:
		logger.error(f"Error resetting agent prompt for {agent_name}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/agents/instructions/<agent_name>', methods=['PUT'])
@cross_origin()
def update_agent_instructions(agent_name):
	"""Update an agent's instructions"""
	try:
		data = request.get_json()
		
		if not data or 'instructions' not in data:
			return jsonify({'error': 'Instructions are required'}), 400
		
		success = agent_manager.update_agent_instructions(agent_name, data['instructions'])
		
		if not success:
			return jsonify({'error': 'Agent not found'}), 404
		
		return jsonify({'message': f'Agent {agent_name} instructions updated successfully'})
		
	except Exception as e:
		logger.error(f"Error updating agent instructions for {agent_name}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

# Handoff prompts management
@bmad_bp.route('/api/agents/handoff/<agent_name>', methods=['GET'])
@cross_origin()
def get_handoff_prompt(agent_name):
	try:
		prompt = agent_manager.get_handoff_prompt(agent_name)
		return jsonify({'agent': agent_name, 'handoff_prompt': prompt})
	except Exception as e:
		logger.error(f"Error getting handoff prompt for {agent_name}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/agents/handoff/<agent_name>', methods=['PUT'])
@cross_origin()
def update_handoff_prompt(agent_name):
	try:
		data = request.get_json() or {}
		if data is None or 'handoff_prompt' not in data:
			return jsonify({'error': 'handoff_prompt is required'}), 400
		ok = agent_manager.update_handoff_prompt(agent_name, data['handoff_prompt'])
		if not ok:
			return jsonify({'error': 'Failed to update handoff prompt'}), 400
		return jsonify({'message': f'Handoff prompt updated for {agent_name}'})
	except Exception as e:
		logger.error(f"Error updating handoff prompt for {agent_name}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

# Custom Agent Management
@bmad_bp.route('/api/agents/custom', methods=['GET'])
@cross_origin()
def get_custom_agents():
	"""Get all custom agents"""
	try:
		from src.models.custom_agent import CustomAgent
		custom_agents = CustomAgent.get_active_custom_agents()
		return jsonify({
			'custom_agents': [agent.to_dict() for agent in custom_agents]
		})
		
	except Exception as e:
		logger.error(f"Error getting custom agents: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/agents/custom', methods=['POST'])
@cross_origin()
def create_custom_agent():
	"""Create a new custom agent"""
	try:
		data = request.get_json()
		
		if not data:
			return jsonify({'error': 'No data provided'}), 400
		
		name = data.get('name')
		display_name = data.get('display_name')
		description = data.get('description', '')
		prompt = data.get('prompt')
		instructions = data.get('instructions', '')
		
		if not name or not display_name or not prompt:
			return jsonify({'error': 'Name, display_name, and prompt are required'}), 400
		
		# Check if agent name already exists (built-in or custom)
		if agent_manager.validate_agent_name(name):
			return jsonify({'error': 'Agent name already exists'}), 400
		
		from src.models.custom_agent import CustomAgent
		import uuid
		
		# Check if custom agent name already exists
		existing_agent = CustomAgent.query.filter_by(name=name).first()
		if existing_agent:
			return jsonify({'error': 'Custom agent with this name already exists'}), 400
		
		# Create new custom agent
		custom_agent = CustomAgent(
			id=str(uuid.uuid4()),
			name=name,
			display_name=display_name,
			description=description,
			prompt=prompt,
			instructions=instructions,
			is_active=True,
			created_by='user'
		)
		
		db.session.add(custom_agent)
		db.session.commit()
		
		logger.info(f"Created new custom agent: {name}")
		
		return jsonify({
			'message': 'Custom agent created successfully',
			'agent': custom_agent.to_dict()
		}), 201
		
	except Exception as e:
		logger.error(f"Error creating custom agent: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/agents/custom/<agent_id>', methods=['GET'])
@cross_origin()
def get_custom_agent(agent_id):
	"""Get a specific custom agent"""
	try:
		from src.models.custom_agent import CustomAgent
		custom_agent = CustomAgent.query.get(agent_id)
		
		if not custom_agent:
			return jsonify({'error': 'Custom agent not found'}), 404
		
		return jsonify(custom_agent.to_dict())
		
	except Exception as e:
		logger.error(f"Error getting custom agent {agent_id}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/agents/custom/<agent_id>', methods=['PUT'])
@cross_origin()
def update_custom_agent(agent_id):
	"""Update a custom agent"""
	try:
		data = request.get_json()
		
		if not data:
			return jsonify({'error': 'No data provided'}), 400
		
		from src.models.custom_agent import CustomAgent
		custom_agent = CustomAgent.query.get(agent_id)
		
		if not custom_agent:
			return jsonify({'error': 'Custom agent not found'}), 404
		
		# Update fields
		if 'name' in data:
			# Check if new name conflicts with existing agent
			if agent_manager.validate_agent_name(data['name']) and data['name'] != custom_agent.name:
				return jsonify({'error': 'Agent name already exists'}), 400
			custom_agent.name = data['name']
		
		if 'display_name' in data:
			custom_agent.display_name = data['display_name']
		
		if 'description' in data:
			custom_agent.description = data['description']
		
		if 'prompt' in data:
			custom_agent.prompt = data['prompt']
		
		if 'instructions' in data:
			custom_agent.instructions = data['instructions']
		
		if 'is_active' in data:
			custom_agent.is_active = data['is_active']
		
		custom_agent.updated_at = datetime.utcnow()
		db.session.commit()
		
		logger.info(f"Updated custom agent: {custom_agent.name}")
		
		return jsonify({
			'message': 'Custom agent updated successfully',
			'agent': custom_agent.to_dict()
		})
		
	except Exception as e:
		logger.error(f"Error updating custom agent {agent_id}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/agents/custom/<agent_id>', methods=['DELETE'])
@cross_origin()
def delete_custom_agent(agent_id):
	"""Delete a custom agent"""
	try:
		from src.models.custom_agent import CustomAgent
		custom_agent = CustomAgent.query.get(agent_id)
		
		if not custom_agent:
			return jsonify({'error': 'Custom agent not found'}), 404
		
		# Soft delete by setting is_active to False
		custom_agent.is_active = False
		custom_agent.updated_at = datetime.utcnow()
		db.session.commit()
		
		logger.info(f"Deleted custom agent: {custom_agent.name}")
		
		return jsonify({'message': 'Custom agent deleted successfully'})
		
	except Exception as e:
		logger.error(f"Error deleting custom agent {agent_id}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/agents/custom/<agent_id>/copy', methods=['POST'])
@cross_origin()
def copy_custom_agent(agent_id):
	"""Copy a custom agent"""
	try:
		data = request.get_json()
		
		if not data or 'name' not in data:
			return jsonify({'error': 'New agent name is required'}), 400
		
		from src.models.custom_agent import CustomAgent
		import uuid
		
		original_agent = CustomAgent.query.get(agent_id)
		
		if not original_agent:
			return jsonify({'error': 'Custom agent not found'}), 404
		
		# Check if new name already exists
		if agent_manager.validate_agent_name(data['name']):
			return jsonify({'error': 'Agent name already exists'}), 400
		
		# Create copy
		new_agent = CustomAgent(
			id=str(uuid.uuid4()),
			name=data['name'],
			display_name=data.get('display_name', f"Copy of {original_agent.display_name}"),
			description=data.get('description', original_agent.description),
			prompt=original_agent.prompt,
			instructions=original_agent.instructions,
			is_active=True,
			created_by='user'
		)
		
		db.session.add(new_agent)
		db.session.commit()
		
		logger.info(f"Copied custom agent {original_agent.name} to {new_agent.name}")
		
		return jsonify({
			'message': 'Custom agent copied successfully',
			'agent': new_agent.to_dict()
		}), 201
		
	except Exception as e:
		logger.error(f"Error copying custom agent {agent_id}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

# Workflow Management
@bmad_bp.route('/api/workflows', methods=['GET'])
@cross_origin()
def get_workflows():
	"""Get all workflows"""
	try:
		_ensure_workflows_schema()
		workflows = Workflow.get_active_workflows()
		return jsonify({
			'workflows': [workflow.to_dict() for workflow in workflows]
		})
		
	except Exception as e:
		logger.error(f"Error getting workflows: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/workflows', methods=['POST'])
@cross_origin()
def create_workflow():
	"""Create a new workflow"""
	try:
		_ensure_workflows_schema()
		data = request.get_json()
		
		if not data:
			return jsonify({'error': 'No data provided'}), 400
		
		name = data.get('name')
		description = data.get('description', '')
		agent_sequence = data.get('agent_sequence', [])
		agent_models = data.get('agent_models', [])
		agent_temperatures = data.get('agent_temperatures', [])
		agent_clis = data.get('agent_clis', [])
		
		if not name:
			return jsonify({'error': 'Workflow name is required'}), 400
		
		if not agent_sequence:
			return jsonify({'error': 'Agent sequence is required'}), 400
		
		# Check if workflow name already exists
		existing_workflow = Workflow.query.filter_by(name=name).first()
		if existing_workflow:
			return jsonify({'error': 'Workflow with this name already exists'}), 400
		
		# Align arrays
		if not agent_models:
			agent_models = [None] * len(agent_sequence)
		if not agent_temperatures:
			# default None means use system default
			agent_temperatures = [None] * len(agent_sequence)
		if not agent_clis:
			agent_clis = ['gemini'] * len(agent_sequence)
		
		# Create new workflow
		import uuid
		workflow = Workflow(
			id=str(uuid.uuid4()),
			name=name,
			description=description,
			agent_sequence=json.dumps(agent_sequence),
			agent_models=json.dumps(agent_models),
			agent_temperatures=json.dumps(agent_temperatures),
			agent_clis=json.dumps(agent_clis),
			is_default=False,
			is_active=True,
			created_by='user'
		)
		
		db.session.add(workflow)
		db.session.commit()
		
		logger.info(f"Created new workflow: {name}")
		
		return jsonify({
			'message': 'Workflow created successfully',
			'workflow': workflow.to_dict()
		}), 201
		
	except Exception as e:
		logger.error(f"Error creating workflow: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/workflows/<workflow_id>', methods=['GET'])
@cross_origin()
def get_workflow(workflow_id):
	"""Get a specific workflow"""
	try:
		_ensure_workflows_schema()
		workflow = Workflow.query.get(workflow_id)
		
		if not workflow:
			return jsonify({'error': 'Workflow not found'}), 404
		
		return jsonify(workflow.to_dict())
		
	except Exception as e:
		logger.error(f"Error getting workflow {workflow_id}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/workflows/<workflow_id>', methods=['PUT'])
@cross_origin()
def update_workflow(workflow_id):
	"""Update a workflow"""
	try:
		_ensure_workflows_schema()
		data = request.get_json()
		
		if not data:
			return jsonify({'error': 'No data provided'}), 400
		
		workflow = Workflow.query.get(workflow_id)
		
		if not workflow:
			return jsonify({'error': 'Workflow not found'}), 404
		
		# Update fields
		if 'name' in data:
			# Check if new name conflicts with existing workflow
			existing_workflow = Workflow.query.filter_by(name=data['name']).first()
			if existing_workflow and existing_workflow.id != workflow_id:
				return jsonify({'error': 'Workflow with this name already exists'}), 400
			workflow.name = data['name']
		
		if 'description' in data:
			workflow.description = data['description']
		
		if 'agent_sequence' in data:
			import json
			workflow.agent_sequence = json.dumps(data['agent_sequence'])
			# If agent_models/agent_temperatures are absent, align size with sequence
			if 'agent_models' not in data:
				workflow.agent_models = json.dumps([None] * len(data['agent_sequence']))
			if 'agent_temperatures' not in data:
				workflow.agent_temperatures = json.dumps([None] * len(data['agent_sequence']))
			if 'agent_clis' not in data:
				workflow.agent_clis = json.dumps(['gemini'] * len(data['agent_sequence']))
		
		if 'agent_models' in data:
			import json
			workflow.agent_models = json.dumps(data['agent_models'])
		
		if 'agent_temperatures' in data:
			import json
			workflow.agent_temperatures = json.dumps(data['agent_temperatures'])
		
		if 'agent_clis' in data:
			import json
			workflow.agent_clis = json.dumps(data['agent_clis'])
		
		if 'is_active' in data:
			workflow.is_active = data['is_active']
		
		workflow.updated_at = datetime.utcnow()
		db.session.commit()
		
		logger.info(f"Updated workflow: {workflow.name}")
		
		return jsonify({
			'message': 'Workflow updated successfully',
			'workflow': workflow.to_dict()
		})
		
	except Exception as e:
		logger.error(f"Error updating workflow {workflow_id}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/workflows/<workflow_id>', methods=['DELETE'])
@cross_origin()
def delete_workflow(workflow_id):
	"""Delete a workflow"""
	try:
		workflow = Workflow.query.get(workflow_id)
		
		if not workflow:
			return jsonify({'error': 'Workflow not found'}), 404
		
		if workflow.is_default:
			return jsonify({'error': 'Cannot delete default workflow'}), 400
		
		# Soft delete by setting is_active to False
		workflow.is_active = False
		workflow.updated_at = datetime.utcnow()
		db.session.commit()
		
		logger.info(f"Deleted workflow: {workflow.name}")
		
		return jsonify({'message': 'Workflow deleted successfully'})
		
	except Exception as e:
		logger.error(f"Error deleting workflow {workflow_id}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/workflows/<workflow_id>/copy', methods=['POST'])
@cross_origin()
def copy_workflow(workflow_id):
	"""Copy a workflow"""
	try:
		_ensure_workflows_schema()
		data = request.get_json()
		
		if not data or 'name' not in data:
			return jsonify({'error': 'New workflow name is required'}), 400
		
		original_workflow = Workflow.query.get(workflow_id)
		
		if not original_workflow:
			return jsonify({'error': 'Workflow not found'}), 404
		
		# Check if new name already exists
		existing_workflow = Workflow.query.filter_by(name=data['name']).first()
		if existing_workflow:
			return jsonify({'error': 'Workflow with this name already exists'}), 400
		
		# Create copy
		import uuid
		new_workflow = Workflow(
			id=str(uuid.uuid4()),
			name=data['name'],
			description=data.get('description', f"Copy of {original_workflow.name}"),
			agent_sequence=original_workflow.agent_sequence,  # Copy the agent sequence
			agent_models=getattr(original_workflow, 'agent_models', None),
			agent_temperatures=getattr(original_workflow, 'agent_temperatures', None),
			agent_clis=getattr(original_workflow, 'agent_clis', None),
			is_default=False,
			is_active=True,
			created_by='user'
		)
		
		db.session.add(new_workflow)
		db.session.commit()
		
		logger.info(f"Copied workflow {original_workflow.name} to {new_workflow.name}")
		
		return jsonify({
			'message': 'Workflow copied successfully',
			'workflow': new_workflow.to_dict()
		}), 201
		
	except Exception as e:
		logger.error(f"Error copying workflow {workflow_id}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/workflows/default', methods=['GET'])
@cross_origin()
def get_default_workflow():
	"""Get the default workflow sequence"""
	try:
		_ensure_workflows_schema()
		default_workflow = Workflow.get_default_workflow()
		
		if default_workflow:
			wf = default_workflow.to_dict()
			return jsonify({
				'workflow_sequence': wf['agent_sequence'],
				'agent_models': wf.get('agent_models', []),
				'agent_temperatures': wf.get('agent_temperatures', []),
				'available_agents': agent_manager.get_agent_names()
			})
		else:
			# Fallback to agent manager default
			return jsonify({
				'workflow_sequence': agent_manager.get_default_workflow_sequence(),
				'agent_models': [],
				'agent_temperatures': [],
				'available_agents': agent_manager.get_agent_names()
			})
	except Exception as e:
		logger.error(f"Error getting default workflow: {e}")
		return jsonify({'error': 'Internal server error'}), 500

# Usage Statistics
@bmad_bp.route('/api/usage/summary', methods=['GET'])
@cross_origin()
def get_usage_summary():
	"""Get usage statistics summary"""
	try:
		summary = token_meter.get_usage_summary()
		return jsonify(summary)
		
	except Exception as e:
		logger.error(f"Error getting usage summary: {e}")
		return jsonify({'error': 'Internal server error'}), 500

# File Upload
@bmad_bp.route('/api/upload', methods=['POST'])
@cross_origin()
def upload_file():
	"""Upload and process a file"""
	try:
		if 'file' not in request.files:
			return jsonify({'error': 'No file provided'}), 400
		
		file = request.files['file']
		
		if file.filename == '':
			return jsonify({'error': 'No file selected'}), 400
		
		if not allowed_file(file.filename):
			return jsonify({'error': 'File type not allowed'}), 400
		
		# Save file
		filename = secure_filename(file.filename)
		file_path = os.path.join(UPLOAD_FOLDER, filename)
		file.save(file_path)
		
		# Process file
		try:
			parsed_content = file_parser.parse_file(file_path)
			
			return jsonify({
				'filename': filename,
				'file_path': file_path,
				'content': parsed_content,
				'message': 'File uploaded and processed successfully'
			})
			
		except Exception as parse_error:
			logger.error(f"Error parsing file {filename}: {parse_error}")
			return jsonify({
				'filename': filename,
				'file_path': file_path,
				'error': f'File uploaded but parsing failed: {str(parse_error)}'
			}), 206  # Partial content
		
	except Exception as e:
		logger.error(f"Error uploading file: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/tasks/<task_id>/upload', methods=['POST'])
@cross_origin()
def upload_file_for_task(task_id):
	"""Upload a file and place it into the task's .sureai/uploads directory, then parse it."""
	try:
		if 'file' not in request.files:
			return jsonify({'error': 'No file provided'}), 400
		
		file = request.files['file']
		if file.filename == '':
			return jsonify({'error': 'No file selected'}), 400
		if not allowed_file(file.filename):
			return jsonify({'error': 'File type not allowed'}), 400
		
		project_dir = _resolve_project_dir(task_id)
		if not project_dir:
			return jsonify({'error': 'Invalid task ID'}), 404
		
		uploads_dir = os.path.join(project_dir, '.sureai', 'uploads')
		os.makedirs(uploads_dir, exist_ok=True)
		
		filename = secure_filename(file.filename)
		dest_path = os.path.join(uploads_dir, filename)
		if os.path.exists(dest_path):
			name, ext = os.path.splitext(filename)
			counter = 1
			while os.path.exists(dest_path):
				alt = f"{name}({counter}){ext}"
				dest_path = os.path.join(uploads_dir, alt)
				counter += 1
		file.save(dest_path)
		
		try:
			parsed_content = file_parser.parse_file(dest_path)
		except Exception as parse_error:
			logger.warning(f"Parsing failed for {dest_path}: {parse_error}")
			parsed_content = None
		
		# Append an entry to a manifest file for traceability
		try:
			manifest_path = os.path.join(project_dir, '.sureai', 'uploads_manifest.json')
			manifest = []
			if os.path.exists(manifest_path):
				with open(manifest_path, 'r', encoding='utf-8') as f:
					manifest = json.load(f)
			manifest.append({
				'filename': filename,
				'path': os.path.relpath(dest_path, project_dir),
				'uploaded_at': datetime.utcnow().isoformat(),
				'parsed': parsed_content is not None
			})
			with open(manifest_path, 'w', encoding='utf-8') as f:
				json.dump(manifest, f, indent=2)
		except Exception as mf_err:
			logger.warning(f"Could not update uploads manifest: {mf_err}")
		
		return jsonify({
			'task_id': task_id,
			'filename': os.path.basename(dest_path),
			'relative_path': os.path.relpath(dest_path, project_dir),
			'content': parsed_content,
			'message': 'File uploaded to task and processed successfully' if parsed_content is not None else 'File uploaded to task; parsing failed'
		})
	except Exception as e:
		logger.error(f"Error uploading file for task {task_id}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

# Task Logs
@bmad_bp.route('/api/tasks/<task_id>/logs', methods=['GET'])
@cross_origin()
def get_task_logs(task_id):
	"""Get logs for a specific task"""
	try:
		logs = get_task_logs(task_id)
		return jsonify({'logs': logs})
		
	except Exception as e:
		logger.error(f"Error getting logs for task {task_id}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

# Download Task Results
@bmad_bp.route('/api/tasks/<task_id>/download', methods=['GET'])
@cross_origin()
def download_task_results(task_id):
	"""Download task results as a zip file"""
	try:
		# Get task output directory
		output_dir = _resolve_project_dir(task_id)
		
		if not output_dir or not os.path.exists(output_dir):
			return jsonify({'error': 'Task results not found'}), 404
		
		# Create zip file
		import zipfile
		import tempfile
		
		with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
			with zipfile.ZipFile(tmp_file.name, 'w') as zip_file:
				for root, dirs, files in os.walk(output_dir):
					for file in files:
						file_path = os.path.join(root, file)
						arc_name = os.path.relpath(file_path, output_dir)
						zip_file.write(file_path, arc_name)
			
			return send_file(
				tmp_file.name,
				as_attachment=True,
				download_name=f'task_{task_id}_results.zip',
				mimetype='application/zip'
			)
		
	except Exception as e:
		logger.error(f"Error downloading task results for {task_id}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

# Download Generated Project
@bmad_bp.route('/api/tasks/<task_id>/project', methods=['GET'])
@cross_origin()
def download_generated_project(task_id):
	"""Download generated project files as a zip file"""
	try:
		project_dir = f"/tmp/bmad_projects/{task_id}"
		
		if not os.path.exists(project_dir):
			return jsonify({'error': 'Generated project not found'}), 404
		
		# Create zip file
		import zipfile
		zip_path = f"/tmp/bmad_projects/{task_id}_project.zip"
		
		with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
			for root, dirs, files in os.walk(project_dir):
				for file in files:
					file_path = os.path.join(root, file)
					arcname = os.path.relpath(file_path, project_dir)
					zipf.write(file_path, arcname)
		
		return send_file(zip_path, as_attachment=True, download_name=f"{task_id}_project.zip")
		
	except Exception as e:
		logger.error(f"Error downloading project for task {task_id}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

# Create and fetch Zrok share for deployed frontend
@bmad_bp.route('/api/tasks/<task_id>/deploy/frontend/share', methods=['POST'])
@cross_origin()
def create_frontend_share(task_id):
	"""Create a public zrok share for the deployed frontend of this task.
	Requires env ZROK_API_ENDPOINT and ZROK_ACCOUNT_TOKEN and zrok binary installed.
	Body can optionally include { "local_url": "http://bmad-frontend:80" } else default to frontend container.
	"""
	try:
		if not _zrok_configured():
			return jsonify({'error': 'Zrok not configured on server'}), 400
		body = request.get_json(silent=True) or {}
		# Compute strict target using deploy.json or compose
		local_url = body.get('local_url')
		if not local_url:
			frontend_port, _proj = get_frontend_port_for_task(task_id)
			if not frontend_port:
				return jsonify({'error': 'Unable to determine frontend port for zrok share'}), 400
			vm_ip = get_vm_ip()
			local_url = f"http://{vm_ip}:{frontend_port}"
		# Normalize
		if not local_url.startswith('http'):
			local_url = f'http://{local_url}'
		# Compose container network uses service name and port 80 for frontend
		if not local_url.startswith('http'):
			local_url = f'http://{local_url}'
		# Ensure zrok is enabled and create share
		label = f'frontend-{task_id[:8]}'
		public_url = _zrok_share_http(label, local_url)
		if not public_url:
			return jsonify({'error': 'Failed to create zrok share'}), 500
		# Persist to deploy.json under task project folder
		project_dir = _resolve_project_dir(task_id)
		if project_dir:
			meta_dir = os.path.join(project_dir, '.sureai')
			os.makedirs(meta_dir, exist_ok=True)
			deploy_path = os.path.join(meta_dir, 'deploy.json')
			data = {}
			if os.path.exists(deploy_path):
				try:
					with open(deploy_path, 'r', encoding='utf-8') as f:
						data = json.load(f)
				except Exception:
					data = {}
			data['frontend_url'] = public_url
			with open(deploy_path, 'w', encoding='utf-8') as f:
				json.dump(data, f, indent=2)
		return jsonify({'frontend_url': public_url})
	except Exception as e:
		logger.error(f"Error creating zrok share for task {task_id}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

# Automatically create zrok share for completed tasks
@bmad_bp.route('/api/tasks/<task_id>/deploy/auto-share', methods=['POST'])
@cross_origin()
def auto_create_frontend_share(task_id):
	"""Automatically create a zrok share for a completed task deployment.
	This endpoint is called automatically when tasks are completed to provide external access.
	"""
	try:
		if not _zrok_configured():
			logger.warning(f"Zrok not configured, cannot create auto-share for task {task_id}")
			return jsonify({'error': 'Zrok not configured on server'}), 400
		
		body = request.get_json(silent=True) or {}
		# Compute strict target using deploy.json or compose
		local_url = body.get('local_url')
		if not local_url:
			frontend_port, _proj = get_frontend_port_for_task(task_id)
			if not frontend_port:
				return jsonify({'error': 'Unable to determine frontend port for zrok share'}), 400
			vm_ip = get_vm_ip()
			local_url = f"http://{vm_ip}:{frontend_port}"
		# Normalize
		if not local_url.startswith('http'):
			local_url = f'http://{local_url}'
		# Create a descriptive label for the share
		label = f'auto-deploy-{task_id[:8]}'
		public_url = _zrok_share_http(label, local_url)
		
		if not public_url:
			logger.error(f"Failed to create auto zrok share for task {task_id}")
			return jsonify({'error': 'Failed to create zrok share'}), 500
		
		# Save the URL to the task's metadata
		project_dir = _resolve_project_dir(task_id)
		if project_dir:
			meta_dir = os.path.join(project_dir, '.sureai')
			os.makedirs(meta_dir, exist_ok=True)
			deploy_path = os.path.join(meta_dir, 'deploy.json')
			
			data = {}
			if os.path.exists(deploy_path):
				try:
					with open(deploy_path, 'r', encoding='utf-8') as f:
						data = json.load(f)
				except Exception:
					data = {}
			
			data['frontend_url'] = public_url
			data['auto_created'] = True
			data['created_at'] = datetime.now().isoformat()
			
			with open(deploy_path, 'w', encoding='utf-8') as f:
				json.dump(data, f, indent=2)
			
			logger.info(f"Auto-created zrok share for task {task_id}: {public_url}")
		
		return jsonify({
			'frontend_url': public_url,
			'message': 'Zrok share created automatically for completed task',
			'auto_created': True
		})
		
	except Exception as e:
		logger.error(f"Error creating auto zrok share for task {task_id}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

# Get Project Status
@bmad_bp.route('/api/tasks/<task_id>/project/status', methods=['GET'])
@cross_origin()
def get_project_status(task_id):
	"""Get the status of generated project"""
	try:
		project_dir = f"/tmp/bmad_projects/{task_id}"
		
		if not os.path.exists(project_dir):
			return jsonify({'status': 'not_generated'})
		
		# Count files
		file_count = 0
		for root, dirs, files in os.walk(project_dir):
			file_count += len(files)
		
		return jsonify({
			'status': 'generated',
			'project_dir': project_dir,
			'file_count': file_count,
			'files': [f for f in os.listdir(project_dir) if os.path.isfile(os.path.join(project_dir, f))]
		})
		
	except Exception as e:
		logger.error(f"Error getting project status for task {task_id}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

# MCP Management
@bmad_bp.route('/api/mcp/servers', methods=['GET'])
@cross_origin()
def list_mcp_servers():
	try:
		servers = MCPServer.query.order_by(MCPServer.created_at.desc()).all()
		try:
			gemini_cli_client.set_mcp_servers([s.to_dict() for s in servers if s.enabled])
		except Exception:
			pass
		return jsonify({'servers': [s.to_dict() for s in servers]})
	except Exception as e:
		logger.error(f"Error listing MCP servers: {e}")
		return jsonify({'error': 'Internal server error'}), 500

def _gemini_settings_path() -> Path:
	# Gemini CLI stores state under ~/.gemini; use settings.json there
	home = Path(os.environ.get('HOME', '/root'))
	return home.joinpath('.gemini', 'settings.json')

def _ensure_settings_dir(path: Path):
	try:
		path.parent.mkdir(parents=True, exist_ok=True)
	except Exception as e:
		logger.warning(f"Could not create settings dir {path.parent}: {e}")

def _read_settings() -> Dict[str, Any]:
	path = _gemini_settings_path()
	try:
		if path.exists():
			with open(path, 'r', encoding='utf-8') as f:
				return json.load(f)
	except Exception as e:
		logger.warning(f"Failed to read settings.json: {e}")
	return {}

def _deep_merge(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
	out = dict(a or {})
	for k, v in (b or {}).items():
		if isinstance(v, dict) and isinstance(out.get(k), dict):
			out[k] = _deep_merge(out[k], v)
		else:
			out[k] = v
	return out

def _write_settings(data: Dict[str, Any]) -> bool:
	path = _gemini_settings_path()
	_ensure_settings_dir(path)
	try:
		with open(path, 'w', encoding='utf-8') as f:
			json.dump(data, f, indent=2)
		return True
	except Exception as e:
		logger.error(f"Failed to write settings.json: {e}")
		return False

def _remove_preconfigured_context7_from_settings():
	"""Remove only the preconfigured default Context7 MCP from Gemini settings.json.
	A preconfigured entry matches type=streamable-http and url=http://localhost:4003/mcp.
	User-added entries with different settings are preserved.
	"""
	try:
		current = _read_settings()
		servers = current.get('mcpServers') or {}
		if isinstance(servers, dict) and 'context7' in servers:
			cfg = servers.get('context7')
			if isinstance(cfg, dict):
				is_default_type = cfg.get('type') == 'streamable-http'
				is_default_url = cfg.get('url') == 'http://localhost:4003/mcp'
				if is_default_type and is_default_url:
					del servers['context7']
					current['mcpServers'] = servers
					if _write_settings(current):
						logger.info("Removed preconfigured Context7 MCP from Gemini settings.json")
						try:
							# Clear explicit CLI MCP flags to rely on settings.json
							gemini_cli_client.set_mcp_servers([])
						except Exception:
							pass
					return
		logger.info("No preconfigured Context7 MCP to remove from Gemini settings.json")
	except Exception as e:
		logger.warning(f"Could not remove preconfigured Context7 MCP: {e}")

# ---- Default MCP servers to seed into Gemini settings.json ----
DEFAULT_MCP_SERVERS: Dict[str, Any] = {
    'io8': { 'url': 'http://157.66.191.31:4001/sse' },
    'gitea': { 'url': 'http://157.66.191.31:4000/sse' },
    'flf': { 'url': 'http://157.66.191.31:4002/sse' }
}

def _ensure_default_mcp_servers():
    """Ensure default SSE MCP servers exist in settings.json without overwriting user entries."""
    try:
        current = _read_settings() or {}
        servers = current.get('mcpServers')
        if not isinstance(servers, dict):
            servers = {}
        changed = False
        for name, cfg in DEFAULT_MCP_SERVERS.items():
            if name not in servers:
                servers[name] = cfg
                changed = True
        if changed:
            current['mcpServers'] = servers
            if _write_settings(current):
                logger.info("Seeded default MCP servers into Gemini settings.json")
                try:
                    # Clear explicit CLI MCP flags so settings.json is authoritative
                    gemini_cli_client.set_mcp_servers([])
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"Failed to ensure default MCP servers: {e}")

# MCP Management
@bmad_bp.route('/api/mcp/settings', methods=['GET'])
@cross_origin()
def get_mcp_settings():
	try:
		_ensure_default_mcp_servers()
		settings = _read_settings()
		return jsonify({'settings': settings})
	except Exception as e:
		logger.error(f"Error reading MCP settings: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/mcp/settings', methods=['PUT'])
@cross_origin()
def update_mcp_settings():
	"""Merge the provided JSON into Gemini CLI settings.json (append mcpServers etc.)."""
	try:
		payload = request.get_json() or {}
		if not isinstance(payload, dict):
			return jsonify({'error': 'JSON body must be an object'}), 400
		# Normalize: support payloads that omit the mcpServers block
		single_server_mode = False
		if 'mcpServers' not in payload:
			# Case A: payload looks like a servers map {name: {url|command...}, ...}
			if payload and all(isinstance(v, dict) for v in payload.values()):
				payload = {'mcpServers': payload}
			# Case B: payload looks like a single server object; require serverName query param
			elif any(k in payload for k in ['url', 'command', 'args', 'env']):
				server_name = request.args.get('serverName')
				if not server_name:
					return jsonify({'error': 'For single server JSON, provide ?serverName=<name>'}), 400
				payload = {'mcpServers': {server_name: payload}}
				single_server_mode = True
		# Validate mcpServers entries
		warnings: List[str] = []
		valid_servers: Dict[str, Any] = {}
		servers = (payload.get('mcpServers') or {}) if isinstance(payload.get('mcpServers'), dict) else {}
		for name, cfg in servers.items():
			if not isinstance(cfg, dict):
				warnings.append(f"{name}: configuration must be an object")
				continue
			has_url = isinstance(cfg.get('url'), str) and cfg.get('url').strip() != ''
			has_cmd = isinstance(cfg.get('command'), str) and cfg.get('command').strip() != ''
			if not has_url and not has_cmd:
				warnings.append(f"{name}: must provide either 'url' (SSE/HTTP) or 'command' (STDIO)")
				continue
			# Validate URL format if present
			if has_url and not (cfg['url'].startswith('http://') or cfg['url'].startswith('https://')):
				warnings.append(f"{name}: url should start with http:// or https://")
				# still accept
			# Validate args/env types for STDIO
			if has_cmd:
				if 'args' in cfg and not isinstance(cfg['args'], list):
					warnings.append(f"{name}: 'args' must be an array; ignoring provided value")
					cfg = {**cfg}
					cfg.pop('args', None)
				if 'env' in cfg and not isinstance(cfg['env'], dict):
					warnings.append(f"{name}: 'env' must be an object; ignoring provided value")
					cfg = {**cfg}
					cfg.pop('env', None)
			valid_servers[name] = cfg
		# If user provided only invalid servers, error out
		if servers and not valid_servers:
			return jsonify({'error': 'No valid MCP servers found in payload', 'warnings': warnings}), 400
		# Build merge payload: keep other top-level keys (e.g., theme) but replace mcpServers with validated set
		payload_for_merge = dict(payload)
		if servers:
			payload_for_merge['mcpServers'] = valid_servers
		current = _read_settings()
		merged = _deep_merge(current, payload_for_merge)
		ok = _write_settings(merged)
		if not ok:
			return jsonify({'error': 'Failed to write settings'}), 500
		# Since settings.json drives MCP, clear explicit CLI MCP flags to avoid conflicts
		try:
			gemini_cli_client.set_mcp_servers([])
		except Exception:
			pass
		msg = 'Settings updated'
		if warnings:
			msg += ' with warnings'
		return jsonify({'message': msg, 'settings': merged, 'warnings': warnings})
	except Exception as e:
		logger.error(f"Error updating MCP settings: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/mcp/servers', methods=['POST'])
@cross_origin()
def create_mcp_server():
	try:
		data = request.get_json() or {}
		name = data.get('name')
		command = data.get('command')
		args = data.get('args') or []
		env = data.get('env') or {}
		enabled = bool(data.get('enabled', True))
		if not name or not command:
			return jsonify({'error': 'name and command are required'}), 400
		import uuid, json
		server = MCPServer(
			id=str(uuid.uuid4()),
			name=name,
			command=command,
			args=json.dumps(args),
			env=json.dumps(env),
			enabled=enabled
		)
		db.session.add(server)
		db.session.commit()
		try:
			all_servers = MCPServer.query.all()
			gemini_cli_client.set_mcp_servers([s.to_dict() for s in all_servers if s.enabled])
		except Exception:
			pass
		return jsonify({'message': 'MCP server created', 'server': server.to_dict()}), 201
	except Exception as e:
		logger.error(f"Error creating MCP server: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/mcp/servers/<server_id>', methods=['PUT'])
@cross_origin()
def update_mcp_server(server_id):
	try:
		data = request.get_json() or {}
		server = MCPServer.query.get(server_id)
		if not server:
			return jsonify({'error': 'MCP server not found'}), 404
		import json
		if 'name' in data:
			server.name = data['name']
		if 'command' in data:
			server.command = data['command']
		if 'args' in data:
			server.args = json.dumps(data['args'] or [])
		if 'env' in data:
			server.env = json.dumps(data['env'] or {})
		if 'enabled' in data:
			server.enabled = bool(data['enabled'])
		server.updated_at = datetime.utcnow()
		db.session.commit()
		try:
			all_servers = MCPServer.query.all()
			gemini_cli_client.set_mcp_servers([s.to_dict() for s in all_servers if s.enabled])
		except Exception:
			pass
		return jsonify({'message': 'MCP server updated', 'server': server.to_dict()})
	except Exception as e:
		logger.error(f"Error updating MCP server {server_id}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/mcp/servers/<server_id>', methods=['DELETE'])
@cross_origin()
def delete_mcp_server(server_id):
	try:
		server = MCPServer.query.get(server_id)
		if not server:
			return jsonify({'error': 'MCP server not found'}), 404
		db.session.delete(server)
		db.session.commit()
		try:
			all_servers = MCPServer.query.all()
			gemini_cli_client.set_mcp_servers([s.to_dict() for s in all_servers if s.enabled])
		except Exception:
			pass
		return jsonify({'message': 'MCP server deleted'})
	except Exception as e:
		logger.error(f"Error deleting MCP server {server_id}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/mcp/servers/<server_id>/test', methods=['POST'])
@cross_origin()
def test_mcp_server(server_id):
	"""Registers the MCP server with Gemini CLI for this process and lists available tools."""
	try:
		server = MCPServer.query.get(server_id)
		if not server:
			return jsonify({'error': 'MCP server not found'}), 404
		import subprocess, json, os
		env = os.environ.copy()
		try:
			supplied_env = server.to_dict().get('env') or {}
		except Exception:
			supplied_env = {}
		env.update({k: str(v) for k, v in (supplied_env or {}).items()})
		# Build the gemini CLI command to register MCP server and list tools
		# Note: Assuming gemini CLI supports MCP via flags like: --mcp <name>=<command> [args]
		# And a command to list tools (hypothetical: gemini tools list)
		mcp_spec = server.to_dict()
		cmd = ['gemini', '--yolo', '--model', gemini_cli_client.get_model_info().get('model_name', 'gemini-2.5-flash'), f"--mcp={mcp_spec['name']}={mcp_spec['command']}"]
		args = mcp_spec.get('args') or []
		for a in args:
			cmd.append(str(a))
		# Try a lightweight tools list; fall back to a ping prompt
		try:
			tools_proc = subprocess.run(['gemini', 'tools', 'list'], capture_output=True, text=True, env=env, timeout=10)
			tools_out = tools_proc.stdout.strip() or tools_proc.stderr.strip()
		except Exception:
			tools_out = ''
		# Simple ping to confirm server registers in a run
		test_proc = subprocess.run(cmd + ["Ping MCP server and respond with 'OK'"], capture_output=True, text=True, env=env, timeout=30)
		output = (test_proc.stdout or '').strip() or (test_proc.stderr or '').strip()
		return jsonify({'message': 'MCP test executed', 'tools': tools_out, 'output': output, 'return_code': test_proc.returncode})
	except Exception as e:
		logger.error(f"Error testing MCP server {server_id}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/mcp/settings/servers', methods=['GET'])
@cross_origin()
def list_settings_mcp_servers():
	try:
		_ensure_default_mcp_servers()
		settings = _read_settings()
		servers = settings.get('mcpServers') or {}
		if not isinstance(servers, dict):
			servers = {}
		items = []
		for name, cfg in servers.items():
			if isinstance(cfg, dict):
				items.append({'name': name, 'config': cfg})
		return jsonify({'servers': items})
	except Exception as e:
		logger.error(f"Error listing settings MCP servers: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/mcp/settings/servers/<name>', methods=['PUT'])
@cross_origin()
def update_settings_mcp_server(name: str):
	try:
		body = request.get_json() or {}
		if not isinstance(body, dict):
			return jsonify({'error': 'Server config must be an object'}), 400
		settings = _read_settings()
		servers = settings.get('mcpServers') or {}
		if not isinstance(servers, dict):
			servers = {}
		servers[name] = body
		settings['mcpServers'] = servers
		if not _write_settings(settings):
			return jsonify({'error': 'Failed to write settings'}), 500
		try:
			gemini_cli_client.set_mcp_servers([])
		except Exception:
			pass
		return jsonify({'message': 'Server updated', 'server': {'name': name, 'config': body}})
	except Exception as e:
		logger.error(f"Error updating settings MCP server {name}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/mcp/settings/servers/<name>', methods=['DELETE'])
@cross_origin()
def delete_settings_mcp_server(name: str):
	try:
		settings = _read_settings()
		servers = settings.get('mcpServers') or {}
		if isinstance(servers, dict) and name in servers:
			del servers[name]
			settings['mcpServers'] = servers
			if not _write_settings(settings):
				return jsonify({'error': 'Failed to write settings'}), 500
			try:
				gemini_cli_client.set_mcp_servers([])
			except Exception:
				pass
			return jsonify({'message': 'Server deleted'})
		return jsonify({'error': 'Server not found'}), 404
	except Exception as e:
		logger.error(f"Error deleting settings MCP server {name}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

# Remove preconfigured Context7 MCP at import time (best-effort)
try:
	_remove_preconfigured_context7_from_settings()
except Exception as _e:
	logger.warning(f"Context7 MCP cleanup failed: {_e}")

def _get_vm_ip() -> str:
	"""Return VM IP for zrok target. Hardcoded per request."""
	return '157.66.191.31'

def _resolve_project_dir(task_id: str) -> str | None:
	"""Resolve the project directory for a task, with fallback to scanning /tmp/bmad_output.
	Returns an absolute path or None if not found.
	"""
	try:
		proj = task_manager.get_task_output_directory(task_id)
		if proj and os.path.exists(proj):
			return proj
		# Strict per-task fallback: try TaskState context.project_path (older tasks)
		try:
			state = task_manager.get_task_state(task_id)
			if state and isinstance(state.context, dict):
				alt = state.context.get('project_path')
				if alt and os.path.exists(alt):
					return alt
		except Exception:
			pass
		return None
	except Exception as e:
		logger.warning(f"Failed to resolve project dir for task {task_id}: {e}")
		return None

def get_vm_ip() -> str:
	"""Return hardcoded VM IP for zrok sharing (wrapper)."""
	return _get_vm_ip()


def resolve_project_dir(task_id: str) -> str | None:
	"""Wrapper that resolves the project directory for a task."""
	return _resolve_project_dir(task_id)


def get_frontend_port_for_task(task_id: str) -> tuple[str | None, str | None]:
	"""
	Get frontend port for a task using strict per-task logic.
	Returns (frontend_port, project_dir).
	"""
	project_dir = resolve_project_dir(task_id)
	if not project_dir:
		logger.warning(f"Could not resolve project directory for task {task_id}")
		return None, None
	# Try to read from existing deploy.json
	try:
		deploy_path = os.path.join(project_dir, '.sureai', 'deploy.json')
		if os.path.exists(deploy_path):
			with open(deploy_path, 'r', encoding='utf-8') as f:
				meta = json.load(f)
				port = str(meta.get('frontend_port') or meta.get('port') or '').strip()
				if port:
					return port, project_dir
	except Exception as e:
		logger.warning(f"Error reading deploy.json for task {task_id}: {e}")
	# Detect and create deploy.json
	try:
		from src.utils.port_detector import PortDetector
		frontend_port = PortDetector.auto_detect_and_create_deploy_json(project_dir)
		if frontend_port:
			return frontend_port, project_dir
		# Fallback to direct detection and manual write
		frontend_port = PortDetector.detect_frontend_port_from_compose(project_dir)
		if frontend_port:
			try:
				meta_dir = os.path.join(project_dir, '.sureai')
				os.makedirs(meta_dir, exist_ok=True)
				with open(os.path.join(meta_dir, 'deploy.json'), 'w', encoding='utf-8') as f:
					json.dump({'frontend_port': frontend_port}, f, indent=2)
			except Exception as e:
				logger.warning(f"Failed to create deploy.json for task {task_id}: {e}")
			return frontend_port, project_dir
	except Exception as e:
		logger.error(f"Error detecting frontend port for task {task_id}: {e}")
		return None, project_dir
	return None, project_dir

@bmad_bp.route('/api/tasks/<task_id>/deploy/refresh-link', methods=['POST'])
@cross_origin()
def refresh_frontend_share(task_id):
	"""Refresh/recreate the zrok share for a task's frontend using strict per-task logic."""
	try:
		if not _zrok_configured():
			return jsonify({'error': 'Zrok not configured on server'}), 400
		frontend_port, project_dir = get_frontend_port_for_task(task_id)
		if not frontend_port:
			return jsonify({'error': 'Unable to determine frontend port for zrok share'}), 400
		vm_ip = get_vm_ip()
		local_url = f"http://{vm_ip}:{frontend_port}"
		label = f'refresh-{task_id[:8]}'
		public_url = _zrok_share_http(label, local_url)
		if not public_url:
			return jsonify({'error': 'Failed to create zrok share'}), 500
		if 'localhost' in public_url or '127.0.0.1' in public_url:
			return jsonify({'error': 'Invalid zrok share URL returned'}), 500
		if project_dir:
			meta_dir = os.path.join(project_dir, '.sureai')
			os.makedirs(meta_dir, exist_ok=True)
			deploy_path = os.path.join(meta_dir, 'deploy.json')
			data = {}
			if os.path.exists(deploy_path):
				try:
					with open(deploy_path, 'r', encoding='utf-8') as f:
						data = json.load(f)
				except Exception:
					data = {}
			data['frontend_url'] = public_url
			data['refreshed'] = True
			data['refreshed_at'] = datetime.now().isoformat()
			with open(deploy_path, 'w', encoding='utf-8') as f:
				json.dump(data, f, indent=2)
		return jsonify({'frontend_url': public_url, 'message': 'Zrok share refreshed successfully', 'refreshed': True})
	except Exception as e:
		logger.error(f"Error refreshing zrok share for task {task_id}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/tasks/<task_id>/can-resume', methods=['GET'])
@cross_origin()
def can_resume_task(task_id):
	"""Check if a task can be resumed from where it was interrupted"""
	try:
		_ensure_tasks_schema()
		
		# Get the task
		task = task_manager.get_task(task_id)
		if not task:
			return jsonify({'can_resume': False, 'error': 'Task not found'}), 404

		# Check task status
		task_status = None
		if isinstance(task, dict):
			task_status = task.get('status')
		else:
			task_status = getattr(task, 'status', None)

		# Allow resuming from any status where there's a current agent
		# This enables resuming from in_progress, failed, paused, etc.
		if task_status not in ['failed', 'in_progress', 'paused', 'received']:
			return jsonify({
				'can_resume': False, 
				'reason': f'Task status is {task_status}, cannot resume from this status'
			})

		# Check if there's a current agent
		current_agent = None
		if isinstance(task, dict):
			current_agent = task.get('current_agent')
		else:
			current_agent = getattr(task, 'current_agent', None)

		if not current_agent:
			# Try to get from monitor data
			try:
				monitor_data = _compute_monitor_data(task_id)
				if not isinstance(monitor_data, tuple):
					current_agent = monitor_data.get('current_agent')
			except Exception:
				pass

		# If still no current agent, try to determine from workflow sequence and completed agents
		if not current_agent:
			try:
				monitor_data = _compute_monitor_data(task_id)
				if not isinstance(monitor_data, tuple):
					workflow_sequence = monitor_data.get('workflow_sequence', [])
					completed_agents = monitor_data.get('completed_agents', [])
					if workflow_sequence and completed_agents:
						# Find the next agent after the last completed one
						for agent in workflow_sequence:
							if agent not in completed_agents:
								current_agent = agent
								break
			except Exception:
				pass

		if not current_agent:
			return jsonify({
				'can_resume': False,
				'reason': 'Could not determine the current agent'
			})

		# Check if there's a workflow sequence
		workflow_id = None
		if isinstance(task, dict):
			workflow_id = task.get('workflow_id')
		else:
			workflow_id = getattr(task, 'workflow_id', None)

		workflow_sequence = []
		if workflow_id:
			workflow = Workflow.query.get(workflow_id)
			if workflow and workflow.is_active:
				wf_dict = workflow.to_dict()
				workflow_sequence = wf_dict.get('agent_sequence', [])

		if not workflow_sequence:
			try:
				workflow_sequence = agent_manager.get_default_workflow_sequence()
			except Exception:
				pass

		if not workflow_sequence:
			return jsonify({
				'can_resume': False,
				'reason': 'No workflow sequence available'
			})

		if current_agent not in workflow_sequence:
			return jsonify({
				'can_resume': False,
				'reason': f'Agent {current_agent} not found in workflow sequence'
			})

		# Check if there's a user prompt
		user_prompt = None
		if isinstance(task, dict):
			user_prompt = task.get('user_prompt') or task.get('prompt', '')
		else:
			user_prompt = getattr(task, 'user_prompt', '') or getattr(task, 'prompt', '')

		if not user_prompt:
			return jsonify({
				'can_resume': False,
				'reason': 'No user prompt available'
			})

		return jsonify({
			'can_resume': True,
			'current_agent': current_agent,
			'workflow_sequence': workflow_sequence,
			'resume_sequence': workflow_sequence[workflow_sequence.index(current_agent):],
			'original_prompt': user_prompt
		})

	except Exception as e:
		logger.error(f"Error checking if task {task_id} can be resumed: {e}")
		return jsonify({'can_resume': False, 'error': 'Internal server error'}), 500

@bmad_bp.route('/api/tasks/<task_id>/tokens', methods=['GET'])
@cross_origin()
def get_task_tokens(task_id):
	"""Get token usage statistics for a specific task"""
	try:
		# Get token usage from token meter
		token_usage = token_meter.get_task_usage(task_id)
		
		if 'error' in token_usage:
			return jsonify({'error': token_usage['error']}), 500
		
		return jsonify(token_usage)
		
	except Exception as e:
		logger.error(f"Error getting token usage for task {task_id}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/tasks/<task_id>/files', methods=['GET'])
@cross_origin()
def get_task_files(task_id):
	"""List files under the task's project directory.

	Query params:
	- path: relative path under project root (default: '')
	- recursive: '1' to recurse (default: '1')
	- include_hidden: '1' to include dotfiles/dirs (default: '1')
	"""
	try:
		project_dir = resolve_project_dir(task_id)
		if not project_dir or not os.path.exists(project_dir):
			return jsonify({'files': [], 'project_dir': None})
		# Params
		rel = request.args.get('path', '').strip()
		recursive = request.args.get('recursive', '1') == '1'
		include_hidden = request.args.get('include_hidden', '1') == '1'
		# Resolve and secure
		base = os.path.realpath(project_dir)
		target = os.path.realpath(os.path.join(base, rel))
		if not target.startswith(base):
			return jsonify({'error': 'Invalid path'}), 400
		if not os.path.exists(target):
			return jsonify({'files': [], 'project_dir': project_dir, 'path': rel})
		# Build listing
		entries = []
		def should_include(name: str) -> bool:
			if include_hidden:
				return True
			return not name.startswith('.')
		if os.path.isfile(target):
			# Return single file entry
			stat = os.stat(target)
			entries.append({
				'name': os.path.basename(target),
				'path': os.path.relpath(target, base),
				'type': 'file',
				'size_bytes': stat.st_size,
				'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
				'is_hidden': os.path.basename(target).startswith('.')
			})
		else:
			if recursive:
				for root, dirs, files in os.walk(target):
					# Optionally filter hidden dirs
					if not include_hidden:
						dirs[:] = [d for d in dirs if should_include(d)]
					for fname in files:
						if not should_include(fname):
							continue
						full = os.path.join(root, fname)
						try:
							st = os.stat(full)
							entries.append({
								'name': os.path.basename(full),
								'path': os.path.relpath(full, base),
								'type': 'file',
								'size_bytes': st.st_size,
								'modified': datetime.fromtimestamp(st.st_mtime).isoformat(),
								'is_hidden': os.path.basename(full).startswith('.')
							})
						except Exception as e:
							logger.warning(f"Error stat file {full}: {e}")
							continue
			else:
				# Non-recursive: list direct children (files and directories)
				try:
					for name in os.listdir(target):
						if not should_include(name):
							continue
						full = os.path.join(target, name)
						st = os.stat(full)
						entry = {
							'name': name,
							'path': os.path.relpath(full, base),
							'type': 'dir' if os.path.isdir(full) else 'file',
							'modified': datetime.fromtimestamp(st.st_mtime).isoformat(),
							'is_hidden': name.startswith('.')
						}
						if os.path.isfile(full):
							entry['size_bytes'] = st.st_size
						entries.append(entry)
				except Exception as e:
					logger.warning(f"Error listing directory {target}: {e}")
		# Sort by path
		entries.sort(key=lambda x: x.get('path', ''))
		return jsonify({'files': entries, 'project_dir': project_dir, 'path': rel, 'recursive': recursive, 'include_hidden': include_hidden})
	except Exception as e:
		logger.error(f"Error getting files for task {task_id}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

@bmad_bp.route('/api/tasks/<task_id>/files/content', methods=['GET'])
@cross_origin()
def get_task_file_content(task_id):
	"""Read file content (read-only) under the task's project directory.

	Query params:
	- path: relative file path under project root (required)
	- max_bytes: limit read size (default: 200000)
	"""
	try:
		project_dir = resolve_project_dir(task_id)
		if not project_dir or not os.path.exists(project_dir):
			return jsonify({'error': 'Project not found'}), 404
		rel = (request.args.get('path') or '').strip()
		if not rel:
			return jsonify({'error': 'path is required'}), 400
		max_bytes = 200000
		try:
			max_bytes = int(request.args.get('max_bytes', str(max_bytes)))
		except Exception:
			pass
		base = os.path.realpath(project_dir)
		target = os.path.realpath(os.path.join(base, rel))
		if not target.startswith(base):
			return jsonify({'error': 'Invalid path'}), 400
		if not os.path.exists(target) or not os.path.isfile(target):
			return jsonify({'error': 'File not found'}), 404
		# Attempt to read as text
		truncated = False
		content = ''
		try:
			with open(target, 'rb') as f:
				data = f.read(max_bytes + 1)
				if len(data) > max_bytes:
					truncated = True
					data = data[:max_bytes]
				# Try utf-8 decode with replacement
				content = data.decode('utf-8', errors='replace')
		except Exception as e:
			return jsonify({'error': f'Failed to read file: {e}'}), 500
		return jsonify({'path': rel, 'content': content, 'truncated': truncated})
	except Exception as e:
		logger.error(f"Error reading file for task {task_id}: {e}")
		return jsonify({'error': 'Internal server error'}), 500

