#!/bin/bash

# BMAD System Deployment Script
# This script makes it easy to deploy the BMAD system to production environment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
show_usage() {
    echo "BMAD System Deployment Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  configure               - Configure environment for production"
    echo "  build                   - Build Docker images"
    echo "  start                   - Start the system"
    echo "  stop                    - Stop the system"
    echo "  restart                 - Restart the system"
    echo "  logs                    - Show logs"
    echo "  status                  - Show system status"
    echo "  ports                   - Show current port configuration"
    echo "  clean                   - Clean up containers and volumes"
    echo "  deploy                  - Full deployment (configure + build + start)"
    echo "  restore                 - Restore original docker-compose.yml"
    echo ""
    echo "Examples:"
    echo "  $0 configure            - Configure for production VM"
    echo "  $0 deploy               - Full production deployment"
    echo "  $0 start                - Start the system"
    echo "  $0 logs                 - Show logs"
    echo "  $0 ports                - Show port configuration"
    echo "  $0 restore              - Restore original docker-compose.yml"
}

# Function to restore original docker-compose.yml
restore_docker_compose() {
    if [ -f "docker-compose.yml.backup" ]; then
        print_status "Restoring original docker-compose.yml..."
        cp docker-compose.yml.backup docker-compose.yml
        print_success "Original docker-compose.yml restored"
    else
        print_warning "No backup file found to restore"
    fi
}

# Function to configure environment
configure_environment() {
    print_status "Configuring environment for production"
    
    # Read current values from env.config
    if [ -f "env.config" ]; then
        # Source the env.config file to get current values
        source env.config
        
        print_status "Current configuration from env.config:"
        echo "  BACKEND_HOST: $BACKEND_HOST"
        echo "  BACKEND_PORT: $BACKEND_PORT"
        echo "  FRONTEND_HOST: $FRONTEND_HOST"
        echo "  FRONTEND_PORT: $FRONTEND_PORT"
        echo "  API_BASE_URL: $API_BASE_URL"
        echo "  DOCKER_ZROK_CONTROLLER_PORT: $DOCKER_ZROK_CONTROLLER_PORT"
        echo "  DOCKER_ZROK_FRONTEND_PORT: $DOCKER_ZROK_FRONTEND_PORT"
    else
        print_error "env.config file not found!"
        exit 1
    fi
    
    # Update docker-compose.yml with new port values
    print_status "Updating docker-compose.yml with new port configuration..."
    
    # Create a backup of the original docker-compose.yml
    if [ ! -f "docker-compose.yml.backup" ]; then
        cp docker-compose.yml docker-compose.yml.backup
        print_status "Created backup of docker-compose.yml"
    fi
    
    # Create a temporary file for the updated docker-compose.yml
    cp docker-compose.yml docker-compose.yml.tmp
    
    # Update the Zrok controller port (18080)
    if [ -n "$DOCKER_ZROK_CONTROLLER_PORT" ]; then
        # Use a more specific pattern to avoid false matches
        sed -i "s/- \"[0-9]*:18080\"/- \"$DOCKER_ZROK_CONTROLLER_PORT:18080\"/" docker-compose.yml.tmp
        if grep -q "\"$DOCKER_ZROK_CONTROLLER_PORT:18080\"" docker-compose.yml.tmp; then
            print_status "Updated Zrok controller port to $DOCKER_ZROK_CONTROLLER_PORT:18080"
        else
            print_warning "Failed to update Zrok controller port"
        fi
    fi
    
    # Update the Zrok frontend port (8080)
    if [ -n "$DOCKER_ZROK_FRONTEND_PORT" ]; then
        # Use a more specific pattern to avoid false matches
        sed -i "s/- \"[0-9]*:8080\"/- \"$DOCKER_ZROK_FRONTEND_PORT:8080\"/" docker-compose.yml.tmp
        if grep -q "\"$DOCKER_ZROK_FRONTEND_PORT:8080\"" docker-compose.yml.tmp; then
            print_status "Updated Zrok frontend port to $DOCKER_ZROK_FRONTEND_PORT:8080"
        else
            print_warning "Failed to update Zrok frontend port"
        fi
    fi
    
    # Update the backend port if it's different from 5006
    if [ -n "$DOCKER_BACKEND_PORT" ] && [ "$DOCKER_BACKEND_PORT" != "5006" ]; then
        sed -i "s/- \"5006:5000\"/- \"$DOCKER_BACKEND_PORT:5000\"/" docker-compose.yml.tmp
        if grep -q "\"$DOCKER_BACKEND_PORT:5000\"" docker-compose.yml.tmp; then
            print_status "Updated backend port to $DOCKER_BACKEND_PORT:5000"
        else
            print_warning "Failed to update backend port"
        fi
    fi
    
    # Update the frontend port if it's different from 5005
    if [ -n "$DOCKER_FRONTEND_PORT" ] && [ "$DOCKER_FRONTEND_PORT" != "5005" ]; then
        sed -i "s/- \"5005:80\"/- \"$DOCKER_FRONTEND_PORT:80\"/" docker-compose.yml.tmp
        if grep -q "\"$DOCKER_FRONTEND_PORT:80\"" docker-compose.yml.tmp; then
            print_status "Updated frontend port to $DOCKER_FRONTEND_PORT:80"
        else
            print_warning "Failed to update frontend port"
        fi
    fi
    
    # Replace the original file with the updated one
    mv docker-compose.yml.tmp docker-compose.yml
    
    print_success "docker-compose.yml updated with new port configuration"
    
    # Update nginx.conf if service names have changed (for multi-instance deployments)
    print_status "Checking for service name changes in nginx.conf..."
    if [ -f "nginx.conf" ]; then
        # Check if service names in docker-compose.yml are different from nginx.conf
        BACKEND_SERVICE=$(grep -o '^  [a-zA-Z0-9_-]*:' docker-compose.yml | head -1 | sed 's/://' | sed 's/^  //')
        if [ -n "$BACKEND_SERVICE" ] && [ "$BACKEND_SERVICE" != "bmad-backend" ]; then
            print_status "Detected service name change: $BACKEND_SERVICE, updating nginx.conf..."
            # Update nginx.conf to use the new service name
            sed -i "s/bmad-backend:5000/$BACKEND_SERVICE:5000/g" nginx.conf
            print_success "nginx.conf updated with new service name: $BACKEND_SERVICE"
        else
            print_status "No service name changes detected, nginx.conf unchanged"
        fi
    else
        print_warning "nginx.conf not found, skipping service name update"
    fi
    
    # Run the Node.js update script with the current env.config values
    if command -v node &> /dev/null; then
        print_status "Updating frontend configuration..."
        node scripts/update-env.js production
    else
        print_warning "Node.js not found. Skipping frontend configuration update."
    fi
    
    print_success "Environment configured for production"
}

