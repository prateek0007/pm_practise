# BMAD System Environment Configuration

This document explains how to use the centralized environment configuration system for the BMAD project.

## Overview

The BMAD system now uses a centralized environment configuration that eliminates the need to manually edit multiple files when switching between development and production environments.

## Files Created

1. **`env.config`** - Main environment configuration file
2. **`bmad_frontend/src/config/environment.js`** - Frontend environment utility
3. **`scripts/update-env.js`** - Node.js script to update all components
4. **`deploy.sh`** - Deployment script for easy environment switching

## Quick Start

### For Production (VM)
```bash
./deploy.sh configure
./deploy.sh deploy
```

## Environment Configuration File

The `env.config` file contains all production environment settings:

```bash
# Deployment Environment
DEPLOYMENT_ENV=production

# Backend Configuration
BACKEND_HOST=157.66.191.31
BACKEND_PORT=5006
BACKEND_URL=http://157.66.191.31:5006

# Frontend Configuration
FRONTEND_HOST=157.66.191.31
FRONTEND_PORT=5005
FRONTEND_URL=http://157.66.191.31:5005

# API Configuration
API_BASE_URL=http://157.66.191.31:5006/api

# Docker Configuration
DOCKER_BACKEND_PORT=5006
DOCKER_FRONTEND_PORT=5005
DOCKER_ZROK_CONTROLLER_PORT=18080
DOCKER_ZROK_FRONTEND_PORT=8080

# Zrok Configuration
ZROK_API_ENDPOINT=http://157.66.191.31:18080
```

## Deployment Script Usage

The `deploy.sh` script provides easy commands for managing the system:

### Configuration Commands
```bash
./deploy.sh configure       # Configure for production
```

### System Management Commands
```bash
./deploy.sh build           # Build Docker images
./deploy.sh start           # Start the system
./deploy.sh stop            # Stop the system
./deploy.sh restart         # Restart the system
./deploy.sh logs            # Show logs
./deploy.sh status          # Show system status
./deploy.sh clean           # Clean up containers and volumes
```

### Full Deployment Commands
```bash
./deploy.sh deploy          # Full production deployment
```

## Frontend Configuration

The frontend now uses a centralized configuration system in `bmad_frontend/src/config/environment.js`:

```javascript
import { API_BASE_URL, getApiUrl, isProduction, isDevelopment } from './config/environment';

// Use the centralized API_BASE_URL
const response = await fetch(`${API_BASE_URL}/tasks`);

// Or use the utility function
const response = await fetch(getApiUrl('/tasks'));

// Check environment
if (isProduction()) {
    // Production-specific code
}
```

## Components Updated

The following components now use the centralized configuration:

1. **`App.jsx`** - Main application component
2. **`TaskMonitor.jsx`** - Task monitoring component
3. **`WorkflowManager.jsx`** - Workflow management component
4. **`AgentManager.jsx`** - Agent management component
5. **`WorkflowSelector.jsx`** - Workflow selection component
6. **`MCPManager.jsx`** - MCP server management component

## Environment Configuration Process

When you run `./deploy.sh configure`, the following happens:

1. **Update `env.config`** - Sets the production environment and related URLs
2. **Update Frontend Components** - Runs the Node.js script to update all API_BASE_URL constants
3. **Update Docker Configuration** - Updates docker-compose.yml with correct endpoints
4. **Update Environment Utility** - Updates the frontend environment configuration

## Manual Configuration (if needed)

If you need to manually update the environment, you can:

### 1. Edit `env.config`
Change the values in the `env.config` file to match your production environment.

### 2. Run the Update Script
```bash
node scripts/update-env.js  # For production
```

### 3. Update Docker Compose
The script automatically updates `docker-compose.yml` with the correct endpoints.

## Environment Variables

### Production Environment
- **API_BASE_URL**: `http://157.66.191.31:5006/api` (full URL)
- **BACKEND_HOST**: `157.66.191.31`
- **BACKEND_PORT**: `5006`
- **FRONTEND_HOST**: `157.66.191.31`
- **FRONTEND_PORT**: `5005`

## Troubleshooting

### Common Issues

1. **Script Permission Denied**
   ```bash
   chmod +x deploy.sh
   ```

2. **Node.js Not Found**
   - Install Node.js or skip frontend configuration update
   - The script will continue with Docker configuration

3. **Docker Not Running**
   ```bash
   sudo systemctl start docker
   ```

4. **Port Already in Use**
   ```bash
   ./deploy.sh stop
   ./deploy.sh clean
   ./deploy.sh start
   ```

### Debugging

1. **Check Configuration**
   ```bash
   cat env.config
   ```

2. **Check System Status**
   ```bash
   ./deploy.sh status
   ```

3. **View Logs**
   ```bash
   ./deploy.sh logs
   ```

4. **Check Frontend Configuration**
   ```bash
   cat bmad_frontend/src/config/environment.js
   ```

## Migration from Old System

If you were previously manually editing files, the new system will:

1. **Automatically detect** your current configuration
2. **Update all components** to use the centralized system
3. **Preserve your settings** while making them configurable

### Before (Manual Editing)
```bash
# Had to edit multiple files manually
vim bmad_frontend/src/App.jsx
vim bmad_frontend/src/components/TaskMonitor.jsx
vim docker-compose.yml
# ... and many more files
```

### After (Centralized)
```bash
# Single command to switch environments
./deploy.sh configure prod
```

## Benefits

1. **Single Source of Truth** - All configuration in one place
2. **Easy Environment Switching** - One command to switch between dev/prod
3. **Reduced Errors** - No more forgetting to update a file
4. **Consistent Configuration** - All components use the same settings
5. **Automated Updates** - Scripts handle all the file updates
6. **Better Maintainability** - Easy to add new environments or settings

## Future Enhancements

The system is designed to be easily extensible:

1. **Add New Environments** - Staging, testing, etc.
2. **Add New Configuration Options** - Database URLs, API keys, etc.
3. **Add Validation** - Validate configuration before deployment
4. **Add Rollback** - Rollback to previous configuration if needed

## Support

If you encounter issues with the environment configuration:

1. Check the troubleshooting section above
2. Review the logs: `./deploy.sh logs`
3. Check the configuration: `cat env.config`
4. Verify the system status: `./deploy.sh status`
