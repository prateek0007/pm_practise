#!/bin/bash
echo "Starting BMAD with integrated zrok self-hosting..."
echo "Services will start in this order:"
echo "1. OpenZiti setup"
echo "2. Ziti Controller"
echo "3. Ziti Router"
echo "4. zrok Controller"
echo "5. zrok Frontend"
echo "6. BMAD Application"
echo "Starting supervisor to manage all services..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
