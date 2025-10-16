#!/bin/bash
echo "Starting BMAD with zrok environment setup..."
cd /app

echo "Waiting for zrok controller to be ready..."
while ! curl -s http://127.0.0.1:18080/api/v1/version >/dev/null 2>&1; do
  echo "Waiting for zrok controller on port 18080..."
  sleep 10
done

echo "Zrok controller is ready!"
sleep 10

echo "Debug: About to check zrok status..."
export ZROK_API_ENDPOINT="http://127.0.0.1:18080"
export ZROK_ADMIN_TOKEN="zroktoken123456789"

echo "Checking zrok status..."
if zrok status | grep -q "Account Token.*<<SET>>"; then
  echo "Zrok environment already enabled!"
  echo "zrok is now ready to use: zrok share public <port>"
else
  echo "Zrok environment not enabled, attempting to enable..."
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
    echo "Account may already exist, trying to enable existing account..."
    echo "Please check zrok status and enable manually if needed"
  fi
fi

echo "Starting Flask app on port 5000..."
echo "BMAD application logs will now appear below:"
echo "==============================================="
echo "Debug: About to start Python Flask app..."
echo "Debug: Current directory: $(pwd)"
echo "Debug: Python version: $(python --version)"
echo "Debug: Flask app file exists: $(ls -la src/main.py)"
echo "Setting log level to DEBUG for detailed prompt logging..."
export BMAD_LOG_LEVEL=DEBUG
exec python -u src/main.py
