"""
Logger Utility Module for BMAD System

This module provides a centralized logging utility for capturing system events,
agent activities, and task progress. This is crucial for real-time logging to the frontend.
"""

import logging
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional
from logging.handlers import RotatingFileHandler
import json
import hashlib
import time

class LogDeduplicationFilter(logging.Filter):
    """Filter to prevent duplicate log messages from being printed repeatedly"""
    
    def __init__(self, max_duplicates=1, time_window=5.0):
        """
        Initialize the deduplication filter
        
        Args:
            max_duplicates: Maximum number of times the same log can be printed
            time_window: Time window in seconds to consider for deduplication
        """
        super().__init__()
        self.max_duplicates = max_duplicates
        self.time_window = time_window
        self.log_history = {}  # {hash: {'count': int, 'last_seen': float, 'last_printed': float}}
    
    def filter(self, record):
        """Filter method to check if log should be printed"""
        # Create a hash of the log message (excluding timestamp)
        log_content = f"{record.levelname}:{record.getMessage()}"
        log_hash = hashlib.md5(log_content.encode()).hexdigest()
        
        current_time = time.time()
        
        # Clean up old entries
        self._cleanup_old_entries(current_time)
        
        # Check if this log exists in history
        if log_hash in self.log_history:
            entry = self.log_history[log_hash]
            
            # If we've already printed this log enough times, suppress it
            if entry['count'] >= self.max_duplicates:
                # Only print again if enough time has passed since last print
                if current_time - entry['last_printed'] > self.time_window:
                    entry['last_printed'] = current_time
                    return True
                else:
                    return False
            else:
                # Increment count and update last seen
                entry['count'] += 1
                entry['last_seen'] = current_time
                entry['last_printed'] = current_time
                return True
        else:
            # New log message, add to history
            self.log_history[log_hash] = {
                'count': 1,
                'last_seen': current_time,
                'last_printed': current_time
            }
            return True
    
    def _cleanup_old_entries(self, current_time):
        """Remove old entries from history to prevent memory leaks"""
        to_remove = []
        for log_hash, entry in self.log_history.items():
            if current_time - entry['last_seen'] > self.time_window * 2:
                to_remove.append(log_hash)
        
        for log_hash in to_remove:
            del self.log_history[log_hash]

class HTTPRequestDeduplicationFilter(logging.Filter):
    """Specialized filter for HTTP request logs to prevent spam"""
    
    def __init__(self, time_window=30.0):
        """
        Initialize the HTTP request deduplication filter
        
        Args:
            time_window: Time window in seconds to consider for deduplication
        """
        super().__init__()
        self.time_window = time_window
        self.request_history = {}  # {endpoint: {'last_seen': float, 'count': int}}
    
    def filter(self, record):
        """Filter method to check if HTTP request log should be printed"""
        # Only process HTTP request logs
        if not hasattr(record, 'getMessage') or 'HTTP/1.1' not in record.getMessage():
            return True
        
        message = record.getMessage()
        current_time = time.time()
        
        # Extract endpoint from log message
        # Format: "IP - - [timestamp] "METHOD /path HTTP/1.1" status -"
        try:
            if '"' in message:
                parts = message.split('"')
                if len(parts) >= 2:
                    endpoint = parts[1]  # This should be "METHOD /path HTTP/1.1"
                    if endpoint in self.request_history:
                        entry = self.request_history[endpoint]
                        # If same endpoint was seen recently, suppress the log
                        if current_time - entry['last_seen'] < self.time_window:
                            entry['count'] += 1
                            entry['last_seen'] = current_time
                            return False
                        else:
                            # Reset count if enough time has passed
                            entry['count'] = 1
                            entry['last_seen'] = current_time
                            return True
                    else:
                        # New endpoint
                        self.request_history[endpoint] = {
                            'last_seen': current_time,
                            'count': 1
                        }
                        return True
        except Exception:
            # If parsing fails, allow the log through
            pass
        
        return True

