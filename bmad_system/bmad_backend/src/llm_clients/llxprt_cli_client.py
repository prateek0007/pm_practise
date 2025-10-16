"""
LLXPRT (llxprt-code) CLI Client for BMAD System

This client integrates with the open-source llxprt CLI (a fork of gemini-cli)
to run prompts against OpenRouter-supported models. It mirrors the
GeminiCLIClient API where practical so it can be swapped per agent.

Assumptions based on upstream:
- Binary name: `llxprt` (installed via npm i -g @vybestack/llxprt-code)
- Accepts `--model` and stdin prompt (like gemini-cli)
- Auth via OPENROUTER_API_KEY; base URL configurable via OPENROUTER_BASE_URL
- Optional provider selection via PROVIDER (e.g., 'openai')
"""

import os
import json
import time
import subprocess
from typing import Dict, List, Optional, Any, Callable, Tuple
from datetime import datetime
import selectors
from subprocess import Popen, PIPE

from src.utils.logger import get_logger
from src.config.timeout_config import get_agent_timeout_config, get_retry_delay

logger = get_logger(__name__)


class LlxprtCLIError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


class LlxprtCLIClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "qwen/qwen3-coder",
        base_url: str = "https://openrouter.ai/api/v1",
        provider: str = "openai",
    ):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.model_name = model_name
        self.base_url = base_url or os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        self.provider = provider or os.getenv("PROVIDER", "openai")
        self.log_callback: Optional[Callable[[str, str], None]] = None
        self.mcp_args: List[str] = []

        # Load persisted settings if envs not set and no explicit api_key
        if not self.api_key:
            try:
                cfg = self._read_settings()
                if isinstance(cfg, dict):
                    self.api_key = cfg.get('apiKey') or cfg.get('OPENROUTER_API_KEY') or self.api_key
                    self.base_url = cfg.get('baseUrl') or cfg.get('OPENROUTER_BASE_URL') or self.base_url
                    self.provider = cfg.get('provider') or cfg.get('PROVIDER') or self.provider
                    m = cfg.get('model') or cfg.get('model_name')
                    if m:
                        self.model_name = m
            except Exception as _e:
                logger.warning(f"Could not load LLXPRT settings: {_e}")

        self._verify_cli()
        if self.api_key:
            self._configure_api_key()
        else:
            logger.warning("No OPENROUTER_API_KEY provided. LLXPRT client will not be functional.")

    # --- settings persistence helpers ---
    def _settings_path(self) -> str:
        home = os.environ.get('HOME', '/root')
        return os.path.join(home, '.llxprt', 'settings.json')

    def _ensure_settings_dir(self):
        try:
            path = self._settings_path()
            os.makedirs(os.path.dirname(path), exist_ok=True)
        except Exception as e:
            logger.warning(f"Could not create ~/.llxprt: {e}")

    def _read_settings(self) -> Dict[str, Any]:
        path = self._settings_path()
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read LLXPRT settings.json: {e}")
        return {}

    def _write_settings(self, data: Dict[str, Any]) -> bool:
        self._ensure_settings_dir()
        path = self._settings_path()
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to write LLXPRT settings.json: {e}")
            return False

    def _verify_cli(self):
        try:
            result = subprocess.run(["llxprt", "--version"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                self._log("INFO", f"✅ llxprt CLI found: {result.stdout.strip()}")
            else:
                self._log("WARNING", f"⚠️ llxprt CLI check failed: {result.stderr or 'unknown error'}")
        except subprocess.TimeoutExpired:
            self._log("WARNING", "⚠️ llxprt CLI verification timed out - CLI may be installed but unresponsive")
        except FileNotFoundError:
            self._log("WARNING", "⚠️ llxprt CLI not found in PATH - install with: npm install -g @vybestack/llxprt-code")
        except Exception as e:
            self._log("WARNING", f"⚠️ llxprt CLI verification failed: {str(e)}")
        
        # Always log that the client is initializing regardless of CLI status
        self._log("INFO", "📱 llxprt CLI client initialized (CLI verification completed)")

    def _configure_api_key(self):
        try:
            os.environ["OPENROUTER_API_KEY"] = self.api_key
            # Also persist base URL and provider in env for spawned processes
            if self.base_url:
                os.environ["OPENROUTER_BASE_URL"] = self.base_url
            if self.provider:
                os.environ["PROVIDER"] = self.provider
            self._log("INFO", "🔑 OPENROUTER_API_KEY configured for llxprt CLI")
        except Exception as e:
            self._log("ERROR", f"❌ Failed to configure OPENROUTER_API_KEY: {e}")

    def set_log_callback(self, cb: Callable[[str, str], None]):
        self.log_callback = cb

    def _log(self, level: str, message: str):
        ts = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{ts}] {message}"
        if level == "INFO":
            logger.info(formatted)
        elif level == "ERROR":
            logger.error(formatted)
        elif level == "WARNING":
            logger.warning(formatted)
        else:
            logger.debug(formatted)
        if self.log_callback:
            self.log_callback(level, formatted)

    def switch_model(self, model_name: str):
        self._log("INFO", f"🔄 Switching LLXPRT model to {model_name}")
        self.model_name = model_name
        # Persist model change
        try:
            cfg = self._read_settings()
            cfg['model'] = self.model_name
            self._write_settings(cfg)
        except Exception:
            pass

    def update_api_config(self, api_key: Optional[str] = None, base_url: Optional[str] = None, provider: Optional[str] = None):
        if api_key is not None:
            self.api_key = api_key
        if base_url is not None:
            self.base_url = base_url
        if provider is not None:
            self.provider = provider
        self._configure_api_key()
        # Persist to settings.json
        try:
            cfg = self._read_settings()
            if self.api_key:
                cfg['apiKey'] = self.api_key
            if self.base_url:
                cfg['baseUrl'] = self.base_url
            if self.provider:
                cfg['provider'] = self.provider
            # keep current model too
            cfg['model'] = self.model_name
            self._write_settings(cfg)
            self._log("INFO", "💾 Saved LLXPRT settings to ~/.llxprt/settings.json")
        except Exception as e:
            self._log("WARNING", f"Could not persist LLXPRT settings: {e}")

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "api_key_configured": bool(self.api_key),
            "base_url": self.base_url,
            "provider": self.provider,
        }

    async def send_message(self, message: str, agent_name: Optional[str] = None) -> str:
        # Mirror Gemini async behavior via a background thread
        overall = get_agent_timeout_config(agent_name or "").get("overall", 900)
        try:
            import asyncio
            self._log("INFO", f"📤 Sending message to llxprt model {self.model_name}")
            result = await asyncio.wait_for(
                asyncio.to_thread(self._exec_cli, message, None, agent_name),
                timeout=overall + 5,
            )
            return result or "OK"
        except Exception as e:
            self._log("ERROR", f"llxprt send_message error: {e}")
            raise

    def generate_single_response(self, prompt: str, working_dir: Optional[str] = None, agent_name: Optional[str] = None) -> str:
        self._log("INFO", f"⏳ Generating response with llxprt model {self.model_name}")
        return self._exec_cli(prompt, working_dir, agent_name)

    def _exec_cli(self, prompt: str, working_dir: Optional[str], agent_name: Optional[str]) -> str:
        # Quick check if CLI is working before attempting full execution
        try:
            result = subprocess.run(["llxprt", "--version"], capture_output=True, text=True, timeout=3)
            if result.returncode != 0:
                self._log("WARNING", "⚠️ llxprt CLI check failed - returning fallback response")
                return "llxprt CLI is currently not available. Please check the installation and configuration."
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            self._log("WARNING", f"⚠️ llxprt CLI not accessible: {str(e)} - returning fallback response")
            return "llxprt CLI is currently not available. Please check the installation and configuration."
        
        # Retry logic similar to Gemini client
        cfg = get_agent_timeout_config(agent_name or "")
        max_retries = cfg.get("max_retries", 2)
        base_timeout = cfg.get("timeout", 300)
        retry_timeout = cfg.get("retry_timeout", base_timeout)
        overall_cap = cfg.get("overall", base_timeout + retry_timeout)

        def classify(stderr_text: str) -> Optional[LlxprtCLIError]:
            if not stderr_text:
                return None
            s = stderr_text.lower()
            if any(k in s for k in ["quota", "429", "rate limit"]):
                return LlxprtCLIError("quota_exceeded", stderr_text.strip())
            if any(k in s for k in ["unauthorized", "401", "invalid api key", "forbidden", "403"]):
                return LlxprtCLIError("unauthorized", stderr_text.strip())
            if "timeout" in s:
                return LlxprtCLIError("timeout", stderr_text.strip())
            return None

        overall_start = time.time()
        last_exc: Optional[Exception] = None

        def env_for_exec() -> Dict[str, str]:
            env = os.environ.copy()
            if self.api_key:
                env["OPENROUTER_API_KEY"] = self.api_key
            if self.base_url:
                env["OPENROUTER_BASE_URL"] = self.base_url
            if self.provider:
                env["PROVIDER"] = self.provider
            env["CI"] = env.get("CI", "1")
            return env

        def run_streaming(cmd: List[str], input_text: str, timeout_seconds: int, idle_seconds: int, cwd: Optional[str]) -> Tuple[str, str, int]:
            process: Popen = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE, text=True, bufsize=1, cwd=cwd, env=env_for_exec())
            selector = selectors.DefaultSelector()
            if process.stdout:
                selector.register(process.stdout, selectors.EVENT_READ)
            if process.stderr:
                selector.register(process.stderr, selectors.EVENT_READ)
            start = time.time()
            last_out = start
            try:
                if process.stdin:
                    process.stdin.write(input_text)
                    process.stdin.flush()
                    process.stdin.close()
                out_chunks: List[str] = []
                err_chunks: List[str] = []
                while True:
                    now = time.time()
                    if now - start > timeout_seconds:
                        process.kill()
                        raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout_seconds)
                    if now - last_out > idle_seconds:
                        process.kill()
                        raise subprocess.TimeoutExpired(cmd=cmd, timeout=idle_seconds)
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
                            data = ""
                        if not data:
                            try:
                                selector.unregister(stream)
                            except Exception:
                                pass
                            continue
                        last_out = time.time()
                        if stream is process.stdout:
                            out_chunks.append(data)
                        else:
                            err_chunks.append(data)
                rc = process.wait(timeout=1)
                return ("".join(out_chunks).strip(), "".join(err_chunks).strip(), rc)
            finally:
                try:
                    if process.poll() is None:
                        process.kill()
                except Exception:
                    pass
                try:
                    selector.close()
                except Exception:
                    pass

        for attempt in range(max_retries + 1):
            try:
                elapsed = time.time() - overall_start
                if elapsed >= overall_cap:
                    raise Exception(f"Overall timeout exceeded ({int(elapsed)}s >= {overall_cap}s)")
                per_try = base_timeout if attempt == 0 else retry_timeout
                remaining = overall_cap - elapsed
                per_try = max(5, min(per_try, int(remaining)))
                # idle budget
                idle = get_agent_timeout_config(agent_name or "").get("idle", 120)

                # stdin mode
                cmd = [
                    "llxprt",
                    "--yolo",
                    "--provider", str(self.provider or ''),
                    "--key", str(self.api_key or ''),
                    "--baseurl", str(self.base_url or ''),
                    "--model", self.model_name,
                ]
                self._log("DEBUG", f"🔧 Executing llxprt (stdin): {' '.join(cmd)} (Attempt {attempt + 1}/{max_retries + 1})")
                stdout_text, stderr_text, rc = run_streaming(cmd, prompt, per_try, idle, working_dir)
                self._log("DEBUG", f"📄 stdout len: {len(stdout_text)} | stderr len: {len(stderr_text)}")
                if rc == 0:
                    return stdout_text or (stderr_text if not stdout_text else stdout_text)
                err = classify(stderr_text)
                if err:
                    raise err
                # fallback arg mode
                arg_cmd = [
                    "llxprt",
                    "--yolo",
                    "--provider", str(self.provider or ''),
                    "--key", str(self.api_key or ''),
                    "--baseurl", str(self.base_url or ''),
                    "--model", self.model_name,
                    "--prompt", prompt,
                ]
                self._log("DEBUG", f"🔧 Executing llxprt (arg): llxprt --provider {self.provider} --baseurl {self.base_url} --model {self.model_name} --prompt <prompt>")
                # Use Popen for better process control and cleanup
                process = Popen(arg_cmd, stdout=PIPE, stderr=PIPE, text=True, cwd=working_dir, env=env_for_exec())
                try:
                    stdout, stderr = process.communicate(timeout=per_try)
                    return_code = process.returncode
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=1)
                    raise
                
                res = type('obj', (object,), {
                    'stdout': stdout,
                    'stderr': stderr,
                    'returncode': return_code
                })()
                if res.returncode == 0:
                    return (res.stdout or '').strip() or (res.stderr or '').strip()
                err = classify((res.stderr or '').strip())
                if err:
                    raise err
                raise Exception((res.stderr or 'unknown error').strip())
            except subprocess.TimeoutExpired as e:
                last_exc = e
                self._log("WARNING", f"⏰ llxprt timed out (attempt {attempt + 1}/{max_retries + 1})")
                if attempt < max_retries:
                    time.sleep(get_retry_delay('timeout'))
                else:
                    raise LlxprtCLIError("timeout", "llxprt command timed out after retries")
            except LlxprtCLIError as ge:
                last_exc = ge
                self._log("ERROR", f"❌ llxprt classified error [{ge.code}]: {ge.message}")
                if ge.code in ["unauthorized", "quota_exceeded"] or attempt >= max_retries:
                    raise
                time.sleep(get_retry_delay('error'))
            except Exception as e:
                last_exc = e
                self._log("ERROR", f"❌ llxprt error: {e}")
                if attempt < max_retries:
                    time.sleep(get_retry_delay('error'))
                else:
                    raise

        raise last_exc or LlxprtCLIError("unknown", "Unknown llxprt error")

    def set_mcp_servers(self, servers: List[Dict[str, Any]]):
        # Placeholder: if/when llxprt supports MCP flags similar to gemini
        try:
            self.mcp_args = []
        except Exception:
            pass