# Function to build Docker images
build_images() {
    print_status "Building Docker images..."
    docker-compose build
    print_success "Docker images built successfully"
}

# Function to start the system
start_system() {
    print_status "Starting BMAD system..."
    docker-compose up -d
    print_success "BMAD system started"
    
    # Show status
    sleep 2
    show_status
}

# Function to stop the system
stop_system() {
    print_status "Stopping BMAD system..."
    docker-compose down
    print_success "BMAD system stopped"
}

# Function to restart the system
restart_system() {
    print_status "Restarting BMAD system..."
    docker-compose down
    docker-compose up -d
    print_success "BMAD system restarted"
    
    # Show status
    sleep 2
    show_status
}

# Function to show logs
show_logs() {
    print_status "Showing logs (Ctrl+C to exit)..."
    docker-compose logs -f
}

# Function to show current port configuration
show_port_config() {
    print_status "Current Port Configuration:"
    echo ""
    
    if [ -f "env.config" ]; then
        source env.config
        echo "  Backend: $DOCKER_BACKEND_PORT -> 5000 (container)"
        echo "  Frontend: $DOCKER_FRONTEND_PORT -> 80 (container)"
        echo "  Zrok Controller: $DOCKER_ZROK_CONTROLLER_PORT -> 18080 (container)"
        echo "  Zrok Frontend: $DOCKER_ZROK_FRONTEND_PORT -> 8080 (container)"
    else
        print_error "env.config file not found!"
        return 1
    fi
    
    echo ""
    print_status "Docker Compose Port Mappings:"
    if [ -f "docker-compose.yml" ]; then
        grep -E "ports:" -A 10 docker-compose.yml | grep -E "^\s*- \"[0-9]+:" || echo "  No port mappings found"
    else
        print_error "docker-compose.yml not found!"
    fi
}

# Function to show status
show_status() {
    print_status "System Status:"
    echo ""
    
    # Read current values from env.config
    if [ -f "env.config" ]; then
        source env.config
    else
        print_error "env.config file not found!"
        return 1
    fi
    
    # Check if containers are running
    if docker-compose ps | grep -q "Up"; then
        print_success "Containers are running:"
        docker-compose ps
        echo ""
        
        # Show URLs using values from env.config
        print_status "Access URLs:"
        echo "  Frontend: http://$FRONTEND_HOST:$FRONTEND_PORT"
        echo "  Backend API: http://$BACKEND_HOST:$BACKEND_PORT/api"
        echo "  Zrok Controller: http://$BACKEND_HOST:${DOCKER_ZROK_CONTROLLER_PORT:-18080}"
        echo "  Zrok Frontend: http://$BACKEND_HOST:${DOCKER_ZROK_FRONTEND_PORT:-8080}"
        echo ""
        
        # Show current port configuration
        show_port_config
        
        echo ""
        # Check health
        print_status "Health Check:"
        if curl -s http://$BACKEND_HOST:$BACKEND_PORT/api/health > /dev/null; then
            print_success "Backend API is healthy"
        else
            print_warning "Backend API health check failed"
        fi
    else
        print_warning "No containers are running"
    fi
}

# Function to clean up
clean_system() {
    print_warning "This will remove all containers and volumes. Are you sure? (y/N)"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        print_status "Cleaning up system..."
        docker-compose down -v --remove-orphans
        docker system prune -f
        print_success "System cleaned up"
    else
        print_status "Cleanup cancelled"
    fi
}

# Function to deploy everything
deploy_system() {
    print_status "Starting full deployment for production"
    
    # Configure environment
    configure_environment
    
    # Build images
    build_images
    
    # Start system
    start_system
    
    print_success "Deployment completed successfully!"
}

# Main script logic
case "${1:-}" in
    "configure")
        configure_environment
        ;;
    "build")
        build_images
        ;;
    "start")
        start_system
        ;;
    "stop")
        stop_system
        ;;
    "restart")
        restart_system
        ;;
    "logs")
        show_logs
        ;;
    "status")
        show_status
        ;;
    "ports")
        show_port_config
        ;;
    "clean")
        clean_system
        ;;
    "deploy")
        deploy_system
        ;;
    "restore")
        restore_docker_compose
        ;;
    "help"|"-h"|"--help"|"")
        show_usage
        ;;
    *)
        print_error "Unknown command: $1"
        echo ""
        show_usage
        exit 1
        ;;
esac
