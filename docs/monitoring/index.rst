.. _monitoring:

Monitoring Guide
==============

Overview
--------

The Feed Processing System includes comprehensive monitoring capabilities using Prometheus and Grafana.

Components
---------

* Prometheus: Time-series database and monitoring system
* Grafana: Visualization and alerting
* Metrics Exporter: Custom Prometheus exporter for system metrics

Available Metrics
---------------

Processing Metrics
~~~~~~~~~~~~~~~~

* ``feed_items_processed_total``: Counter of processed items
  
  * Labels: ``status=[success|failure]``
  * Description: Total number of items processed
  * Usage: Track processing success rate

* ``feed_processing_latency_seconds``: Processing time histogram
  
  * Description: Distribution of item processing times
  * Buckets: [0.1, 0.5, 1, 2, 5, 10]
  * Usage: Monitor processing performance

* ``feed_queue_size``: Current queue size by priority
  
  * Labels: ``priority=[high|medium|low]``
  * Description: Number of items in each queue
  * Usage: Monitor queue health

Webhook Metrics
~~~~~~~~~~~~~

* ``webhook_retries_total``: Retry attempts counter
  
  * Labels: ``attempt=[1|2|3]``
  * Description: Number of retry attempts
  * Usage: Track delivery reliability

* ``webhook_duration_seconds``: Webhook latency histogram
  
  * Description: Distribution of webhook request times
  * Buckets: [0.1, 0.5, 1, 2, 5, 10]
  * Usage: Monitor webhook performance

* ``webhook_payload_size_bytes``: Payload size histogram
  
  * Description: Distribution of webhook payload sizes
  * Buckets: [100, 1000, 10000, 100000]
  * Usage: Track payload sizes

* ``rate_limit_delay_seconds``: Current rate limit delay gauge
  
  * Description: Current rate limiting delay
  * Usage: Monitor rate limiting impact

Queue Metrics
~~~~~~~~~~~

* ``queue_overflow_total``: Queue overflow counter
  
  * Labels: ``priority=[high|medium|low]``
  * Description: Number of queue overflow events
  * Usage: Track queue capacity issues

* ``queue_items_by_priority``: Current items by priority
  
  * Labels: ``priority=[high|medium|low]``
  * Description: Distribution of items by priority
  * Usage: Monitor queue balance

Grafana Dashboard
---------------

The system includes a pre-configured Grafana dashboard with:

Performance Panels
~~~~~~~~~~~~~~~~

* Processing success/failure rates
* Queue size with thresholds
* Latency trends
* Queue distribution

System Health Panels
~~~~~~~~~~~~~~~~~~

* Webhook retry patterns
* Rate limiting impact
* Payload size trends
* Queue overflow events

Features:

* Real-time updates (5s refresh)
* Historical data viewing
* Interactive tooltips
* Statistical summaries

Custom Metrics
------------

Adding custom metrics:

.. code-block:: python

   from feed_processor.metrics_exporter import PrometheusExporter

   # Initialize the exporter
   exporter = PrometheusExporter(port=8000)
   exporter.start()

   # Update metrics
   metrics_snapshot = processor.metrics.get_snapshot()
   exporter.update_from_snapshot(metrics_snapshot)

Alerting
-------

Configure Grafana alerts:

1. Open Grafana dashboard
2. Click "Alert Rules"
3. Add new alert rule
4. Configure conditions and notifications

Example alert rules:

* Queue overflow > 10 in 5 minutes
* Processing latency > 5s
* Webhook retry rate > 20%

Best Practices
------------

1. Monitor key metrics:
   
   * Processing success rate
   * Queue sizes
   * Latency trends
   * Error rates

2. Set up alerts for:
   
   * Queue overflows
   * High latency
   * Error spikes
   * Rate limit delays

3. Regular dashboard review:
   
   * Check trends
   * Identify bottlenecks
   * Optimize thresholds
