"""
Gemini API Key Manager for BMAD System

This module manages multiple Gemini API keys with automatic rotation
when quota is exhausted, ensuring workflow continuity.
"""

import os
import json
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime
import logging
import threading
import time

logger = logging.getLogger(__name__)

class GeminiAPIKeyManager:
    """
    Manages multiple Gemini API keys with automatic rotation
    """
    
    def __init__(self, keys_file_path: str = None):
        """
        Initialize the API key manager
        
        Args:
            keys_file_path: Path to the keys configuration file
        """
        self.keys_file_path = keys_file_path or self._get_default_keys_path()
        self.api_keys: List[str] = []
        self.current_key_index = 0
        self.exhausted_keys: Dict[str, Dict[str, Any]] = {}  # key -> {timestamp, reason, attempts}
        self.max_retries_per_key = 3
        # Concurrency control and rotation pacing
        self._rotation_lock = threading.Lock()
        self._last_rotation_ts: float = 0.0
        self.rotation_cooldown_seconds: float = 3.0
        
        # Load API keys
        self._load_api_keys()
        
        # Policy: keep exhausted keys for accurate status/indices; skip them during use
        # This preserves UI correctness (current/exhausted display) and stable indices
        self.auto_remove_exhausted_keys: bool = False
    
    def _get_default_keys_path(self) -> str:
        """Get the default path for storing API keys"""
        try:
            # Store in the backend instance directory
            instance_dir = Path(__file__).parent.parent.parent / 'instance'
            instance_dir.mkdir(exist_ok=True)
            keys_path = str(instance_dir / 'gemini_api_keys.json')
            logger.info(f"API keys will be stored at: {keys_path}")
            return keys_path
        except Exception as e:
            logger.error(f"Error creating instance directory: {e}")
            # Fallback to current directory
            fallback_path = str(Path.cwd() / 'gemini_api_keys.json')
            logger.warning(f"Using fallback path: {fallback_path}")
            return fallback_path
    
    def _load_api_keys(self):
        """Load API keys from configuration file"""
        try:
            if os.path.exists(self.keys_file_path):
                try:
                    with open(self.keys_file_path, 'r') as f:
                        config = json.load(f)
                        self.api_keys = config.get('api_keys', [])
                        self.current_key_index = config.get('current_key_index', 0)
                        self.exhausted_keys = config.get('exhausted_keys', {})
                        
                        # Validate keys
                        self.api_keys = [key for key in self.api_keys if key and len(key.strip()) > 0]
                        
                        logger.info(f"Loaded {len(self.api_keys)} API keys from {self.keys_file_path}")
                        
                        # Ensure current_key_index is valid
                        if self.api_keys and (self.current_key_index >= len(self.api_keys) or self.current_key_index < 0):
                            self.current_key_index = 0
                except Exception as file_error:
                    logger.error(f"Error reading keys file {self.keys_file_path}: {file_error}")
                    # Reset to empty state
                    self.api_keys = []
                    self.current_key_index = 0
                    self.exhausted_keys = {}
                        
            else:
                logger.info(f"Keys file not found at {self.keys_file_path}, will try environment variable")
                
            # Try to load from environment variable as fallback
            env_key = os.getenv('GEMINI_API_KEY')
            if env_key:
                if not self.api_keys:  # Only add if we don't already have keys
                    self.api_keys = [env_key]
                    self.current_key_index = 0
                    logger.info("Loaded API key from environment variable")
                    try:
                        self._save_keys()
                    except Exception as save_error:
                        logger.warning(f"Could not save keys to file: {save_error}")
                else:
                    logger.info("API keys already loaded from file, environment variable not needed")
            else:
                if not self.api_keys:
                    logger.warning("No API keys found in configuration or environment")
                    
        except Exception as e:
            logger.error(f"Error loading API keys: {e}")
            # Fallback to environment variable
            env_key = os.getenv('GEMINI_API_KEY')
            if env_key:
                self.api_keys = [env_key]
                self.current_key_index = 0
                try:
                    self._save_keys()
                except Exception as save_error:
                    logger.warning(f"Could not save keys to file: {save_error}")
    
    def _save_keys(self):
        """Save current API key configuration to file"""
        try:
            # Ensure the directory exists
            keys_dir = Path(self.keys_file_path).parent
            keys_dir.mkdir(parents=True, exist_ok=True)
            
            config = {
                'api_keys': self.api_keys,
                'current_key_index': self.current_key_index,
                'exhausted_keys': self.exhausted_keys,
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.keys_file_path, 'w') as f:
                json.dump(config, f, indent=2)
                
            logger.info(f"Saved API key configuration to {self.keys_file_path}")
            
        except Exception as e:
            logger.error(f"Error saving API keys: {e}")
            # Try to save to a fallback location
            try:
                fallback_path = Path.cwd() / 'gemini_api_keys.json'
                with open(fallback_path, 'w') as f:
                    json.dump(config, f, indent=2)
                logger.warning(f"Saved API keys to fallback location: {fallback_path}")
            except Exception as fallback_error:
                logger.error(f"Failed to save to fallback location: {fallback_error}")
    
    def add_api_key(self, api_key: str, key_name: str = None) -> bool:
        """
        Add a new API key
        
        Args:
            api_key: The API key to add
            key_name: Optional name for the key (for identification)
            
        Returns:
            True if key was added successfully
        """
        try:
            if not api_key or not api_key.strip():
                logger.warning("Cannot add empty API key")
                return False
            
            # Check if key already exists
            if api_key in self.api_keys:
                logger.info("API key already exists")
                return True
            
            # Add the new key
            self.api_keys.append(api_key.strip())
            
            # If this is the first key, set it as current
            if len(self.api_keys) == 1:
                self.current_key_index = 0
            
            # Save configuration
            self._save_keys()
            
            logger.info(f"Added new API key (total: {len(self.api_keys)})")
            return True
            
        except Exception as e:
            logger.error(f"Error adding API key: {e}")
            return False
    
    def update_api_key_at_position(self, api_key: str, position: int) -> bool:
        """
        Update an API key at a specific position (0, 1, 2)
        This ensures only 3 keys maximum are maintained
        
        Args:
            api_key: The API key to set
            position: The position to update (0=primary, 1=other1, 2=other2)
            
        Returns:
            True if key was updated successfully
        """
        try:
            if not api_key or not api_key.strip():
                logger.warning("Cannot update with empty API key")
                return False
            
            if position < 0 or position > 2:
                logger.warning(f"Invalid position {position}. Must be 0, 1, or 2")
                return False
            
            api_key = api_key.strip()
            
            # Ensure we have enough slots
            while len(self.api_keys) <= position:
                self.api_keys.append("")
            
            # Update the key at the specified position
            old_key = self.api_keys[position] if position < len(self.api_keys) else ""
            self.api_keys[position] = api_key
            
            # Remove any keys beyond position 2 (keep only 3 keys max)
            if len(self.api_keys) > 3:
                self.api_keys = self.api_keys[:3]
            
            # Adjust current key index if it's beyond the new limit
            if self.current_key_index >= len(self.api_keys):
                self.current_key_index = 0
            
            # Remove exhausted status for the updated key
            if api_key in self.exhausted_keys:
                del self.exhausted_keys[api_key]
            
            # Save configuration
            self._save_keys()
            
            position_names = ["primary", "other1", "other2"]
            logger.info(f"Updated {position_names[position]} API key at position {position}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating API key at position {position}: {e}")
            return False
    
    def remove_api_key(self, api_key: str) -> bool:
        """
        Remove an API key
        
        Args:
            api_key: The API key to remove
            
        Returns:
            True if key was removed successfully
        """
        try:
            if api_key in self.api_keys:
                # Remove from exhausted keys if present
                if api_key in self.exhausted_keys:
                    del self.exhausted_keys[api_key]
                
                # Remove the key
                self.api_keys.remove(api_key)
                
                # Adjust current key index if necessary
                if self.api_keys:
                    if self.current_key_index >= len(self.api_keys):
                        self.current_key_index = 0
                else:
                    self.current_key_index = 0
                
                # Save configuration
                self._save_keys()
                
                logger.info(f"Removed API key (remaining: {len(self.api_keys)})")
                return True
            else:
                logger.warning("API key not found")
                return False
                
        except Exception as e:
            logger.error(f"Error removing API key: {e}")
            return False
    
    def get_current_key(self) -> Optional[str]:
        """
        Get the current active API key
        
        Returns:
            Current API key or None if no keys available
        """
        if not self.api_keys:
            # Reduce noise: only debug-log when no keys are configured
            logger.debug("No API keys available")
            return None
        
        if self.current_key_index >= len(self.api_keys):
            self.current_key_index = 0
        
        current_key = self.api_keys[self.current_key_index]
        logger.debug(f"Using API key {self.current_key_index + 1} of {len(self.api_keys)}")
        return current_key
    
    def mark_key_exhausted(self, api_key: str, reason: str = "quota_exhausted", attempts: int = 1):
        """
        Mark an API key as exhausted
        
        Args:
            api_key: The exhausted API key
            reason: Reason for exhaustion
            attempts: Number of attempts made with this key
        """
        try:
            with self._rotation_lock:
                if api_key in self.api_keys:
                    # Find the index of the exhausted key for better logging
                    exhausted_key_index = self.api_keys.index(api_key)
                    key_id = f"key{exhausted_key_index + 1}"
                    
                    self.exhausted_keys[api_key] = {
                        'timestamp': datetime.now().isoformat(),
                        'reason': reason,
                        'attempts': attempts
                    }
                    logger.warning(f"⚠️ Marked {key_id} as exhausted: {reason}")
                    
                    # Try to rotate to next key first
                    before_idx = self.current_key_index
                    rotated = self._rotate_to_next_key()
                    self._last_rotation_ts = time.time()
                    if not rotated:
                        logger.error("❌ No usable API key found during rotation")
                    else:
                        try:
                            after_idx = self.current_key_index
                            logger.info(f"🔁 Rotation complete: key{before_idx + 1} → key{after_idx + 1}")
                        except Exception:
                            pass
                    
                    # Optionally remove exhausted key (disabled by default)
                    if self.auto_remove_exhausted_keys:
                        try:
                            _ = self.api_keys.pop(exhausted_key_index)
                            self.exhausted_keys.pop(api_key, None)
                            if self.current_key_index >= len(self.api_keys):
                                self.current_key_index = 0 if self.api_keys else 0
                            logger.info(f"🧹 Removed exhausted API key {key_id} from rotation pool")
                        except Exception as _rem_err:
                            logger.warning(f"Could not remove exhausted key: {_rem_err}")
                    
                    # Save configuration
                    self._save_keys()
        except Exception as e:
            logger.error(f"Error marking key as exhausted: {e}")
    
    def _rotate_to_next_key(self) -> bool:
        """
        Rotate to the next available API key
        
        Returns:
            True if rotation was successful
        """
        if not self.api_keys:
            logger.error("No API keys available for rotation")
            return False
        
        # Find next available key
        original_index = self.current_key_index
        original_key = self.api_keys[original_index] if original_index < len(self.api_keys) else None
        attempts = 0
        
        while attempts < len(self.api_keys):
            self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
            current_key = self.api_keys[self.current_key_index]
            
            # Check if this key is not exhausted
            if current_key not in self.exhausted_keys:
                    # Enhanced logging with key identifiers
                    old_key_id = f"key{original_index + 1}" if original_key else "unknown"
                    new_key_id = f"key{self.current_key_index + 1}"
                    logger.info(f"🔄 Rotated from {old_key_id} to {new_key_id} (API key {self.current_key_index + 1} of {len(self.api_keys)})")
                    logger.info(f"✅ Current key is now {new_key_id} - {self.api_keys[self.current_key_index][-4:] if self.api_keys[self.current_key_index] else 'unknown'}")
                    return True
            
            attempts += 1
        
        # If all keys are exhausted, don't reset exhaustion status
        # This prevents infinite rotation through exhausted keys
        logger.error(f"❌ All API keys are exhausted. Cannot rotate to a usable key.")
        logger.error(f"❌ Exhausted keys: {list(self.exhausted_keys.keys())}")
        logger.error(f"🛑 WORKFLOW TERMINATION REQUIRED - No usable API keys available")
        return False
    
    def reset_exhausted_keys(self):
        """Reset all exhausted key statuses"""
        try:
            self.exhausted_keys.clear()
            self._save_keys()
            logger.info("Reset all exhausted key statuses")
        except Exception as e:
            logger.error(f"Error resetting exhausted keys: {e}")
    
    def get_key_status(self) -> Dict[str, Any]:
        """
        Get the current status of all API keys
        
        Returns:
            Dictionary containing key status information
        """
        try:
            status = {
                'total_keys': len(self.api_keys),
                'current_key_index': self.current_key_index,
                'current_key': self.get_current_key(),
                'exhausted_keys_count': len(self.exhausted_keys),
                'available_keys_count': len(self.api_keys) - len(self.exhausted_keys),
                'keys': []
            }
            
            for i, key in enumerate(self.api_keys):
                key_info = {
                    'index': i,
                    'is_current': i == self.current_key_index,
                    'is_exhausted': key in self.exhausted_keys,
                    'last_4_chars': key[-4:] if key else None
                }
                
                if key in self.exhausted_keys:
                    key_info.update({
                        'exhausted_at': self.exhausted_keys[key]['timestamp'],
                        'exhaustion_reason': self.exhausted_keys[key]['reason'],
                        'attempts': self.exhausted_keys[key]['attempts']
                    })
                
                status['keys'].append(key_info)
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting key status: {e}")
            return {}
    
    def is_quota_exhausted_error(self, error_message: str) -> bool:
        """
        Check if an error message indicates quota exhaustion
        
        Args:
            error_message: The error message to check
            
        Returns:
            True if the error indicates quota exhaustion
        """
        quota_indicators = [
            'quota exceeded',
            'quota exhausted',
            'rate limit exceeded',
            'quota limit',
            'billing not enabled',
            'quota limit exceeded',
            'quota exceeded for quota group',
            'insufficient quota',
            'quota exceeded for quota metric'
        ]
        
        error_lower = error_message.lower()
        return any(indicator in error_lower for indicator in quota_indicators)
    
    def handle_api_error(self, error_message: str, current_key: str = None) -> bool:
        """
        Handle API errors and determine if key rotation is needed
        
        Args:
            error_message: The error message from the API
            current_key: The current API key that caused the error
            
        Returns:
            True if key rotation was attempted (even if no additional keys available)
        """
        try:
            with self._rotation_lock:
                if not current_key:
                    current_key = self.get_current_key()
                if not current_key:
                    return False

                # Normalize once
                msg_lower = (error_message or '').lower()

                # 1) Quota exhausted -> rotate immediately (takes precedence over generic rate limit text)
                if self.is_quota_exhausted_error(error_message):
                    current_key_index = self.api_keys.index(current_key) if current_key in self.api_keys else -1
                    current_key_id = f"key{current_key_index + 1}" if current_key_index >= 0 else "unknown"
                    logger.warning(f"⚠️ Quota exhausted for {current_key_id}; marking exhausted and rotating")
                    self.mark_key_exhausted(current_key, "quota_exhausted")
                    # After mark_key_exhausted, current_key_index has advanced to a not-exhausted key if available
                    new_key = self.get_current_key()
                    if not new_key or new_key == current_key or new_key in self.exhausted_keys:
                        logger.error("❌ Rotation did not yield a usable new key")
                        logger.error("❌ No additional API keys available for rotation")
                        logger.error("🛑 WORKFLOW TERMINATION REQUIRED - All keys exhausted")
                        # Return False to signal no rotation possible - workflow should stop
                        return False
                    self._last_rotation_ts = time.time()
                    new_key_index = self.api_keys.index(new_key) if new_key in self.api_keys else -1
                    new_key_id = f"key{new_key_index + 1}" if new_key_index >= 0 else "unknown"
                    logger.info(f"✅ Rotation yielded a new usable key: {new_key_id}")
                    return True

                # 2) Transient rate limit (not quota): do not rotate, let retry/backoff handle
                rate_limit_indicators = ['rate limit', 'too many requests', 'rate limit exceeded']
                if any(ind in msg_lower for ind in rate_limit_indicators):
                    logger.info("Rate limit detected without clear quota exhaustion; not rotating.")
                    return False

                # Other errors: track attempts and possibly exhaust key
                if current_key in self.exhausted_keys:
                    self.exhausted_keys[current_key]['attempts'] += 1
                    if self.exhausted_keys[current_key]['attempts'] >= self.max_retries_per_key:
                        logger.warning("Too many attempts with current key; marking as exhausted")
                        self.mark_key_exhausted(current_key, "too_many_attempts")
                        return True
                return False
        except Exception as e:
            logger.error(f"Error handling API error: {e}")
            return False
    
    def get_available_keys_count(self) -> int:
        """Get the number of available (non-exhausted) keys"""
        return len(self.api_keys) - len(self.exhausted_keys)
    
    def has_available_keys(self) -> bool:
        """Check if there are any available keys"""
        return self.get_available_keys_count() > 0
    
    def is_current_key_usable(self) -> bool:
        """Check if the current key is usable (not exhausted)"""
        try:
            current_key = self.get_current_key()
            if not current_key:
                return False
            return current_key not in self.exhausted_keys
        except Exception as e:
            logger.error(f"Error checking if current key is usable: {e}")
            return False
