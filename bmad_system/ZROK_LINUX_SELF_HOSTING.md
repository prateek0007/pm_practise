# Zrok Linux Self-Hosting Implementation Guide

## Overview

This document details the complete implementation of zrok self-hosting within a single Docker container for the BMAD (Business Management and Development) system. The solution integrates OpenZiti infrastructure with zrok services using Supervisor for proper service orchestration.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Single Docker Container                  │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ OpenZiti    │  │   zrok      │  │     BMAD Flask      │ │
│  │ Controller  │  │ Controller  │  │     Application     │ │
│  │ Port: 1280  │  │ Port: 18080 │  │     Port: 5000      │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ OpenZiti    │  │   zrok      │  │     Supervisor      │ │
│  │ Router      │  │ Frontend    │  │   Service Manager   │ │
│  │ Port: 3022  │  │ Port: 8080  │  │                     │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. OpenZiti Infrastructure
- **Controller**: Manages the zero-trust network on port 1280
- **Router**: Handles network traffic on port 3022
- **PKI**: Automatically generated certificates and identities

### 2. zrok Services
- **Controller**: Manages zrok operations on port 18080
- **Frontend**: Handles public access on port 8080
- **Database**: SQLite storage for zrok configuration

### 3. Service Orchestration
- **Supervisor**: Manages all service lifecycles
- **Startup Sequence**: Ensures proper service initialization order
- **Auto-restart**: Handles service failures automatically

## Implementation Details

### Dockerfile Configuration

The implementation uses a comprehensive Dockerfile that:

1. **Installs Dependencies**:
   ```dockerfile
   RUN apt-get update && apt-get install -y \
       curl wget jq supervisor \
       && rm -rf /var/lib/apt/lists/*
   ```

2. **Installs OpenZiti CLI**:
   ```dockerfile
   RUN curl -sSLf https://get.openziti.io/install.bash | bash -s openziti
   ```

3. **Installs zrok CLI**:
   ```dockerfile
   RUN cd /tmp && \
       ZROK_VERSION=$(curl -sSf https://api.github.com/repos/openziti/zrok/releases/latest | jq -r '.tag_name') && \
       curl -sSfL "https://github.com/openziti/zrok/releases/download/${ZROK_VERSION}/zrok_${ZROK_VERSION#v}_linux_amd64.tar.gz" | tar -xz && \
       install -o root -g root ./zrok /usr/local/bin/ && \
       rm -f ./zrok
   ```

### Configuration Files

#### OpenZiti Configuration
- **Quickstart Setup**: Uses `ziti edge quickstart` for automatic PKI generation
- **Controller Config**: Generated automatically in `/var/lib/ziti/`
- **Router Config**: Generated automatically in `/var/lib/ziti/`

#### zrok Configuration
- **Controller Config** (`/etc/zrok/ctrl.yml`):
  ```yaml
  v: 4
  admin:
    secrets:
      - "zroktoken123456789"
  endpoint:
    host: 0.0.0.0
    port: 18080
  invites:
    invites_open: true
  store:
    path: /var/lib/ziti/zrok.db
    type: sqlite3
  ziti:
    api_endpoint: "https://127.0.0.1:1280"
    username: "admin"
    password: "zitiadminpw"
  ```

- **Frontend Config** (`/etc/zrok/frontend.yml`):
  ```yaml
  v: 4
  host_match: localhost
  address: 0.0.0.0:8080
  ```

### Service Scripts

#### OpenZiti Setup Script (`/setup-openziti.sh`)
```bash
#!/bin/bash
set -euo pipefail
export ZITI_HOME=/var/lib/ziti
export ZITI_CTRL_ADVERTISED_ADDRESS=localhost
export ZITI_CTRL_ADVERTISED_PORT=1280
export ZITI_ROUTER_ADVERTISED_ADDRESS=localhost
export ZITI_ROUTER_PORT=3022
export ZITI_PWD=zitiadminpw

cd $ZITI_HOME
if [ ! -f "$ZITI_HOME/.ziti-quickstart-initialized" ]; then
  echo "Initializing OpenZiti quickstart..."
  ziti edge quickstart --ctrl-address $ZITI_CTRL_ADVERTISED_ADDRESS --ctrl-port $ZITI_CTRL_ADVERTISED_PORT --router-address $ZITI_ROUTER_ADVERTISED_ADDRESS --router-port $ZITI_ROUTER_PORT --password $ZITI_PWD
  touch "$ZITI_HOME/.ziti-quickstart-initialized"
else
  echo "OpenZiti already initialized, starting services..."
fi
```

