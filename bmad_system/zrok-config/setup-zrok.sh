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
