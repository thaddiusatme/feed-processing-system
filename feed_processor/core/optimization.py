"""Optimization utilities for feed processor performance."""

import multiprocessing
import os
import psutil
from dataclasses import dataclass
from typing import List, Optional
import numpy as np

@dataclass
class SystemMetrics:
    """System performance metrics."""
    cpu_usage: float
    memory_usage: float
    load_average: float
    io_wait: float

@dataclass
class ProcessingMetrics:
    """Processing performance metrics."""
    avg_processing_time: float
    error_rate: float
    queue_size: int
    throughput: float

class PerformanceOptimizer:
    """Handles dynamic optimization of processing parameters."""
    
    def __init__(
        self,
        base_batch_size: int = 100,
        min_batch_size: int = 10,
        max_batch_size: int = 500,
        target_cpu_usage: float = 70.0,
        history_window: int = 10
    ):
        """Initialize the performance optimizer.
        
        Args:
            base_batch_size: Starting batch size
            min_batch_size: Minimum allowed batch size
            max_batch_size: Maximum allowed batch size
            target_cpu_usage: Target CPU usage percentage
            history_window: Number of metrics to keep for trending
        """
        self.base_batch_size = base_batch_size
        self.min_batch_size = min_batch_size
        self.max_batch_size = max_batch_size
        self.target_cpu_usage = target_cpu_usage
        self.history_window = history_window
        self.processing_history: List[ProcessingMetrics] = []
        
    def get_system_metrics(self) -> SystemMetrics:
        """Get current system performance metrics."""
        cpu_usage = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        load_avg = os.getloadavg()[0]
        io_wait = psutil.cpu_times_percent().iowait
        
        return SystemMetrics(
            cpu_usage=cpu_usage,
            memory_usage=memory.percent,
            load_average=load_avg,
            io_wait=io_wait
        )
    
    def calculate_optimal_batch_size(
        self,
        system_metrics: SystemMetrics,
        processing_metrics: ProcessingMetrics
    ) -> int:
        """Calculate optimal batch size based on system and processing metrics.
        
        Args:
            system_metrics: Current system metrics
            processing_metrics: Current processing metrics
            
        Returns:
            Optimal batch size
        """
        # Store metrics history
        self.processing_history.append(processing_metrics)
        if len(self.processing_history) > self.history_window:
            self.processing_history.pop(0)
            
        # Calculate adjustment factors
        cpu_factor = 1.0 + (self.target_cpu_usage - system_metrics.cpu_usage) / 100
        error_factor = max(0.5, 1.0 - processing_metrics.error_rate)
        
        # Calculate throughput trend
        if len(self.processing_history) >= 2:
            throughput_trend = (
                self.processing_history[-1].throughput /
                max(self.processing_history[0].throughput, 0.1)
            )
        else:
            throughput_trend = 1.0
            
        # Calculate new batch size
        current_batch_size = processing_metrics.queue_size
        optimal_size = int(
            current_batch_size *
            cpu_factor *
            error_factor *
            throughput_trend
        )
        
        # Ensure within bounds
        return max(
            self.min_batch_size,
            min(optimal_size, self.max_batch_size)
        )
    
    def get_optimal_thread_count(self, system_metrics: SystemMetrics) -> int:
        """Calculate optimal number of processing threads.
        
        Args:
            system_metrics: Current system metrics
            
        Returns:
            Optimal thread count
        """
        cpu_count = multiprocessing.cpu_count()
        
        # Base thread count on CPU cores and load
        if system_metrics.cpu_usage > 90:
            thread_factor = 0.5
        elif system_metrics.cpu_usage > 70:
            thread_factor = 0.75
        else:
            thread_factor = 1.0
            
        # Adjust for I/O wait
        if system_metrics.io_wait > 20:
            thread_factor *= 1.5  # More threads can help with I/O-bound operations
            
        optimal_threads = max(1, int(cpu_count * thread_factor))
        return min(optimal_threads, cpu_count * 2)  # Cap at 2x CPU count