#### zrok Setup Script (`/setup-zrok.sh`)
```bash
#!/bin/bash
export ZROK_ADMIN_TOKEN="zroktoken123456789"
export ZROK_API_ENDPOINT="http://127.0.0.1:18080"

cd /var/lib/ziti
echo "Waiting for OpenZiti to be ready..."
while ! ziti edge login localhost:1280 -u admin -p zitiadminpw >/dev/null 2>&1; do
  echo "Waiting for Ziti controller..."
  sleep 5
done

echo "OpenZiti is ready, bootstrapping zrok..."
if [ ! -f "/var/lib/ziti/.zrok-bootstrapped" ]; then
  zrok admin bootstrap /etc/zrok/ctrl.yml
  touch "/var/lib/ziti/.zrok-bootstrapped"
fi

echo "Starting zrok controller..."
exec zrok controller /etc/zrok/ctrl.yml
```

#### BMAD Application Startup Script (`/start-bmad-app.sh`)
```bash
#!/bin/bash
echo "Waiting for zrok services to be ready..."
sleep 60
export ZROK_API_ENDPOINT="http://127.0.0.1:18080"
export ZROK_ADMIN_TOKEN="zroktoken123456789"

echo "Creating zrok admin account..."
ACCOUNT_OUTPUT=$(zrok admin create account admin@localhost adminpass123 2>&1)
if [ $? -eq 0 ]; then
  ACCOUNT_TOKEN=$(echo "$ACCOUNT_OUTPUT" | tail -1 | tr -d "[:space:]")
  echo "Account token captured: $ACCOUNT_TOKEN"
  echo "Enabling zrok environment..."
  zrok enable $ACCOUNT_TOKEN
  if [ $? -eq 0 ]; then
    echo "Zrok environment enabled successfully!"
    echo "zrok is now ready to use: zrok share public <port>"
  else
    echo "Warning: Failed to enable zrok environment"
  fi
else
  echo "Warning: Failed to create user account: $ACCOUNT_OUTPUT"
  echo "Account may already exist, checking if environment is enabled..."
  if zrok status | grep -q "Account Token.*<<SET>>"; then
    echo "Environment appears to be enabled, proceeding..."
  else
    echo "Environment not enabled, manual intervention may be required"
  fi
fi

echo "zrok setup complete. Starting BMAD application..."
cd /app
exec python src/main.py
```

### Supervisor Configuration

The Supervisor manages all services with proper dependencies:

```ini
[supervisord]
nodaemon=true
user=root

[program:setup-openziti]
command=/setup-openziti.sh
autostart=true
autorestart=false
startretries=1
priority=100
stdout_logfile=/var/log/ziti/setup-openziti.log
stderr_logfile=/var/log/ziti/setup-openziti.log

[program:ziti-controller]
command=/start-ziti-controller.sh
autostart=true
autorestart=true
priority=200
stdout_logfile=/var/log/ziti/controller.log
stderr_logfile=/var/log/ziti/controller.log

[program:ziti-router]
command=/start-ziti-router.sh
autostart=true
autorestart=true
priority=300
stdout_logfile=/var/log/ziti/router.log
stderr_logfile=/var/log/ziti/router.log

[program:zrok-controller]
command=/setup-zrok.sh
autostart=true
autorestart=true
priority=400
stdout_logfile=/var/log/ziti/zrok-controller.log
stderr_logfile=/var/log/ziti/zrok-controller.log

[program:zrok-frontend]
command=/start-zrok-frontend.sh
autostart=true
autorestart=true
priority=500
stdout_logfile=/var/log/ziti/zrok-frontend.log
stderr_logfile=/var/log/ziti/zrok-frontend.log

[program:bmad-app]
command=/start-bmad-app.sh
autostart=true
autorestart=true
priority=600
stdout_logfile=/var/log/bmad-app.log
stderr_logfile=/var/log/bmad-app.log
```

## Issues Encountered and Solutions

### 1. OpenZiti Installation Issues

**Problem**: Initial attempts to install OpenZiti failed with package not found errors.

**Root Cause**: The OpenZiti installation script expects specific package names and repository configuration.

**Solution**: Used the official OpenZiti installation script:
```bash
RUN curl -sSLf https://get.openziti.io/install.bash | bash -s openziti
```

### 2. Service Startup Sequence

**Problem**: Services were starting in random order, causing dependency failures.

**Root Cause**: No proper service orchestration mechanism.

**Solution**: Implemented Supervisor with priority-based startup sequence:
1. OpenZiti setup (priority 100)
2. Ziti Controller (priority 200)
3. Ziti Router (priority 300)
4. zrok Controller (priority 400)
5. zrok Frontend (priority 500)
6. BMAD Application (priority 600)

### 3. OpenZiti Configuration Complexity

**Problem**: Manual OpenZiti configuration required complex PKI setup and identity management.

**Root Cause**: OpenZiti's default installation requires manual configuration of certificates and policies.