class BMADFormatter(logging.Formatter):
    """Custom formatter for BMAD system logs"""
    
    def format(self, record):
        # Add timestamp
        record.timestamp = datetime.now().isoformat()
        
        # Add context if available
        if hasattr(record, 'task_id'):
            record.context = f"[Task: {record.task_id}]"
        elif hasattr(record, 'agent'):
            record.context = f"[Agent: {record.agent}]"
        else:
            record.context = "[System]"
        
        # Format the message
        formatted = f"{record.timestamp} - {record.context} - {record.levelname} - {record.getMessage()}"
        
        # Add exception info if present
        if record.exc_info:
            formatted += "\\n" + self.formatException(record.exc_info)
        
        return formatted

class TaskLogHandler(logging.Handler):
    """Custom handler for task-specific logging"""
    
    def __init__(self):
        super().__init__()
        self.task_logs = {}  # Store logs per task
        self.max_logs_per_task = 1000
    
    def emit(self, record):
        # Captures log records and stores them per task for retrieval
        try:
            task_id = getattr(record, 'task_id', 'system')
            
            if task_id not in self.task_logs:
                self.task_logs[task_id] = []
            
            # Format the record
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'level': record.levelname,
                'message': record.getMessage(),
                'module': record.module,
                'function': record.funcName,
                'line': record.lineno
            }
            
            # Add agent info if available
            if hasattr(record, 'agent'):
                log_entry['agent'] = record.agent
            
            # Add exception info if present
            if record.exc_info:
                log_entry['exception'] = self.format(record)
            
            # Store the log entry
            self.task_logs[task_id].append(log_entry)
            
            # Limit the number of logs per task
            if len(self.task_logs[task_id]) > self.max_logs_per_task:
                self.task_logs[task_id] = self.task_logs[task_id][-self.max_logs_per_task:]
        
        except Exception:
            self.handleError(record)
    
    def get_task_logs(self, task_id: str) -> list:
        # Returns all stored logs for specific task
        """Get logs for a specific task"""
        return self.task_logs.get(task_id, [])
    
    def get_recent_logs(self, task_id: str, limit: int = 50) -> list:
        # Returns recent logs for task with configurable limit
        """Get recent logs for a task"""
        logs = self.task_logs.get(task_id, [])
        return logs[-limit:] if logs else []
    
    def clear_task_logs(self, task_id: str):
        # Removes all stored logs for specific task to free memory
        """Clear logs for a specific task"""
        if task_id in self.task_logs:
            del self.task_logs[task_id]

# Global task log handler instance
task_log_handler = TaskLogHandler()

