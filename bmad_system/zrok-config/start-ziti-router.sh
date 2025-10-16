#!/bin/bash
export ZITI_HOME=/var/lib/ziti
cd $ZITI_HOME

while [ ! -f "$ZITI_HOME/ziti-router.yaml" ]; do
  echo "Waiting for router config..."
  sleep 5
done

echo "Starting Ziti Router..."
exec ziti router run ziti-router.yaml