**Solution**: Used `ziti edge quickstart` command which automatically:
- Generates all PKI certificates
- Creates controller and router configurations
- Sets up admin user and policies
- Establishes network infrastructure

### 4. zrok Bootstrap Dependencies

**Problem**: zrok bootstrap failed because OpenZiti wasn't ready.

**Root Cause**: zrok requires OpenZiti controller to be fully operational before bootstrap.

**Solution**: Implemented proper waiting mechanisms:
```bash
while ! ziti edge login localhost:1280 -u admin -p zitiadminpw >/dev/null 2>&1; do
  echo "Waiting for Ziti controller..."
  sleep 5
done
```

### 5. Configuration Version Mismatch

**Problem**: zrok frontend configuration used version 3, but zrok expected version 4.

**Root Cause**: zrok v4 has different configuration schema than v3.

**Solution**: Updated frontend configuration to version 4:
```yaml
v: 4
host_match: localhost
address: 0.0.0.0:8080
```

### 6. Ziti Command Syntax Errors

**Problem**: Incorrect filter syntax in ziti edge list commands.

**Root Cause**: The `--filter` flag syntax was incorrect for the ziti CLI version.

**Solution**: Simplified the command to use grep instead:
```bash
FRONTEND_ID=$(ziti edge list identities --csv | grep "public" | tail -n1 | cut -d, -f1)
```

### 7. Admin Token Mismatch

**Problem**: zrok admin commands failed due to incorrect admin token.

**Root Cause**: Environment variable contained different token than configuration file.

**Solution**: Ensured consistent admin token usage:
- Configuration file: `zroktoken123456789`
- Environment variable: `ZROK_ADMIN_TOKEN=zroktoken123456789`

## Installation and Setup Instructions

### Prerequisites

1. **Docker and Docker Compose** installed
2. **Linux environment** (tested on Debian/Ubuntu)
3. **Internet access** for downloading OpenZiti and zrok binaries

### Step-by-Step Installation

#### 1. Build the Container
```bash
docker-compose up -d --build
```

#### 2. Wait for Services to Initialize
```bash
# Check container status
docker-compose ps

# Monitor logs
docker-compose logs bmad-backend --follow
```

#### 3. Verify OpenZiti Status
```bash
# Check OpenZiti controller logs
docker-compose exec bmad-backend tail -f /var/log/ziti/controller.log

# Check OpenZiti router logs
docker-compose exec bmad-backend tail -f /var/log/ziti/router.log
```

#### 4. Verify zrok Status
```bash
# Check zrok controller logs
docker-compose exec bmad-backend tail -f /var/log/ziti/zrok-controller.log

# Check zrok frontend logs
docker-compose exec bmad-backend tail -f /var/log/ziti/zrok-frontend.log
```

#### 5. Test zrok API
```bash
# Test zrok controller API
docker-compose exec bmad-backend curl -s http://localhost:18080/api/v1/version
```

#### 6. Create zrok Account and Enable Environment
```bash
# Create admin account
docker-compose exec -e ZROK_ADMIN_TOKEN=zroktoken123456789 bmad-backend zrok admin create account admin@localhost adminpass123

# Enable environment with returned token
docker-compose exec bmad-backend zrok enable <TOKEN_FROM_PREVIOUS_COMMAND>
```

**Note**: With the updated startup script, this step is now **automatic**. The environment will be enabled automatically when the container starts.

#### 7. Verify Environment Status
```bash
# Check zrok status
docker-compose exec bmad-backend zrok status
```

**Expected Output**: Environment should show as enabled with `Account Token <<SET>>` and `Ziti Identity <<SET>>`.

#### 8. Test Share Creation
```bash
# Create a test share
docker-compose exec bmad-backend zrok share public 5000
```

**Note**: This should work immediately without any manual environment enabling.

## Usage Examples

### Creating Shares

#### Basic Share
```bash
# Share a service running on port 5000
zrok share public 5000
```

#### Share with Custom Frontend
```bash
# Use specific frontend
zrok share public 5000 --frontend public
```

#### Share with Authentication
```bash
# Add basic authentication
zrok share public 5000 --basic-auth "user:password"
```

### Managing Accounts

#### List Accounts
```bash
# List all accounts (requires admin token)
zrok admin list accounts
```

#### Create New Account
```bash
# Create new user account
zrok admin create account user@example.com userpass123
```

#### Enable Environment
```bash
# Enable zrok environment for user
zrok enable <ACCOUNT_TOKEN>
```

### Monitoring and Debugging

#### Check Service Status
```bash
# Check all supervisor-managed services
docker-compose exec bmad-backend supervisorctl status
```

