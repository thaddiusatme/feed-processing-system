.. _api:

API Reference
===========

Core Components
-------------

FeedProcessor
~~~~~~~~~~~

.. autoclass:: feed_processor.FeedProcessor
   :members:
   :undoc-members:
   :show-inheritance:

Inoreader Client
~~~~~~~~~~~~~

.. include:: inoreader.rst

PriorityQueue
~~~~~~~~~~~~

.. autoclass:: feed_processor.queue.PriorityQueue
   :members:
   :undoc-members:
   :show-inheritance:

WebhookManager
~~~~~~~~~~~~

.. autoclass:: feed_processor.webhook.WebhookManager
   :members:
   :undoc-members:
   :show-inheritance:

Monitoring Components
------------------

MetricsCollector
~~~~~~~~~~~~~~

.. autoclass:: feed_processor.metrics.MetricsCollector
   :members:
   :undoc-members:
   :show-inheritance:

PrometheusExporter
~~~~~~~~~~~~~~~~

.. autoclass:: feed_processor.metrics_exporter.PrometheusExporter
   :members:
   :undoc-members:
   :show-inheritance:

Error Handling
------------

ErrorHandler
~~~~~~~~~~

.. autoclass:: feed_processor.error_handler.ErrorHandler
   :members:
   :undoc-members:
   :show-inheritance:

CircuitBreaker
~~~~~~~~~~~~

.. autoclass:: feed_processor.error_handler.CircuitBreaker
   :members:
   :undoc-members:
   :show-inheritance:

Enums and Constants
-----------------

Priority
~~~~~~~

.. autoclass:: feed_processor.Priority
   :members:
   :undoc-members:
   :show-inheritance:

ErrorCategory
~~~~~~~~~~~

.. autoclass:: feed_processor.ErrorCategory
   :members:
   :undoc-members:
   :show-inheritance:

ErrorSeverity
~~~~~~~~~~~

.. autoclass:: feed_processor.ErrorSeverity
   :members:
   :undoc-members:
   :show-inheritance:

Exceptions
---------

.. automodule:: feed_processor.exceptions
   :members:
   :undoc-members:
   :show-inheritance:
