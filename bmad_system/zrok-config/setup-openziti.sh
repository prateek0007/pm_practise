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