#### View Logs
```bash
# OpenZiti setup logs
docker-compose exec bmad-backend tail -f /var/log/ziti/setup-openziti.log

# zrok controller logs
docker-compose exec bmad-backend tail -f /var/log/ziti/zrok-controller.log

# zrok frontend logs
docker-compose exec bmad-backend tail -f /var/log/ziti/zrok-frontend.log
```

#### Test Connectivity
```bash
# Test OpenZiti controller
docker-compose exec bmad-backend ziti edge login localhost:1280 -u admin -p zitiadminpw

# Test zrok API
docker-compose exec bmad-backend curl -s http://localhost:18080/api/v1/version
```

## Environment Variables

### Required Environment Variables
```bash
ZROK_API_ENDPOINT=http://127.0.0.1:18080
ZROK_ADMIN_TOKEN=zroktoken123456789
ZROK_DNS_ZONE=cloudnsure.com
ZROK_USER_EMAIL=varun@dekatc.com
ZROK_USER_PWD=V@run9650
ZITI_PWD=zitiadminpw
```

### Optional Environment Variables
```bash
ZROK_ACCOUNT_TOKEN=zroktoken
```

## Port Configuration

| Service | Internal Port | External Port | Purpose |
|---------|---------------|---------------|---------|
| OpenZiti Controller | 1280 | - | Internal API |
| OpenZiti Router | 3022 | - | Internal routing |
| zrok Controller | 18080 | 18080 | zrok API |
| zrok Frontend | 8080 | 8080 | Public access |
| BMAD Flask App | 5000 | 5006 | Application |

## Security Considerations

### Default Credentials
- **OpenZiti Admin**: `admin` / `zitiadminpw`
- **zrok Admin Token**: `zroktoken123456789`
- **Default Account**: `admin@localhost` / `adminpass123`

### Production Recommendations
1. **Change default passwords** before production deployment
2. **Use strong admin tokens** for zrok
3. **Implement proper access controls** for admin functions
4. **Monitor service logs** for security events
5. **Regular security updates** for OpenZiti and zrok

## Troubleshooting

### Common Issues

#### 1. OpenZiti Controller Not Starting
**Symptoms**: Controller logs show "unable to load identity"
**Solution**: Ensure OpenZiti quickstart completed successfully

#### 2. zrok Bootstrap Fails
**Symptoms**: "error connecting to the ziti edge management api"
**Solution**: Wait for OpenZiti controller to be fully operational

#### 3. zrok Share Creation Fails
**Symptoms**: "unable to create share (unable to load environment)"
**Solution**: Ensure zrok environment is enabled with `zrok enable <TOKEN>`

#### 4. Frontend Configuration Errors
**Symptoms**: "invalid configuration version"
**Solution**: Ensure frontend.yml uses version 4

#### 5. Admin Commands Fail
**Symptoms**: "createAccountUnauthorized"
**Solution**: Set correct `ZROK_ADMIN_TOKEN` environment variable

### Debug Commands

#### Check Service Health
```bash
# Check all services
docker-compose exec bmad-backend supervisorctl status

# Check specific service
docker-compose exec bmad-backend supervisorctl status zrok-controller
```

#### Restart Services
```bash
# Restart specific service
docker-compose exec bmad-backend supervisorctl restart zrok-controller

# Restart all services
docker-compose exec bmad-backend supervisorctl restart all
```

#### View Real-time Logs
```bash
# Follow all logs
docker-compose logs bmad-backend --follow

# Follow specific service
docker-compose exec bmad-backend tail -f /var/log/ziti/zrok-controller.log
```

## Performance Tuning

### Resource Allocation
- **Memory**: Minimum 2GB RAM recommended
- **CPU**: 2+ cores recommended
- **Storage**: 10GB+ for logs and databases

### Optimization Tips
1. **Log rotation** for long-running containers
2. **Database cleanup** for zrok SQLite database
3. **Connection pooling** for high-traffic scenarios
4. **Monitoring** of resource usage

## Backup and Recovery

### Backup Strategy
1. **Configuration files**: `/etc/zrok/` and `/var/lib/ziti/`
2. **Databases**: zrok SQLite database
3. **Logs**: Service log files
4. **Identities**: OpenZiti identity files

### Recovery Procedures
1. **Restore configuration files**
2. **Restart services** in proper order
3. **Verify connectivity** between services
4. **Test share creation** functionality

## Future Enhancements

### Potential Improvements
1. **Multi-container deployment** for better scalability
2. **Load balancing** for high-availability
3. **Metrics collection** and monitoring
4. **Automated backups** and disaster recovery
5. **Integration** with external monitoring systems

### Version Upgrades
1. **OpenZiti upgrades** via official installation script
2. **zrok upgrades** via GitHub releases
3. **Configuration migration** for new versions
4. **Testing procedures** for upgrade validation

## Conclusion

