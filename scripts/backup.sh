#!/bin/bash

# Configuration
BACKUP_DIR="/backups/feed-processor"
RETENTION_DAYS=7
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Backup Prometheus data
echo "Backing up Prometheus data..."
docker run --rm \
  --volumes-from feed-processing-system_prometheus_1 \
  -v "$BACKUP_DIR:/backup" \
  alpine tar czf "/backup/prometheus_$DATE.tar.gz" /prometheus

# Backup Grafana data
echo "Backing up Grafana data..."
docker run --rm \
  --volumes-from feed-processing-system_grafana_1 \
  -v "$BACKUP_DIR:/backup" \
  alpine tar czf "/backup/grafana_$DATE.tar.gz" /var/lib/grafana

# Backup AlertManager data
echo "Backing up AlertManager data..."
docker run --rm \
  --volumes-from feed-processing-system_alertmanager_1 \
  -v "$BACKUP_DIR:/backup" \
  alpine tar czf "/backup/alertmanager_$DATE.tar.gz" /alertmanager

# Clean up old backups
echo "Cleaning up old backups..."
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete

echo "Backup completed successfully!"
