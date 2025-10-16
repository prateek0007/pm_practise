# Zrok Self-Hosting Setup Script for BMAD (Windows PowerShell)
# This script initializes the zrok environment after containers are running

param(
    [switch]$SkipWait
)

# Colors for output
$Red = "Red"
$Green = "Green"
$Yellow = "Yellow"
$Blue = "Blue"

function Write-Status {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor $Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor $Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor $Red
}

function Write-Header {
    param([string]$Message)
    Write-Host "================================`n$Message`n================================" -ForegroundColor $Blue
}

# Wait for zrok controller to be ready
function Wait-Controller {
    Write-Header "Waiting for Zrok Controller"
    
    Write-Status "Waiting for zrok controller to be ready..."
    for ($i = 1; $i -le 30; $i++) {
        try {
            $result = docker exec zrok-server curl -s http://localhost:18080/api/v1/version 2>$null
            if ($LASTEXITCODE -eq 0) {
                Write-Status "Zrok controller is ready!"
                return $true
            }
        } catch {
            # Ignore errors
        }
        Write-Status "Attempt $i/30 - waiting for controller..."
        Start-Sleep -Seconds 10
    }
    
    Write-Error "Zrok controller failed to start within timeout"
    return $false
}

# Create user account and get token
function Create-Account {
    Write-Header "Creating Zrok User Account"
    
    Write-Status "Creating user account..."
    try {
        $accountOutput = docker exec zrok-server bash -c 'zrok admin create account varun@dekatc.com V@run9650' 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-Status "User account created successfully"
            
            # Extract the token from the output (last non-empty line)
            $lines = $accountOutput -split "`n" | Where-Object { $_.Trim() -ne "" }
            $accountToken = $lines[-1].Trim()
            
            if ($accountToken -and $accountToken.Length -gt 5) {
                Write-Status "Account token: $accountToken"
                $accountToken | Out-File -FilePath ".zrok_token" -Encoding UTF8
                return $true
            } else {
                Write-Error "Failed to extract account token"
                Write-Error "Output: $accountOutput"
                return $false
            }
        } else {
            Write-Error "Failed to create user account"
            Write-Error "Output: $accountOutput"
            return $false
        }
    } catch {
        Write-Error "Exception during account creation: $_"
        return $false
    }
}

# Enable zrok environment
function Enable-Environment {
    Write-Header "Enabling Zrok Environment"
    
    if (-not (Test-Path ".zrok_token")) {
        Write-Error "Account token not found. Run account creation first."
        return $false
    }
    
    $accountToken = Get-Content ".zrok_token" -Raw
    Write-Status "Enabling zrok environment with token: $accountToken"
    
    try {
        # Set API endpoint and enable
        docker exec zrok-server bash -c "zrok config set apiEndpoint http://api.cloudnsure.com:8888"
        docker exec zrok-server bash -c "export ZROK_API_ENDPOINT=http://api.cloudnsure.com:8888 && zrok enable $accountToken"
        
        if ($LASTEXITCODE -eq 0) {
            Write-Status "Zrok environment enabled successfully"
            return $true
        } else {
            Write-Error "Failed to enable zrok environment"
            return $false
        }
    } catch {
        Write-Error "Exception during environment enable: $_"
        return $false
    }
}

# Test zrok functionality
function Test-Zrok {
    Write-Header "Testing Zrok Setup"
    
    Write-Status "Testing API endpoint..."
    try {
        $result = Invoke-WebRequest -Uri "http://api.cloudnsure.com:8888/api/v1/version" -UseBasicParsing -TimeoutSec 10
        if ($result.StatusCode -eq 200) {
            Write-Status "API endpoint is accessible"
        } else {
            Write-Warning "API endpoint returned status: $($result.StatusCode)"
        }
    } catch {
        Write-Warning "API endpoint not accessible - check DNS configuration"
    }
    
    Write-Status "Testing nginx proxy..."
    try {
        $result = Invoke-WebRequest -Uri "http://localhost:8888/health" -UseBasicParsing -TimeoutSec 10
        if ($result.StatusCode -eq 200) {
            Write-Status "Nginx proxy is working"
        } else {
            Write-Warning "Nginx proxy returned status: $($result.StatusCode)"
        }
    } catch {
        Write-Warning "Nginx proxy not accessible"
    }
}

# Main execution
function Main {
    Write-Header "Zrok Self-Hosting Setup for BMAD"
    
    if (-not $SkipWait) {
        if (-not (Wait-Controller)) {
            Write-Error "Controller setup failed"
            exit 1
        }
    }
    
    if (-not (Create-Account)) {
        Write-Error "Account creation failed"
        exit 1
    }
    
    if (-not (Enable-Environment)) {
        Write-Error "Environment enable failed"
        exit 1
    }
    
    Test-Zrok
    
    Write-Header "Setup Complete!"
    Write-Status "Your zrok self-hosted instance is ready!"
    Write-Status "API Endpoint: http://api.cloudnsure.com:8888"
    Write-Status "Nginx Proxy: http://localhost:8888"
    
    if (Test-Path ".zrok_token") {
        $token = Get-Content ".zrok_token" -Raw
        Write-Status "Account Token: $token"
    } else {
        Write-Status "Account Token: Not found"
    }
    
    Write-Status "To use zrok in BMAD backend:"
    Write-Status "1. The backend container has zrok CLI installed"
    Write-Status "2. Environment variables are configured"
    Write-Status "3. Use the API endpoint to create shares for deployed frontends"
}

# Execute main function
Main
