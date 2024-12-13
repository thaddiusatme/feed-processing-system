import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List

import pytest

from feed_processor.error_handling import (CircuitBreaker, ErrorCategory,
                                           ErrorHandler, ErrorSeverity)


@dataclass
class PerformanceMetrics:
    operation: str
    latencies: List[float]
    error_count: int
    success_count: int
    start_time: float
    end_time: float

    @property
    def avg_latency(self) -> float:
        return statistics.mean(self.latencies) if self.latencies else 0

    @property
    def p95_latency(self) -> float:
        if not self.latencies:
            return 0
        sorted_latencies = sorted(self.latencies)
        idx = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[idx]

    @property
    def throughput(self) -> float:
        duration = self.end_time - self.start_time
        total_ops = self.error_count + self.success_count
        return total_ops / duration if duration > 0 else 0


class TestErrorHandlingPerformance:
    @pytest.fixture
    def error_handler(self):
        return ErrorHandler()

    def measure_operation(
        self, operation: Callable, num_iterations: int = 1000
    ) -> PerformanceMetrics:
        """Measure performance metrics for an operation"""
        latencies = []
        error_count = 0
        success_count = 0
        start_time = time.time()

        for _ in range(num_iterations):
            try:
                op_start = time.time()
                operation()
                latencies.append(time.time() - op_start)
                success_count += 1
            except Exception:
                error_count += 1

        return PerformanceMetrics(
            operation=operation.__name__,
            latencies=latencies,
            error_count=error_count,
            success_count=success_count,
            start_time=start_time,
            end_time=time.time(),
        )

    def test_error_handling_latency(self, error_handler):
        """Measure basic error handling latency"""

        def error_operation():
            try:
                raise Exception("Test error")
            except Exception as e:
                error_handler.handle_error(
                    error=e,
                    category=ErrorCategory.SYSTEM_ERROR,
                    severity=ErrorSeverity.LOW,
                    service="latency_test",
                    details={"timestamp": time.time()},
                )

        metrics = self.measure_operation(error_operation, num_iterations=1000)

        # Verify performance meets requirements
        assert metrics.avg_latency < 0.001  # Less than 1ms average
        assert metrics.p95_latency < 0.005  # Less than 5ms for 95th percentile

        print(f"\nError Handling Latency Metrics:")
        print(f"Average Latency: {metrics.avg_latency*1000:.2f}ms")
        print(f"P95 Latency: {metrics.p95_latency*1000:.2f}ms")
        print(f"Throughput: {metrics.throughput:.2f} ops/sec")

    def test_retry_strategy_performance(self, error_handler):
        """Compare performance of different retry strategies"""
        strategies = {
            "fixed": lambda x: 1.0,
            "exponential": lambda x: 2**x,
            "exponential_with_jitter": lambda x: (2**x) * (1 + random.random() * 0.1),
        }

        results = {}
        for name, strategy in strategies.items():
            start_time = time.time()
            latencies = []

            for _ in range(100):
                try:
                    op_start = time.time()
                    # Simulate retries
                    for retry in range(3):
                        delay = strategy(retry)
                        time.sleep(delay * 0.01)  # Scale down for testing
                    latencies.append(time.time() - op_start)
                except Exception:
                    pass

            results[name] = {
                "avg_latency": statistics.mean(latencies),
                "p95_latency": sorted(latencies)[int(len(latencies) * 0.95)],
                "total_time": time.time() - start_time,
            }

        # Print comparison
        print("\nRetry Strategy Performance Comparison:")
        for strategy, metrics in results.items():
            print(f"\n{strategy.title()}:")
            print(f"Average Latency: {metrics['avg_latency']*1000:.2f}ms")
            print(f"P95 Latency: {metrics['p95_latency']*1000:.2f}ms")
            print(f"Total Time: {metrics['total_time']:.2f}s")

    def test_logging_pipeline_performance(self, error_handler):
        """Measure logging pipeline performance under load"""
        num_threads = 4
        iterations_per_thread = 250

        def logging_worker():
            latencies = []
            for _ in range(iterations_per_thread):
                try:
                    raise Exception("Test error")
                except Exception as e:
                    start_time = time.time()
                    error_handler.handle_error(
                        error=e,
                        category=ErrorCategory.SYSTEM_ERROR,
                        severity=ErrorSeverity.LOW,
                        service="logging_test",
                        details={
                            "timestamp": datetime.utcnow().isoformat(),
                            "data": "x" * 1000,  # 1KB payload
                        },
                    )
                    latencies.append(time.time() - start_time)
                time.sleep(0.001)  # Simulate some processing
            return latencies

        start_time = time.time()
        all_latencies = []

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(logging_worker) for _ in range(num_threads)]

            for future in as_completed(futures):
                all_latencies.extend(future.result())

        end_time = time.time()

        metrics = PerformanceMetrics(
            operation="logging_pipeline",
            latencies=all_latencies,
            error_count=0,
            success_count=len(all_latencies),
            start_time=start_time,
            end_time=end_time,
        )

        print("\nLogging Pipeline Performance:")
        print(f"Average Latency: {metrics.avg_latency*1000:.2f}ms")
        print(f"P95 Latency: {metrics.p95_latency*1000:.2f}ms")
        print(f"Throughput: {metrics.throughput:.2f} logs/sec")

        # Verify performance requirements
        assert metrics.avg_latency < 0.005  # Less than 5ms average
        assert metrics.p95_latency < 0.020  # Less than 20ms for 95th percentile
        assert metrics.throughput > 100  # At least 100 logs per second
