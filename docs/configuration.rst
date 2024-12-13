.. _configuration:

Configuration Guide
=================

Environment Variables
------------------

Core Settings
~~~~~~~~~~~

.. code-block:: bash

   # API Configuration
   INOREADER_TOKEN=your_token_here  # Required: Inoreader API token

   # Webhook Configuration
   WEBHOOK_URL=https://api.example.com/webhook  # Required: Webhook endpoint
   WEBHOOK_RATE_LIMIT=0.2  # Optional: Requests per second (default: 0.2)

Queue Settings
~~~~~~~~~~~~

.. code-block:: bash

   # Queue Configuration
   QUEUE_SIZE=1000  # Optional: Maximum queue size (default: 1000)
   ERROR_HISTORY_SIZE=100  # Optional: Error history length (default: 100)

Monitoring Ports
~~~~~~~~~~~~~

.. code-block:: bash

   # Monitoring Stack Ports
   METRICS_PORT=8000  # Optional: Metrics exporter port (default: 8000)
   GRAFANA_PORT=3000  # Optional: Grafana dashboard port (default: 3000)
   PROMETHEUS_PORT=9090  # Optional: Prometheus port (default: 9090)

Configuration File
---------------

The system also supports configuration via YAML:

.. code-block:: yaml

   # config.yaml
   api:
     inoreader_token: your_token_here
     timeout: 30

   webhook:
     url: https://api.example.com/webhook
     rate_limit: 0.2
     max_retries: 3
     retry_delay: 5

   queue:
     size: 1000
     error_history: 100
     priority_weights:
       high: 3
       medium: 2
       low: 1

   monitoring:
     metrics_port: 8000
     grafana_port: 3000
     prometheus_port: 9090

Priority Rules
-----------

Default Rules
~~~~~~~~~~~

The system includes default priority rules:

.. code-block:: python

   from feed_processor import Priority

   def default_priority_rules(item):
       """Default priority determination logic."""
       if "breaking" in item.get("title", "").lower():
           return Priority.HIGH
       return Priority.NORMAL

Custom Rules
~~~~~~~~~~

Create custom priority rules:

.. code-block:: python

   def custom_priority_rules(item):
       """Custom priority determination based on content."""
       title = item.get("title", "").lower()
       content = item.get("content", "").lower()
       
       # Breaking news gets high priority
       if "breaking" in title or "urgent" in title:
           return Priority.HIGH
           
       # Technology news gets medium priority
       if any(tech in content for tech in ["ai", "blockchain"]):
           return Priority.MEDIUM
           
       return Priority.LOW

Error Handling
-----------

Circuit Breaker
~~~~~~~~~~~~

Configure circuit breaker behavior:

.. code-block:: python

   from feed_processor.error_handler import CircuitBreaker

   circuit_breaker = CircuitBreaker(
       failure_threshold=5,
       reset_timeout=300,
       half_open_timeout=60
   )

Rate Limiting
-----------

Configure rate limiting:

.. code-block:: python

   from feed_processor.webhook import WebhookManager

   webhook_manager = WebhookManager(
       webhook_url="https://api.example.com/webhook",
       rate_limit=0.2,  # requests per second
       max_retries=3,
       retry_delay=5
   )

Monitoring Stack
-------------

Docker Compose configuration:

.. code-block:: yaml

   # docker-compose.monitoring.yml
   version: '3'
   services:
     prometheus:
       image: prom/prometheus
       ports:
         - "${PROMETHEUS_PORT}:9090"
       volumes:
         - ./prometheus.yml:/etc/prometheus/prometheus.yml

     grafana:
       image: grafana/grafana
       ports:
         - "${GRAFANA_PORT}:3000"
       environment:
         - GF_SECURITY_ADMIN_PASSWORD=admin
       depends_on:
         - prometheus

Logging
------

Configure logging:

.. code-block:: python

   import logging

   logging.basicConfig(
       level=logging.INFO,
       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
       handlers=[
           logging.FileHandler('feed_processor.log'),
           logging.StreamHandler()
       ]
   )
