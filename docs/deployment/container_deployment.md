# Container Deployment Guide

This guide provides detailed instructions for deploying the Feed Processing System using containers.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Container Configuration](#container-configuration)
- [Deployment Steps](#deployment-steps)
- [Monitoring and Health Checks](#monitoring-and-health-checks)
- [Scaling and Resource Management](#scaling-and-resource-management)
- [Troubleshooting](#troubleshooting)

## Prerequisites

Before deploying the container, ensure you have:

1. Docker installed (version 20.10.0 or higher)
2. Required environment variables:
   ```env
   FEED_PROCESSOR_DB_URL=postgresql://user:pass@localhost:5432/db
   FEED_PROCESSOR_API_KEY=your-api-key
   AZURE_CONTAINER_REGISTRY=your-registry.azurecr.io
   METRICS_PORT=8080
   ```
3. Access to Azure Container Registry
4. Minimum system requirements:
   - CPU: 2 cores
   - Memory: 4GB RAM
   - Storage: 10GB available space

## Container Configuration

### Dockerfile Structure

The container uses a multi-stage build for optimized size and security:

1. Build Stage:
   - Base image: `python:3.12-slim`
   - Installs build dependencies
   - Compiles requirements
   - Prepares application code

2. Runtime Stage:
   - Minimal runtime dependencies
   - Non-root user execution
   - Exposed ports: 8080 (metrics), 8443 (HTTPS)
   - Health check endpoint

### Resource Limits

Default resource limits are configured as:
```yaml
resources:
  limits:
    cpu: "1"
    memory: "2Gi"
  requests:
    cpu: "0.5"
    memory: "1Gi"
```

## Deployment Steps

1. Build the Container:
   ```bash
   docker build -t feed-processor:latest .
   ```

2. Test the Build:
   ```bash
   docker run --rm feed-processor:latest pytest tests/deployment/
   ```

3. Push to Azure Container Registry:
   ```bash
   az acr login --name your-registry
   docker tag feed-processor:latest your-registry.azurecr.io/feed-processor:latest
   docker push your-registry.azurecr.io/feed-processor:latest
   ```

4. Deploy to Azure Container Apps:
   ```bash
   az containerapp create \
     --name feed-processor \
     --resource-group your-rg \
     --image your-registry.azurecr.io/feed-processor:latest \
     --environment your-environment \
     --target-port 8080 \
     --ingress external
   ```

## Monitoring and Health Checks

### Metrics Endpoint

The container exposes Prometheus metrics at `http://localhost:8080/metrics` including:
- `feed_processor_queue_size`: Current size of the processing queue
- `feed_processor_processing_time_seconds`: Feed processing duration
- `feed_processor_memory_bytes`: Memory usage
- `feed_processor_cpu_percent`: CPU usage
- `feed_processor_feeds_total`: Total processed feeds
- `feed_processor_errors_total`: Processing errors

### Health Checks

The container implements a health check that:
- Runs every 30 seconds
- Times out after 30 seconds
- Has 3 retries
- Checks the metrics endpoint

Configure monitoring alerts for:
- Queue size > 80% capacity
- Processing time > 5 seconds
- Error rate > 1%
- Memory usage > 90%
- CPU usage > 80%

## Scaling and Resource Management

### Automatic Scaling

The system supports automatic scaling based on:
1. Queue size (triggers at 80% capacity)
2. CPU utilization (triggers at 70%)
3. Memory usage (triggers at 80%)

Configure scaling rules in Azure:
```bash
az containerapp update \
  --name feed-processor \
  --resource-group your-rg \
  --min-replicas 1 \
  --max-replicas 10 \
  --scale-rule-name http-rule \
  --scale-rule-type http \
  --scale-rule-http-concurrency 50
```

### Resource Optimization

Best practices for resource management:
1. Monitor metrics to adjust resource limits
2. Use horizontal scaling for increased load
3. Implement proper queue management
4. Enable resource cleanup on shutdown

## Troubleshooting

### Common Issues

1. Container fails to start:
   - Check environment variables
   - Verify resource limits
   - Check logs: `docker logs <container-id>`

2. Health check failures:
   - Verify metrics endpoint accessibility
   - Check resource usage
   - Review application logs

3. Performance issues:
   - Monitor queue size
   - Check resource utilization
   - Review scaling configurations

### Logging

Access container logs:
```bash
# Docker logs
docker logs <container-id>

# Azure Container Apps logs
az containerapp logs show \
  --name feed-processor \
  --resource-group your-rg \
  --follow
```

### Recovery Procedures

1. Container restart:
   ```bash
   az containerapp restart \
     --name feed-processor \
     --resource-group your-rg
   ```

2. Rollback to previous version:
   ```bash
   az containerapp update \
     --name feed-processor \
     --resource-group your-rg \
     --image your-registry.azurecr.io/feed-processor:previous-tag
   ```

3. Scale to handle backlog:
   ```bash
   az containerapp update \
     --name feed-processor \
     --resource-group your-rg \
     --min-replicas 3
   ```
