# Production Deployment Guide

## Prerequisites

- Docker and Docker Compose v2
- Access to production environment
- Required API credentials:
  - Inoreader API credentials
  - Airtable API key and configuration
  - Slack webhook URL (for notifications)

## Initial Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/feed-processing-system.git
cd feed-processing-system
```

2. Create production environment file:
```bash
cp config/production.env.example config/production.env
# Edit config/production.env with your production credentials
```

3. Create required directories:
```bash
mkdir -p data/feed-processor
mkdir -p backups/feed-processor
```

## Deployment

1. Build and start services:
```bash
docker-compose build
docker-compose up -d
```

2. Verify services are running:
```bash
docker-compose ps
```

3. Check logs:
```bash
docker-compose logs -f feed-processor
```

## Monitoring

1. Access monitoring interfaces:
   - Prometheus: http://your-host:9090
   - Grafana: http://your-host:3000
   - AlertManager: http://your-host:9093

2. Default credentials:
   - Grafana:
     - Username: admin
     - Password: Set in GRAFANA_ADMIN_PASSWORD environment variable

## Backup and Maintenance

1. Configure backup script:
```bash
chmod +x scripts/backup.sh
# Edit BACKUP_DIR in scripts/backup.sh if needed
```

2. Set up daily backups (using cron):
```bash
sudo crontab -e
# Add the following line:
0 0 * * * /path/to/feed-processing-system/scripts/backup.sh
```

3. Verify backups:
```bash
ls -l /backups/feed-processor
```

## Alerts and Notifications

1. Configure Slack notifications:
   - Set SLACK_WEBHOOK_URL in production.env
   - Create #feed-processor-alerts Slack channel

2. Alert rules are defined in:
   - monitoring/prometheus/rules/feed_processor_alerts.yml

3. Alert configuration:
   - monitoring/alertmanager/config.yml

## Troubleshooting

1. Check service status:
```bash
docker-compose ps
```

2. View logs:
```bash
docker-compose logs -f [service-name]
```

3. Common issues:
   - Memory issues: Check container memory usage
   - Network issues: Verify connectivity to APIs
   - Queue overflow: Monitor queue size metrics

## Scaling

1. Adjust resource limits in production.env:
   - MAX_QUEUE_SIZE
   - MAX_MEMORY_MB
   - MAX_CPU_PERCENT

2. Monitor system resources:
   - Use Grafana dashboards
   - Set up resource alerts

## Security

1. Ensure all credentials are securely stored
2. Regular security updates:
```bash
docker-compose pull
docker-compose up -d
```

3. Monitor security logs
4. Implement access controls for monitoring interfaces

## Recovery Procedures

1. From backup:
```bash
# Stop services
docker-compose down

# Restore from backup
tar xzf /backups/feed-processor/prometheus_YYYYMMDD_HHMMSS.tar.gz -C /path/to/prometheus/data
tar xzf /backups/feed-processor/grafana_YYYYMMDD_HHMMSS.tar.gz -C /path/to/grafana/data
tar xzf /backups/feed-processor/alertmanager_YYYYMMDD_HHMMSS.tar.gz -C /path/to/alertmanager/data

# Restart services
docker-compose up -d
```

2. Manual intervention:
   - Access container shell: `docker-compose exec feed-processor sh`
   - Check logs: `docker-compose logs -f feed-processor`
   - Restart service: `docker-compose restart feed-processor`

## Performance Tuning

1. Content Analysis Pipeline Settings:
```bash
# In config/production.env
CONTENT_ANALYSIS_BATCH_SIZE=50
CONTENT_ANALYSIS_WORKERS=4
CONTENT_ANALYSIS_QUEUE_SIZE=1000
CONTENT_ANALYSIS_TIMEOUT=300
```

2. Memory Management:
   - Monitor memory usage in Grafana
   - Adjust JVM settings for optimal performance:
```bash
# In docker-compose.yml
environment:
  - JAVA_OPTS=-Xms2g -Xmx4g -XX:+UseG1GC
