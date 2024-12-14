Inoreader API Client
==================

The Inoreader API client provides a robust interface for interacting with the Inoreader API. It handles authentication, rate limiting, and error handling.

Configuration
------------

.. autoclass:: feed_processor.inoreader.client.InoreaderConfig
   :members:
   :undoc-members:
   :show-inheritance:

Client
------

.. autoclass:: feed_processor.inoreader.client.InoreaderClient
   :members:
   :undoc-members:
   :show-inheritance:

Authentication
-------------

The client uses a combination of OAuth token and API credentials for authentication:

1. OAuth Token
   - Passed in the Authorization header as "Bearer {token}"
   - Used for user authentication
   - Required for all API requests

2. API Credentials
   - AppId and AppKey are passed as URL parameters
   - Required for application authentication
   - Must use correct capitalization: "AppId" and "AppKey"

Example Usage
------------

.. code-block:: python

    from feed_processor.inoreader.client import InoreaderClient, InoreaderConfig

    # Initialize configuration
    config = InoreaderConfig(
        token="your_oauth_token",
        app_id="your_app_id",
        api_key="your_api_key"
    )

    # Create client instance
    client = InoreaderClient(config)

    # Get stream contents
    items = await client.get_stream_contents(count=20)

Environment Variables
------------------

The following environment variables are used:

- ``INOREADER_TOKEN``: OAuth token for authentication
- ``INOREADER_APP_ID``: Application ID
- ``INOREADER_API_KEY``: Application key

Rate Limiting
------------

The client includes built-in rate limiting to prevent exceeding API quotas:

- Default rate limit: 50 requests per minute
- Configurable through InoreaderConfig
- Automatic retry with exponential backoff for rate limit errors
