"""Tests for feed processor optimization components."""

import unittest
from unittest.mock import Mock, patch
from datetime import datetime

import pytest

from feed_processor.core.optimization import (
    PerformanceOptimizer,
    ProcessingMetrics,
    SystemMetrics
)
from feed_processor.core.processor import FeedProcessor
from feed_processor.config.processor_config import ProcessorConfig


class TestPerformanceOptimizer:
    """Test suite for PerformanceOptimizer."""

    @pytest.fixture
    def optimizer(self):
        """Create a test optimizer instance."""
        return PerformanceOptimizer(
            base_batch_size=100,
            min_batch_size=10,
            max_batch_size=500,
            target_cpu_usage=70.0
        )

    @pytest.fixture
    def system_metrics(self):
        """Create test system metrics."""
        return SystemMetrics(
            cpu_usage=50.0,
            memory_usage=60.0,
            load_average=1.5,
            io_wait=5.0
        )

    @pytest.fixture
    def processing_metrics(self):
        """Create test processing metrics."""
        return ProcessingMetrics(
            avg_processing_time=0.5,
            error_rate=0.05,
            queue_size=100,
            throughput=200.0
        )

    def test_init(self, optimizer):
        """Test optimizer initialization."""
        assert optimizer.base_batch_size == 100
        assert optimizer.min_batch_size == 10
        assert optimizer.max_batch_size == 500
        assert optimizer.target_cpu_usage == 70.0
        assert len(optimizer.processing_history) == 0

    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('os.getloadavg')
    @patch('psutil.cpu_times_percent')
    def test_get_system_metrics(
        self,
        mock_cpu_times,
        mock_loadavg,
        mock_memory,
        mock_cpu_percent,
        optimizer
    ):
        """Test system metrics collection."""
        # Mock system calls
        mock_cpu_percent.return_value = 50.0
        mock_memory.return_value = Mock(percent=60.0)
        mock_loadavg.return_value = (1.5, 1.0, 0.5)
        mock_cpu_times.return_value = Mock(iowait=5.0)

        metrics = optimizer.get_system_metrics()
        assert metrics.cpu_usage == 50.0
        assert metrics.memory_usage == 60.0
        assert metrics.load_average == 1.5
        assert metrics.io_wait == 5.0

    def test_calculate_optimal_batch_size_low_load(self, optimizer, system_metrics, processing_metrics):
        """Test batch size calculation under low system load."""
        # Low CPU usage should increase batch size
        system_metrics.cpu_usage = 30.0
        batch_size = optimizer.calculate_optimal_batch_size(system_metrics, processing_metrics)
        assert batch_size > processing_metrics.queue_size

    def test_calculate_optimal_batch_size_high_load(self, optimizer, system_metrics, processing_metrics):
        """Test batch size calculation under high system load."""
        # High CPU usage should decrease batch size
        system_metrics.cpu_usage = 90.0
        batch_size = optimizer.calculate_optimal_batch_size(system_metrics, processing_metrics)
        assert batch_size < processing_metrics.queue_size

    def test_calculate_optimal_batch_size_bounds(self, optimizer, system_metrics, processing_metrics):
        """Test batch size stays within bounds."""
        # Test minimum bound
        processing_metrics.queue_size = 1
        system_metrics.cpu_usage = 90.0
        batch_size = optimizer.calculate_optimal_batch_size(system_metrics, processing_metrics)
        assert batch_size >= optimizer.min_batch_size

        # Test maximum bound
        processing_metrics.queue_size = 1000
        system_metrics.cpu_usage = 30.0
        batch_size = optimizer.calculate_optimal_batch_size(system_metrics, processing_metrics)
        assert batch_size <= optimizer.max_batch_size

    def test_get_optimal_thread_count(self, optimizer, system_metrics):
        """Test thread count calculation."""
        # Low CPU usage should allow more threads
        system_metrics.cpu_usage = 30.0
        system_metrics.io_wait = 5.0
        thread_count = optimizer.get_optimal_thread_count(system_metrics)
        assert thread_count > 0

        # High CPU usage should reduce threads
        system_metrics.cpu_usage = 90.0
        reduced_thread_count = optimizer.get_optimal_thread_count(system_metrics)
        assert reduced_thread_count < thread_count

        # High IO wait should increase threads
        system_metrics.cpu_usage = 50.0
        system_metrics.io_wait = 25.0
        io_thread_count = optimizer.get_optimal_thread_count(system_metrics)
        assert io_thread_count > reduced_thread_count


class TestFeedProcessorOptimization:
    """Test suite for FeedProcessor optimization integration."""

    @pytest.fixture
    def config(self):
        """Create test processor configuration."""
        return ProcessorConfig(
            batch_size=100,
            min_batch_size=10,
            max_batch_size=500,
            enable_dynamic_optimization=True,
            target_cpu_usage=70.0
        )

    @pytest.fixture
    def processor(self, config):
        """Create test processor instance."""
        return FeedProcessor(
            inoreader_token="test_token",
            webhook_url="http://test.com/webhook",
            config=config
        )

    def test_optimization_enabled(self, processor):
        """Test optimization is properly initialized when enabled."""
        assert processor.optimizer is not None
        assert processor.optimizer.base_batch_size == processor.config.batch_size
        assert processor.optimizer.target_cpu_usage == processor.config.target_cpu_usage

    def test_optimization_disabled(self):
        """Test optimization is disabled when configured."""
        config = ProcessorConfig(enable_dynamic_optimization=False)
        processor = FeedProcessor(
            inoreader_token="test_token",
            webhook_url="http://test.com/webhook",
            config=config
        )
        assert processor.optimizer is None

    @patch('feed_processor.core.optimization.PerformanceOptimizer.get_system_metrics')
    def test_processing_parameter_adjustment(
        self,
        mock_get_metrics,
        processor,
        system_metrics
    ):
        """Test processing parameters are adjusted based on metrics."""
        # Mock system metrics
        mock_get_metrics.return_value = system_metrics

        # Set initial metrics
        processor.processing_metrics.items_processed = 1000
        processor.processing_metrics.items_failed = 50
        processor.processing_metrics.processing_time = 10.0

        # Test parameter adjustment
        processor._adjust_processing_parameters()

        # Verify metrics were updated
        assert processor.batch_size_gauge._value is not None
        assert processor.thread_count_gauge._value is not None

    def test_metrics_collection(self, processor):
        """Test optimization metrics are properly collected."""
        # Process some test data
        processor.process_batch()

        # Verify metrics are collected
        metrics = processor.get_metrics()
        assert 'items_processed' in metrics
        assert 'processing_time' in metrics
        assert 'avg_batch_size' in metrics
