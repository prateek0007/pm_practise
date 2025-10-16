"""
Zrok Utilities Module

This module provides zrok-related utility functions to avoid circular imports
between the master workflow and bmad_api modules.
"""

import os
import subprocess
import json
import re
import time
from datetime import datetime
from src.utils.logger import get_logger

logger = get_logger(__name__)

def zrok_configured() -> bool:
    """Check if zrok is configured with required environment variables"""
    return bool(os.environ.get('ZROK_API_ENDPOINT')) and bool(os.environ.get('ZROK_ACCOUNT_TOKEN'))

def ensure_zrok_enabled() -> bool:
    """Ensure zrok environment is enabled"""
    if not zrok_configured():
        return False
    try:
        # idempotent: set endpoint then enable using token; ignore failures if already enabled
        endpoint = os.environ.get('ZROK_API_ENDPOINT')
        token = os.environ.get('ZROK_ACCOUNT_TOKEN')
        
        # Set the API endpoint
        subprocess.run(['zrok', 'config', 'set', 'apiEndpoint', endpoint], check=False)
        
        # Try to enable with the token
        proc = subprocess.run(['zrok', 'enable', token], capture_output=True, text=True)
        
        # Treat "already enabled" as success
        out = (proc.stdout or '').lower()
        err = (proc.stderr or '').lower()
        combined = out + '\n' + err
        already_enabled = any(sig in combined for sig in [
            'already enabled',
            'already have an enabled environment',
            'enabled environment'
        ])
        
        if proc.returncode == 0 or already_enabled:
            logger.info("Zrok environment enabled or already enabled")
            return True
        else:
            logger.warning(f"Zrok enable failed: {proc.stderr}")
            return False
    except Exception as e:
        logger.error(f"Failed to enable zrok: {e}")
        return False

def zrok_share_http(label: str, target_url: str) -> str | None:
    """Create a public HTTP share pointing to target_url. Returns public URL or None."""
    try:
        if not ensure_zrok_enabled():
            logger.warning("Zrok not enabled, cannot create share")
            return None

        # Start zrok share as a long-running process and stream output
        cmd = ['zrok', 'share', 'public', target_url, '--open', '--headless']
        logger.info(f"Starting zrok share: {' '.join(cmd)}")
        proc = subprocess.Popen(
            cmd,
            env=os.environ.copy(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        # Read lines until we detect the public URL or we hit a short deadline
        public_url = None
        deadline = time.time() + 30
        while time.time() < deadline:
            line = proc.stdout.readline() if proc.stdout else ''
            if not line:
                # process may still be starting; small sleep and retry
                time.sleep(0.2)
                continue
            logger.info(f"Zrok share output: {line.strip()}")
            # Extract URL conservatively; then sanitize trailing JSON punctuation
            matches = re.findall(r'(https?://[^\s]+)', line)
            if matches:
                candidate = matches[0]
                # Trim common trailing characters introduced by JSON logs
                candidate = candidate.strip().lstrip('@').strip('"')
                for stopper in ['","', '"', ',', '}', ']', ')']:
                    if stopper in candidate:
                        candidate = candidate.split(stopper)[0]
                # Final conservative rstrip of punctuation
                candidate = candidate.rstrip('",]} )')
                public_url = candidate
                break

        if not public_url:
            logger.error("Timed out waiting for zrok public URL")
            # Leave process running if it started; caller may retry
            return None

        logger.info(f"Created zrok share: {public_url}")
        return public_url
    except Exception as e:
        logger.error(f"Exception in zrok share: {e}")
        return None

def auto_create_zrok_share_for_task(task_id: str, project_dir: str, frontend_port: str) -> str | None:
    """
    Automatically create a zrok share for a task after port detection.
    This function is called from the master workflow to avoid circular imports.
    
    Args:
        task_id: The task identifier
        project_dir: Path to the project directory
        frontend_port: Detected frontend port
        
    Returns:
        The zrok public URL if successful, None otherwise
    """
    try:
        if not zrok_configured():
            logger.info(f"Zrok not configured, skipping automatic share creation for task {task_id}")
            return None
            
        if not ensure_zrok_enabled():
            logger.warning(f"Zrok not enabled, cannot create automatic share for task {task_id}")
            return None
            
        vm_ip = "157.66.191.31"  # Hardcoded VM IP
        local_url = f"http://{vm_ip}:{frontend_port}"
        label = f'auto-deploy-{task_id[:8]}'
        
        logger.info(f"🚀 Automatically creating zrok share for frontend port {frontend_port}")
        public_url = zrok_share_http(label, local_url)
        
        if public_url:
            # Update deploy.json with zrok URL
            deploy_path = os.path.join(project_dir, '.sureai', 'deploy.json')
            if os.path.exists(deploy_path):
                try:
                    with open(deploy_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    data['frontend_url'] = public_url
                    data['auto_created'] = True
                    data['created_at'] = datetime.now().isoformat()
                    with open(deploy_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2)
                    logger.info(f"✅ Auto-created zrok share: {public_url}")
                    return public_url
                except Exception as e:
                    logger.warning(f"⚠️ Could not update deploy.json with zrok URL: {e}")
                    return None
            else:
                logger.warning("⚠️ deploy.json not found for zrok URL update")
                return None
        else:
            logger.warning("⚠️ Failed to create automatic zrok share")
            return None
            
    except Exception as e:
        logger.error(f"❌ Error creating automatic zrok share: {str(e)}")
        return None
