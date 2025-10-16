#!/bin/bash
export ZROK_ADMIN_TOKEN="zroktoken123456789"
export ZROK_API_ENDPOINT="http://127.0.0.1:18080"

echo "Waiting for zrok controller to be ready..."
while ! curl -s http://localhost:18080/api/v1/version >/dev/null 2>&1; do
  echo "Waiting for zrok controller..."
  sleep 5
done

sleep 10
echo "Creating zrok frontend..."
FRONTEND_ID=$(ziti edge list identities --csv | grep "public" | tail -n1 | cut -d, -f1)
if [ ! -z "$FRONTEND_ID" ]; then
  zrok admin create frontend "$FRONTEND_ID" public "http://{token}.cloudnsure.com:8080" || true
fi

echo "Starting zrok frontend..."
exec zrok access public /etc/zrok/frontend.yml