def setup_logging(log_level: str = "INFO", log_dir: str = "/tmp/bmad_logs") -> logging.Logger:
    """
    Set up logging configuration for the BMAD system
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory to store log files
        
    Returns:
        Configured logger instance
    """
    # Create log directory
    os.makedirs(log_dir, exist_ok=True)
    
    # Create main logger
    logger = logging.getLogger('bmad')
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = BMADFormatter()
    console_handler.setFormatter(console_formatter)
    
    # Add deduplication filter to console handler
    dedup_filter = LogDeduplicationFilter(max_duplicates=1, time_window=10.0)
    console_handler.addFilter(dedup_filter)
    
    logger.addHandler(console_handler)
    
    # File handler with rotation
    log_file = os.path.join(log_dir, 'bmad.log')
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = BMADFormatter()
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # Add task-specific handler
    task_log_handler.setLevel(logging.DEBUG)
    logger.addHandler(task_log_handler)
    
    # Error file handler
    error_file = os.path.join(log_dir, 'bmad_errors.log')
    error_handler = RotatingFileHandler(
        error_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=3
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)
    logger.addHandler(error_handler)
    
    logger.info("BMAD logging system initialized")
    return logger

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module
    
    Args:
        name: Name of the module/component
        
    Returns:
        Logger instance
    """
    # Get or create the main logger if it doesn't exist
    main_logger = logging.getLogger('bmad')
    if not main_logger.handlers:
        setup_logging()
    
    # Create child logger
    logger = logging.getLogger(f'bmad.{name}')
    return logger

class TaskLogger:
    """Context manager for task-specific logging"""
    
    def __init__(self, task_id: str, agent: str = None):
        self.task_id = task_id
        self.agent = agent
        self.logger = get_logger('task')
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.error(f"Exception in task {self.task_id}: {exc_val}")
    
    def _log(self, level: str, message: str, **kwargs):
        # Internal method that adds task context to log messages
        """Internal logging method"""
        extra = {'task_id': self.task_id}
        if self.agent:
            extra['agent'] = self.agent
        extra.update(kwargs)
        
        getattr(self.logger, level.lower())(message, extra=extra)
    
    def debug(self, message: str, **kwargs):
        self._log('DEBUG', message, **kwargs)
    
    def info(self, message: str, **kwargs):
        self._log('INFO', message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        self._log('WARNING', message, **kwargs)
    
    def error(self, message: str, **kwargs):
        self._log('ERROR', message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        self._log('CRITICAL', message, **kwargs)

class AgentLogger:
    """Logger specifically for agent activities"""
    
    def __init__(self, agent_name: str, task_id: str = None):
        self.agent_name = agent_name
        self.task_id = task_id
        self.logger = get_logger(f'agent.{agent_name}')
    
    def log_agent_start(self, task_description: str):
        # Logs when agent begins working on a task
        """Log when an agent starts working"""
        extra = {'agent': self.agent_name}
        if self.task_id:
            extra['task_id'] = self.task_id
        
        self.logger.info(
            f"Agent {self.agent_name} started: {task_description}",
            extra=extra
        )
    
    def log_agent_progress(self, progress_message: str, progress_percent: float = None):
        # Logs agent progress updates with optional percentage
        """Log agent progress"""
        extra = {'agent': self.agent_name}
        if self.task_id:
            extra['task_id'] = self.task_id
        if progress_percent is not None:
            extra['progress_percent'] = progress_percent
        
        self.logger.info(
            f"Agent {self.agent_name} progress: {progress_message}",
            extra=extra
        )
    
    def log_agent_complete(self, result_summary: str):
        # Logs when agent successfully completes a task
        """Log when an agent completes its task"""
        extra = {'agent': self.agent_name}
        if self.task_id:
            extra['task_id'] = self.task_id
        
        self.logger.info(
            f"Agent {self.agent_name} completed: {result_summary}",
            extra=extra
        )
    
    def log_agent_error(self, error_message: str, exception: Exception = None):
        # Logs agent errors with optional exception details
        """Log agent errors"""
        extra = {'agent': self.agent_name}
        if self.task_id:
            extra['task_id'] = self.task_id
        
        self.logger.error(
            f"Agent {self.agent_name} error: {error_message}",
            extra=extra,
            exc_info=exception
        )

def get_task_logs(task_id: str, limit: int = 50) -> list:
    """
    Get recent logs for a specific task
    
    Args:
        task_id: Task identifier
        limit: Maximum number of logs to return
        
    Returns:
        List of log entries
    """
    return task_log_handler.get_recent_logs(task_id, limit)

def get_all_task_logs(task_id: str) -> list:
    """
    Get all logs for a specific task
    
    Args:
        task_id: Task identifier
        
    Returns:
        List of all log entries for the task
    """
    return task_log_handler.get_task_logs(task_id)

def clear_task_logs(task_id: str):
    """
    Clear logs for a specific task
    
    Args:
        task_id: Task identifier
    """
    task_log_handler.clear_task_logs(task_id)

def export_task_logs(task_id: str, file_path: str) -> bool:
    """
    Export task logs to a file
    
    Args:
        task_id: Task identifier
        file_path: Path to export the logs
        
    Returns:
        True if export was successful, False otherwise
    """
    try:
        logs = get_all_task_logs(task_id)
        
        with open(file_path, 'w') as f:
            json.dump(logs, f, indent=2)
        
        return True
    except Exception as e:
        logger = get_logger('export')
        logger.error(f"Failed to export logs for task {task_id}: {e}")
        return False

# Initialize logging on module import
setup_logging()

