"""
SureCli Client

A lightweight client that uses Google's python library `google.generativeai`
for text generation. This client does not perform any filesystem operations;
the Python system (workflow) is responsible for parsing responses and writing
files as needed.
"""

import os
import time
import threading
import asyncio
from typing import Optional, Callable, Any, Dict
from datetime import datetime
import os

from src.utils.logger import get_logger

logger = get_logger(__name__)


class SureCliError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


class SureCliClient:
    """Minimal wrapper around google.generativeai for text generation."""

    def __init__(self):
        self._log_callback: Optional[Callable[[str, str], None]] = None
        # Default to latest stable per Vertex AI model versions: gemini-2.5-flash
        # See: https://cloud.google.com/vertex-ai/generative-ai/docs/learn/model-versions
        self._model_name: str = os.getenv("SURECLI_MODEL", "gemini-2.5-flash")
        self._configured: bool = False
        self._init_client()
        # Simple per-process throttle to respect free tier RPM
        try:
            # Increase default spacing between requests (was 4s). Now 7s by default.
            self._min_interval_seconds: float = float(os.getenv("SURECLI_MIN_INTERVAL", "7"))
        except Exception:
            self._min_interval_seconds = 7.0
        self._last_call_ts: float = 0.0
        self._throttle_lock = threading.Lock()
        # Shared Gemini key manager for unified rotation across clients
        try:
            from src.llm_clients.gemini_api_key_manager import GeminiAPIKeyManager  # lazy import
            self._key_manager = GeminiAPIKeyManager()
        except Exception:
            self._key_manager = None

    def _init_client(self):
        try:
            import google.generativeai as genai  # type: ignore
            # Prefer shared GeminiAPIKeyManager current key, then explicit envs
            api_key = None
            try:
                if getattr(self, "_key_manager", None) is None:
                    from src.llm_clients.gemini_api_key_manager import GeminiAPIKeyManager
                    self._key_manager = GeminiAPIKeyManager()
                api_key = self._key_manager.get_current_key()
            except Exception:
                api_key = None
            if not api_key:
                api_key = (
                    os.getenv("SURECLI_API_KEY")
                    or os.getenv("GOOGLE_API_KEY")
                    or os.getenv("GEMINI_API_KEY")
                )
            if not api_key:
                # Final fallback: consult the shared gemini_cli_client singleton
                try:
                    from src.routes.bmad_api import gemini_cli_client  # type: ignore
                    if hasattr(gemini_cli_client, "api_key_manager"):
                        api_key = gemini_cli_client.api_key_manager.get_current_key()
                except Exception:
                    api_key = None
            if not api_key:
                # Final fallback: consult the shared gemini_cli_client singleton
                try:
                    from src.routes.bmad_api import gemini_cli_client  # type: ignore
                    if hasattr(gemini_cli_client, "api_key_manager"):
                        api_key = gemini_cli_client.api_key_manager.get_current_key()
                except Exception:
                    api_key = None
            if not api_key:
                self._configured = False
                # Demote to DEBUG to avoid noisy log lines during normal operations
                logger.debug("SureCli: no API key configured (set SURECLI_API_KEY/GOOGLE_API_KEY/GEMINI_API_KEY or add a key via API keys manager)")
                return
            # Set both env vars to maximize compatibility
            try:
                os.environ["GEMINI_API_KEY"] = api_key
                os.environ["GOOGLE_API_KEY"] = api_key
            except Exception:
                pass
            genai.configure(api_key=api_key)
            self._genai = genai
            self._configured = True
        except Exception as e:
            self._configured = False
            logger.error(f"SureCli initialization failed: {e}")

    def _sync_key_from_manager(self):
        """Ensure google.generativeai is configured with the manager's current key before a call."""
        try:
            import google.generativeai as genai  # type: ignore
            if getattr(self, "_key_manager", None) is None:
                from src.llm_clients.gemini_api_key_manager import GeminiAPIKeyManager
                self._key_manager = GeminiAPIKeyManager()
            current = self._key_manager.get_current_key() if self._key_manager else None
            if current:
                try:
                    os.environ["GEMINI_API_KEY"] = current
                    os.environ["GOOGLE_API_KEY"] = current
                except Exception:
                    pass
                genai.configure(api_key=current)
                self._genai = genai
                self._configured = True
        except Exception:
            pass

    def _reconfigure_after_rotation(self):
        try:
            if not getattr(self, "_key_manager", None):
                from src.llm_clients.gemini_api_key_manager import GeminiAPIKeyManager
                self._key_manager = GeminiAPIKeyManager()
            import google.generativeai as genai  # type: ignore
            new_key = None
            try:
                new_key = self._key_manager.get_current_key() if self._key_manager else None
            except Exception:
                new_key = None
            if new_key:
                try:
                    os.environ["GEMINI_API_KEY"] = new_key
                    os.environ["GOOGLE_API_KEY"] = new_key
                except Exception:
                    pass
                genai.configure(api_key=new_key)
                self._genai = genai
                self._configured = True
                self._log("INFO", "SureCli reconfigured with rotated API key")
            else:
                self._configured = False
                self._log("ERROR", "No API key available after rotation; SureCli not configured")
        except Exception as e:
            self._configured = False
            self._log("ERROR", f"Failed to reconfigure SureCli after rotation: {e}")

    def _throttle(self):
        """Ensure a minimum interval between SureCli requests to avoid 429 rate limits."""
        try:
            with self._throttle_lock:
                now = time.time()
                elapsed = now - (self._last_call_ts or 0.0)
                wait = self._min_interval_seconds - elapsed
                if wait > 0:
                    try:
                        self._log("INFO", f"⏳ SureCli throttling for {wait:.1f}s to respect rate limits")
                    except Exception:
                        pass
                    time.sleep(wait)
                self._last_call_ts = time.time()
        except Exception:
            # Best-effort throttle; ignore errors
            pass

    def _apply_retry_delay_hint(self, message: str):
        """Best-effort: parse retry delay from server error and defer next allowed call."""
        try:
            import re
            lower = (message or "").lower()
            # Common patterns: 'retry_delay {\n  seconds: 23\n}' or 'retry after 23s'
            m = re.search(r"retry[_ ]?delay[^0-9]*seconds\s*[:=]\s*(\d+)", message)
            seconds = None
            if m:
                seconds = int(m.group(1))
            else:
                m2 = re.search(r"retry\s+after\s+(\d+)s", lower)
                if m2:
                    seconds = int(m2.group(1))
            if seconds and seconds > 0:
                try:
                    self._log("WARNING", f"⏳ Respecting server retry delay hint: {seconds}s")
                except Exception:
                    pass
                # Push last_call_ts into the future so _throttle waits ~seconds on next call
                with self._throttle_lock:
                    self._last_call_ts = time.time() - self._min_interval_seconds + float(seconds)
        except Exception:
            pass

    def set_log_callback(self, cb: Callable[[str, str], None]):
        self._log_callback = cb

    def _log(self, level: str, msg: str):
        if self._log_callback:
            self._log_callback(level, msg)
        else:
            if level == "ERROR":
                logger.error(msg)
            elif level == "WARNING":
                logger.warning(msg)
            elif level == "DEBUG":
                logger.debug(msg)
            else:
                logger.info(msg)

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "client": "surecli",
            "model_name": self._model_name,
            "api_key_configured": self._configured,
        }

    def switch_model(self, model: str):
        if model:
            self._model_name = model
            self._log("INFO", f"SureCli model set to {model}")

    def _detect_base_project_structure(self, working_dir: str) -> Optional[str]:
        """
        Detect if a base project was cloned by looking for predefined documents.
        Recursively searches for any .sureai directory with predefined documents,
        regardless of the base project's directory structure.
        Returns the path to the base project .sureai directory if found.
        """
        try:
            # Recursively search for .sureai directories within the working directory
            def find_sureai_dirs(root_dir: str) -> list:
                sureai_dirs = []
                try:
                    for root, dirs, files in os.walk(root_dir):
                        # Skip BMAD-specific directories to avoid false positives
                        if os.path.basename(root).startswith('.io8') or os.path.basename(root) == '.sureai':
                            if os.path.basename(root) == '.sureai':
                                # Found a .sureai directory, check if it's a base project
                                sureai_dirs.append(root)
                            continue
                        
                        # Remove BMAD directories from search to avoid recursing into them
                        dirs[:] = [d for d in dirs if not d.startswith('.io8')]
                        
                        if '.sureai' in dirs:
                            sureai_path = os.path.join(root, '.sureai')
                            sureai_dirs.append(sureai_path)
                            
                except Exception as e:
                    self._log("WARNING", f"Error walking directory {root_dir}: {e}")
                
                return sureai_dirs
            
            # Find all .sureai directories
            sureai_candidates = find_sureai_dirs(working_dir)
            self._log("DEBUG", f"Found {len(sureai_candidates)} .sureai directories: {sureai_candidates}")
            
            # Check each .sureai directory for predefined base project documents
            for sureai_path in sureai_candidates:
                if not os.path.exists(sureai_path) or not os.path.isdir(sureai_path):
                    continue
                    
                # List of expected predefined documents in a base project
                expected_files = [
                    ".directory_structure.md",
                    "analysis_document.md", 
                    "requirements_document.md",
                    "architecture_document.md",
                    "tech_stack_document.md",
                    "prd_document.md",
                    "project_plan.md"
                ]
                
                found_count = 0
                found_files = []
                
                for expected_file in expected_files:
                    file_path = os.path.join(sureai_path, expected_file)
                    if os.path.exists(file_path):
                        found_count += 1
                        found_files.append(expected_file)
                
                # If we found multiple expected files, this is likely a base project
                if found_count >= 3:
                    self._log("INFO", f"🎯 Detected base project .sureai at: {sureai_path}")
                    self._log("INFO", f"📋 Found {found_count} predefined documents: {found_files[:5]}...")
                    return sureai_path
                elif found_count > 0:
                    self._log("DEBUG", f"Found {found_count} documents in {sureai_path}, but not enough for base project (need 3+)")
            
            self._log("INFO", "🔍 No base project .sureai directory found with sufficient predefined documents")
            return None
            
        except Exception as e:
            self._log("WARNING", f"Error detecting base project structure: {e}")
            return None

    def _get_base_project_file_mapping(self, agent_name: Optional[str]) -> Dict[str, str]:
        """
        Get the mapping of agent names to their corresponding base project files.
        Returns a dict of {file_key: filename} for the agent.
        """
        name = (agent_name or "").strip().lower()
        
        mappings = {
            "io8directory_structure": {
                "directory": ".directory_structure.md"
            },
            "io8codermaster": {
                "breakdown": ".io8codermaster_breakdown.md",
                "plan": ".io8codermaster_plan.md"
            },
            "io8analyst": {
                "analysis": "analysis_document.md",
                "requirements": "requirements_document.md"
            },
            "io8architect": {
                "architecture": "architecture_document.md",
                "tech_stack": "tech_stack_document.md"
            },
            "io8pm": {
                "prd": "prd_document.md",
                "project_plan": "project_plan.md"
            }
        }
        
        return mappings.get(name, {})

    def _append_to_base_project_files(self, text: str, agent_name: Optional[str], base_project_sureai_path: str) -> bool:
        """
        Append AI-generated content to existing base project files based on agent type.
        Returns True if successful, False otherwise.
        """
        try:
            import json
            
            self._log("INFO", f"📄 Processing response for {agent_name} to append to base project")
            self._log("DEBUG", f"📝 Response text (first 200 chars): {text[:200]}...")
            
            # Parse JSON response from AI
            data = None
            t = text.strip()
            if t.startswith("```"):
                t = t.strip("`\n").split("\n", 1)[-1]
                if t.startswith("json\n"):
                    t = t[5:]
            
            try:
                data = json.loads(t)
                self._log("DEBUG", f"✅ Successfully parsed JSON data: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
            except json.JSONDecodeError as e:
                self._log("ERROR", f"❌ Response is not valid JSON: {e}")
                self._log("DEBUG", f"📝 Raw response: {t[:500]}")
                return False
            
            if not isinstance(data, dict):
                self._log("ERROR", f"❌ Parsed data is not a dictionary: {type(data)}")
                return False
            
            # Get file mapping for this agent
            file_mapping = self._get_base_project_file_mapping(agent_name)
            if not file_mapping:
                self._log("WARNING", f"⚠️ No base project file mapping for agent: {agent_name}")
                return False
            
            self._log("INFO", f"🔧 Appending to base project files for {agent_name}")
            self._log("DEBUG", f"📊 File mapping: {file_mapping}")
            
            appended_any = False
            agent_lower = (agent_name or "").lower()
            
            # Handle different agent types with flexible content mapping
            if agent_lower == "io8directory_structure":
                # For directory structure, append to .directory_structure.md
                directory_file = os.path.join(base_project_sureai_path, ".directory_structure.md")
                raw_dir = data.get("directory_structure") or data.get("directory") or data.get("content") or str(data)
                content_to_append = self._normalize_markdown_content(raw_dir)
                self._log("DEBUG", f"📁 Directory content to append: {content_to_append[:100]}...")
                if self._append_content_to_file(directory_file, content_to_append, "DIRECTORY STRUCTURE UPDATE"):
                    appended_any = True
                    
            elif agent_lower == "io8codermaster":
                # For codermaster, append breakdown and plan to separate files
                breakdown_content = self._normalize_markdown_content(data.get("breakdown") or "") if data.get("breakdown") else None
                plan_content = self._normalize_markdown_content(data.get("plan") or "") if data.get("plan") else None
                
                self._log("DEBUG", f"📊 Codermaster breakdown: {bool(breakdown_content)}, plan: {bool(plan_content)}")
                
                if breakdown_content:
                    # Try new filename first, then old filename for compatibility
                    breakdown_file_new = os.path.join(base_project_sureai_path, ".io8codermaster_breakdown.md")
                    breakdown_file_old = os.path.join(base_project_sureai_path, ".io8coder_breakdown.md")
                    
                    if os.path.exists(breakdown_file_new):
                        target_file = breakdown_file_new
                    elif os.path.exists(breakdown_file_old):
                        target_file = breakdown_file_old
                        self._log("INFO", f"📝 Using legacy filename: .io8coder_breakdown.md")
                    else:
                        target_file = breakdown_file_new  # Default to new filename
                        
                    if self._append_content_to_file(target_file, breakdown_content, "CODER BREAKDOWN UPDATE"):
                        appended_any = True
                        
                if plan_content:
                    # Try new filename first, then old filename for compatibility
                    plan_file_new = os.path.join(base_project_sureai_path, ".io8codermaster_plan.md")
                    plan_file_old = os.path.join(base_project_sureai_path, ".io8coder_plan.md")
                    
                    if os.path.exists(plan_file_new):
                        target_file = plan_file_new
                    elif os.path.exists(plan_file_old):
                        target_file = plan_file_old
                        self._log("INFO", f"📝 Using legacy filename: .io8coder_plan.md")
                    else:
                        target_file = plan_file_new  # Default to new filename
                        
                    if self._append_content_to_file(target_file, plan_content, "CODER PLAN UPDATE"):
                        appended_any = True
                        
            elif agent_lower in ["io8analyst", "io8 business analyst", "business analyst"]:
                # For analyst agents, try multiple content keys and file mappings
                analysis_content = data.get("analysis") or data.get("analysis_document") or data.get("business_analysis")
                requirements_content = data.get("requirements") or data.get("requirements_document") or data.get("business_requirements")

                if analysis_content:
                    analysis_content = self._normalize_markdown_content(analysis_content)
                if requirements_content:
                    requirements_content = self._normalize_markdown_content(requirements_content)
                
                # If no specific keys found, try to use the whole response for analysis
                if not analysis_content and not requirements_content:
                    # Check if response contains analysis-related content
                    full_content = str(data)
                    if any(keyword in full_content.lower() for keyword in ['analysis', 'requirement', 'business']):
                        analysis_content = self._normalize_markdown_content(full_content)
                
                self._log("DEBUG", f"📊 Analyst analysis: {bool(analysis_content)}, requirements: {bool(requirements_content)}")
                
                if analysis_content:
                    analysis_file = os.path.join(base_project_sureai_path, file_mapping["analysis"])
                    if self._append_content_to_file(analysis_file, analysis_content, "BUSINESS ANALYSIS UPDATE"):
                        appended_any = True
                        
                if requirements_content:
                    requirements_file = os.path.join(base_project_sureai_path, file_mapping["requirements"])
                    if self._append_content_to_file(requirements_file, requirements_content, "REQUIREMENTS UPDATE"):
                        appended_any = True
                        
            elif agent_lower in ["io8architect", "io8 system architect", "system architect"]:
                # For architect agents, try multiple content keys
                architecture_content = data.get("architecture") or data.get("architecture_document") or data.get("system_architecture")
                tech_stack_content = data.get("tech_stack") or data.get("tech_stack_document") or data.get("technology_stack")

                if architecture_content:
                    architecture_content = self._normalize_markdown_content(architecture_content)
                if tech_stack_content:
                    tech_stack_content = self._normalize_markdown_content(tech_stack_content)
                
                # If no specific keys found, try to use the whole response
                if not architecture_content and not tech_stack_content:
                    full_content = str(data)
                    if any(keyword in full_content.lower() for keyword in ['architecture', 'tech', 'technology', 'stack']):
                        architecture_content = self._normalize_markdown_content(full_content)
                
                self._log("DEBUG", f"📊 Architect architecture: {bool(architecture_content)}, tech_stack: {bool(tech_stack_content)}")
                
                if architecture_content:
                    architecture_file = os.path.join(base_project_sureai_path, file_mapping["architecture"])
                    if self._append_content_to_file(architecture_file, architecture_content, "ARCHITECTURE UPDATE"):
                        appended_any = True
                        
                if tech_stack_content:
                    tech_stack_file = os.path.join(base_project_sureai_path, file_mapping["tech_stack"])
                    if self._append_content_to_file(tech_stack_file, tech_stack_content, "TECH STACK UPDATE"):
                        appended_any = True
                        
            elif agent_lower in ["io8pm", "io8 project manager", "project manager"]:
                # For PM agents, try multiple content keys
                prd_content = data.get("prd") or data.get("prd_document") or data.get("product_requirements")
                project_plan_content = data.get("project_plan") or data.get("project_plan_document") or data.get("plan")
                
                # If no specific keys found, try to use the whole response
                if not prd_content and not project_plan_content:
                    full_content = str(data)
                    if any(keyword in full_content.lower() for keyword in ['prd', 'product', 'project', 'plan', 'requirements']):
                        prd_content = full_content
                
                self._log("DEBUG", f"📊 PM prd: {bool(prd_content)}, project_plan: {bool(project_plan_content)}")
                
                if prd_content:
                    prd_file = os.path.join(base_project_sureai_path, file_mapping["prd"])
                    if self._append_content_to_file(prd_file, prd_content, "PRD UPDATE"):
                        appended_any = True
                        
                if project_plan_content:
                    project_plan_file = os.path.join(base_project_sureai_path, file_mapping["project_plan"])
                    if self._append_content_to_file(project_plan_file, project_plan_content, "PROJECT PLAN UPDATE"):
                        appended_any = True
            
            # Fallback: If no content was appended but we have a valid agent, try to append the whole response
            if not appended_any and file_mapping:
                self._log("WARNING", f"⚠️ No specific content found for {agent_name}, trying fallback append")
                self._log("DEBUG", f"📝 Available response keys: {list(data.keys())}")
                
                # Try to append to the first file in the mapping as fallback
                fallback_file_key = list(file_mapping.keys())[0]
                fallback_file = os.path.join(base_project_sureai_path, file_mapping[fallback_file_key])
                fallback_content = str(data)
                
                self._log("INFO", f"🔄 Fallback: Appending full response to {file_mapping[fallback_file_key]}")
                if self._append_content_to_file(fallback_file, fallback_content, f"{agent_name.upper()} UPDATE"):
                    appended_any = True
            
            if not appended_any:
                self._log("WARNING", f"⚠️ No content was appended for {agent_name}. Available keys in response: {list(data.keys())}")
                self._log("DEBUG", f"📝 Full response data: {data}")
            
            return appended_any
            
        except Exception as e:
            self._log("ERROR", f"❌ Failed to append to base project files: {e}")
            import traceback
            self._log("DEBUG", f"🐛 Stack trace: {traceback.format_exc()}")
            return False
    
    def _append_content_to_file(self, file_path: str, content: str, section_title: str) -> bool:
        """
        Append content to an existing file with a clear section header.
        """
        try:
            # Normalize markdown content to avoid fenced JSON being written verbatim
            content = self._normalize_markdown_content(content)
            if not os.path.exists(file_path):
                self._log("WARNING", f"Base project file does not exist: {file_path}")
                # List available files in the directory for debugging
                dir_path = os.path.dirname(file_path)
                if os.path.exists(dir_path):
                    available_files = [f for f in os.listdir(dir_path) if f.endswith('.md')]
                    self._log("DEBUG", f"📁 Available .md files in {dir_path}: {available_files}")
                return False
            
            # Prepare append content with timestamp and section
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            append_text = f"\n\n---\n\n## {section_title} - {timestamp}\n\n{content}\n"
            
            # Append to the file (use 'a' mode for append, not 'w')
            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(append_text)
            
            self._log("INFO", f"✅ Appended content to {os.path.basename(file_path)}")
            return True
            
        except Exception as e:
            self._log("ERROR", f"Failed to append to file {file_path}: {e}")
            return False
        name = (agent_name or "").strip()
        outputs = {
            "directory_structure": {
                "files": [
                    "backend/",
                    "frontend/",
                    "deployment_config.yml",
                    "docker-compose.yml",
                    "Dockerfile.backend",
                    "Dockerfile.frontend",
                ]
            },
            "io8codermaster": {
                "files": [
                    ".sureai/.io8codermaster_breakdown.md",
                    ".sureai/.io8codermaster_plan.md",
                ]
            },
            "analyst": {
                "files": [
                    ".sureai/analysis_document.md",
                    ".sureai/requirements_document.md",
                ]
            },
            "architect": {
                "files": [
                    ".sureai/architecture_document.md",
                    ".sureai/tech_stack_document.md",
                ]
            },
            "pm": {
                "files": [
                    ".sureai/prd_document.md",
                    ".sureai/project_plan.md",
                ]
            },
        }
        return outputs.get(name, {"files": []})

    def _inject_base_project_references(self, prompt: str, agent_name: Optional[str], base_project_sureai_path: str) -> str:
        """
        Inject reference documents from base project for io8 workflow agents.
        Each agent gets different previous documents injected based on workflow sequence.
        """
        try:
            agent_lower = (agent_name or "").lower()
            refs = []
            
            # Define which documents each agent needs as references
            reference_mappings = {
                "io8directory_structure": [
                    # Directory structure agent doesn't need references - it creates the first document
                ],
                "io8codermaster": [
                    ".directory_structure.md"
                ],
                "io8analyst": [
                    ".io8codermaster_breakdown.md",
                    ".io8codermaster_plan.md"
                ],
                "io8architect": [
                    "analysis_document.md",
                    "requirements_document.md"
                ],
                "io8pm": [
                    "analysis_document.md",
                    "architecture_document.md",
                    "tech_stack_document.md"
                ],
                "io8developer": [
                    "prd_document.md",
                    "project_plan.md",
                    "architecture_document.md",
                    "tech_stack_document.md"
                ],
                "io8devops": [
                    "architecture_document.md",
                    "tech_stack_document.md"
                ]
            }
            
            required_refs = reference_mappings.get(agent_lower, [])
            
            if not required_refs:
                self._log("DEBUG", f"No reference documents needed for {agent_name}")
                return prompt
            
            self._log("INFO", f"📄 Injecting {len(required_refs)} reference documents for {agent_name}")
            
            # Read each required reference document
            for ref_file in required_refs:
                ref_path = os.path.join(base_project_sureai_path, ref_file)
                content_found = False
                
                # First try the specified filename
                if os.path.exists(ref_path):
                    try:
                        with open(ref_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                        refs.append((ref_file, content))
                        self._log("DEBUG", f"✅ Injected reference: {ref_file} ({len(content)} chars)")
                        content_found = True
                    except Exception as e:
                        self._log("WARNING", f"⚠️ Failed to read reference {ref_file}: {e}")
                
                # If not found, try legacy naming for common io8 files
                if not content_found:
                    legacy_mappings = {
                        ".io8codermaster_breakdown.md": ".io8coder_breakdown.md",
                        ".io8codermaster_plan.md": ".io8coder_plan.md",
                        "analysis_document.md": "analysis_document.md",  # Same name but might be in different location
                        "requirements_document.md": "requirements_document.md",
                        "architecture_document.md": "architecture_document.md",
                        "tech_stack_document.md": "tech_stack_document.md",
                        "prd_document.md": "prd_document.md",
                        "project_plan.md": "project_plan.md",
                        ".directory_structure.md": ".directory_structure.md"
                    }
                    
                    # Check if this file has a legacy equivalent
                    legacy_name = legacy_mappings.get(ref_file, ref_file.replace(".io8codermaster_", ".io8coder_"))
                    legacy_path = os.path.join(base_project_sureai_path, legacy_name)
                    
                    if os.path.exists(legacy_path):
                        try:
                            with open(legacy_path, "r", encoding="utf-8", errors="ignore") as f:
                                content = f.read()
                            refs.append((ref_file, content))  # Keep original name in reference
                            self._log("DEBUG", f"✅ Injected legacy reference: {legacy_name} -> {ref_file} ({len(content)} chars)")
                            content_found = True
                        except Exception as e:
                            self._log("WARNING", f"⚠️ Failed to read legacy reference {legacy_name}: {e}")
                
                if not content_found:
                    self._log("WARNING", f"⚠️ Reference document not found: {ref_path}")
                    # List available files for debugging
                    try:
                        available_files = [f for f in os.listdir(base_project_sureai_path) if f.endswith('.md')]
                        self._log("DEBUG", f"📁 Available .md files in base project: {available_files}")
                    except Exception:
                        pass
            
            # Inject references into prompt if any were found
            if refs:
                ref_block = ["\n\nREFERENCE DOCUMENTS FROM BASE PROJECT (read-only, for context):\n"]
                for ref_file, content in refs:
                    ref_block.append(f"=== {ref_file} ===\n{content}\n\n")
                
                enhanced_prompt = prompt + "\n" + "".join(ref_block)
                self._log("INFO", f"✅ Successfully injected {len(refs)} reference documents into prompt")
                return enhanced_prompt
            else:
                self._log("WARNING", f"🚨 No reference documents could be loaded for {agent_name}")
                return prompt
                
        except Exception as e:
            self._log("ERROR", f"❌ Error injecting base project references: {e}")
            return prompt

    def _inject_reference_files(self, prompt: str, working_dir: Optional[str]) -> str:
        """Inject contents of files referenced with @path in the prompt.
        Looks under working_dir and falls back to working_dir/.sureai by basename.
        """
        if not working_dir:
            return prompt
        try:
            import re
            sureai_dir = os.path.join(working_dir, ".sureai")
            refs = []
            # Find @file references like @.sureai/file.md or @path/file
            for m in re.finditer(r"@([\w\./\-]+)", prompt):
                rel = m.group(1)
                # normalize relative path rooted at working_dir
                p = rel if os.path.isabs(rel) else os.path.join(working_dir, rel)
                if os.path.exists(p):
                    try:
                        with open(p, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                        refs.append((rel, content))
                    except Exception:
                        pass
                else:
                    # also try .sureai if not absolute and not already in .sureai
                    if not rel.startswith(".sureai/"):
                        p2 = os.path.join(sureai_dir, os.path.basename(rel))
                        if os.path.exists(p2):
                            try:
                                with open(p2, "r", encoding="utf-8", errors="ignore") as f:
                                    content = f.read()
                                refs.append((rel, content))
                            except Exception:
                                pass
            if refs:
                ref_block = ["\n\nREFERENCE FILES (inline, read-only):\n"]
                for rel, content in refs:
                    ref_block.append(f"=== {rel} ===\n{content}\n\n")
                return prompt + "\n" + "".join(ref_block)
            return prompt
        except Exception:
            return prompt

    def _wrap_prompt_as_json_spec(self, prompt: str, agent_name: Optional[str], working_dir: Optional[str]) -> str:
        # Check if this is io8 workflow with base project
        is_io8_workflow = agent_name and agent_name.lower().startswith('io8')
        base_project_sureai_path = None
        
        if is_io8_workflow and working_dir:
            base_project_sureai_path = self._detect_base_project_structure(working_dir)
        
        # Inject reference documents based on workflow type
        if is_io8_workflow and base_project_sureai_path:
            # For io8 workflows with base project, inject base project references
            prompt_with_refs = self._inject_base_project_references(prompt, agent_name, base_project_sureai_path)
        else:
            # For standard workflows, use standard reference injection
            prompt_with_refs = self._inject_reference_files(prompt, working_dir)
        
        # Apply appropriate JSON specification based on workflow type
        if is_io8_workflow and base_project_sureai_path:
            # Special JSON format for base project appending
            agent_lower = agent_name.lower()
            
            if agent_lower == "io8directory_structure":
                instruction = (
                    "\n\nYou are working with a BASE PROJECT that has been cloned. "
                    "Respond in STRICT JSON format with content to APPEND to existing documents:\n"
                    "{\n  \"directory_structure\": \"content to append to .directory_structure.md based on user prompt\"\n}\n"
                    "Rules:\n- Generate content that builds upon the existing base project structure\n"
                    "- Focus only on modifications/additions based on the user prompt\n"
                    "- Do not recreate the entire directory structure\n"
                    "- Content will be appended to the existing .directory_structure.md file\n"
                    "- NEVER modify, create, or overwrite predefined documents (analysis_document.md, requirements_document.md, etc.)\n"
                    "- NEVER create any directories or files - ONLY document existing structure\n"
                    "- ONLY work with directory structure documentation"
                )
            elif agent_lower == "io8codermaster":
                instruction = (
                    "\n\nYou are working with a BASE PROJECT that has been cloned. "
                    "Respond in STRICT JSON format with content to APPEND to existing documents:\n"
                    "{\n  \"breakdown\": \"content to append to .io8codermaster_breakdown.md\",\n  \"plan\": \"content to append to .io8codermaster_plan.md\"\n}\n"
                    "Rules:\n- Generate content that builds upon the existing base project\n"
                    "- Focus on modifications/additions based on the user prompt\n"
                    "- NEVER overwrite or replace existing content - ONLY append\n"
                    "- Use the directory structure reference document provided above for context\n"
                    "- Content will be appended to existing files\n"
                    "- ONLY work with .io8codermaster_breakdown.md and .io8codermaster_plan.md files\n"
                    "- DO NOT modify any other predefined documents"
                )
            elif agent_lower == "io8analyst":
                instruction = (
                    "\n\nYou are working with a BASE PROJECT that has been cloned. "
                    "Respond in STRICT JSON format with content to APPEND to existing documents:\n"
                    "{\n  \"analysis\": \"content to append to analysis_document.md\",\n  \"requirements\": \"content to append to requirements_document.md\"\n}\n"
                    "Rules:\n- Generate content that builds upon the existing analysis and requirements\n"
                    "- Focus on modifications/additions based on the user prompt\n"
                    "- NEVER overwrite or replace existing content - ONLY append\n"
                    "- Use the coder breakdown and plan reference documents provided above for context\n"
                    "- Content will be appended to existing files\n"
                    "- Preserve all existing content in the predefined documents"
                )
            elif agent_lower == "io8architect":
                instruction = (
                    "\n\nYou are working with a BASE PROJECT that has been cloned. "
                    "Respond in STRICT JSON format with content to APPEND to existing documents:\n"
                    "{\n  \"architecture\": \"content to append to architecture_document.md\",\n  \"tech_stack\": \"content to append to tech_stack_document.md\"\n}\n"
                    "Rules:\n- Generate content that builds upon the existing architecture and tech stack\n"
                    "- Focus on modifications/additions based on the user prompt\n"
                    "- NEVER overwrite or replace existing content - ONLY append\n"
                    "- Use the analysis and requirements reference documents provided above for context\n"
                    "- Content will be appended to existing files\n"
                    "- Preserve all existing content in the predefined documents"
                )
            elif agent_lower == "io8pm":
                instruction = (
                    "\n\nYou are working with a BASE PROJECT that has been cloned. "
                    "Respond in STRICT JSON format with content to APPEND to existing documents:\n"
                    "{\n  \"prd\": \"content to append to prd_document.md\",\n  \"project_plan\": \"content to append to project_plan.md\"\n}\n"
                    "Rules:\n- Generate content that builds upon the existing PRD and project plan\n"
                    "- Focus on modifications/additions based on the user prompt\n"
                    "- NEVER overwrite or replace existing content - ONLY append\n"
                    "- Use the analysis, architecture, and tech stack reference documents provided above for context\n"
                    "- Content will be appended to existing files\n"
                    "- Preserve all existing content in the predefined documents"
                )
            else:
                # Fallback for other io8 agents
                instruction = (
                    "\n\nYou are working with a BASE PROJECT that has been cloned. "
                    "Respond in STRICT JSON format with content to append based on the user prompt.\n"
                    "Focus on modifications/additions to the existing base project."
                )
        else:
            # Standard JSON format for regular workflows with INTELLIGENT FILE OPERATIONS
            expected = self._expected_outputs_for_agent(agent_name)
            expected_list = expected.get("files", []) or []
            expected_str = "\n".join([f"- {p}" for p in expected_list]) if expected_list else "(none; include only files you truly create)"
            instruction = (
                "\n\n🧠 INTELLIGENT SURECLI SYSTEM ACTIVATED 🧠\n"
                "You are working with an intelligent CLI that can understand and execute file operations.\n"
                "The CLI can automatically search for files, create directories, and perform self-correction.\n\n"
                "PREFERRED FORMAT - Structured File Operations (NEW!):\n"
                '{\n  "file_operations": [\n'
                '    {\n      "filename": "path/to/file.ext",\n'
                '      "operation": "write|append|delete|search|create_dir|replace",\n'
                '      "content": "file content or search term",\n'
                '      "search": "text to search for (for replace operations)",\n'
                '      "replace": "text to replace with (for replace operations)",\n'
                '      "line_number": 10,  // Optional: specific line number for replace operations\n'
                '      "location": "optional/custom/path"\n    }\n  ]\n}\n\n'
                "LEGACY FORMAT - Files Array (Still Supported):\n"
                "{ \"files\": [ { \"path\": \"file.ext\", \"content\": \"...\", \"is_dir\": false } ] }\n\n"
                "AUTO-DETECTION - Simple Key-Value:\n"
                "{ \"readme.md\": \"content\", \"src/app.py\": \"code\" } (filenames as keys)\n\n"
                "SUPPORTED OPERATIONS:\n"
                "• write/create: Create or overwrite files\n"
                "• append/add: Add content to existing files\n"
                "• delete/remove: Delete files or directories\n"
                "• search/find: Search for content in files\n"
                "• create_dir/mkdir: Create directories\n"
                "• replace: Replace text in existing files (supports line-specific replacements)\n\n"
                "ADVANCED FEATURES:\n"
                "• File search: CLI automatically searches for existing files\n"
                "• Self-correction: Errors are logged to bug-list.md for review\n"
                "• Real-time feedback: Detailed operation logging with emojis\n"
                "• Directory creation: Automatic parent directory creation\n"
                "• Replace operations: Search and replace text in files\n"
                "• Line-specific replacements: Replace text at specific line numbers\n\n"
                "RULES:\n"
                "- Respond in JSON format only (no markdown blocks)\n"
                "- Use relative paths from project root\n"
                "- SureCli will show real-time operation status with emojis\n"
                "- Multiple operations in single response supported\n"
                "- CLI will provide user feedback and error handling\n"
                "- If operation fails, it will be logged to bug-list.md\n"
                "- For replace operations, provide both 'search' and 'replace' fields\n"
                "- For line-specific replacements, provide 'line_number' field\n"
                "- Line numbers are 1-based (first line is line 1)\n\n"
                f"Expected outputs for this agent (guidance):\n{expected_str}\n"
            )
        
        return prompt_with_refs + instruction

    def _normalize_markdown_content(self, text: str) -> str:
        """
        Normalize content before writing to .md files:
        - Strip ```json fenced blocks and parse inner JSON
        - If JSON with known doc keys, extract and concatenate as Markdown
        - Otherwise, return plain text unchanged
        """
        try:
            if not isinstance(text, str) or not text:
                return ""
            t = text.strip()
            # Unwrap fenced code blocks
            if t.startswith("```"):
                # Remove starting fences and language tag
                t2 = t.strip("`\n").split("\n", 1)
                if len(t2) == 2:
                    head, body = t2[0], t2[1]
                    if head.strip().lower() == "json":
                        t = body
            # If looks like JSON, try parse
            if (t.startswith("{") and t.endswith("}")) or (t.startswith("[") and t.endswith("]")):
                import json
                try:
                    data = json.loads(t)
                except Exception:
                    return text
                # Map known key pairs to concatenated markdown
                if isinstance(data, dict):
                    # Architect
                    if "architecture" in data or "tech_stack" in data:
                        parts = []
                        if isinstance(data.get("architecture"), (str, int, float)):
                            parts.append(str(data.get("architecture")))
                        if isinstance(data.get("tech_stack"), (str, int, float)):
                            parts.append(str(data.get("tech_stack")))
                        if parts:
                            return "\n\n".join(parts)
                    # Analyst
                    if "analysis" in data or "requirements" in data:
                        parts = []
                        if isinstance(data.get("analysis"), (str, int, float)):
                            parts.append(str(data.get("analysis")))
                        if isinstance(data.get("requirements"), (str, int, float)):
                            parts.append(str(data.get("requirements")))
                        if parts:
                            return "\n\n".join(parts)
                    # Codermaster
                    if "breakdown" in data or "plan" in data:
                        parts = []
                        if isinstance(data.get("breakdown"), (str, int, float)):
                            parts.append(str(data.get("breakdown")))
                        if isinstance(data.get("plan"), (str, int, float)):
                            parts.append(str(data.get("plan")))
                        if parts:
                            return "\n\n".join(parts)
                # Fallback: for arrays or other dicts, return original text
                return text
            return text
        except Exception:
            return text

    async def send_message(self, prompt: str, *, agent_name: Optional[str] = None, temperature: Optional[float] = None) -> str:
        if not self._configured:
            # Retry init in case keys were added at runtime
            self._init_client()
            if not self._configured:
                raise SureCliError("not_configured", "SureCli is not configured. Provide SURECLI_API_KEY/GOOGLE_API_KEY/GEMINI_API_KEY or add a key via the keys manager.")

        # google.generativeai is synchronous; run in thread to avoid blocking loop
        def _generate_sync() -> str:
            try:
                # Throttle before making the SDK call
                self._throttle()
                # Ensure we are using the manager's current key at call time
                self._sync_key_from_manager()
                model = self._genai.GenerativeModel(self._model_name)
                gen_kwargs = {}
                if temperature is not None:
                    gen_kwargs["generation_config"] = {"temperature": float(temperature)}
                    
                resp = model.generate_content(prompt, **gen_kwargs)
                
                # Extract text
                text = getattr(resp, "text", None)
                if not text and hasattr(resp, "candidates"):
                    try:
                        cand = (resp.candidates or [None])[0]
                        text = getattr(getattr(cand, "content", None), "parts", [None])[0].text  # type: ignore
                    except Exception:
                        text = None
                return text or ""
            except Exception as e:
                msg = str(e)
                lower = msg.lower()
                # Only treat explicit quota exhaustion messages as quota_exceeded
                quota_indicators = [
                    "you exceeded your current quota",
                    "quota exceeded",
                    "quota exhausted",
                    "quota metric",
                    "insufficient quota",
                    "resource_exhausted",
                ]
                rate_limit_indicators = [
                    "rate limit",
                    "too many requests",
                    "status: 429",
                ]
                if any(ind in lower for ind in quota_indicators):
                    raise SureCliError("quota_exceeded", msg)
                if any(ind in lower for ind in rate_limit_indicators):
                    # Apply retry delay hint for subsequent calls
                    self._apply_retry_delay_hint(msg)
                    raise SureCliError("rate_limit", msg)
                if any(ind in lower for ind in ["unauthorized", "invalid api key", "status: 401", "status: 403", "forbidden"]):
                    raise SureCliError("unauthorized", msg)
                raise SureCliError("error", msg)

        self._log("INFO", f"SureCli generating for agent: {agent_name or ''}")
        loop = asyncio.get_event_loop()
        max_attempts = 3
        attempt = 0
        while attempt < max_attempts:
            try:
                text: str = await loop.run_in_executor(None, _generate_sync)
                if not text:
                    raise SureCliError("empty", "Empty response from SureCli")
                return text
            except SureCliError as se:
                code = getattr(se, "code", "error")
                if code == "quota_exceeded":
                    # Rotate and retry automatically
                    before_idx = -1
                    try:
                        if getattr(self, "_key_manager", None):
                            before_idx = self._key_manager.current_key_index
                    except Exception:
                        before_idx = -1
                    self._log("ERROR", "API Quota Exceeded")
                    self._log("ERROR", "Status 429")
                    self._log("INFO", "API quota has been exceeded. The system is attempting to rotate to a new key.")
                    rotated = False
                    try:
                        if getattr(self, "_key_manager", None):
                            rotated = self._key_manager.handle_api_error(se.message, self._key_manager.get_current_key())
                    except Exception as re:
                        self._log("ERROR", f"Key rotation handling failed: {re}")
                        rotated = False
                    if rotated:
                        self._reconfigure_after_rotation()
                        after_idx = -1
                        try:
                            after_idx = self._key_manager.current_key_index if getattr(self, "_key_manager", None) else -1
                        except Exception:
                            after_idx = -1
                        self._log("INFO", f"🔁 Rotated from key{before_idx + 1} to key{after_idx + 1}. Resuming current agent.")
                        # brief backoff
                        time.sleep(0.5)
                        attempt += 1
                        continue
                    else:
                        try:
                            is_quota = self._key_manager.is_quota_exhausted_error(se.message) if getattr(self, "_key_manager", None) else False
                            no_keys_left = not self._key_manager.has_available_keys() if getattr(self, "_key_manager", None) else False
                        except Exception:
                            is_quota = False
                            no_keys_left = False
                        if is_quota and no_keys_left:
                            raise SureCliError("no_keys_available", "No usable API keys available - workflow must be terminated")
                        # Treat as rate limit for now
                        raise SureCliError("rate_limit", se.message)
                # Pass through other structured errors
                raise

    # Synchronous-style API to be compatible with SequentialDocumentBuilder expectations
    def _ensure_dirs(self, base_dir: str, rel_path: str):
        try:
            target_dir = os.path.dirname(os.path.join(base_dir, rel_path))
            if target_dir:
                os.makedirs(target_dir, exist_ok=True)
        except Exception:
            pass

    def _parse_and_execute_file_operations(self, text: str, working_dir: Optional[str]) -> bool:
        """
        INTELLIGENT FILE OPERATIONS SYSTEM
        Parses AI responses and autonomously decides what file operations to perform.
        Supports structured JSON with file_operations array and auto-detection from content.
        """
        if not working_dir:
            self._log("WARNING", "🚨 No working directory provided for file operations")
            return False
            
        try:
            import json
            
            self._log("INFO", "🧠 SureCli Intelligent CLI: Analyzing AI response for file operations...")
            self._log("INFO", f"📂 Working directory: {working_dir}")
            self._log("DEBUG", f"📝 Response text (first 300 chars): {text[:300]}...")
            
            # Clean and parse JSON response
            data = None
            t = text.strip()
            if t.startswith("```"):
                t = t.strip("`\n").split("\n", 1)[-1]
                if t.startswith("json\n"):
                    t = t[5:]
            
            try:
                data = json.loads(t)
                self._log("DEBUG", f"✅ Successfully parsed JSON: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
            except json.JSONDecodeError as e:
                self._log("ERROR", f"❌ Failed to parse JSON response: {e}")
                self._log("DEBUG", f"📝 Raw response: {t[:500]}")
                return False
            
            if not isinstance(data, dict):
                self._log("ERROR", f"❌ Response is not a JSON object: {type(data)}")
                return False
            
            operations_performed = False
            total_operations = 0
            operation_summary = []
            
            # Method 1: Structured file_operations array (preferred)
            if "file_operations" in data and isinstance(data["file_operations"], list):
                total_operations = len(data['file_operations'])
                self._log("INFO", f"🔧 Found structured file_operations array with {total_operations} operations")
                successful_ops = 0
                for i, operation in enumerate(data["file_operations"]):
                    op_type = operation.get("operation", "unknown")
                    op_file = operation.get("filename", "unknown")
                    operation_summary.append(f"{op_type} -> {op_file}")
                    if self._execute_single_file_operation(operation, working_dir, i + 1):
                        successful_ops += 1
                        operations_performed = True
                
                self._log("INFO", f"📊 Operation Summary: {successful_ops}/{total_operations} operations successful")
                for summary in operation_summary:
                    self._log("INFO", f"   📋 {summary}")
            
            # Method 2: Dedicated replace_operations array
            elif "replace_operations" in data and isinstance(data["replace_operations"], list):
                total_operations = len(data['replace_operations'])
                self._log("INFO", f"🔧 Found replace_operations array with {total_operations} operations")
                successful_ops = 0
                for i, operation in enumerate(data["replace_operations"]):
                    operation["operation"] = "replace"  # Force operation type
                    op_type = operation.get("operation", "unknown")
                    op_file = operation.get("filename", "unknown")
                    operation_summary.append(f"{op_type} -> {op_file}")
                    if self._execute_single_file_operation(operation, working_dir, i + 1):
                        successful_ops += 1
                        operations_performed = True
                
                self._log("INFO", f"📊 Operation Summary: {successful_ops}/{total_operations} operations successful")
                for summary in operation_summary:
                    self._log("INFO", f"   📋 {summary}")
            
            # Method 3: Legacy files array (backward compatibility)
            elif "files" in data and isinstance(data["files"], list):
                total_operations = len(data['files'])
                self._log("INFO", f"🔄 Found legacy files array with {total_operations} items")
                successful_ops = 0
                for i, item in enumerate(data["files"]):
                    # Convert legacy format to operation format
                    operation = {
                        "filename": item.get("path") or item.get("file"),
                        "operation": "write",
                        "content": item.get("content") or item.get("body"),
                        "location": working_dir
                    }
                    if item.get("is_dir") or (operation["filename"] and operation["filename"].endswith("/")):
                        operation["operation"] = "create_dir"
                    
                    op_type = operation.get("operation", "unknown")
                    op_file = operation.get("filename", "unknown")
                    operation_summary.append(f"{op_type} -> {op_file}")
                    
                    if self._execute_single_file_operation(operation, working_dir, i + 1):
                        successful_ops += 1
                        operations_performed = True
                
                self._log("INFO", f"📊 Operation Summary: {successful_ops}/{total_operations} operations successful")
                for summary in operation_summary:
                    self._log("INFO", f"   📋 {summary}")
            
            # Method 4: Auto-detection from top-level content keys
            else:
                self._log("INFO", "🔍 No structured operations found, auto-detecting from content keys...")
                detected_operations = self._auto_detect_file_operations(data, working_dir)
                
                if detected_operations:
                    total_operations = len(detected_operations)
                    self._log("INFO", f"🎯 Auto-detected {total_operations} file operations")
                    successful_ops = 0
                    for i, operation in enumerate(detected_operations):
                        op_type = operation.get("operation", "unknown")
                        op_file = operation.get("filename", "unknown")
                        operation_summary.append(f"{op_type} -> {op_file}")
                        if self._execute_single_file_operation(operation, working_dir, i + 1):
                            successful_ops += 1
                            operations_performed = True
                    
                    self._log("INFO", f"📊 Operation Summary: {successful_ops}/{total_operations} operations successful")
                    for summary in operation_summary:
                        self._log("INFO", f"   📋 {summary}")
                else:
                    self._log("WARNING", "⚠️ No file operations detected in AI response")
                    self._log("DEBUG", f"📊 Available keys: {list(data.keys())}")
            
            if operations_performed:
                self._log("INFO", "✅ SureCli Intelligent CLI completed file operations successfully")
                # Log final summary
                self._log("INFO", "📈 FINAL SUMMARY:")
                self._log("INFO", f"   📂 Working Directory: {working_dir}")
                self._log("INFO", f"   🧮 Total Operations: {total_operations}")
                self._log("INFO", f"   ✅ Successful Operations: {sum(1 for s in operation_summary if '->' in s)}")
                self._log("INFO", f"   📋 Operations List: {', '.join(operation_summary)}")
            else:
                self._log("WARNING", "⚠️ No file operations were performed")
            
            return operations_performed
            
        except Exception as e:
            self._log("ERROR", f"❌ SureCli Intelligent CLI error: {e}")
            import traceback
            self._log("DEBUG", f"🐛 Stack trace: {traceback.format_exc()}")
            return False
    
    def _auto_detect_file_operations(self, data: dict, working_dir: str) -> list:
        """
        Auto-detect file operations from content in the JSON response.
        Looks for common patterns like filenames as keys with content as values.
        """
    
    def generate_single_response(self, prompt: str, *, working_dir: Optional[str] = None, agent_name: Optional[str] = None, temperature: Optional[float] = None) -> str:
        """
        INTELLIGENT SURECLI SYSTEM
        
        Generate a single response using google.generativeai and intelligently execute file operations
        based on AI responses. This system can understand and perform:
        - File writing (create/overwrite)
        - File appending 
        - File deletion
        - File searching
        - Directory creation
        - Text replacement in files
        
        For io8 workflows with base projects, this will append to existing predefined documents.
        For standard workflows, it will intelligently parse AI responses for file operations.
        
        The system supports multiple input formats:
        1. Structured JSON with file_operations array (preferred)
        2. Legacy files array (backward compatibility) 
        3. Auto-detection from content keys
        
        This mirrors the interface of other CLI clients used by SequentialDocumentBuilder
        but adds intelligent file operation capabilities.
        """
        try:
            # Check if this is an io8 workflow with a base project
            is_io8_workflow = agent_name and agent_name.lower().startswith('io8')
            base_project_sureai_path = None
            
            if is_io8_workflow and working_dir:
                base_project_sureai_path = self._detect_base_project_structure(working_dir)
                if base_project_sureai_path:
                    self._log("INFO", f"🎆 io8 workflow detected with base project - will append to existing documents")
                else:
                    self._log("INFO", f"🎆 io8 workflow detected but no base project found - using standard file creation")
            
            # Run the async send_message in a blocking manner for compatibility
            loop = None
            try:
                import asyncio
                loop = asyncio.get_event_loop()
            except Exception:
                loop = None

            if loop and loop.is_running():
                # If we're already in an event loop, run in a new loop via thread executor
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    wrapped = self._wrap_prompt_as_json_spec(prompt, agent_name, working_dir)
                    fut = pool.submit(lambda: asyncio.run(self.send_message(wrapped, agent_name=agent_name, temperature=temperature)))
                    text = fut.result()
            else:
                import asyncio
                wrapped = self._wrap_prompt_as_json_spec(prompt, agent_name, working_dir)
                text = asyncio.run(self.send_message(wrapped, agent_name=agent_name, temperature=temperature))

            # Handle file writing based on workflow type
            if working_dir:
                try:
                    os.makedirs(working_dir, exist_ok=True)
                    
                    # For io8 workflows, STRICTLY only append to base project documents - NO file creation
                    if is_io8_workflow:
                        if base_project_sureai_path:
                            # Base project detected - try to append
                            appended = self._append_to_base_project_files(text, agent_name, base_project_sureai_path)
                            if appended:
                                self._log("INFO", f"✅ Successfully appended to base project documents for {agent_name}")
                                return text
                            else:
                                # For io8 workflows, do NOT fall back to file creation - log error and return
                                self._log("ERROR", f"❌ Failed to append to base project documents for {agent_name} - STRICT APPEND-ONLY MODE")
                                self._log("INFO", f"🔍 Base project path: {base_project_sureai_path}")
                                self._log("INFO", f"📝 Agent: {agent_name} should append to predefined documents only")
                                self._log("WARNING", f"🚫 NO FILES WILL BE CREATED for io8 workflow - append failed")
                                return text  # Return text but create NO files
                        else:
                            # No base project detected for io8 workflow - this should not happen
                            self._log("ERROR", f"❌ io8 workflow {agent_name} detected but NO base project found")
                            self._log("WARNING", f"🚫 NO FILES WILL BE CREATED for io8 workflow without base project")
                            self._log("INFO", f"🔍 Working directory: {working_dir}")
                            return text  # Return text but create NO files
                    
                    # Standard workflow (non-io8): Use intelligent file operations system
                    else:
                        self._log("INFO", f"🤖 Processing standard workflow for agent: {agent_name}")
                        self._log("INFO", f"📁 Working directory: {working_dir}")
                        
                        # Use the new intelligent file operations system
                        operations_successful = self._parse_and_execute_file_operations(text, working_dir)
                        
                        if operations_successful:
                            self._log("INFO", f"✅ Successfully completed file operations for {agent_name}")
                        else:
                            self._log("WARNING", f"⚠️ No file operations completed for {agent_name}")
                            self._log("INFO", f"💡 Tip: Ensure AI response contains structured file operations or detectable file patterns")
                        
                        # Enhanced user feedback
                        self._log("INFO", f"📊 Agent Response Status: {'Success' if operations_successful else 'No Operations'}")
                        self._log("INFO", f"🔄 Next Agent Handoff: Ready for next workflow step")
                        
                        # Show what files were created/modified
                        if operations_successful:
                            try:
                                # List files in working directory to show what was created
                                created_files = []
                                for root, dirs, files in os.walk(working_dir):
                                    for file in files:
                                        created_files.append(os.path.relpath(os.path.join(root, file), working_dir))
                                
                                if created_files:
                                    self._log("INFO", f"📁 Files in working directory: {', '.join(created_files[:10])}")
                                    if len(created_files) > 10:
                                        self._log("INFO", f"... and {len(created_files) - 10} more files")
                            except Exception as e:
                                self._log("DEBUG", f"Could not list working directory files: {e}")
                except Exception as e:
                    self._log("WARNING", f"SureCli could not write files to working dir: {e}")

            return text
        except SureCliError as se:
            # Bubble up structured errors so workflow can stop and resume
            raise se
        except Exception as e:
            # Wrap generic errors
            raise SureCliError("error", str(e))

    def _auto_detect_file_operations(self, data: dict, working_dir: str) -> list:
        """
        Auto-detect file operations from content in the JSON response.
        Looks for common patterns like filenames as keys with content as values.
        """
        operations = []
        
        # Common file-like keys that indicate file creation
        file_indicators = [
            # Direct file extensions
            r".*\.(md|txt|py|js|ts|html|css|json|yml|yaml|xml|sql|sh|bat|dockerfile)$",
            # Common file patterns
            r".*/.*\.(md|txt|py|js|ts|html|css|json|yml|yaml|xml|sql|sh|bat)$",
            # Common filenames
            r"^(readme|index|main|app|config|setup|install|requirements|package|docker-compose|makefile)\.(md|txt|py|js|ts|html|css|json|yml|yaml|xml|sql|sh|bat)$",
            # Directory patterns
            r".*/.*/$",
        ]
        
        import re
        
        for key, value in data.items():
            # Skip non-string values that are likely metadata
            if not isinstance(value, str) or len(value.strip()) == 0:
                continue
            
            # Check if key looks like a filename
            is_file = any(re.match(pattern, key.lower()) for pattern in file_indicators)
            
            # Also check for common document names that might not match patterns
            common_docs = [
                "analysis_document", "requirements_document", "architecture_document", 
                "tech_stack_document", "prd_document", "project_plan", "tasks_list",
                "sprint_plan", "directory_structure", "bug_list"
            ]
            
            is_common_doc = any(doc in key.lower() for doc in common_docs)
            
            if is_file or is_common_doc or key == "bug_report":
                # Determine operation type based on key and value content
                operation_type = "write"
                if key.endswith("/"):
                    operation_type = "create_dir"
                elif "append" in key.lower() or "add" in key.lower():
                    operation_type = "append"
                elif "delete" in key.lower() or "remove" in key.lower():
                    operation_type = "delete"
                elif "search" in key.lower() or "find" in key.lower():
                    operation_type = "search"
                elif "replace" in key.lower():
                    operation_type = "replace"
                elif key == "bug_report":
                    operation_type = "append"
                
                operation = {
                    "filename": key,
                    "operation": operation_type,
                    "content": value,
                    "location": working_dir
                }
                
                # Special handling for bug reports
                if key == "bug_report":
                    operation["filename"] = "bug-list.md"
                
                operations.append(operation)
                self._log("DEBUG", f"🎯 Auto-detected {operation_type} operation for: {key}")
        
        # If no operations detected, try to detect from content structure
        if not operations and isinstance(data, dict):
            # Look for common document sections
            doc_sections = {
                "analysis": ["analysis", "business_analysis"],
                "requirements": ["requirements", "business_requirements"],
                "architecture": ["architecture", "system_architecture"],
                "tech_stack": ["tech_stack", "technology_stack"],
                "prd": ["prd", "product_requirements"],
                "project_plan": ["project_plan", "plan"],
                "bug_list": ["bug_list", "bugs", "issues"]
            }
            
            for section, keys in doc_sections.items():
                for key in keys:
                    if key in data and isinstance(data[key], str):
                        filename = f"{section}_document.md"
                        if section == "bug_list":
                            filename = "bug-list.md"
                        operation = {
                            "filename": filename,
                            "operation": "write",
                            "content": data[key],
                            "location": working_dir
                        }
                        operations.append(operation)
                        self._log("DEBUG", f"🎯 Auto-detected document operation for: {filename}")
                        break
        
        # Check for line-specific replace operations
        if "replace_operations" in data and isinstance(data["replace_operations"], list):
            for op in data["replace_operations"]:
                if isinstance(op, dict):
                    operation = {
                        "filename": op.get("filename") or op.get("file"),
                        "operation": "replace",
                        "search": op.get("search"),
                        "replace": op.get("replace"),
                        "line_number": op.get("line_number") or op.get("line"),
                        "location": working_dir
                    }
                    operations.append(operation)
                    self._log("DEBUG", f"🎯 Auto-detected line-specific replace operation for: {operation['filename']}")
        
        return operations
    
    def _execute_single_file_operation(self, operation: dict, working_dir: str, operation_number: int) -> bool:
        """
        Execute a single file operation based on the operation specification.
        """
        try:
            filename = operation.get("filename") or operation.get("file") or operation.get("path")
            op_type = (operation.get("operation") or "write").lower()
            content = operation.get("content") or operation.get("body") or ""
            location = operation.get("location") or working_dir
            
            if not filename:
                self._log("WARNING", f"⚠️ Operation #{operation_number}: No filename specified")
                return False
            
            # Search for the file first
            abs_path = self._search_for_file(location, filename)
            
            self._log("INFO", f"🔧 Operation #{operation_number}: {op_type.upper()} -> {filename}")
            self._log("DEBUG", f"📁 Full path: {abs_path}")
            
            # Execute operation based on type
            result = False
            try:
                if op_type in ["write", "create", "w"]:
                    result = self._write_file(abs_path, content, filename)
                elif op_type in ["append", "add", "a"]:
                    result = self._append_file(abs_path, content, filename)
                elif op_type in ["delete", "remove", "rm", "d"]:
                    result = self._delete_file(abs_path, filename)
                elif op_type in ["search", "find", "s"]:
                    result = self._search_file(abs_path, content, filename)
                elif op_type in ["create_dir", "mkdir", "dir"]:
                    result = self._create_directory(abs_path, filename)
                elif op_type in ["replace", "replace_text", "r"]:
                    result = self._replace_in_file(abs_path, filename, operation)
                else:
                    self._log("WARNING", f"⚠️ Operation #{operation_number}: Unknown operation type '{op_type}'")
                    return False
                    
            except Exception as e:
                # Write bug report for self-correction
                self._write_bug_report(working_dir, operation, str(e))
                raise e
                
            return result
                
        except Exception as e:
            self._log("ERROR", f"❌ Operation #{operation_number} failed: {e}")
            return False

    def _search_for_file(self, working_dir: str, filename: str) -> str:
        """
        Search for a file in the working directory and subdirectories.
        Returns the absolute path if found, otherwise returns the expected path.
        """
        try:
            # First check if file exists at the specified path
            if os.path.isabs(filename):
                if os.path.exists(filename):
                    self._log("INFO", f"🔍 File found at absolute path: {filename}")
                    return filename
            else:
                # Check relative to working directory
                abs_path = os.path.join(working_dir, filename)
                if os.path.exists(abs_path):
                    self._log("INFO", f"🔍 File found at relative path: {filename}")
                    return abs_path
                
                # Search in subdirectories with more intelligent matching
                self._log("INFO", f"🔍 Searching for file '{filename}' in working directory and subdirectories...")
                for root, dirs, files in os.walk(working_dir):
                    # Skip hidden directories and virtual environments
                    dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', '__pycache__', 'venv', 'env']]
                    
                    # Exact match first
                    if filename in files:
                        found_path = os.path.join(root, filename)
                        self._log("INFO", f"✅ File found at: {found_path}")
                        return found_path
                    
                    # Check for files with similar names (case-insensitive)
                    for file in files:
                        if filename.lower() == file.lower():
                            found_path = os.path.join(root, file)
                            self._log("INFO", f"✅ File found (case-insensitive match): {found_path}")
                            return found_path
                    
                    # Check for partial matches in filename
                    for file in files:
                        if filename.lower() in file.lower() or file.lower() in filename.lower():
                            found_path = os.path.join(root, file)
                            self._log("INFO", f"✅ Similar file found: {found_path}")
                            return found_path
            
            # File not found, return expected path
            if os.path.isabs(filename):
                return filename
            else:
                abs_path = os.path.join(working_dir, filename)
                self._log("INFO", f"📁 File not found, will create at: {abs_path}")
                return abs_path
                
        except Exception as e:
            self._log("ERROR", f"❌ Error searching for file {filename}: {e}")
            # Return expected path even if search fails
            if os.path.isabs(filename):
                return filename
            else:
                return os.path.join(working_dir, filename)

    def _write_bug_report(self, working_dir: str, operation: dict, error: str) -> bool:
        """
        Write a bug report to bug-list.md for self-correction.
        """
        try:
            bug_file = os.path.join(working_dir, "bug-list.md")
            
            # Create bug report entry
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            bug_entry = f"""
## 🐛 Bug Report - {timestamp}

**Operation:** {operation.get('operation', 'unknown')}
**File:** {operation.get('filename', 'unknown')}
**Error:** {error}

**Operation Details:**
```json
{json.dumps(operation, indent=2)}
```

**🔍 Action Required:** Review and correct the operation

---
"""
            
            # Ensure parent directory exists
            parent_dir = os.path.dirname(bug_file)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            
            # Append to bug file
            with open(bug_file, "a", encoding="utf-8") as f:
                f.write(bug_entry)
            
            self._log("INFO", f"📝 Bug report written to: bug-list.md")
            return True
            
        except Exception as e:
            self._log("ERROR", f"❌ Failed to write bug report: {e}")
            return False

    def _write_file(self, abs_path: str, content: str, filename: str) -> bool:
        """
        Write content to a file (create or overwrite).
        """
        try:
            self._log("INFO", f"💾 Writing file: {filename}")
            self._log("INFO", f"📏 Content length: {len(content)} characters")
            
            # Ensure parent directory exists
            parent_dir = os.path.dirname(abs_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
                self._log("INFO", f"📁 Ensured parent directory exists: {parent_dir}")
            
            # Write file
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(self._normalize_markdown_content(content))
            
            self._log("INFO", f"✅ File created: {filename} ({len(content)} chars)")
            self._log("DEBUG", f"📍 File location: {abs_path}")
            return True
            
        except Exception as e:
            self._log("ERROR", f"❌ Failed to replace in file {filename}: {e}")
            return False
    
    def _append_file(self, abs_path: str, content: str, filename: str) -> bool:
        """
        Append content to an existing file.
        """
        try:
            self._log("INFO", f"📎 Appending to file: {filename}")
            self._log("INFO", f"📏 Content to append: {len(content)} characters")
            
            # Check if file exists
            if not os.path.exists(abs_path):
                self._log("WARNING", f"⚠️ File does not exist for append: {filename}")
                self._log("INFO", f"🔄 Creating new file instead: {filename}")
                return self._write_file(abs_path, content, filename)
            
            # Get current file size for logging
            current_size = os.path.getsize(abs_path)
            
            # Append to file
            with open(abs_path, "a", encoding="utf-8") as f:
                f.write(self._normalize_markdown_content(content))
            
            new_size = os.path.getsize(abs_path)
            appended_size = new_size - current_size
            
            self._log("INFO", f"✅ Content appended: {filename} (+{appended_size} chars, total: {new_size} chars)")
            self._log("DEBUG", f"📍 File location: {abs_path}")
            return True
            
        except Exception as e:
            self._log("ERROR", f"❌ Failed to append to file {filename}: {e}")
            return False
    
    def _delete_file(self, abs_path: str, filename: str) -> bool:
        """
        Delete a file or directory.
        """
        try:
            self._log("INFO", f"🗑️ Deleting: {filename}")
            
            if not os.path.exists(abs_path):
                self._log("WARNING", f"⚠️ File does not exist for deletion: {filename}")
                return False
            
            if os.path.isdir(abs_path):
                import shutil
                shutil.rmtree(abs_path)
                self._log("INFO", f"✅ Directory deleted: {filename}")
            else:
                os.remove(abs_path)
                self._log("INFO", f"✅ File deleted: {filename}")
            
            self._log("DEBUG", f"📍 Path deleted: {abs_path}")
            return True
            
        except Exception as e:
            self._log("ERROR", f"❌ Failed to delete {filename}: {e}")
            return False
    
    def _search_file(self, abs_path: str, search_term: str, filename: str) -> bool:
        """
        Search for content in a file and report results.
        """
        try:
            self._log("INFO", f"🔍 Searching in file: {filename}")
            self._log("INFO", f"🔎 Search term: '{search_term}'")
            
            if not os.path.exists(abs_path):
                self._log("WARNING", f"⚠️ File does not exist for search: {filename}")
                return False
            
            with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            
            # Simple search for now - can be enhanced with regex
            if search_term.lower() in content.lower():
                self._log("INFO", f"✅ Search found in {filename}: '{search_term}'")
                # Count occurrences
                count = content.lower().count(search_term.lower())
                self._log("INFO", f"📊 Found {count} occurrence(s) of '{search_term}'")
                
                # Show context around matches (first 3 matches)
                lines = content.split('\n')
                matches_found = 0
                for i, line in enumerate(lines):
                    if search_term.lower() in line.lower() and matches_found < 3:
                        self._log("DEBUG", f"📄 Line {i+1}: {line.strip()}")
                        matches_found += 1
            else:
                self._log("INFO", f"❌ Search not found in {filename}: '{search_term}'")
            
            self._log("DEBUG", f"📍 File searched: {abs_path}")
            return True
            
        except Exception as e:
            self._log("ERROR", f"❌ Failed to search file {filename}: {e}")
            return False
    
    def _create_directory(self, abs_path: str, dirname: str) -> bool:
        """
        Create a directory.
        """
        try:
            self._log("INFO", f"📁 Creating directory: {dirname}")
            
            os.makedirs(abs_path, exist_ok=True)
            self._log("INFO", f"✅ Directory created: {dirname}")
            self._log("DEBUG", f"📍 Directory path: {abs_path}")
            return True
            
        except Exception as e:
            self._log("ERROR", f"❌ Failed to create directory {dirname}: {e}")
            return False

    def _replace_in_file(self, abs_path: str, filename: str, operation: dict) -> bool:
        """
        Replace content in a file based on search and replace parameters.
        Supports both global search/replace and line-specific replacements.
        """
        try:
            search_term = operation.get("search", "")
            replace_term = operation.get("replace", "")
            line_number = operation.get("line_number") or operation.get("line")
            
            if not search_term and not line_number:
                self._log("WARNING", f"⚠️ No search term or line number provided for replace operation")
                return False
            
            self._log("INFO", f"🔄 Replacing in file: {filename}")
            if search_term:
                self._log("INFO", f"🔎 Search term: '{search_term}'")
            if replace_term:
                self._log("INFO", f"✍️ Replace term: '{replace_term}'")
            if line_number:
                self._log("INFO", f"📍 Line number: {line_number}")
            
            if not os.path.exists(abs_path):
                self._log("WARNING", f"⚠️ File does not exist for replace: {filename}")
                return False
            
            # Read file content
            with open(abs_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            # Line-specific replacement
            if line_number is not None:
                try:
                    line_idx = int(line_number) - 1  # Convert to 0-based index
                    if 0 <= line_idx < len(lines):
                        old_line = lines[line_idx]
                        if search_term:
                            # Replace specific text in the line
                            new_line = old_line.replace(search_term, replace_term)
                        else:
                            # Replace entire line
                            new_line = replace_term + "\n"
                        lines[line_idx] = new_line
                        self._log("INFO", f"✅ Replaced line {line_number}: '{old_line.strip()}' -> '{new_line.strip()}'")
                    else:
                        self._log("WARNING", f"⚠️ Line number {line_number} is out of range (1-{len(lines)})")
                        return False
                except ValueError:
                    self._log("ERROR", f"❌ Invalid line number: {line_number}")
                    return False
            else:
                # Global search and replace
                content = "".join(lines)
                count_before = content.lower().count(search_term.lower())
                new_content = content.replace(search_term, replace_term)
                count_after = new_content.lower().count(replace_term.lower())
                lines = new_content.splitlines(keepends=True)
                self._log("INFO", f"✅ Replaced {count_before} occurrence(s) in {filename}")
            
            # Write back to file
            with open(abs_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            
            self._log("DEBUG", f"📍 File location: {abs_path}")
            return True
            
        except Exception as e:
            self._log("ERROR", f"❌ Failed to replace in file {filename}: {e}")
            return False


if __name__ == "__main__":
    # This is just for testing purposes
    pass
