# UPDATED ENV DEPLOYMENT - Centralized Configuration System

## 🎯 NEW: Single Configuration File System

### **For BMAD URLs (Frontend/Backend):**
**File:** `env.config`
- `BACKEND_HOST` - Backend server IP
- `BACKEND_PORT` - Backend server port  
- `BACKEND_URL` - Full backend URL
- `FRONTEND_HOST` - Frontend server IP
- `FRONTEND_PORT` - Frontend server port
- `FRONTEND_URL` - Full frontend URL
- `API_BASE_URL` - API base URL for frontend
- `DEPLOYMENT_ENV` - Environment (production/development)
- `DOCKER_BACKEND_PORT` - Docker host port for backend (auto-updates docker-compose.yml)
- `DOCKER_FRONTEND_PORT` - Docker host port for frontend (auto-updates docker-compose.yml)

### **For JobPro Configuration:**
**File:** `bmad_frontend/src/config/environment.js`
- JobPro server details (IP, port, protocol, path)
- Connection settings (timeout, retries)
- Processing settings (intervals, batch size)
- Storage settings (prefix, max jobs, cleanup)

## 🚀 Quick Deployment Commands:

```bash
# Configure and deploy everything
./deploy.sh configure
./deploy.sh deploy

# Or single command
./deploy.sh deploy
```

## 📝 Manual Configuration:

### **To change BMAD URLs:**
```bash
# Edit env.config
vim env.config

# Then run to update frontend
./deploy.sh configure
```

### **To change JobPro settings:**
```bash
# Edit environment.js
vim bmad_frontend/src/config/environment.js
```

### **Important: Docker Port Mappings**
The `scripts/update-env.js` script automatically updates `docker-compose.yml` port mappings when you change ports in `env.config`:
- **Backend**: `"5006:5000"` (host:container)
- **Frontend**: `"5005:80"` (host:container)

**You only need to change ports in `env.config` - the script handles docker-compose.yml automatically!**

---

# OLD: Files to Change from localhost to IP 157.66.191.31

## Frontend Components (Change API_BASE_URL from '/api' to 'http://157.66.191.31:5006/api')

1. `bmad_frontend/src/App.jsx`
2. `bmad_frontend/src/components/TaskMonitor.jsx`
3. `bmad_frontend/src/components/WorkflowManager.jsx`
4. `bmad_frontend/src/components/AgentManager.jsx`
5. `bmad_frontend/src/components/WorkflowSelector.jsx`
6. `bmad_frontend/src/components/MCPManager.jsx`

## Docker Configuration (Change localhost to 157.66.191.31)

7. `docker-compose.yml`
   - Line 22: `ZROK_API_ENDPOINT=http://localhost:18080` → `ZROK_API_ENDPOINT=http://157.66.191.31:18080`
   - Line 35: `http://localhost:5000/api/health` → `http://157.66.191.31:5006/api/health`

8. `Dockerfile.backend` (if rebuilding)
   - The startup script has been simplified to start Flask app immediately
   - Alternative simple startup script added for testing

## What to Change:
- Find `const API_BASE_URL = '/api';`
- Replace with `const API_BASE_URL = 'http://157.66.191.31:5006/api';`

## Note:
- These changes are needed when deploying to production VM
- For local development, use relative URLs ('/api')
- For production deployment, use full URLs with production IP

## Recommended Setup:

### **Zrok-Enabled Setup (Recommended)**
For full functionality including zrok self-hosting:

```bash
# Stop current containers
docker-compose down

# Use the updated docker-compose.yml with full supervisor setup
docker-compose up -d --build

# Check status
docker-compose ps

# Monitor zrok services
docker-compose logs bmad-backend --follow
```

This setup uses the full supervisor configuration to start all zrok services, then automatically enables the zrok environment.

## Deployment Fixes Applied:

### 1. **Fixed Connection Refused Errors**
- **Problem**: Flask app wasn't starting due to zrok service failures
- **Solution**: Created simplified startup script that starts Flask app immediately
- **Result**: Backend now responds to API requests on port 5000

