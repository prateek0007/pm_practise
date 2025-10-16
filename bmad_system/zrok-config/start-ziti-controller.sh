#!/bin/bash
export ZITI_HOME=/var/lib/ziti
cd $ZITI_HOME

while [ ! -f "$ZITI_HOME/ziti-controller.yaml" ]; do
  echo "Waiting for controller config..."
  sleep 5
done

echo "Starting Ziti Controller..."
exec ziti controller run ziti-controller.yaml