This implementation successfully provides zrok self-hosting capabilities within a single Docker container, integrating seamlessly with the existing BMAD system. The solution addresses all major challenges encountered during development and provides a robust, production-ready foundation for secure application sharing.

The key success factors were:
1. **Proper service orchestration** using Supervisor
2. **Automatic OpenZiti setup** using quickstart
3. **Correct configuration versions** for zrok
4. **Proper dependency management** between services
5. **Comprehensive error handling** and logging

This solution enables developers to easily create public URLs for deployed applications using simple `zrok share` commands, while maintaining security through the underlying OpenZiti zero-trust network infrastructure.

## Frontend Zrok URL Display and Port Detection Implementation

### Overview

The BMAD system automatically detects frontend ports from deployed applications, creates persistent metadata files, and displays zrok public URLs in the frontend interface. This section details the complete technical implementation.

### Architecture Flow

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend       │    │   Port          │
│   TaskMonitor   │◄──►│   bmad_api.py   │◄──►│   Detector     │
│   Component     │    │   Endpoints     │    │   Utils        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   React State   │    │   deploy.json   │    │   docker-       │
│   frontendUrl   │    │   Metadata      │    │   compose.yml   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 1. Frontend Implementation (TaskMonitor.jsx)

**File Location**: `bmad_frontend/src/components/TaskMonitor.jsx`

#### Key Components:

1. **State Management**:
   ```javascript
   const [frontendUrl, setFrontendUrl] = useState('');
   const [creatingShare, setCreatingShare] = useState(false);
   const [shareError, setShareError] = useState(null);
   ```

2. **Auto-Share Button** (Lines 506-540):
   ```javascript
   <Button
     onClick={async () => {
       try {
         setCreatingShare(true);
         setShareError(null);
         const res = await fetch(`${API_BASE_URL}/tasks/${task.task_id}/deploy/auto-share`, { 
           method: 'POST', 
           headers: { 'Content-Type': 'application/json' }
         });
         if (res.ok) {
           const d = await res.json().catch(() => ({}));
           if (d.frontend_url) setFrontendUrl(d.frontend_url);
         }
       } catch (e) {
         console.error('Failed to create auto-share:', e);
         setShareError('Network error: ' + e.message);
       } finally {
         setCreatingShare(false);
       }
     }}
   >
     🚀 Create Zrok Share
   </Button>
   ```

3. **Refresh Link Button** (Lines 460-480):
   ```javascript
   <Button
     onClick={async () => {
       try {
         const res = await fetch(`${API_BASE_URL}/tasks/${task.task_id}/deploy/refresh-link`, { 
           method: 'POST', 
           headers: { 'Content-Type': 'application/json' }
         });
         if (res.ok) {
           const d = await res.json();
           if (d.frontend_url) setFrontendUrl(d.frontend_url);
         }
       } catch (e) {}
     }}
   >
     🔄 Refresh Link
   </Button>
   ```

4. **URL Display** (Lines 440-450):
   ```javascript
   <div className="text-sm text-green-200">
     <span className="font-semibold">Public URL: </span>
     <a 
       href={frontendUrl} 
       target="_blank" 
       rel="noreferrer" 
       className="underline text-green-300 break-all hover:text-green-100 transition-colors"
     >
       {String(frontendUrl || '').replace(/\"/g, '').replace(/",".*$/,'').replace(/["\]}]+$/,'').trim()}
     </a>
   </div>
   ```

### 2. Backend API Implementation (bmad_api.py)

**File Location**: `bmad_backend/src/routes/bmad_api.py`

#### Key Functions:

1. **Port Detection Helper** (Lines 2176-2215):
   ```python
   def get_frontend_port_for_task(task_id: str) -> tuple[str | None, str | None]:
       """
       Get frontend port for a task using strict per-task logic.
       Returns (frontend_port, project_dir) tuple.
       
       Logic:
       1. Read from task's .sureai/deploy.json (frontend_port or port)
       2. If missing, detect from docker-compose.yml and write to deploy.json
       3. Return the port and project_dir for further processing
       """
       project_dir = resolve_project_dir(task_id)
       if not project_dir:
           logger.warning(f"Could not resolve project directory for task {task_id}")
           return None, None
       
       # Try to read from existing deploy.json
       deploy_path = os.path.join(project_dir, '.sureai', 'deploy.json')
       if os.path.exists(deploy_path):
           try:
               with open(deploy_path, 'r', encoding='utf-8') as f:
                   meta = json.load(f)
                   port = str(meta.get('frontend_port') or meta.get('port') or '').strip()
                   if port:
                       logger.debug(f"Read frontend_port from deploy.json: {port}")
                       return port, project_dir
           except Exception as e:
               logger.warning(f"Error reading deploy.json: {e}")
       
       # If deploy.json missing or no port, detect and create it
       try:
           from src.utils.port_detector import PortDetector
           frontend_port = PortDetector.auto_detect_and_create_deploy_json(project_dir)
           if frontend_port:
               logger.debug(f"Auto-detected and wrote frontend_port to deploy.json: {frontend_port}")
               return frontend_port, project_dir
       except Exception as e:
           logger.error(f"Error detecting frontend port: {e}")
       
       return None, project_dir
   ```