### 2. **Fixed Frontend API Configuration**
- **Problem**: Frontend was using hardcoded localhost URLs
- **Solution**: Changed all components to use relative URLs (`/api`)
- **Result**: Frontend now works correctly with nginx proxying

### 3. **Enhanced Nginx Configuration**
- **Problem**: nginx proxy was timing out
- **Solution**: Added timeout settings and better error handling
- **Result**: Stable API proxy connections

### 4. **Simplified Service Orchestration**
- **Problem**: Complex supervisor setup was failing
- **Solution**: Created alternative simple docker-compose file
- **Result**: Reliable deployment without zrok complexity

## Current Working Configuration:

- **Backend**: Flask app running on port 5000 (mapped to host port 5006)
- **Frontend**: React app served by nginx on port 5005
- **API Proxy**: nginx forwards `/api/*` requests to backend
- **Network**: All services on same Docker network for internal communication

## For Future zrok Integration:

When you're ready to add zrok functionality back:
1. Use the full `docker-compose.yml` (not the simple version)
2. Ensure all localhost references are updated to VM IP
3. The zrok services will start after the Flask app is running
4. Monitor logs for any zrok startup issues

## Zrok Configuration for Production:

### **DNS Setup Required:**
- **Domain**: `cloudnsure.com`
- **Wildcard DNS**: `*.cloudnsure.com` → `157.66.191.31`
- **Frontend Port**: `8080` (exposed to internet)

### **Generated URLs:**
- **Format**: `http://{token}.cloudnsure.com:8080`
- **Example**: `http://vyx5xza4587x.cloudnsure.com:8080`

### **Port Configuration:**
- **Controller**: `18080` (internal API)
- **Frontend**: `8080` (public access)
- **Backend**: `5006` (Flask app)

## Manual zrok Environment Enabling (Troubleshooting):

If automatic environment enabling fails, you can manually enable zrok:

```bash
# Connect to the backend container
docker exec -it bmad-backend bash

# Check zrok status
zrok status

# If environment is not enabled, create account and enable:
zrok admin create account admin@localhost adminpass123
# Copy the token from output, then:
zrok enable <TOKEN_FROM_PREVIOUS_COMMAND>

# Verify environment is enabled
zrok status

# Test zrok share
zrok share public localhost:3000
```

## Troubleshooting BMAD Logs Not Showing:

If you're not seeing BMAD application logs, try these solutions:

### **Option 1: Check Supervisor Status**
```bash
# Connect to container
docker exec -it bmad-backend bash

# Check supervisor status
supervisorctl status

# Check specific program status
supervisorctl status bmad-app

# View supervisor logs
tail -f /var/log/supervisor/supervisord.log
```

### **Option 2: Use Direct Startup (Bypass Supervisor)**
```bash
# Stop current container
docker-compose down

# Modify docker-compose.yml to use direct startup
# Change command: ["/start-bmad.sh"] to command: ["/start-bmad-direct.sh"]

# Restart
docker-compose up -d --build
```

### **Option 3: Check Log Files Directly**
```bash
# View BMAD app log file
docker exec bmad-backend cat /var/log/bmad-app.log

# View supervisor logs
docker exec bmad-backend tail -f /var/log/supervisor/supervisord.log
```

### **Option 4: Enable DEBUG Logging for Detailed Prompts**
To see the actual agent prompts being sent to Gemini CLI:

```bash
# Connect to container
docker exec -it bmad-backend bash

# Enable DEBUG logging
/enable-debug-logs.sh

# Restart container to apply changes
docker-compose restart bmad-backend

# Monitor logs with DEBUG level
docker-compose logs bmad-backend --follow
```

**What You'll See with DEBUG Logging:**
- ✅ Full agent prompts sent to Gemini CLI
- ✅ Prompt length and content details
- ✅ Previous documents being included
- ✅ Memory JSON injection details
- ✅ Complete prompt context

## Current Working Configuration:

- **Backend**: Flask app running on port 5000 (mapped to host port 5006)
- **Frontend**: React app served by nginx on port 5005
- **API Proxy**: nginx forwards `/api/*` requests to backend
- **Network**: All services on same Docker network for internal communication
- **Zrok**: Environment automatically enabled on startup (with zrok-enabled setup)


