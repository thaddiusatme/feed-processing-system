import pytest
import socket
import threading
import time
from unittest.mock import patch, MagicMock
from contextlib import contextmanager
from typing import Generator, Any

from feed_processor.error_handling import (
    ErrorHandler,
    ErrorCategory,
    ErrorSeverity
)

class NetworkPartitionSimulator:
    def __init__(self):
        self._original_socket = socket.socket
        self.active = False

    def start(self):
        """Start simulating network partition"""
        self.active = True
        socket.socket = self._broken_socket

    def stop(self):
        """Stop simulating network partition"""
        self.active = False
        socket.socket = self._original_socket

    def _broken_socket(self, *args, **kwargs):
        """Create a socket that fails all operations"""
        if self.active:
            raise socket.error("Network unreachable")
        return self._original_socket(*args, **kwargs)

class TestErrorHandlingEdgeCases:
    @pytest.fixture
    def error_handler(self):
        return ErrorHandler()

    @pytest.fixture
    def network_partition(self):
        simulator = NetworkPartitionSimulator()
        yield simulator
        simulator.stop()  # Ensure cleanup

    def test_network_partition_recovery(self, error_handler, network_partition):
        """Test system behavior during network partition"""
        # Step 1: Normal operation
        self._verify_normal_operation(error_handler)
        
        # Step 2: Simulate network partition
        network_partition.start()
        partition_errors = []
        
        for _ in range(5):
            try:
                self._make_external_call()
            except Exception as e:
                partition_errors.append(
                    error_handler.handle_error(
                        error=e,
                        category=ErrorCategory.NETWORK_ERROR,
                        severity=ErrorSeverity.HIGH,
                        service="external_api",
                        details={"state": "partition"}
                    )
                )
        
        assert len(partition_errors) == 5
        assert error_handler._get_circuit_breaker("external_api").state == "open"
        
        # Step 3: Recover from partition
        network_partition.stop()
        time.sleep(error_handler._get_circuit_breaker("external_api").reset_timeout)
        
        # Step 4: Verify recovery
        self._verify_normal_operation(error_handler)

    def test_database_connection_failures(self, error_handler):
        """Test handling of database connection failures"""
        with patch("psycopg2.connect") as mock_connect:
            # Simulate intermittent failures
            failure_count = 0
            def flaky_connect(*args, **kwargs):
                nonlocal failure_count
                failure_count += 1
                if failure_count % 2 == 0:
                    raise Exception("Connection refused")
                return MagicMock()

            mock_connect.side_effect = flaky_connect
            
            # Test connection retry logic
            for _ in range(10):
                try:
                    self._db_operation()
                except Exception as e:
                    error_handler.handle_error(
                        error=e,
                        category=ErrorCategory.DATABASE_ERROR,
                        severity=ErrorSeverity.HIGH,
                        service="database",
                        details={"attempt": failure_count}
                    )
            
            # Verify error handling
            metrics = error_handler.get_error_metrics()
            assert metrics["errors_by_category"][ErrorCategory.DATABASE_ERROR.value] == 5

    def test_partial_system_failure(self, error_handler):
        """Test system behavior during partial component failures"""
        components = ["api", "database", "cache", "queue"]
        failed_components = set()
        
        def component_operation(component: str) -> bool:
            if component in failed_components:
                raise Exception(f"{component} failure")
            return True

        # Simulate partial system failure
        failed_components.update(["cache", "queue"])
        
        # Test system operation with partial failures
        for component in components:
            try:
                component_operation(component)
            except Exception as e:
                error_handler.handle_error(
                    error=e,
                    category=ErrorCategory.SYSTEM_ERROR,
                    severity=ErrorSeverity.HIGH,
                    service=component,
                    details={"state": "degraded"}
                )
        
        # Verify system state
        circuit_states = {
            component: error_handler._get_circuit_breaker(component).state
            for component in components
        }
        
        assert circuit_states["api"] == "closed"
        assert circuit_states["database"] == "closed"
        assert circuit_states["cache"] == "open"
        assert circuit_states["queue"] == "open"

    def test_catastrophic_failure_recovery(self, error_handler):
        """Test recovery from catastrophic system failure"""
        # Step 1: Simulate catastrophic failure
        with self._simulate_catastrophic_failure():
            for _ in range(10):
                try:
                    self._critical_operation()
                except Exception as e:
                    error_handler.handle_error(
                        error=e,
                        category=ErrorCategory.SYSTEM_ERROR,
                        severity=ErrorSeverity.CRITICAL,
                        service="core_system",
                        details={"state": "failed"}
                    )
        
        # Step 2: Verify all circuits are open
        assert all(
            cb.state == "open"
            for cb in error_handler.circuit_breakers.values()
        )
        
        # Step 3: Begin recovery
        time.sleep(max(
            cb.reset_timeout
            for cb in error_handler.circuit_breakers.values()
        ))
        
        # Step 4: Verify recovery
        recovery_success = 0
        for _ in range(5):
            try:
                self._critical_operation()
                recovery_success += 1
            except Exception as e:
                error_handler.handle_error(
                    error=e,
                    category=ErrorCategory.SYSTEM_ERROR,
                    severity=ErrorSeverity.HIGH,
                    service="core_system",
                    details={"state": "recovering"}
                )
        
        assert recovery_success > 0
        assert any(
            cb.state == "closed"
            for cb in error_handler.circuit_breakers.values()
        )

    @contextmanager
    def _simulate_catastrophic_failure(self) -> Generator[None, None, None]:
        """Simulate a catastrophic system failure"""
        with patch.multiple(
            "socket.socket",
            connect=MagicMock(side_effect=socket.error),
            send=MagicMock(side_effect=socket.error),
            recv=MagicMock(side_effect=socket.error)
        ), patch(
            "psycopg2.connect",
            side_effect=Exception("Database unreachable")
        ), patch(
            "redis.Redis",
            side_effect=Exception("Cache unreachable")
        ):
            yield

    def _verify_normal_operation(self, error_handler: ErrorHandler) -> None:
        """Verify system is operating normally"""
        try:
            self._make_external_call()
            return True
        except Exception as e:
            error_handler.handle_error(
                error=e,
                category=ErrorCategory.SYSTEM_ERROR,
                severity=ErrorSeverity.HIGH,
                service="system_check",
                details={"state": "checking"}
            )
            return False

    def _make_external_call(self) -> Any:
        """Simulate external API call"""
        return requests.get("https://api.example.com/test")

    def _db_operation(self) -> Any:
        """Simulate database operation"""
        import psycopg2
        conn = psycopg2.connect("dbname=test")
        return conn

    def _critical_operation(self) -> None:
        """Simulate critical system operation"""
        self._make_external_call()
        self._db_operation()
