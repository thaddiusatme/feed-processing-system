import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from feed_processor.error_handling import (ErrorCategory, ErrorHandler,
                                           ErrorSeverity)


class TestErrorLoggingPipeline:
    @pytest.fixture
    def error_handler(self):
        return ErrorHandler()

    @pytest.fixture
    def log_dir(self, tmp_path):
        """Create temporary directory for log files"""
        log_path = tmp_path / "logs"
        log_path.mkdir()
        return log_path

    def test_end_to_end_logging_flow(self, error_handler, log_dir):
        """Test complete logging pipeline from error to storage"""
        # Step 1: Generate various types of errors
        errors = self._generate_test_errors()

        # Step 2: Process errors through handler
        logged_errors = []
        for error_info in errors:
            try:
                raise Exception(error_info["message"])
            except Exception as e:
                result = error_handler.handle_error(
                    error=e,
                    category=error_info["category"],
                    severity=error_info["severity"],
                    service=error_info["service"],
                    details=error_info["details"],
                )
                logged_errors.append(result)

        # Step 3: Verify system logs
        system_log_file = log_dir / "system.log"
        with patch("logging.FileHandler") as mock_handler:
            mock_handler.baseFilename = str(system_log_file)

            # Verify all errors were logged
            assert mock_handler.handle.call_count >= len(errors)

            # Verify log format and content
            for call in mock_handler.handle.call_args_list:
                record = call[0][0]
                assert hasattr(record, "error_id")
                assert hasattr(record, "severity")
                assert hasattr(record, "category")

    def test_airtable_logging_integration(self, error_handler):
        """Test Airtable logging pipeline"""
        with patch("pyairtable.Table") as mock_table:
            # Generate and process test errors
            errors = self._generate_test_errors()
            for error_info in errors:
                try:
                    raise Exception(error_info["message"])
                except Exception as e:
                    error_handler.handle_error(
                        error=e,
                        category=error_info["category"],
                        severity=error_info["severity"],
                        service=error_info["service"],
                        details=error_info["details"],
                    )

            # Verify Airtable records
            create_calls = mock_table.create.call_args_list
            assert len(create_calls) > 0

            for call in create_calls:
                record = call[0][0]
                # Verify sensitive data was removed
                assert "api_key" not in str(record)
                assert "password" not in str(record)
                # Verify required fields
                assert "error_id" in record
                assert "timestamp" in record
                assert "severity" in record

    def test_error_notification_pipeline(self, error_handler):
        """Test error notification system"""
        with patch("requests.post") as mock_post:
            # Simulate critical error
            try:
                raise Exception("Critical system failure")
            except Exception as e:
                error_handler.handle_error(
                    error=e,
                    category=ErrorCategory.SYSTEM_ERROR,
                    severity=ErrorSeverity.CRITICAL,
                    service="core_system",
                    details={"impact": "high"},
                )

            # Verify notification was sent
            assert mock_post.called
            notification_data = mock_post.call_args[1]["json"]
            assert "CRITICAL" in str(notification_data)
            assert "core_system" in str(notification_data)

    def test_log_rotation_and_cleanup(self, error_handler, log_dir):
        """Test log rotation and cleanup functionality"""
        max_log_size = 1024  # 1KB
        max_log_age = timedelta(days=7)

        # Create some old log files
        old_log = log_dir / "system.log.1"
        old_log.write_text("Old log content")
        old_time = time.time() - (max_log_age.days + 1) * 86400
        os.utime(str(old_log), (old_time, old_time))

        # Generate enough errors to trigger rotation
        large_message = "x" * (max_log_size // 10)
        for _ in range(20):
            try:
                raise Exception(large_message)
            except Exception as e:
                error_handler.handle_error(
                    error=e,
                    category=ErrorCategory.SYSTEM_ERROR,
                    severity=ErrorSeverity.LOW,
                    service="test",
                    details={"size": len(large_message)},
                )

        # Verify log rotation
        assert (log_dir / "system.log").exists()
        assert (log_dir / "system.log.1").exists()

        # Verify old logs were cleaned up
        assert not old_log.exists()

    def test_error_metrics_aggregation(self, error_handler):
        """Test error metrics collection and aggregation"""
        # Generate errors across different categories and severities
        errors = self._generate_test_errors()
        expected_counts = {"category": {}, "severity": {}, "service": {}}

        # Process errors and track expected counts
        for error_info in errors:
            try:
                raise Exception(error_info["message"])
            except Exception as e:
                error_handler.handle_error(
                    error=e,
                    category=error_info["category"],
                    severity=error_info["severity"],
                    service=error_info["service"],
                    details=error_info["details"],
                )

                # Update expected counts
                cat = error_info["category"].value
                sev = error_info["severity"].value
                svc = error_info["service"]

                expected_counts["category"][cat] = expected_counts["category"].get(cat, 0) + 1
                expected_counts["severity"][sev] = expected_counts["severity"].get(sev, 0) + 1
                expected_counts["service"][svc] = expected_counts["service"].get(svc, 0) + 1

        # Verify metrics
        metrics = error_handler.get_error_metrics()
        assert metrics["errors_by_category"] == expected_counts["category"]
        assert metrics["errors_by_severity"] == expected_counts["severity"]
        assert all(metrics["circuit_breaker_states"].get(svc) for svc in expected_counts["service"])

    @staticmethod
    def _generate_test_errors() -> List[Dict[str, Any]]:
        """Generate test error scenarios"""
        return [
            {
                "message": "API Authentication failed",
                "category": ErrorCategory.API_ERROR,
                "severity": ErrorSeverity.HIGH,
                "service": "inoreader",
                "details": {"api_key": "secret", "endpoint": "/auth"},
            },
            {
                "message": "Rate limit exceeded",
                "category": ErrorCategory.RATE_LIMIT_ERROR,
                "severity": ErrorSeverity.MEDIUM,
                "service": "webhook",
                "details": {"limit": 100, "current": 150},
            },
            {
                "message": "Database connection failed",
                "category": ErrorCategory.SYSTEM_ERROR,
                "severity": ErrorSeverity.CRITICAL,
                "service": "database",
                "details": {
                    "connection_string": "sensitive_info",
                    "error_code": "CONNECTION_REFUSED",
                },
            },
        ]
