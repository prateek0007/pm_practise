FROM nginx:alpine

# Install curl for health checks
RUN apk add --no-cache curl

# Copy configuration
COPY conf.d/zrok.conf /etc/nginx/conf.d/default.conf

# Remove default nginx config
RUN rm -f /etc/nginx/conf.d/default.conf.bak

# Create log directory and set permissions
RUN mkdir -p /var/log/nginx && \
    touch /var/log/nginx/zrok-frontend.log && \
    touch /var/log/nginx/zrok-controller.log && \
    touch /var/log/nginx/catch-all.log && \
    chmod 666 /var/log/nginx/*.log

# Expose ports
EXPOSE 80 443

# Add health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
