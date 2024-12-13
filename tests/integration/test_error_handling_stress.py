import pytest
import threading
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any

from feed_processor.error_handling import (
    ErrorHandler,
    ErrorCategory,
    ErrorSeverity,
    CircuitBreaker
)

class TestErrorHandlingStress:
    @pytest.fixture
    def error_handler(self):
        return ErrorHandler()

    def simulate_api_call(self, error_handler: ErrorHandler, service: str) -> None:
        """Simulate an API call that might fail"""
        try:
            if random.random() < 0.3:  # 30% chance of failure
                raise Exception(f"Simulated {service} error")
        except Exception as e:
            error_handler.handle_error(
                error=e,
                category=random.choice(list(ErrorCategory)),
                severity=random.choice(list(ErrorSeverity)),
                service=service,
                details={"thread_id": threading.get_ident()},
            )

    def test_concurrent_error_handling(self, error_handler):
        """Test error handling under concurrent load"""
        num_threads = 10
        iterations = 100
        
        def worker():
            for _ in range(iterations):
                self.simulate_api_call(error_handler, "stress_test")
                time.sleep(random.uniform(0.01, 0.05))  # Random delay
        
        threads = [
            threading.Thread(target=worker)
            for _ in range(num_threads)
        ]
        
        start_time = time.time()
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        duration = time.time() - start_time
        
        # Verify error handling integrity
        metrics = error_handler.get_error_metrics()
        assert len(error_handler.error_history) <= error_handler.error_history.maxlen
        assert all(cb.state in ["open", "closed", "half-open"] 
                  for cb in error_handler.circuit_breakers.values())

    def test_concurrent_circuit_breakers(self, error_handler):
        """Test multiple circuit breakers under concurrent load"""
        services = ["service1", "service2", "service3"]
        num_threads = 5
        iterations = 50
        
        def service_worker(service: str):
            for _ in range(iterations):
                # Simulate service calls with varying failure rates
                failure_rate = 0.4 if service == "service2" else 0.2
                try:
                    if random.random() < failure_rate:
                        raise Exception(f"{service} error")
                except Exception as e:
                    error_handler.handle_error(
                        error=e,
                        category=ErrorCategory.API_ERROR,
                        severity=ErrorSeverity.HIGH,
                        service=service,
                        details={"thread": threading.get_ident()},
                    )
                time.sleep(random.uniform(0.01, 0.03))
        
        with ThreadPoolExecutor(max_workers=num_threads * len(services)) as executor:
            futures = []
            for service in services:
                for _ in range(num_threads):
                    futures.append(
                        executor.submit(service_worker, service)
                    )
            
            # Wait for all futures to complete
            for future in as_completed(futures):
                future.result()
        
        # Verify circuit breaker states
        circuit_states = {
            service: error_handler._get_circuit_breaker(service).state
            for service in services
        }
        
        # service2 should be more likely to be open due to higher failure rate
        assert any(state == "open" for state in circuit_states.values())

    def test_error_logging_under_load(self, error_handler):
        """Test error logging system under heavy load"""
        num_threads = 8
        iterations = 75
        
        error_scenarios = [
            (ErrorCategory.API_ERROR, ErrorSeverity.HIGH),
            (ErrorCategory.RATE_LIMIT_ERROR, ErrorSeverity.MEDIUM),
            (ErrorCategory.SYSTEM_ERROR, ErrorSeverity.CRITICAL),
            (ErrorCategory.PROCESSING_ERROR, ErrorSeverity.LOW),
        ]
        
        def logging_worker():
            for _ in range(iterations):
                category, severity = random.choice(error_scenarios)
                try:
                    raise Exception("Test error under load")
                except Exception as e:
                    error_handler.handle_error(
                        error=e,
                        category=category,
                        severity=severity,
                        service="logging_test",
                        details={
                            "thread": threading.get_ident(),
                            "timestamp": time.time(),
                            "test_data": "x" * random.randint(100, 1000)
                        },
                    )
                time.sleep(random.uniform(0.001, 0.01))
        
        threads = [
            threading.Thread(target=logging_worker)
            for _ in range(num_threads)
        ]
        
        start_time = time.time()
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        duration = time.time() - start_time
        
        # Verify logging integrity
        metrics = error_handler.get_error_metrics()
        assert len(error_handler.error_history) > 0
        assert all(isinstance(err.error_id, str) for err in error_handler.error_history)
        
        # Check error distribution
        category_counts = metrics["errors_by_category"]
        severity_counts = metrics["errors_by_severity"]
        assert len(category_counts) > 0
        assert len(severity_counts) > 0

    def test_memory_usage_under_load(self, error_handler):
        """Test memory usage with large error payloads"""
        import sys
        import gc
        
        initial_memory = self._get_memory_usage()
        large_data = "x" * 1000000  # 1MB string
        
        for _ in range(1000):
            try:
                raise Exception("Large error payload test")
            except Exception as e:
                error_handler.handle_error(
                    error=e,
                    category=ErrorCategory.SYSTEM_ERROR,
                    severity=ErrorSeverity.HIGH,
                    service="memory_test",
                    details={"large_data": large_data},
                )
        
        gc.collect()  # Force garbage collection
        final_memory = self._get_memory_usage()
        
        # Verify memory usage is within reasonable bounds
        memory_increase = final_memory - initial_memory
        assert memory_increase < 100 * 1024 * 1024  # Less than 100MB increase

    @staticmethod
    def _get_memory_usage() -> int:
        """Get current memory usage in bytes"""
        import psutil
        process = psutil.Process()
        return process.memory_info().rss
