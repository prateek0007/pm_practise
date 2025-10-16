#!/bin/bash

# Zrok Self-Hosting Setup Script for BMAD
# This script initializes the zrok environment after containers are running

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}"
}

# Wait for zrok controller to be ready
wait_for_controller() {
    print_header "Waiting for Zrok Controller"
    
    print_status "Waiting for zrok controller to be ready..."
    for i in {1..30}; do
        if docker exec zrok-controller curl -s http://localhost:18080/api/v1/version > /dev/null 2>&1; then
            print_status "Zrok controller is ready!"
            return 0
        fi
        print_status "Attempt $i/30 - waiting for controller..."
        sleep 10
    done
    
    print_error "Zrok controller failed to start within timeout"
    return 1
}

# Create user account and get token
create_account() {
    print_header "Creating Zrok User Account"
    
    print_status "Creating user account..."
    ACCOUNT_OUTPUT=$(docker exec zrok-controller bash -c 'zrok admin create account varun@dekatc.com V@run9650' 2>&1)
    
    if [ $? -eq 0 ]; then
        print_status "User account created successfully"
        
        # Extract the token from the output
        ACCOUNT_TOKEN=$(echo "$ACCOUNT_OUTPUT" | grep -v "INFO\|+" | tail -1 | tr -d '[:space:]')
        
        if [ -n "$ACCOUNT_TOKEN" ] && [ ${#ACCOUNT_TOKEN} -gt 5 ]; then
            print_status "Account token: $ACCOUNT_TOKEN"
            echo "$ACCOUNT_TOKEN" > .zrok_token
            return 0
        else
            print_error "Failed to extract account token"
            return 1
        fi
    else
        print_error "Failed to create user account"
        print_error "Output: $ACCOUNT_OUTPUT"
        return 1
    fi
}

# Enable zrok environment
enable_environment() {
    print_header "Enabling Zrok Environment"
    
    if [ ! -f .zrok_token ]; then
        print_error "Account token not found. Run account creation first."
        return 1
    fi
    
    ACCOUNT_TOKEN=$(cat .zrok_token)
    print_status "Enabling zrok environment with token: $ACCOUNT_TOKEN"
    
    # Set API endpoint and enable
    docker exec zrok-controller bash -c "zrok config set apiEndpoint http://api.cloudnsure.com:8888"
    docker exec zrok-controller bash -c "export ZROK_API_ENDPOINT=http://api.cloudnsure.com:8888 && zrok enable $ACCOUNT_TOKEN"
    
    if [ $? -eq 0 ]; then
        print_status "Zrok environment enabled successfully"
        return 0
    else
        print_error "Failed to enable zrok environment"
        return 1
    fi
}

# Test zrok functionality
test_zrok() {
    print_header "Testing Zrok Setup"
    
    print_status "Testing API endpoint..."
    if curl -s http://api.cloudnsure.com:8888/api/v1/version > /dev/null; then
        print_status "API endpoint is accessible"
    else
        print_warning "API endpoint not accessible - check DNS configuration"
    fi
    
    print_status "Testing nginx proxy..."
    if curl -s http://localhost:8888/health > /dev/null; then
        print_status "Nginx proxy is working"
    else
        print_warning "Nginx proxy not accessible"
    fi
}

# Main execution
main() {
    print_header "Zrok Self-Hosting Setup for BMAD"
    
    wait_for_controller
    create_account
    enable_environment
    test_zrok
    
    print_header "Setup Complete!"
    print_status "Your zrok self-hosted instance is ready!"
    print_status "API Endpoint: http://api.cloudnsure.com:8888"
    print_status "Nginx Proxy: http://localhost:8888"
    print_status "Account Token: $(cat .zrok_token 2>/dev/null || echo 'Not found')"
    
    print_status "To use zrok in BMAD backend:"
    print_status "1. The backend container has zrok CLI installed"
    print_status "2. Environment variables are configured"
    print_status "3. Use the API endpoint to create shares for deployed frontends"
}

main "$@"