```

3. Database Optimization:
   - Regular index maintenance
   - Query optimization
   - Connection pool tuning

## Load Testing

1. Set up load testing environment:
```bash
# Create load test config
cp config/loadtest.env.example config/loadtest.env

# Run load tests
docker-compose -f docker-compose.loadtest.yml up
```

2. Monitor during load test:
   - CPU usage
   - Memory consumption
   - Response times
   - Error rates
   - Queue sizes

3. Performance metrics to watch:
   - Feed processing rate
   - Content analysis throughput
   - Webhook delivery latency
   - Database query times

## High Availability Setup

1. Database Replication:
```bash
# In docker-compose.prod.yml
services:
  db-primary:
    image: postgres:13
    volumes:
      - db-primary-data:/var/lib/postgresql/data
    environment:
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_REPLICATION: 'on'
      
  db-replica:
    image: postgres:13
    volumes:
      - db-replica-data:/var/lib/postgresql/data
    environment:
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_MASTER_HOST: db-primary
```

2. Load Balancing:
   - Use nginx for load balancing
   - Configure health checks
   - Set up SSL termination

3. Service Discovery:
   - Implement Consul for service discovery
   - Configure health checks
   - Set up DNS resolution

## Monitoring Enhancements

1. Custom Dashboards:
   - Content Analysis Performance
   - Feed Processing Metrics
   - Error Rates and Types
   - System Resources

2. Alert Rules:
```yaml
# monitoring/prometheus/rules/content_analysis_alerts.yml
groups:
  - name: content_analysis
    rules:
      - alert: HighProcessingLatency
        expr: content_analysis_processing_time_seconds > 30
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: High content analysis processing time
          
      - alert: HighErrorRate
        expr: rate(content_analysis_errors_total[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: High error rate in content analysis
```

3. Metrics Collection:
   - Custom metrics for content analysis
   - Business metrics
   - SLA monitoring

## Disaster Recovery

1. Backup Strategy:
   - Hourly snapshots of critical data
   - Daily full backups
   - Weekly archival backups
   - Regular backup testing

2. Recovery Time Objectives (RTO):
   - Critical services: < 1 hour
   - Non-critical services: < 4 hours

3. Recovery Point Objectives (RPO):
   - Database: < 5 minutes
   - File storage: < 1 hour

## Security Hardening

1. Network Security:
   - Configure firewalls
   - Set up VPN access
   - Implement rate limiting
   - Enable DDoS protection

2. Access Control:
   - Role-based access control (RBAC)
   - Multi-factor authentication
   - Regular access audits
   - Session management

3. Data Protection:
   - Encryption at rest
   - Encryption in transit
   - Regular security scans
   - Vulnerability assessments

## Maintenance Procedures

1. Regular Updates:
```bash
# Update system packages
apt-get update && apt-get upgrade

# Update Docker images
docker-compose pull
docker-compose up -d

# Update Python dependencies
pip install --upgrade -r requirements.txt
```

2. Database Maintenance:
```bash
# Vacuum database
docker-compose exec db psql -U postgres -c "VACUUM ANALYZE;"

# Reindex database
docker-compose exec db psql -U postgres -c "REINDEX DATABASE feed_processor;"
```

3. Log Rotation:
```bash
# Configure logrotate
cat << EOF > /etc/logrotate.d/feed-processor
/var/log/feed-processor/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 feed-processor feed-processor
    sharedscripts
    postrotate
        systemctl reload feed-processor
    endscript
}
EOF
```

## Compliance and Auditing

1. Logging Requirements:
   - Access logs
   - Error logs
   - Audit logs
   - Security logs

2. Compliance Monitoring:
   - Regular audits
   - Policy enforcement
   - Data retention
   - Privacy controls

3. Documentation:
   - System architecture
   - Configuration changes
   - Incident reports
   - Recovery procedures