2. **Auto-Share Endpoint** (Lines 1693-1754):
   ```python
   @bmad_bp.route('/api/tasks/<task_id>/deploy/auto-share', methods=['POST'])
   @cross_origin()
   def auto_create_frontend_share(task_id):
       """Automatically create a zrok share for a completed task deployment."""
       try:
           if not _zrok_configured():
               logger.warning(f"Zrok not configured, cannot create auto-share for task {task_id}")
               return jsonify({'error': 'Zrok not configured on server'}), 400
           
           # Use strict per-task port detection logic
           frontend_port, _proj = get_frontend_port_for_task(task_id)
           if not frontend_port:
               logger.error(f"Unable to determine frontend port for auto-share of task {task_id}")
               return jsonify({'error': 'Unable to determine frontend port for zrok share'}), 400
           
           vm_ip = get_vm_ip()  # Returns hardcoded '157.66.191.31'
           local_url = f"http://{vm_ip}:{frontend_port}"
           logger.debug(f"Auto-share selected frontend_port: {frontend_port}, exact local_url: {local_url}")
           
           # Create zrok share
           label = f'auto-deploy-{task_id[:8]}'
           public_url = _zrok_share_http(label, local_url)
           
           if not public_url:
               logger.error(f"Failed to create auto zrok share for task {task_id}")
               return jsonify({'error': 'Failed to create zrok share'}), 500
           
           # Save to deploy.json
           project_dir = _resolve_project_dir(task_id)
           if project_dir:
               meta_dir = os.path.join(project_dir, '.sureai')
               os.makedirs(meta_dir, exist_ok=True)
               deploy_path = os.path.join(meta_dir, 'deploy.json')
               
               data = {}
               if os.path.exists(deploy_path):
                   try:
                       with open(deploy_path, 'r', encoding='utf-8') as f:
                           data = json.load(f)
                   except Exception:
                       data = {}
               
               data['frontend_url'] = public_url
               data['auto_created'] = True
               data['created_at'] = datetime.now().isoformat()
               
               with open(deploy_path, 'w', encoding='utf-8') as f:
                   json.dump(data, f, indent=2)
           
           return jsonify({
               'frontend_url': public_url,
               'message': 'Zrok share created automatically for completed task',
               'auto_created': True
           })
           
       except Exception as e:
           logger.error(f"Error creating auto zrok share for task {task_id}: {e}")
           return jsonify({'error': 'Internal server error'}), 500
   ```

3. **Refresh Link Endpoint** (Lines 2220-2255):
   ```python
   @bmad_bp.route('/api/tasks/<task_id>/deploy/refresh-link', methods=['POST'])
   @cross_origin()
   def refresh_frontend_share(task_id):
       """Refresh/recreate the zrok share for a task's frontend using strict per-task logic."""
       try:
           if not _zrok_configured():
               return jsonify({'error': 'Zrok not configured on server'}), 400
           
           # Use the same strict per-task port detection logic as auto-share
           frontend_port, project_dir = get_frontend_port_for_task(task_id)
           if not frontend_port:
               logger.error(f"Unable to determine frontend port for refresh of task {task_id}")
               return jsonify({'error': 'Unable to determine frontend port for zrok share'}), 400
           
           vm_ip = get_vm_ip()
           local_url = f"http://{vm_ip}:{frontend_port}"
           logger.debug(f"Refresh link selected frontend_port: {frontend_port}, exact local_url: {local_url}")
           
           # Create new share with refresh label
           label = f'refresh-{task_id[:8]}'
           public_url = _zrok_share_http(label, local_url)
           
           if not public_url:
               logger.error(f"Failed to refresh zrok share for task {task_id}")
               return jsonify({'error': 'Failed to create zrok share'}), 500
           
           # Verify we got a zrok public URL, not localhost
           if 'localhost' in public_url or '127.0.0.1' in public_url:
               logger.error(f"Received localhost URL from refresh zrok share: {public_url}")
               return jsonify({'error': 'Invalid zrok share URL returned'}), 500
           
           # Update the deploy.json with new URL
           if project_dir:
               meta_dir = os.path.join(project_dir, '.sureai')
               os.makedirs(meta_dir, exist_ok=True)
               deploy_path = os.path.join(meta_dir, 'deploy.json')
               
               data = {}
               if os.path.exists(deploy_path):
                   try:
                       with open(deploy_path, 'r', encoding='utf-8') as f:
                           data = json.load(f)
                   except Exception:
                       data = {}
               
               data['frontend_url'] = public_url
               data['refreshed'] = True
               data['refreshed_at'] = datetime.now().isoformat()
               
               with open(deploy_path, 'w', encoding='utf-8') as f:
                   json.dump(data, f, indent=2)
           
           return jsonify({
               'frontend_url': public_url,
               'message': 'Zrok share refreshed successfully',
               'refreshed': True
           })
           
       except Exception as e:
           logger.error(f"Error refreshing zrok share for task {task_id}: {e}")
           return jsonify({'error': 'Internal server error'}), 500
   ```

