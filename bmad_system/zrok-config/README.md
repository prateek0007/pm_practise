# Zrok Configuration Directory

This directory contains all the modularized zrok-related configuration files and scripts that were previously embedded in the Dockerfile.backend.

## File Structure

### Configuration Files
- **`ctrl.yml`** - Zrok controller configuration with OpenZiti integration
- **`frontend.yml`** - Zrok frontend configuration for public access
- **`supervisord.conf`** - Supervisor configuration for managing all services

### Setup Scripts
- **`setup-openziti.sh`** - OpenZiti quickstart initialization
- **`start-ziti-controller.sh`** - OpenZiti controller startup
- **`start-ziti-router.sh`** - OpenZiti router startup
- **`setup-zrok.sh`** - Zrok bootstrap and controller startup
- **`start-zrok-frontend.sh`** - Zrok frontend startup

### Application Scripts
- **`start-bmad-with-zrok.sh`** - BMAD startup with zrok environment setup
- **`start-bmad.sh`** - Main startup script that launches supervisor

## Service Startup Order

The services start in this specific order to ensure proper dependencies:

1. **OpenZiti Setup** (Priority 100) - Initializes the zero-trust network
2. **Ziti Controller** (Priority 200) - Manages the OpenZiti network
3. **Ziti Router** (Priority 300) - Handles network traffic routing
4. **Zrok Controller** (Priority 400) - Manages zrok operations
5. **Zrok Frontend** (Priority 500) - Handles public access
6. **BMAD Application** (Priority 600) - Main Flask application

## Configuration Details

### OpenZiti Configuration
- **Controller Port**: 1280
- **Router Port**: 3022
- **Admin Password**: zitiadminpw
- **Auto-initialization**: Uses quickstart for first-time setup

### Zrok Configuration
- **Controller Port**: 18080
- **Frontend Port**: 8080
- **Admin Token**: zroktoken123456789
- **Domain**: cloudnsure.com
- **Database**: SQLite at `/var/lib/ziti/zrok.db`

### Supervisor Configuration
- **Log Directory**: `/var/log/ziti/`
- **Auto-restart**: Enabled for all services except setup
- **Priority-based startup**: Ensures proper service order
- **Log Rotation**: Configured for all services

## Usage

### Building the Container
The Dockerfile.backend now copies these files instead of embedding them:

```dockerfile
# Copy zrok configuration files
COPY zrok-config/ /etc/zrok/
COPY zrok-config/supervisord.conf /etc/supervisor/conf.d/

# Copy zrok setup scripts and make them executable
COPY zrok-config/setup-openziti.sh /setup-openziti.sh
# ... other scripts
```

### Starting Services
The container uses the modularized startup script:

```bash
CMD ["/start-bmad.sh"]
```

### Manual Service Management
You can manually start individual services if needed:

```bash
# Start OpenZiti setup
/setup-openziti.sh

# Start zrok controller
/setup-zrok.sh

# Start BMAD with zrok
/start-bmad-with-zrok.sh
```

## Benefits of Modularization

1. **Maintainability**: Easier to update individual components
2. **Readability**: Clear separation of concerns
3. **Reusability**: Scripts can be used independently
4. **Debugging**: Easier to troubleshoot specific services
5. **Version Control**: Better tracking of configuration changes

## Troubleshooting

### Service Startup Issues
Check the supervisor logs:
```bash
docker exec -it <container> tail -f /var/log/ziti/<service>.log
```

### Configuration Issues
Verify configuration files are properly copied:
```bash
docker exec -it <container> ls -la /etc/zrok/
docker exec -it <container> ls -la /etc/supervisor/conf.d/
```

### Permission Issues
Ensure scripts are executable:
```bash
docker exec -it <container> ls -la /setup-*.sh
```

## Notes

- All scripts use the same environment variables and paths as before
- The service startup order and dependencies remain unchanged
- Logging and error handling are preserved
- The overall functionality is identical to the previous embedded version
