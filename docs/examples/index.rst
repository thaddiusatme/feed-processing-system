.. _examples:

Usage Examples
============

Basic Usage
---------

Simple Feed Processing
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from feed_processor import FeedProcessor

   # Initialize processor
   processor = FeedProcessor()

   # Process items
   processor.fetch_and_queue_items()
   processor.process_queue(batch_size=10)

Custom Priority Rules
------------------

Implementing Priority Logic
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from feed_processor import FeedProcessor, Priority

   class CustomFeedProcessor(FeedProcessor):
       def _is_breaking_news(self, item):
           title = item.get("title", "").lower()
           return any(keyword in title 
                     for keyword in ["breaking", "urgent"])

       def _determine_priority(self, item):
           if self._is_breaking_news(item):
               return Priority.HIGH
           return Priority.NORMAL

Monitoring Integration
-------------------

Setting Up Metrics
~~~~~~~~~~~~~~~

.. code-block:: python

   from feed_processor.metrics_exporter import PrometheusExporter

   # Initialize exporter
   exporter = PrometheusExporter(port=8000)
   exporter.start()

   # Update metrics
   processor = FeedProcessor()
   metrics = processor.metrics.get_snapshot()
   exporter.update_from_snapshot(metrics)

Error Handling
-----------

Using Circuit Breaker
~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from feed_processor import (
       FeedProcessor, 
       ErrorCategory, 
       ErrorSeverity
   )

   processor = FeedProcessor()

   try:
       processor.process_queue()
   except Exception as e:
       processor.error_handler.handle_error(
           error=e,
           category=ErrorCategory.PROCESSING_ERROR,
           severity=ErrorSeverity.HIGH
       )

Queue Management
-------------

Custom Queue Implementation
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from feed_processor.queue import PriorityQueue
   from feed_processor import Priority

   # Initialize queue
   queue = PriorityQueue(max_size=1000)

   # Add items
   queue.enqueue({"id": 1}, Priority.HIGH)
   queue.enqueue({"id": 2}, Priority.NORMAL)

   # Process items
   while not queue.is_empty():
       item = queue.dequeue()
       process_item(item)

Webhook Integration
----------------

Custom Webhook Handler
~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from feed_processor.webhook import WebhookManager

   # Initialize manager
   webhook_manager = WebhookManager(
       webhook_url="https://api.example.com/webhook",
       rate_limit=0.2,
       max_retries=3
   )

   # Send data
   result = webhook_manager.send({"key": "value"})
   if result.success:
       print("Webhook delivered")
   else:
       print(f"Delivery failed: {result.error}")

Complete Example
-------------

Full Implementation
~~~~~~~~~~~~~~~~

.. code-block:: python

   from feed_processor import (
       FeedProcessor, 
       Priority,
       ErrorCategory
   )
   from feed_processor.metrics_exporter import PrometheusExporter

   class CustomProcessor(FeedProcessor):
       def _determine_priority(self, item):
           if self._is_breaking_news(item):
               return Priority.HIGH
           return Priority.NORMAL

   # Initialize components
   processor = CustomProcessor()
   exporter = PrometheusExporter(port=8000)
   exporter.start()

   try:
       # Process feeds
       processor.fetch_and_queue_items()
       processor.process_queue(batch_size=10)

       # Update metrics
       metrics = processor.metrics.get_snapshot()
       exporter.update_from_snapshot(metrics)

   except Exception as e:
       processor.error_handler.handle_error(
           error=e,
           category=ErrorCategory.PROCESSING_ERROR
       )
       raise

   finally:
       exporter.stop()