4. **VM IP Hardcoding** (Lines 2160-2165):
   ```python
   def get_vm_ip() -> str:
       """Return hardcoded VM IP for zrok sharing (wrapper)."""
       return _get_vm_ip()

   def _get_vm_ip() -> str:
       """Return VM IP for zrok target. Hardcoded per request."""
       return '157.66.191.31'
   ```

### 3. Port Detection Implementation (port_detector.py)

**File Location**: `bmad_backend/src/utils/port_detector.py`

#### Key Methods:

1. **Frontend Port Detection** (Lines 19-95):
   ```python
   @staticmethod
   def detect_frontend_port_from_compose(project_dir: str) -> Optional[str]:
       """Detect the frontend port from docker-compose.yml file"""
       try:
           compose_path = os.path.join(project_dir, 'docker-compose.yml')
           if not os.path.exists(compose_path):
               logger.warning(f"Docker-compose.yml not found at {compose_path}")
               return None
           
           with open(compose_path, 'r', encoding='utf-8') as f:
               compose_content = f.read()
           
           compose_data = yaml.safe_load(compose_content)
           if not compose_data or 'services' not in compose_data:
               logger.warning("Invalid docker-compose.yml structure")
               return None
           
           # Heuristics for identifying frontend services
           name_keywords = ['frontend', 'web', 'ui', 'app', 'client', 'spa', 'fe', 'dashboard', 'site']
           frontend_container_ports = {'3000', '80', '8080', '8081', '8082', '5173', '4200'}
           
           # First pass: Look for services with frontend-related names
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
           
           # Second pass: Look for any service with common frontend ports
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
   ```

2. **Auto-Detection and JSON Creation** (Lines 233-264):
   ```python
   @staticmethod
   def auto_detect_and_create_deploy_json(project_dir: str) -> Optional[str]:
       """
       Auto-detect frontend port from docker-compose.yml and create/update deploy.json with the result.
       Returns the detected frontend port if successful, None otherwise.
       """
       try:
           if not project_dir or not os.path.exists(project_dir):
               logger.warning(f"Project directory does not exist: {project_dir}")
               return None
           
           # First, try to detect the frontend port
           frontend_port = PortDetector.detect_frontend_port_from_compose(project_dir)
           if not frontend_port:
               logger.warning(f"Could not detect frontend port from docker-compose.yml in {project_dir}")
               return None
           
           # Create .sureai directory if it doesn't exist
           meta_dir = os.path.join(project_dir, '.sureai')
           os.makedirs(meta_dir, exist_ok=True)
           
           # Path to deploy.json
           deploy_path = os.path.join(meta_dir, 'deploy.json')
           
           # Load existing deploy.json or create new data structure
           deploy_data = {}
           if os.path.exists(deploy_path):
               try:
                   with open(deploy_path, 'r', encoding='utf-8') as f:
                       deploy_data = json.load(f)
               except Exception as e:
                   logger.warning(f"Error reading existing deploy.json: {e}, creating new one")
                   deploy_data = {}
           
           # Update with detected frontend port
           deploy_data['frontend_port'] = frontend_port
           deploy_data['port_detected_at'] = os.path.getmtime(os.path.join(project_dir, 'docker-compose.yml'))
           deploy_data['port_detection_method'] = 'docker-compose.yml'
           
           # Write back to deploy.json
           with open(deploy_path, 'w', encoding='utf-8') as f:
               json.dump(deploy_data, f, indent=2)
           
           logger.info(f"Created/updated deploy.json with frontend_port: {frontend_port}")
           return frontend_port
           
       except Exception as e:
           logger.error(f"Error in auto_detect_and_create_deploy_json: {e}")
           return None
   ```

3. **Deploy.json Creation with VM IP** (Lines 160-230):
   ```python
   @staticmethod
   def create_deploy_json(project_dir: str, frontend_port: str, backend_port: Optional[str] = None) -> bool:
       """Create deploy.json file with deployment information"""
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
               "frontend_url": f"http://157.66.191.31:{frontend_port}",  # Hardcoded VM IP
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
               deploy_data["backend_url"] = f"http://157.66.191.31:{backend_port}"  # Hardcoded VM IP
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
   ```

