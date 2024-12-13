.. _development:

Development Guide
===============

Setup
-----

1. Install development dependencies:

   .. code-block:: bash

      pip install -r requirements-dev.txt

2. Install pre-commit hooks:

   .. code-block:: bash

      pre-commit install

Code Quality
----------

The project uses several tools to maintain code quality:

Black
~~~~~

Code formatting:

.. code-block:: bash

   # Format code
   black .

   # Check formatting
   black . --check

Configuration in ``pyproject.toml``:

.. code-block:: toml

   [tool.black]
   line-length = 100
   target-version = ['py38']

Flake8
~~~~~~

Linting:

.. code-block:: bash

   flake8

Configuration in ``.flake8``:

.. code-block:: ini

   [flake8]
   max-line-length = 100
   extend-ignore = E203

MyPy
~~~~

Type checking:

.. code-block:: bash

   mypy .

Configuration in ``pyproject.toml``:

.. code-block:: toml

   [tool.mypy]
   python_version = "3.8"
   warn_return_any = true

Testing
------

Test Structure
~~~~~~~~~~~~

* ``tests/unit/``: Unit tests
* ``tests/integration/``: Integration tests
* ``tests/conftest.py``: Shared fixtures

Running Tests
~~~~~~~~~~~

.. code-block:: bash

   # Run all tests
   pytest

   # Run specific test types
   pytest tests/unit/
   pytest tests/integration/

   # Run with coverage
   pytest --cov

   # Generate coverage report
   pytest --cov --cov-report=html

Test Configuration
~~~~~~~~~~~~~~~

Configuration in ``pyproject.toml``:

.. code-block:: toml

   [tool.pytest.ini_options]
   minversion = "6.0"
   addopts = "-ra -q --cov"

Monitoring Development
-------------------

Local Setup
~~~~~~~~~~

1. Start monitoring stack:

   .. code-block:: bash

      docker-compose -f docker-compose.monitoring.yml up -d

2. Access services:
   
   * Grafana: http://localhost:3000
   * Prometheus: http://localhost:9090

Development Workflow
~~~~~~~~~~~~~~~~~

1. Write code and tests
2. Run code quality checks
3. Run tests with coverage
4. Update documentation
5. Submit pull request

Pull Request Guidelines
--------------------

1. Create feature branch
2. Write tests
3. Update documentation
4. Run quality checks
5. Submit PR with:
   
   * Description of changes
   * Test coverage report
   * Documentation updates
   * Breaking changes noted

Documentation
-----------

Building Docs
~~~~~~~~~~~

.. code-block:: bash

   # Install Sphinx
   pip install -r requirements-dev.txt

   # Build documentation
   cd docs
   make html

Writing Docs
~~~~~~~~~~

* Use reStructuredText format
* Include docstrings
* Add examples
* Update API reference

Release Process
------------

1. Update version in:
   
   * ``setup.py``
   * ``docs/conf.py``
   * ``CHANGELOG.md``

2. Run tests and checks
3. Build documentation
4. Create release tag
5. Push to repository
