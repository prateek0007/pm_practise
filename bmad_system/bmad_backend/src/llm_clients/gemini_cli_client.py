"""
Official Gemini CLI Client Module for BMAD System

This module implements direct integration with the official Gemini CLI tool
to provide CLI-like interaction with Gemini models, including direct file system access
and detailed logging that mirrors the interactive CLI experience.
"""

import os
import json
import time
import subprocess
import logging
from typing import Dict, List, Optional, Any, Callable, Tuple
from datetime import datetime
from src.utils.logger import get_logger
from src.config.timeout_config import get_agent_timeout_config, get_retry_delay
from src.llm_clients.gemini_api_key_manager import GeminiAPIKeyManager
import asyncio
import selectors
from subprocess import Popen, PIPE

logger = get_logger(__name__)

class GeminiCLIError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message

class GeminiCLIClient:
    """
    Official Gemini CLI Client that provides direct integration with the Gemini CLI tool
    with file system access and detailed logging that mirrors CLI interactive mode.
    """
    
    def __init__(self, api_key: str = None, model_name: str = "gemini-2.5-flash"):
        """
        Initialize the official Gemini CLI client
        
        Args:
            api_key: Gemini API key
            model_name: Model to use (default: gemini-2.5-flash)
        """
        self.model_name = model_name
        self.log_callback = None
        self.conversation_history = []
        self.mcp_args: List[str] = []  # CLI tokens to register MCP servers
        self._active_process: Optional[Popen] = None  # Track current running CLI process for cancellation
        
        # Initialize API key manager
        try:
            self.api_key_manager = GeminiAPIKeyManager()
            self._log_cli_output("INFO", "✅ API key manager initialized successfully")
        except Exception as e:
            self._log_cli_output("ERROR", f"❌ Failed to initialize API key manager: {str(e)}")
            # Create a minimal API key manager as fallback
            self.api_key_manager = None
        
        # Set initial API key if provided
        if api_key:
            try:
                if self.api_key_manager:
                    self.api_key_manager.add_api_key(api_key)
                    self._log_cli_output("INFO", "✅ Initial API key added successfully")
                else:
                    self._log_cli_output("WARNING", "⚠️ Cannot add API key - manager not initialized")
            except Exception as e:
                self._log_cli_output("ERROR", f"❌ Failed to add initial API key: {str(e)}")
        
        # Verify Gemini CLI is installed
        self._verify_gemini_cli()
        
        # Configure API key
        self._configure_api_key()
    
    def _verify_gemini_cli(self):
        """Verify that Gemini CLI is installed and accessible"""
        try:
            # Use shorter timeout and better error handling
            result = subprocess.run(['gemini', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                self._log_cli_output("INFO", f"✅ Gemini CLI found: {result.stdout.strip()}")
            else:
                self._log_cli_output("WARNING", f"⚠️ Gemini CLI check failed: {result.stderr}")
                # Don't raise exception, allow system to start
        except subprocess.TimeoutExpired:
            self._log_cli_output("WARNING", "⚠️ Gemini CLI verification timed out - CLI may be installed but unresponsive")
            # Don't raise exception, allow system to start
        except FileNotFoundError:
            self._log_cli_output("WARNING", "⚠️ Gemini CLI not found in PATH - install with: npm install -g @google/gemini-cli")
            # Don't raise exception, allow system to start
        except Exception as e:
            self._log_cli_output("WARNING", f"⚠️ Gemini CLI verification failed: {str(e)}")
            # Don't raise exception, allow system to start
        
        # Always log that the client is initializing regardless of CLI status
        self._log_cli_output("INFO", "📱 Gemini CLI client initialized (CLI verification completed)")
    
    def _configure_api_key(self):
        """Configure the API key for Gemini CLI"""
        try:
            # Ensure API key manager is properly initialized
            if not hasattr(self, 'api_key_manager') or self.api_key_manager is None:
                self._log_cli_output("ERROR", "❌ API key manager not initialized")
                return
            
            # Always fetch current key fresh before each configuration
            current_key = self.api_key_manager.get_current_key()
            if current_key:
                # Set the API key as environment variable
                os.environ['GEMINI_API_KEY'] = current_key
                self._log_cli_output("INFO", f"🔑 API key configured for Gemini CLI (key {self.api_key_manager.current_key_index + 1} of {len(self.api_key_manager.api_keys)})")
            else:
                # Avoid noisy warning in normal operation; debug level is enough
                self._log_cli_output("DEBUG", "No API keys available for Gemini CLI configuration")
                # Try to load from environment as fallback
                env_key = os.getenv('GEMINI_API_KEY')
                if env_key:
                    self._log_cli_output("INFO", "🔑 Using API key from environment variable")
                    os.environ['GEMINI_API_KEY'] = env_key
                else:
                    self._log_cli_output("ERROR", "❌ No API keys available and no environment variable set")
        except Exception as e:
            self._log_cli_output("ERROR", f"❌ Failed to configure API key: {str(e)}")
            # Try to use environment variable as last resort
            env_key = os.getenv('GEMINI_API_KEY')
            if env_key:
                self._log_cli_output("INFO", "🔑 Using API key from environment variable as fallback")
                os.environ['GEMINI_API_KEY'] = env_key
    
    def set_log_callback(self, callback: Callable[[str, str], None]):
        """
        Set a callback function for logging CLI-like output
        
        Args:
            callback: Function that takes (log_level, message) parameters
        """
        self.log_callback = callback
    
    def _log_cli_output(self, level: str, message: str):
        # Logs CLI-like output with timestamp and calls custom callback if set
        """Log CLI-like output"""
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted_message = f"[{timestamp}] {message}"
            
            # Log to standard logger
            if level == "INFO":
                logger.info(formatted_message)
            elif level == "ERROR":
                logger.error(formatted_message)
            elif level == "WARNING":
                logger.warning(formatted_message)
            elif level == "DEBUG":
                logger.debug(formatted_message)
            
            # Call custom callback if set
            if self.log_callback:
                self.log_callback(level, formatted_message)
        except Exception as e:
            # Fallback logging if logger fails
            try:
                print(f"[{level}] {message}")
            except:
                pass
    
    def start_chat_session(self, system_prompt: str = None):
        # Initializes new chat session and clears conversation history
        """
        Start a new chat session with Gemini CLI
        
        Args:
            system_prompt: Optional system prompt to initialize the session
        """
        try:
            self._log_cli_output("INFO", "🚀 Starting Gemini CLI chat session")
            
            # Clear conversation history
            self.conversation_history = []
            
            if system_prompt:
                self._log_cli_output("INFO", f"📝 System prompt: {system_prompt[:100]}...")
            
            self._log_cli_output("INFO", "✅ Chat session started successfully")
            
        except Exception as e:
            self._log_cli_output("ERROR", f"❌ Failed to start chat session: {str(e)}")
            raise
    
    async def send_message(self, message: str, context: Dict[str, Any] = None, agent_name: str = None, temperature: Optional[float] = None) -> str:
        """
        Send a message to Gemini CLI and get response
        
        Args:
            message: The message to send
            context: Optional context information
            agent_name: Name of the agent for timeout configuration (optional)
            temperature: Optional sampling temperature (advisory only; CLI has no flag)
            
        Returns:
            The model's response
        """
        try:
            # Log the input
            self._log_cli_output("INFO", f"📤 Sending message to {self.model_name}")
            self._log_cli_output("DEBUG", f"💬 Message length: {len(message)} characters")
            
            if context:
                self._log_cli_output("DEBUG", f"📋 Context provided: {list(context.keys())}")
            
            if agent_name:
                self._log_cli_output("DEBUG", f"🤖 Agent: {agent_name}")
            if temperature is not None:
                self._log_cli_output("DEBUG", f"🌡️ Temperature (advisory): {temperature}")
            
            # Prepare the full message with context
            full_message = message
            if context:
                context_str = "\n\n=== CONTEXT ===\n"
                for key, value in context.items():
                    context_str += f"{key}: {value}\n"
                full_message = context_str + "\n\n=== MESSAGE ===\n" + message
            
            # Determine overall timeout for async guard
            if agent_name:
                timeout_config = get_agent_timeout_config(agent_name)
                overall_cap = timeout_config.get('overall', 900)
            else:
                overall_cap = 900

            # Send message to Gemini CLI
            start_time = time.time()
            self._log_cli_output("INFO", "⏳ Waiting for model response...")
            
            # Execute Gemini CLI command with agent-specific timeout in a background thread
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self._execute_gemini_cli_command,
                        full_message,
                        None,
                        2,
                        agent_name,
                        None  # do not pass CLI flag for temperature
                    ),
                    timeout=overall_cap + 5  # small cushion above internal cap
                )
            except asyncio.TimeoutError:
                self._log_cli_output("ERROR", f"❌ Async overall timeout exceeded ({overall_cap}s) for agent {agent_name or 'unknown'}")
                raise GeminiCLIError("timeout", f"Overall timeout exceeded after {overall_cap}s")
            
            end_time = time.time()
            response_time = end_time - start_time
            
            # Log the response
            self._log_cli_output("INFO", f"✅ Response received in {response_time:.2f} seconds")
            if isinstance(response, str):
                self._log_cli_output("DEBUG", f"📝 Response length: {len(response)} characters")
            else:
                self._log_cli_output("WARNING", "📝 Response was not a string; coercing to 'OK'")
                response = "OK"
            
            # Add to conversation history
            self.conversation_history.append({"role": "user", "content": message})
            self.conversation_history.append({"role": "assistant", "content": response})
            
            return response or "OK"
            
        except GeminiCLIError as ge:
            self._log_cli_output("ERROR", f"❌ Gemini CLI error [{ge.code}]: {ge.message}")
            raise
        except Exception as e:
            error_msg = str(e)
            self._log_cli_output("ERROR", f"❌ Error sending message: {error_msg}")
            raise
    
    def generate_single_response(self, prompt: str, context: Dict[str, Any] = None, working_dir: str = None, agent_name: str = None, temperature: Optional[float] = None) -> str:
        """
        Generate a single response without maintaining chat history
        
        Args:
            prompt: The prompt to send
            context: Optional context information
            working_dir: Working directory for the command (optional)
            agent_name: Name of the agent for timeout configuration (optional)
            temperature: Optional sampling temperature (advisory only; CLI has no flag)
            
        Returns:
            The model's response
        """
        try:
            # Log the input
            self._log_cli_output("INFO", f"📤 Generating single response with {self.model_name}")
            self._log_cli_output("DEBUG", f"💬 Prompt length: {len(prompt)} characters")
            
            if context:
                self._log_cli_output("DEBUG", f"📋 Context provided: {list(context.keys())}")
            
            if working_dir:
                self._log_cli_output("DEBUG", f"📁 Working directory: {working_dir}")
            
            if agent_name:
                self._log_cli_output("DEBUG", f"🤖 Agent: {agent_name}")
            if temperature is not None:
                self._log_cli_output("DEBUG", f"🌡️ Temperature (advisory): {temperature}")
            
            # Prepare the full prompt with context
            full_prompt = prompt
            if context:
                context_str = "\n\n=== CONTEXT ===\n"
                for key, value in context.items():
                    context_str += f"{key}: {value}\n"
                full_prompt = context_str + "\n\n=== PROMPT ===\n" + prompt
            
            # Generate response and track timing
            start_time = time.time()
            self._log_cli_output("INFO", "⏳ Generating response...")
            
            # Execute Gemini CLI command with agent-specific timeout
            response = self._execute_gemini_cli_command(full_prompt, working_dir, agent_name=agent_name, temperature=None)
            
            end_time = time.time()
            response_time = end_time - start_time
            
            # Log the response
            self._log_cli_output("INFO", f"✅ Response generated in {response_time:.2f} seconds")
            self._log_cli_output("DEBUG", f"📝 Response length: {len(response)} characters")
            
            return response
            
        except GeminiCLIError as ge:
            self._log_cli_output("ERROR", f"❌ Error generating response [{ge.code}]: {ge.message}")
            raise
        except Exception as e:
            error_msg = str(e)
            self._log_cli_output("ERROR", f"❌ Error generating response: {error_msg}")
            raise
    
    def _execute_gemini_cli_command(self, prompt: str, working_dir: str = None, max_retries: int = 2, agent_name: str = None, temperature: Optional[float] = None) -> str:
        """
        Execute a command using the official Gemini CLI with retry logic
        
        Args:
            prompt: The prompt to send to Gemini CLI
            working_dir: Working directory for the command (optional)
            max_retries: Maximum number of retry attempts (default: 2)
            agent_name: Name of the agent for timeout configuration (optional)
            temperature: Deprecated/no-op for CLI (kept for API compatibility)
            
        Returns:
            The response from Gemini CLI
        """
        
        # Skip the preflight check since we know Gemini CLI is installed
        # This prevents timeout issues when the CLI is slow to respond to --version
        
        last_exception = None
        
        def _build_include_dirs_args() -> List[str]:
            include_args: List[str] = []
            dirs: List[str] = []
            if working_dir:
                dirs.append(working_dir)
                # Also include common subdirectories that might be created in the project
                try:
                    # Check if backend/ and frontend/ directories exist in the working directory
                    backend_dir = os.path.join(working_dir, 'backend')
                    frontend_dir = os.path.join(working_dir, 'frontend')
                    sureai_dir = os.path.join(working_dir, '.sureai')
                    
                    if os.path.exists(backend_dir):
                        dirs.append(backend_dir)
                    if os.path.exists(frontend_dir):
                        dirs.append(frontend_dir)
                    if os.path.exists(sureai_dir):
                        dirs.append(sureai_dir)
                        
                    # Also include any other subdirectories that might exist
                    for item in os.listdir(working_dir):
                        item_path = os.path.join(working_dir, item)
                        if os.path.isdir(item_path) and item not in ['.git', '__pycache__', '.pytest_cache']:
                            dirs.append(item_path)
                except Exception as e:
                    # Log but don't fail if we can't scan directories
                    pass
            
            # De-duplicate
            seen = set()
            for d in dirs:
                if d and d not in seen:
                    include_args.extend(['--include-directories', d])
                    seen.add(d)
            
            # Log the directories being included for debugging
            if dirs:
                self._log_cli_output("DEBUG", f"📁 Including directories: {', '.join(dirs)}")
            
            return include_args

        # Get timeout configuration based on agent name
        if agent_name:
            timeout_config = get_agent_timeout_config(agent_name)
            max_retries = timeout_config.get('max_retries', max_retries)
            base_timeout = timeout_config.get('timeout', 300)
            retry_timeout = timeout_config.get('retry_timeout', base_timeout)
            overall_cap = timeout_config.get('overall', base_timeout + retry_timeout)
        else:
            base_timeout = 300
            retry_timeout = 600
            overall_cap = 900
        
        def classify_error(stderr_text: str) -> Optional[GeminiCLIError]:
            if not stderr_text:
                return None
            s = stderr_text.lower()
            if any(k in s for k in ["exceeded your current quota", "quota exhausted", "quota exceeded", "status: 429", "resource_exhausted"]):
                return GeminiCLIError("quota_exceeded", "API Quota Exceeded (429). Attempting key rotation.")
            if any(k in s for k in ["rate limit", "too many requests"]):
                return GeminiCLIError("rate_limit", "Rate limit encountered (429). Backing off and retrying.")
            if any(k in s for k in ["unauthorized", "invalid api key", "status: 401", "forbidden", "status: 403"]):
                return GeminiCLIError("unauthorized", "Unauthorized or invalid API key (401/403).")
            if any(k in s for k in ["timeout", "timed out"]):
                return GeminiCLIError("timeout", "Command timed out.")
            if any(k in s for k in ["emptystreamerror", "model stream ended", "invalid chunk", "missing finish reason"]):
                return GeminiCLIError("stream_error", "Stream error from model.")
            return None
        
        overall_start = time.time()
        
        for attempt in range(max_retries + 1):
            try:
                # Abort if we've exceeded overall cap
                elapsed = time.time() - overall_start
                if elapsed >= overall_cap:
                    raise Exception(f"Overall timeout exceeded ({int(elapsed)}s >= {overall_cap}s)")
                
                # Per-attempt timeout budget
                timeout_duration = base_timeout if attempt == 0 else retry_timeout
                remaining_overall = overall_cap - elapsed
                timeout_duration = max(5, min(timeout_duration, int(remaining_overall)))
                # Idle timeout budget from config (if available)
                try:
                    idle_timeout = get_agent_timeout_config(agent_name or "").get('idle', 120)
                except Exception:
                    idle_timeout = 120
 
                # 1) Prefer STDIN mode to minimize sandbox warnings
                stdin_cmd = ['gemini', '--yolo', '--model', self.model_name] + _build_include_dirs_args() + (self.mcp_args or [])
                self._log_cli_output("DEBUG", f"🔧 Executing (stdin mode): {' '.join(stdin_cmd)} (Attempt {attempt + 1}/{max_retries + 1})")
                stdout_text, stderr_text, return_code = self._run_cli_with_streaming(
                    cmd=stdin_cmd,
                    input_text=prompt,
                    timeout_seconds=timeout_duration,
                    idle_timeout_seconds=idle_timeout,
                    cwd=working_dir
                )
                self._log_cli_output("DEBUG", f"📄 CLI stdout length: {len(stdout_text)} | stderr length: {len(stderr_text)}")

                if return_code == 0:
                    self._log_cli_output("INFO", f"✅ Gemini CLI (stdin mode) completed successfully (Attempt {attempt + 1})")
                    # On successful return code, do not treat stderr as fatal; prefer stdout
                    if stdout_text:
                        return stdout_text
                    if stderr_text:
                        # Return stderr as content if stdout is empty
                        return stderr_text
                    return "OK"
                else:
                    # Non-zero return code: parse error before fallback
                    err = classify_error(stderr_text)
                    if err:
                        raise err
                    # Keep stderr out of chat; log concise message
                    self._log_cli_output("WARNING", "Gemini CLI (stdin mode) failed; trying arg mode")

                # 2) Fall back to ARG-MODE
                base_arg = ['gemini', '--yolo', '--model', self.model_name]
                arg_cmd = base_arg + _build_include_dirs_args() + (self.mcp_args or []) + ['-p', prompt]
                self._log_cli_output("DEBUG", f"🔧 Executing (arg mode): {' '.join(base_arg)} -p <prompt> (Attempt {attempt + 1}/{max_retries + 1})")
                try:
                    # Use Popen for better process control and cleanup
                    env = dict(os.environ, GEMINI_API_KEY=self.api_key_manager.get_current_key(), CI="1") if self.api_key_manager.get_current_key() else (dict(os.environ, GEMINI_API_KEY=os.getenv('GEMINI_API_KEY'), CI="1") if os.getenv('GEMINI_API_KEY') else dict(os.environ, CI="1"))
                    
                    process = Popen(
                        arg_cmd,
                        stdout=PIPE,
                        stderr=PIPE,
                        text=True,
                        cwd=working_dir,
                        env=env
                    )
                    
                    try:
                        stdout, stderr = process.communicate(timeout=timeout_duration)
                        return_code = process.returncode
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=1)
                        raise
                    
                    arg_result = type('obj', (object,), {
                        'stdout': stdout,
                        'stderr': stderr,
                        'returncode': return_code
                    })()
                    arg_stdout = (arg_result.stdout or "").strip()
                    arg_stderr = (arg_result.stderr or "").strip()
                    self._log_cli_output("DEBUG", f"📄 Arg-mode stdout length: {len(arg_stdout)} | stderr length: {len(arg_stderr)}")
                    if arg_result.returncode == 0:
                        self._log_cli_output("INFO", f"✅ Gemini CLI (arg mode) completed successfully (Attempt {attempt + 1})")
                        if arg_stdout:
                            return arg_stdout
                        if arg_stderr:
                            err = classify_error(arg_stderr)
                            if err:
                                raise err
                            return arg_stderr
                        return "OK"
                    else:
                        err = classify_error(arg_stderr)
                        if err:
                            raise err
                        self._log_cli_output("ERROR", "❌ Gemini CLI (arg mode) failed")
                        raise Exception("Gemini CLI failed")
                except GeminiCLIError as ge:
                    # Handle quota exhausted: rotate and immediately retry within this method
                    if ge.code == "quota_exceeded":
                        self._log_cli_output("WARNING", "🔄 Quota exhausted detected (arg mode) - rotating key and retrying automatically")
                        before_idx = self.api_key_manager.current_key_index if self.api_key_manager else -1
                        rotated = self.handle_api_error(ge.message)
                        if rotated:
                            after_idx = self.api_key_manager.current_key_index if self.api_key_manager else -1
                            self._log_cli_output("INFO", f"🔁 Rotated from key{before_idx + 1} to key{after_idx + 1} (arg mode). Resuming current agent.")
                            # After rotation, retry this attempt without incrementing outer loop unnecessarily
                            time.sleep(0.5)
                            continue
                        else:
                            self._log_cli_output("ERROR", "❌ Key rotation failed or no more keys available")
                            raise GeminiCLIError("no_keys_available", "No usable API keys available - workflow must be terminated")
                    elif ge.code == "stream_error":
                        self._log_cli_output("WARNING", f"🔄 Stream error detected, retrying (attempt {attempt + 1}/{max_retries + 1})")
                        if attempt < max_retries:
                            time.sleep(2)  # Brief delay before retry
                            continue
                        else:
                            self._log_cli_output("ERROR", "❌ Stream error retries exhausted")
                            raise ge
                    raise
                except Exception as arg_exc:
                    self._log_cli_output("ERROR", f"❌ Gemini CLI (arg mode) error: {arg_exc}")
                 
            except subprocess.TimeoutExpired as e:
                last_exception = e
                self._log_cli_output("WARNING", f"⏰ Gemini CLI command timed out (Attempt {attempt + 1}/{max_retries + 1})")
                if attempt < max_retries:
                    retry_delay = get_retry_delay('timeout')
                    self._log_cli_output("INFO", f"🔄 Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    self._log_cli_output("ERROR", "❌ All retry attempts failed - Gemini CLI command timed out")
                    raise GeminiCLIError("timeout", "Gemini CLI command timed out after all retry attempts")
            except GeminiCLIError as ge:
                # Log concise error line
                self._log_cli_output("ERROR", f"❌ Gemini error [{ge.code}] on attempt {attempt + 1}")
                
                # Handle quota exhausted: rotate and continue automatically
                if ge.code == "quota_exceeded":
                    self._log_cli_output("INFO", "API quota exceeded; attempting automatic key rotation and retry")
                    before_idx = self.api_key_manager.current_key_index if self.api_key_manager else -1
                    rotated = self.handle_api_error(ge.message)
                    if rotated:
                        after_idx = self.api_key_manager.current_key_index if self.api_key_manager else -1
                        self._log_cli_output("INFO", f"🔁 Rotated from key{before_idx + 1} to key{after_idx + 1}. Resuming current agent.")
                        # Do not count this as a failed attempt; try again with new key
                        time.sleep(0.5)
                        continue
                    else:
                        raise GeminiCLIError("no_keys_available", "No usable API keys available - workflow must be terminated")
                
                # Do not retry unauthorized errors
                if ge.code == "unauthorized" or attempt >= max_retries:
                    raise
                
                retry_delay = get_retry_delay('error')
                self._log_cli_output("INFO", f"🔄 Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            except Exception as e:
                last_exception = e
                self._log_cli_output("ERROR", f"❌ Failed to execute Gemini CLI command (Attempt {attempt + 1}): {str(e)}")
                if attempt < max_retries:
                    retry_delay = get_retry_delay('error')
                    self._log_cli_output("INFO", f"🔄 Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    raise
        
        # If we get here, all retries failed
        raise last_exception if last_exception else GeminiCLIError("unknown", "Unknown error occurred")

    def _run_cli_with_streaming(self, cmd: List[str], input_text: str, timeout_seconds: int, idle_timeout_seconds: int, cwd: Optional[str]) -> Tuple[str, str, int]:
        """
        Run the CLI command with streaming IO to enforce idle timeouts and avoid hangs.
        Returns (stdout, stderr, return_code).
        """
        start_time = time.time()
        last_output_time = start_time
        # Build environment using the latest current key to avoid stale usage
        ck = self.api_key_manager.get_current_key() if self.api_key_manager else None
        env = dict(os.environ, GEMINI_API_KEY=ck, CI="1") if ck else (dict(os.environ, GEMINI_API_KEY=os.getenv('GEMINI_API_KEY'), CI="1") if os.getenv('GEMINI_API_KEY') else dict(os.environ, CI="1"))
        ck2 = self.api_key_manager.get_current_key() if self.api_key_manager else None
        env = dict(os.environ, GEMINI_API_KEY=ck2, CI="1") if ck2 else (dict(os.environ, GEMINI_API_KEY=os.getenv('GEMINI_API_KEY'), CI="1") if os.getenv('GEMINI_API_KEY') else dict(os.environ, CI="1"))

        process: Popen = Popen(
            cmd,
            stdin=PIPE,
            stdout=PIPE,
            stderr=PIPE,
            text=True,
            bufsize=1,
            cwd=cwd,
            env=env
        )
        # Expose active process for external cancellation
        try:
            self._active_process = process
        except Exception:
            pass

        selector = selectors.DefaultSelector()
        if process.stdout:
            selector.register(process.stdout, selectors.EVENT_READ)
        if process.stderr:
            selector.register(process.stderr, selectors.EVENT_READ)

        try:
            # Send input immediately
            if process.stdin:
                process.stdin.write(input_text)
                process.stdin.flush()
                process.stdin.close()

            stdout_chunks: List[str] = []
            stderr_chunks: List[str] = []

            while True:
                # Check overall timeout
                now = time.time()
                if now - start_time > timeout_seconds:
                    process.kill()
                    raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout_seconds)

                # Check idle timeout
                if now - last_output_time > idle_timeout_seconds:
                    process.kill()
                    raise subprocess.TimeoutExpired(cmd=cmd, timeout=idle_timeout_seconds)

                if process.poll() is not None and not selector.get_map():
                    break

                events = selector.select(timeout=0.5)
                if not events:
                    continue

                for key, _ in events:
                    stream = key.fileobj
                    try:
                        data = stream.readline()
                    except Exception:
                        data = ''
                    if not data:
                        # Stream closed; unregister
                        try:
                            selector.unregister(stream)
                        except Exception:
                            pass
                        continue
                    last_output_time = time.time()
                    if stream is process.stdout:
                        stdout_chunks.append(data)
                    else:
                        stderr_chunks.append(data)

            # Ensure process is reaped with better cleanup
            try:
                return_code = process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                # Force kill if wait times out
                process.kill()
                return_code = process.wait(timeout=1)
            
            return ("".join(stdout_chunks).strip(), "".join(stderr_chunks).strip(), return_code)
        finally:
            # Clear active process and ensure kill
            try:
                if getattr(self, "_active_process", None) is process:
                    self._active_process = None
            except Exception:
                pass
            # Enhanced cleanup to prevent zombie processes
            try:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=1)
                elif process.returncode is None:
                    # Process might be a zombie, try to reap it
                    try:
                        process.wait(timeout=0.1)
                    except subprocess.TimeoutExpired:
                        pass
            except (OSError, subprocess.TimeoutExpired):
                # Process already terminated or can't be reaped
                pass
            except Exception:
                # Any other cleanup error, ignore
                pass
            
            try:
                selector.close()
            except Exception:
                pass

    def cancel_active(self) -> bool:
        """Attempt to cancel any currently running Gemini CLI process immediately."""
        try:
            proc = getattr(self, "_active_process", None)
            if proc is not None:
                try:
                    proc.kill()
                except Exception:
                    pass
                try:
                    proc.wait(timeout=1)
                except Exception:
                    pass
                self._active_process = None
                self._log_cli_output("WARNING", "⛔ Gemini CLI process cancelled by request")
                return True
        except Exception as _e:
            try:
                self._log_cli_output("WARNING", f"Cancel attempt encountered error: {_e}")
            except Exception:
                pass
        return False
    
    def switch_model(self, model_name: str):
        """
        Switch to a different Gemini model
        
        Args:
            model_name: Name of the model to switch to
        """
        try:
            self._log_cli_output("INFO", f"🔄 Switching from {self.model_name} to {model_name}")
            
            old_model = self.model_name
            self.model_name = model_name
            
            self._log_cli_output("INFO", f"✅ Successfully switched to {model_name}")
            
        except Exception as e:
            self._log_cli_output("ERROR", f"❌ Failed to switch model: {str(e)}")
            raise
    
    def add_api_key(self, api_key: str) -> bool:
        """Add a new API key to the manager"""
        try:
            success = self.api_key_manager.add_api_key(api_key)
            if success:
                self._log_cli_output("INFO", f"✅ Added new API key (total: {len(self.api_key_manager.api_keys)})")
            return success
        except Exception as e:
            self._log_cli_output("ERROR", f"❌ Error adding API key: {e}")
            return False
    
    def update_api_key_at_position(self, api_key: str, position: int) -> bool:
        """Update an API key at a specific position (0=primary, 1=other1, 2=other2)"""
        try:
            success = self.api_key_manager.update_api_key_at_position(api_key, position)
            if success:
                position_names = ["primary", "other1", "other2"]
                self._log_cli_output("INFO", f"✅ Updated {position_names[position]} API key at position {position}")
            return success
        except Exception as e:
            self._log_cli_output("ERROR", f"❌ Error updating API key at position {position}: {e}")
            return False
    
    def remove_api_key(self, api_key: str) -> bool:
        """Remove an API key from the manager"""
        try:
            success = self.api_key_manager.remove_api_key(api_key)
            if success:
                self._log_cli_output("INFO", f"✅ Removed API key (remaining: {len(self.api_key_manager.api_keys)})")
            return success
        except Exception as e:
            self._log_cli_output("ERROR", f"❌ Error removing API key: {e}")
            return False
    
    def get_api_key_status(self) -> Dict[str, Any]:
        """Get the current status of all API keys"""
        return self.api_key_manager.get_key_status()
    
    def reset_exhausted_keys(self):
        """Reset all exhausted key statuses"""
        try:
            self.api_key_manager.reset_exhausted_keys()
            self._log_cli_output("INFO", "✅ Reset all exhausted key statuses")
        except Exception as e:
            self._log_cli_output("ERROR", f"❌ Error resetting exhausted keys: {e}")
    
    def update_api_key(self, api_key: str):
        """
        Update the API key (for backward compatibility)
        
        Args:
            api_key: New API key
        """
        try:
            self._log_cli_output("INFO", "🔑 Updating API key")
            # Add the new key and set it as current
            if self.api_key_manager.add_api_key(api_key):
                # Set this as the current key
                self.api_key_manager.current_key_index = len(self.api_key_manager.api_keys) - 1
                self._configure_api_key()
                self._log_cli_output("INFO", "✅ API key updated successfully")
            else:
                self._log_cli_output("ERROR", "❌ Failed to add new API key")
        except Exception as e:
            self._log_cli_output("ERROR", f"❌ Failed to update API key: {str(e)}")
            raise
    
    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """Get the conversation history"""
        return self.conversation_history.copy()
    
    def clear_conversation_history(self):
        """Clear the conversation history"""
        self.conversation_history = []
        self._log_cli_output("INFO", "🗑️ Conversation history cleared")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model"""
        try:
            api_key_configured = False
            api_keys_count = 0
            available_keys_count = 0
            
            if hasattr(self, 'api_key_manager') and self.api_key_manager is not None:
                try:
                    api_key_configured = bool(self.api_key_manager.get_current_key())
                    api_keys_count = len(self.api_key_manager.api_keys)
                    available_keys_count = self.api_key_manager.get_available_keys_count()
                except Exception:
                    # Fallback to safe defaults if API key manager has issues
                    pass
            
            return {
                "model_name": getattr(self, 'model_name', 'gemini-1.5-flash'),
                "api_key_configured": api_key_configured,
                "conversation_history_length": len(getattr(self, 'conversation_history', [])),
                "api_keys_count": api_keys_count,
                "available_keys_count": available_keys_count
            }
        except Exception as e:
            # Return safe defaults if anything fails
            return {
                "model_name": "gemini-1.5-flash",
                "api_key_configured": False,
                "conversation_history_length": 0,
                "api_keys_count": 0,
                "available_keys_count": 0
            }
    
    def save_conversation(self, file_path: str):
        """
        Save the conversation history to a file
        
        Args:
            file_path: Path to save the conversation
        """
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.conversation_history, f, indent=2, ensure_ascii=False)
            
            self._log_cli_output("INFO", f"💾 Conversation saved to {file_path}")
            
        except Exception as e:
            self._log_cli_output("ERROR", f"❌ Failed to save conversation: {str(e)}")
            raise
    
    def load_conversation(self, file_path: str):
        """
        Load conversation history from a file
        
        Args:
            file_path: Path to load the conversation from
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.conversation_history = json.load(f)
            
            self._log_cli_output("INFO", f"📂 Conversation loaded from {file_path}")
            
        except Exception as e:
            self._log_cli_output("ERROR", f"❌ Failed to load conversation: {str(e)}")
            raise

    def set_mcp_servers(self, servers: List[Dict[str, Any]]):
        """Configure MCP servers to be passed to Gemini CLI as flags on every call.
        Expected server dicts contain: name, command, enabled (bool)."""
        try:
            args: List[str] = []
            for s in servers or []:
                try:
                    if not s.get('enabled', True):
                        continue
                    name = s.get('name')
                    cmd = s.get('command')
                    if name and cmd:
                        args.append(f"--mcp={name}={cmd}")
                except Exception:
                    continue
            self.mcp_args = args
            self._log_cli_output("INFO", f"🔧 Configured {len(self.mcp_args)} MCP server flags for Gemini CLI")
        except Exception as e:
            self._log_cli_output("ERROR", f"Failed to configure MCP servers: {e}")
    
    def handle_api_error(self, error_message: str) -> bool:
        """
        Handle API errors and automatically rotate keys if needed
        
        Args:
            error_message: The error message from the API
            
        Returns:
            True if key rotation was performed and a new session should be started
        """
        try:
            current_key = self.api_key_manager.get_current_key()
            if not current_key:
                return False
            
            # Check if this is a quota exhaustion error that requires key rotation
            if self.api_key_manager.handle_api_error(error_message, current_key):
                # Key was rotated successfully, announce rotation from -> to with indices for UI
                try:
                    old_idx = self.api_key_manager.api_keys.index(current_key) if current_key in self.api_key_manager.api_keys else -1
                except Exception:
                    old_idx = -1
                try:
                    new_idx = self.api_key_manager.current_key_index
                except Exception:
                    new_idx = -1
                if old_idx >= 0 and new_idx >= 0:
                    self._log_cli_output("INFO", f"🔁 Key rotated from {old_idx + 1} to {new_idx + 1}")
                else:
                    self._log_cli_output("INFO", "🔁 Key rotated to next available key")
                # Key was rotated, need to restart session
                self._log_cli_output("WARNING", "🔄 API key rotated due to quota exhaustion")
                self._log_cli_output("INFO", "🔄 Restarting Gemini CLI session with new key")
                
                # Reconfigure with new key
                self._configure_api_key()
                
                # Clear conversation history for new session
                self.conversation_history.clear()
                
                return True
            
            return False
            
        except Exception as e:
            self._log_cli_output("ERROR", f"❌ Error handling API error: {e}")
            return False
    
    def restart_session_with_new_key(self):
        """
        Restart the Gemini CLI session with a new API key
        This is called when a key is rotated due to quota exhaustion
        """
        try:
            self._log_cli_output("INFO", "🔄 Restarting session with new API key")
            
            # Reconfigure with current key
            self._configure_api_key()
            
            # Clear conversation history
            self.conversation_history.clear()
            
            # Start new chat session
            self.start_chat_session()
            
            self._log_cli_output("INFO", "✅ Session restarted successfully with new API key")
            
        except Exception as e:
            self._log_cli_output("ERROR", f"❌ Error restarting session: {e}")
            raise

    def env_for_exec(self) -> Dict[str, Any]:
        """Return environment suitable for CLI executions, including optional zrok vars."""
        env = os.environ.copy()
        try:
            current_key = self.api_key_manager.get_current_key()
            if current_key:
                env['GEMINI_API_KEY'] = current_key
            else:
                # Fallback to environment variable
                env_key = os.getenv('GEMINI_API_KEY')
                if env_key:
                    env['GEMINI_API_KEY'] = env_key
        except Exception as e:
            # Fallback to environment variable if API key manager fails
            env_key = os.getenv('GEMINI_API_KEY')
            if env_key:
                env['GEMINI_API_KEY'] = env_key
        
        if os.environ.get('ZROK_API_ENDPOINT'):
            env['ZROK_API_ENDPOINT'] = os.environ['ZROK_API_ENDPOINT']
        if os.environ.get('ZROK_ACCOUNT_TOKEN'):
            env['ZROK_ACCOUNT_TOKEN'] = os.environ['ZROK_ACCOUNT_TOKEN']
        env['CI'] = env.get('CI', '1')
        return env