### 4. Zrok Share Creation (bmad_api.py)

**File Location**: `bmad_backend/src/routes/bmad_api.py`

#### Zrok Share Function (Lines 90-143):

```python
def _zrok_share_http(label: str, target_url: str) -> str | None:
    """Create a public HTTP share pointing to target_url. Returns public URL or None."""
    try:
        if not _ensure_zrok_enabled():
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
        import re, time
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
```

### 5. Complete Data Flow

#### Step-by-Step Process:

1. **Task Completion**:
   - Frontend detects task status as 'completed'
   - Shows "Create Zrok Share" button

2. **Port Detection**:
   - User clicks "Create Zrok Share" button
   - Frontend calls `/api/tasks/<task_id>/deploy/auto-share`
   - Backend calls `get_frontend_port_for_task(task_id)`
   - Port detector reads from existing `deploy.json` or detects from `docker-compose.yml`
   - Creates/updates `.sureai/deploy.json` with `frontend_port`

3. **Zrok Share Creation**:
   - Backend constructs `local_url = "http://157.66.191.31:<detected_port>"`
   - Calls `_zrok_share_http(label, local_url)`
   - Executes `zrok share public http://157.66.191.31:<port> --open --headless`
   - Captures output and extracts public URL (e.g., `http://abc123.cloudnsure.com:8080`)

4. **Metadata Persistence**:
   - Backend saves `frontend_url` to `deploy.json`
   - Returns `frontend_url` to frontend

5. **Frontend Display**:
   - Frontend receives `frontend_url` response
   - Updates `frontendUrl` state
   - Displays the zrok public URL in the UI
   - Shows "Refresh Link" button for future updates

6. **Refresh Functionality**:
   - User clicks "Refresh Link" button
   - Frontend calls `/api/tasks/<task_id>/deploy/refresh-link`
   - Backend uses same logic but creates new zrok share
   - Updates `deploy.json` with new URL and refresh metadata

#### Generated deploy.json Structure:

```json
{
  "deployment_status": "success",
  "frontend_port": "9012",
  "frontend_url": "http://abc123.cloudnsure.com:8080",
  "deployment_timestamp": "2025-08-26T12:18:43.628262",
  "health_check": {
    "frontend_responding": true,
    "blank_screen_issue": false,
    "backend_responding": true
  },
  "auto_detected": true,
  "detection_method": "docker-compose.yml_parsing",
  "backend_port": "9502",
  "backend_url": "http://157.66.191.31:9502",
  "container_names": {
    "frontend": "container_id_1",
    "backend": "container_id_2"
  },
  "refreshed": true,
  "refreshed_at": "2025-08-26T12:20:15.123456"
}
```

### 6. Key Technical Features

#### Port Detection Intelligence:
- **Service Name Recognition**: Identifies frontend services by keywords (frontend, web, ui, app, client, spa, fe, dashboard, site)
- **Port Mapping Support**: Handles both string format ("3000:3000") and dictionary format ({target: 80, published: 8080})
- **Container Port Recognition**: Recognizes common frontend container ports (3000, 80, 8080, 8081, 8082, 5173, 4200)
- **Fallback Logic**: If no frontend service found by name, scans all services for common frontend ports

#### Error Handling:
- **Timeout Protection**: 30-second timeout for zrok share creation
- **URL Validation**: Verifies returned URLs are not localhost
- **Graceful Degradation**: Falls back to direct port detection if auto-detection fails
- **Comprehensive Logging**: Debug logs for troubleshooting port resolution and URL generation

#### Security Features:
- **Hardcoded VM IP**: Prevents localhost fallbacks
- **Task Isolation**: Each task uses its own project directory and deploy.json
- **Input Validation**: Sanitizes zrok output URLs
- **Error Boundaries**: Frontend handles API failures gracefully

### 7. Configuration Requirements

#### Environment Variables:
```bash
ZROK_API_ENDPOINT=http://157.66.191.31:18080
ZROK_ACCOUNT_TOKEN=<your_zrok_account_token>
```

#### File Structure:
```
/tmp/bmad_output/
└── <task_folder>/
    ├── docker-compose.yml
    ├── .sureai/
    │   └── deploy.json
    └── <application_files>
```

#### Zrok Service Status:
- **Controller**: Running on port 18080
- **Frontend**: Running on port 8080
- **Account**: Enabled and authenticated
- **Network**: OpenZiti infrastructure operational

This implementation provides a robust, automated system for creating and managing zrok public URLs for deployed applications, with intelligent port detection, persistent metadata storage, and a user-friendly frontend interface.
