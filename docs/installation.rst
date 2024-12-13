.. _installation:

Installation Guide
================

Prerequisites
------------

* Python 3.8 or higher
* Docker and Docker Compose (for monitoring stack)
* Git

Basic Installation
----------------

1. Clone the repository:

   .. code-block:: bash

      git clone https://github.com/yourusername/feed-processing-system.git
      cd feed-processing-system

2. Create and activate a virtual environment:

   .. code-block:: bash

      python -m venv venv
      source venv/bin/activate  # On Windows: venv\Scripts\activate

3. Install dependencies:

   .. code-block:: bash

      pip install -r requirements.txt

Development Installation
----------------------

For development, install additional dependencies:

.. code-block:: bash

   pip install -r requirements-dev.txt

This includes:

* Testing tools (pytest, pytest-cov)
* Code quality tools (black, flake8, mypy)
* Documentation tools (sphinx)

Monitoring Stack
--------------

To set up the monitoring stack:

1. Ensure Docker and Docker Compose are installed
2. Start the monitoring services:

   .. code-block:: bash

      docker-compose -f docker-compose.monitoring.yml up -d

3. Access the monitoring interfaces:

   * Grafana: http://localhost:3000 (admin/admin)
   * Prometheus: http://localhost:9090

Environment Setup
---------------

1. Copy the environment template:

   .. code-block:: bash

      cp env.example .env

2. Edit `.env` with your configuration:

   * API credentials
   * Webhook settings
   * Performance tuning
   * Monitoring ports

Verification
----------

Verify the installation:

.. code-block:: bash

   # Run tests
   python -m pytest

   # Check code quality
   black .
   flake8
   mypy .

   # Start the monitoring stack
   docker-compose -f docker-compose.monitoring.yml up -d

   # Run the example
   python examples/basic_usage.py
