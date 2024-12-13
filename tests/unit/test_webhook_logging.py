import pytest
from unittest.mock import Mock, patch, create_autospec
import structlog
import time
from datetime import datetime
from feed_processor.webhook_manager import WebhookManager, WebhookResponse

@pytest.fixture
def mock_logger():
    """Create a mock logger that supports method chaining"""
    logger = Mock()
    logger.debug = Mock(return_value=logger)
    logger.info = Mock(return_value=logger)
    logger.warning = Mock(return_value=logger)
    logger.error = Mock(return_value=logger)
    logger.bind = Mock(return_value=logger)
    return logger

@pytest.fixture
def webhook_manager(mock_logger):
    with patch('structlog.get_logger', return_value=mock_logger):
        manager = WebhookManager(
            webhook_url="http://test.webhook",
            rate_limit=0.2,
            max_retries=3
        )
        return manager, mock_logger

@pytest.fixture
def valid_payload():
    return {
        "title": "Test Article",
        "contentType": ["BLOG"],
        "brief": "Test summary",
        "sourceMetadata": {"feedId": "test123"}
    }

class TestWebhookManagerLogging:
    def test_initialization_logging(self, webhook_manager):
        manager, logger = webhook_manager
        logger.info.assert_called_with(
            "webhook_manager_initialized"
        )

    def test_rate_limit_logging(self, webhook_manager, valid_payload):
        manager, logger = webhook_manager
        
        with patch('time.time', side_effect=[0, 0, 0.2]):  # Initial, elapsed check, final
            manager._wait_for_rate_limit()
            logger.debug.assert_called_with(
                "rate_limit_delay",
                sleep_time=0.2,
                elapsed=0
            )

    def test_validation_success_logging(self, webhook_manager, valid_payload):
        manager, logger = webhook_manager
        manager._validate_payload(valid_payload)
        logger.debug.assert_called_with(
            "payload_validation_success",
            payload=valid_payload
        )

    def test_validation_failure_logging(self, webhook_manager):
        manager, logger = webhook_manager
        invalid_payload = {"title": "Test"}  # Missing required fields
        
        with pytest.raises(ValueError):
            manager._validate_payload(invalid_payload)
        
        # Sort missing fields to ensure consistent order
        missing_fields = ["brief", "contentType"]  # Already sorted
        logger.warning.assert_called_with(
            "payload_validation_failed",
            error="missing_fields",
            missing_fields=missing_fields,
            payload=invalid_payload
        )

    def test_request_success_logging(self, webhook_manager, valid_payload):
        manager, logger = webhook_manager
        
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.text = "OK"
            
            manager.send_webhook(valid_payload)
            
            # Check all debug logs in sequence
            assert logger.debug.call_args_list[0][0][0] == "payload_validation_success"
            assert logger.debug.call_args_list[1][0][0] == "sending_webhook_request"
            assert logger.info.call_args_list[-1][0][0] == "webhook_request_success"

    def test_request_failure_logging(self, webhook_manager, valid_payload):
        manager, logger = webhook_manager
        
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 500
            mock_post.return_value.text = "Internal Server Error"
            
            manager.send_webhook(valid_payload)
            
            logger.warning.assert_any_call(
                "webhook_request_failed_retrying",
                status_code=500,
                retry_attempt=1,
                error="Internal Server Error"
            )

    def test_max_retries_logging(self, webhook_manager, valid_payload):
        manager, logger = webhook_manager
        
        with patch('requests.post') as mock_post, \
             patch('time.time', return_value=1734080222):
            mock_post.return_value.status_code = 500
            mock_post.return_value.text = "Internal Server Error"
            
            response = manager.send_webhook(valid_payload)
            
            logger.error.assert_called_with(
                "webhook_request_failed_max_retries",
                status_code=500,
                error="Internal Server Error",
                error_id=response.error_id
            )

    def test_bulk_send_logging(self, webhook_manager, valid_payload):
        manager, logger = webhook_manager
        payloads = [valid_payload.copy() for _ in range(3)]
        
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            
            manager.bulk_send(payloads)
            
            logger.info.assert_any_call(
                "starting_bulk_send",
                payload_count=3
            )
            
            logger.info.assert_any_call(
                "bulk_send_completed",
                total_items=3,
                success_count=3,
                error_count=0
            )

    def test_rate_limit_hit_logging(self, webhook_manager, valid_payload):
        manager, logger = webhook_manager
        
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 429
            mock_post.return_value.text = "Rate limit exceeded"
            
            manager.send_webhook(valid_payload)
            
            logger.warning.assert_any_call(
                "rate_limit_hit_adding_delay",
                delay=0.4,
                status_code=429,
                error="Rate limit exceeded"
            )

    def test_error_id_consistency(self, webhook_manager, valid_payload):
        manager, logger = webhook_manager
        
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 400
            mock_post.return_value.text = "Bad Request"
            
            response = manager.send_webhook(valid_payload)
            
            # Verify error ID format
            assert response.error_id.startswith("err_")
            assert response.error_id.split("_")[2] == "400"  # Status code in error ID
