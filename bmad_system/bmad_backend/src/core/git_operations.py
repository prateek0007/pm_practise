"""
Git Operations Module for FLF Agent

This module provides functions for git operations needed by the FLF agent,
such as cloning repositories and analyzing field patterns.
"""

import os
import subprocess
import logging
import json
import re
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

def clone_repository(url: str, destination: str) -> bool:
    """
    Clone a git repository to the specified destination
    
    Args:
        url: The git repository URL
        destination: The local destination path
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Validate inputs
        if not url or not destination:
            logger.error("Invalid parameters: url or destination is empty")
            return False
            
        # Ensure destination directory exists
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        
        # Remove destination if it already exists
        if os.path.exists(destination):
            import shutil
            try:
                shutil.rmtree(destination)
                logger.info(f"Removed existing directory: {destination}")
            except Exception as e:
                logger.error(f"Failed to remove existing directory {destination}: {e}")
                return False
        
        # Clone the repository
        logger.info(f"Cloning repository from {url} to {destination}")
        try:
            result = subprocess.run(
                ['git', 'clone', url, destination],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
        except FileNotFoundError:
            logger.error("Git command not found. Please ensure Git is installed and available in PATH.")
            return False
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout while cloning repository from {url}")
            return False
        except Exception as e:
            logger.error(f"Error running git clone command: {e}")
            return False
        
        if result.returncode == 0:
            logger.info(f"Successfully cloned repository from {url} to {destination}")
            return True
        else:
            logger.error(f"Failed to clone repository from {url}. Return code: {result.returncode}")
            logger.error(f"STDOUT: {result.stdout}")
            logger.error(f"STDERR: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Error cloning repository from {url}: {e}")
        return False

def analyze_field_patterns(project_path: str, folder_name: str) -> List[Dict[str, Any]]:
    """
    Analyze field patterns in the specified folder
    
    Args:
        project_path: The path to the cloned project
        folder_name: The folder name to analyze
        
    Returns:
        List of field pattern dictionaries
    """
    try:
        # Validate inputs
        if not project_path or not folder_name:
            logger.error("Invalid parameters: project_path or folder_name is empty")
            return [{"error": "Invalid parameters"}]
        
        target_path = os.path.join(project_path, folder_name)
        if not os.path.exists(target_path):
            logger.error(f"Target folder does not exist: {target_path}")
            return [{"error": f"Target folder not found: {target_path}"}]
        
        logger.info(f"Analyzing field patterns in {target_path}")
        
        # Scan directory for field patterns
        field_patterns = scan_directory_for_fields(target_path)
        
        # If no patterns found, return a default pattern
        if not field_patterns:
            logger.info("No field patterns found, returning default pattern")
            field_patterns = [{
                "techStack": "generic",
                "javacode": "Standardized template with fieldname and Labelfieldname placeholders",
                "operation_type": "ui_component_section",
                "fieldtype": "generic"
            }]
        
        logger.info(f"Found {len(field_patterns)} field patterns")
        return field_patterns
    except Exception as e:
        logger.error(f"Error analyzing field patterns: {e}")
        return [{"error": f"Field analysis failed: {str(e)}"}]

def find_ui_components(file_path: str) -> List[Dict[str, Any]]:
    """
    Find UI components in a file and extract field usage patterns
    
    Args:
        file_path: Path to the file to analyze
        
    Returns:
        List of field pattern dictionaries
    """
    try:
        # Validate input
        if not file_path:
            logger.error("Invalid parameter: file_path is empty")
            return []
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        field_patterns = []
        
        # Identify technology stack based on file extension and content
        tech_stack = identify_tech_stack(file_path, content)
        
        # Extract field patterns based on common UI patterns
        patterns = extract_field_patterns(content, tech_stack)
        field_patterns.extend(patterns)
        
        return field_patterns
    except Exception as e:
        logger.error(f"Error analyzing file {file_path}: {e}")
        return []

def identify_tech_stack(file_path: str, content: str) -> str:
    """
    Identify the technology stack based on file extension and content
    
    Args:
        file_path: Path to the file
        content: File content
        
    Returns:
        Technology stack identifier
    """
    try:
        # Validate inputs
        if not file_path:
            return 'generic'
        
        # Determine tech stack based on file extension and content clues
        if file_path.endswith('.html') or file_path.endswith('.htm'):
            if 'clr-' in content or 'clarity' in content.lower():
                return 'angularClarity'
            elif 'mat-' in content or 'material' in content.lower():
                return 'reactMaterial'
            elif 'el-' in content or 'element' in content.lower():
                return 'vueElement'
            else:
                return 'html'
        elif file_path.endswith('.js') or file_path.endswith('.jsx'):
            if 'angular' in content.lower() or 'ng-' in content:
                return 'angularClarity'
            elif 'react' in content.lower() or 'ReactDOM' in content:
                return 'reactMaterial'
            else:
                return 'javascript'
        elif file_path.endswith('.ts') or file_path.endswith('.tsx'):
            if '@angular' in content or 'ng-' in content:
                return 'angularClarity'
            elif 'react' in content.lower() or 'ReactDOM' in content:
                return 'reactMaterial'
            else:
                return 'typescript'
        elif file_path.endswith('.vue'):
            return 'vueElement'
        else:
            return 'generic'
    except Exception as e:
        logger.error(f"Error identifying tech stack for {file_path}: {e}")
        return 'generic'

def extract_field_patterns(content: str, tech_stack: str) -> List[Dict[str, Any]]:
    """
    Extract field patterns from content
    
    Args:
        content: File content
        tech_stack: Technology stack identifier
        
    Returns:
        List of field pattern dictionaries
    """
    try:
        field_patterns = []
        
        # Validate inputs
        if not content or not tech_stack:
            return field_patterns
        
        # Look for common field patterns
        # Input fields
        input_patterns = re.findall(r'<input[^>]*type=["\'](\w+)["\'][^>]*name=["\']([^"\']*)["\'][^>]*/?>', content)
        for field_type, field_name in input_patterns:
            field_patterns.append({
                "techStack": tech_stack,
                "javacode": f'<input type="{field_type}" name="fieldname" />',
                "operation_type": "addForm",
                "fieldtype": field_type
            })
        
        # Textarea fields
        textarea_patterns = re.findall(r'<textarea[^>]*name=["\']([^"\']*)["\'][^>]*>', content)
        for field_name in textarea_patterns:
            field_patterns.append({
                "techStack": tech_stack,
                "javacode": '<textarea name="fieldname"></textarea>',
                "operation_type": "addForm",
                "fieldtype": "textarea"
            })
        
        # Select fields
        select_patterns = re.findall(r'<select[^>]*name=["\']([^"\']*)["\'][^>]*>', content)
        for field_name in select_patterns:
            field_patterns.append({
                "techStack": tech_stack,
                "javacode": '<select name="fieldname">\n  //foreachentrysetstart\n  <option>fieldOption</option>\n  //foreachentrysetend\n</select>',
                "operation_type": "addForm",
                "fieldtype": "select"
            })
        
        # Handle Angular-specific patterns
        if 'angular' in tech_stack.lower():
            # Form control patterns
            form_control_patterns = re.findall(r'<input[^>]*formControlName=["\']([^"\']*)["\'][^>]*/?>', content)
            for field_name in form_control_patterns:
                field_patterns.append({
                    "techStack": tech_stack,
                    "javacode": '<input type="text" formControlName="fieldname" />',
                    "operation_type": "addForm",
                    "fieldtype": "text"
                })
            
            # ngModel patterns
            ng_model_patterns = re.findall(r'<input[^>]*\[\(ngModel\)\][^>]*name=["\']([^"\']*)["\'][^>]*/?>', content)
            for field_name in ng_model_patterns:
                field_patterns.append({
                    "techStack": tech_stack,
                    "javacode": '<input type="text" [(ngModel)]="rowSelected.fieldname" name="fieldname" />',
                    "operation_type": "editForm",
                    "fieldtype": "text"
                })
        
        return field_patterns
    except Exception as e:
        logger.error(f"Error extracting field patterns: {e}")
        return []

def scan_directory_for_fields(directory_path: str) -> List[Dict[str, Any]]:
    """
    Scan a directory for files and extract field patterns
    
    Args:
        directory_path: Path to the directory to scan
        
    Returns:
        List of field pattern dictionaries
    """
    field_patterns = []
    
    try:
        # Validate input
        if not directory_path or not os.path.exists(directory_path):
            logger.error(f"Invalid directory path: {directory_path}")
            return field_patterns
        
        for root, dirs, files in os.walk(directory_path):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for file in files:
                # Focus on common frontend file types
                if file.endswith(('.js', '.jsx', '.ts', '.tsx', '.html', '.vue')):
                    file_path = os.path.join(root, file)
                    try:
                        patterns = find_ui_components(file_path)
                        field_patterns.extend(patterns)
                    except Exception as e:
                        logger.error(f"Error processing file {file_path}: {e}")
                        continue
    except Exception as e:
        logger.error(f"Error scanning directory {directory_path}: {e}")
    
    # Remove duplicates by converting to set of tuples and back to list of dicts
    try:
        seen = set()
        unique_patterns = []
        for pattern in field_patterns:
            pattern_tuple = tuple(sorted(pattern.items()))
            if pattern_tuple not in seen:
                seen.add(pattern_tuple)
                unique_patterns.append(pattern)
        
        return unique_patterns
    except Exception as e:
        logger.error(f"Error removing duplicates: {e}")
        return field_patterns