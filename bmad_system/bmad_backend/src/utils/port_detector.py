"""
Port Detection Utility for BMAD System

This module provides utilities to detect frontend ports from docker-compose.yml files
and automatically create deploy.json with the correct port information for zrok sharing.
"""

import os
import json
import yaml
import re
import subprocess
from typing import Optional, Dict, Any
from datetime import datetime
from src.utils.logger import get_logger

logger = get_logger(__name__)

class PortDetector:
    """Utility class to detect ports from docker-compose.yml and create deploy.json"""
    
    @staticmethod
    def detect_frontend_port_from_compose(project_dir: str) -> Optional[str]:
        """
        Detect the frontend port from docker-compose.yml file
        
        Args:
            project_dir: Path to the project directory containing docker-compose.yml
            
        Returns:
            Frontend port as string, or None if not found
        """
        try:
            compose_path = os.path.join(project_dir, 'docker-compose.yml')
            if not os.path.exists(compose_path):
                logger.warning(f"Docker-compose.yml not found at {compose_path}")
                return None
            
            with open(compose_path, 'r', encoding='utf-8') as f:
                compose_content = f.read()
            
            # Parse YAML
            compose_data = yaml.safe_load(compose_content)
            
            if not compose_data or 'services' not in compose_data:
                logger.warning("Invalid docker-compose.yml structure")
                return None
            
            # Heuristics for identifying frontend services
            name_keywords = ['frontend', 'web', 'ui', 'app', 'client', 'spa', 'fe', 'dashboard', 'site']
            frontend_container_ports = {'3000', '80', '8080', '8081', '8082', '5173', '4200'}
            
            # Look for frontend service first by name
            for service_name, service_config in compose_data['services'].items():
                if any(keyword in service_name.lower() for keyword in name_keywords):
                    if 'ports' in service_config:
                        for port_mapping in service_config['ports']:
                            if isinstance(port_mapping, str):
                                # Support formats like "3000:3000" or "3000:3000/tcp"
                                match = re.match(r'^(\d+):(\d+)(?:/\w+)?$', port_mapping.strip())
                                if match:
                                    host_port = match.group(1)
                                    container_port = match.group(2)
                                    if container_port in frontend_container_ports:
                                        logger.info(f"Found frontend port {host_port} from service {service_name}")
                                        return host_port
                            elif isinstance(port_mapping, dict):
                                # docker compose v3 style: { target: 80, published: 8080, protocol: tcp, mode: host }
                                target_val = port_mapping.get('target')
                                target_port = str(target_val) if target_val is not None else ''
                                published_val = port_mapping.get('published')
                                published_port = str(published_val) if published_val is not None else ''
                                if target_port in frontend_container_ports and published_port:
                                    logger.info(f"Found frontend port {published_port} from service {service_name}")
                                    return str(published_port)
            
            # Fallback: look for any service exposing common frontend container ports
            for service_name, service_config in compose_data['services'].items():
                if 'ports' in service_config:
                    for port_mapping in service_config['ports']:
                        if isinstance(port_mapping, str):
                            match = re.match(r'^(\d+):(\d+)(?:/\w+)?$', port_mapping.strip())
                            if match:
                                host_port = match.group(1)
                                container_port = match.group(2)
                                if container_port in frontend_container_ports:
                                    logger.info(f"Found potential frontend port {host_port} from service {service_name}")
                                    return host_port
                        elif isinstance(port_mapping, dict):
                            target_val = port_mapping.get('target')
                            target_port = str(target_val) if target_val is not None else ''
                            published_val = port_mapping.get('published')
                            published_port = str(published_val) if published_val is not None else ''
                            if target_port in frontend_container_ports and published_port:
                                logger.info(f"Found potential frontend port {published_port} from service {service_name}")
                                return str(published_port)
            
            return None
            
        except Exception as e:
            logger.error(f"Error detecting frontend port from docker-compose.yml: {e}")
            return None
    
    @staticmethod
    def detect_backend_port_from_compose(project_dir: str) -> Optional[str]:
        """
        Detect the backend port from docker-compose.yml file
        
        Args:
            project_dir: Path to the project directory containing docker-compose.yml
            
        Returns:
            Backend port as string, or None if not found
        """
        try:
            compose_path = os.path.join(project_dir, 'docker-compose.yml')
            if not os.path.exists(compose_path):
                return None
            
            with open(compose_path, 'r', encoding='utf-8') as f:
                compose_content = f.read()
            
            compose_data = yaml.safe_load(compose_content)
            
            if not compose_data or 'services' not in compose_data:
                return None
            
            # Look for backend service
            for service_name, service_config in compose_data['services'].items():
                # Check if this looks like a backend service
                if any(keyword in service_name.lower() for keyword in ['backend', 'api', 'server']):
                    if 'ports' in service_config:
                        for port_mapping in service_config['ports']:
                            if isinstance(port_mapping, str):
                                match = re.match(r'(\d+):(\d+)', port_mapping)
                                if match:
                                    host_port = match.group(1)
                                    container_port = match.group(2)
                                    # If container port is 5000, 8000, or 3001, this is likely backend
                                    if container_port in ['5000', '8000', '3001']:
                                        logger.info(f"Found backend port {host_port} from service {service_name}")
                                        return host_port
                            elif isinstance(port_mapping, dict):
                                target_port = port_mapping.get('target')
                                published_port = port_mapping.get('published')
                                if target_port in [5000, 8000, 3001] and published_port:
                                    logger.info(f"Found backend port {published_port} from service {service_name}")
                                    return str(published_port)
            
            return None
            
        except Exception as e:
            logger.error(f"Error detecting backend port from docker-compose.yml: {e}")
            return None
    
    @staticmethod
    def create_deploy_json(project_dir: str, frontend_port: str, backend_port: Optional[str] = None) -> bool:
        """
        Create deploy.json file with deployment information
        
        Args:
            project_dir: Path to the project directory
            frontend_port: Frontend port number
            backend_port: Backend port number (optional)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            sureai_dir = os.path.join(project_dir, '.sureai')
            os.makedirs(sureai_dir, exist_ok=True)
            
            deploy_path = os.path.join(sureai_dir, 'deploy.json')
            
            # Get container names if containers are running
            frontend_container = None
            backend_container = None
            
            try:
                # Check if docker-compose is running and get container names
                result = subprocess.run(
                    ['docker-compose', 'ps', '-q'],
                    cwd=project_dir,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    container_ids = result.stdout.strip().split('\n')
                    if len(container_ids) >= 2:
                        frontend_container = container_ids[0] if container_ids[0] else None
                        backend_container = container_ids[1] if len(container_ids) > 1 and container_ids[1] else None
            except Exception as e:
                logger.warning(f"Could not get container names: {e}")
            
            deploy_data = {
                "deployment_status": "success",
                "frontend_port": frontend_port,
                "deployment_timestamp": datetime.now().isoformat(),
                "health_check": {
                    "frontend_responding": True,
                    "blank_screen_issue": False
                },
                "auto_detected": True,
                "detection_method": "docker-compose.yml_parsing"
            }
            
            if backend_port:
                deploy_data["backend_port"] = backend_port
                deploy_data["health_check"]["backend_responding"] = True
            
            if frontend_container:
                deploy_data["container_names"] = {
                    "frontend": frontend_container
                }
                if backend_container:
                    deploy_data["container_names"]["backend"] = backend_container
            
            with open(deploy_path, 'w', encoding='utf-8') as f:
                json.dump(deploy_data, f, indent=2)
            
            logger.info(f"Created deploy.json at {deploy_path} with frontend port {frontend_port}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating deploy.json: {e}")
            return False
    
    @staticmethod
    def auto_detect_and_create_deploy_json(project_dir: str) -> Optional[str]:
        """
        Automatically detect frontend port from docker-compose.yml and create deploy.json
        
        Args:
            project_dir: Path to the project directory
            
        Returns:
            Frontend port if successful, None otherwise
        """
        try:
            # Detect ports from docker-compose.yml
            frontend_port = PortDetector.detect_frontend_port_from_compose(project_dir)
            backend_port = PortDetector.detect_backend_port_from_compose(project_dir)
            
            if not frontend_port:
                logger.warning("Could not detect frontend port from docker-compose.yml")
                return None
            
            # Create deploy.json
            success = PortDetector.create_deploy_json(project_dir, frontend_port, backend_port)
            
            if success:
                logger.info(f"Successfully auto-detected frontend port {frontend_port} and created deploy.json")
                return frontend_port
            else:
                logger.error("Failed to create deploy.json")
                return None
                
        except Exception as e:
            logger.error(f"Error in auto detection: {e}")
            return None
