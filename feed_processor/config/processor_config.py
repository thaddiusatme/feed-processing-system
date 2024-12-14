"""Configuration settings for feed processor functionality."""

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class ProcessorConfig:
    """Configuration for the feed processor.

    Attributes:
        batch_size: Base number of items to process in each batch
        min_batch_size: Minimum allowed batch size
        max_batch_size: Maximum allowed batch size
        max_retries: Maximum number of retry attempts for failed operations
        processing_timeout: Maximum time in seconds for processing a batch
        concurrent_processors: Base number of concurrent processing threads
        min_processors: Minimum number of processing threads
        max_processors: Maximum number of processing threads
        poll_interval: Time in seconds between feed polling
        metrics_port: Port for Prometheus metrics server
        test_mode: If True, won't start continuous processing
        target_cpu_usage: Target CPU usage percentage
        enable_dynamic_optimization: Enable dynamic performance optimization
    """

    batch_size: int = 100
    min_batch_size: int = 10
    max_batch_size: int = 500
    max_retries: int = 3
    processing_timeout: int = 300
    concurrent_processors: int = 4
    min_processors: int = 2
    max_processors: int = 16
    poll_interval: int = 60
    metrics_port: int = 8000
    test_mode: bool = False
    target_cpu_usage: float = 70.0
    enable_dynamic_optimization: bool = True

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "ProcessorConfig":
        """Create a ProcessorConfig instance from a dictionary.

        Args:
            config_dict: Dictionary containing configuration values

        Returns:
            ProcessorConfig instance with values from dictionary
        """
        return cls(**{k: v for k, v in config_dict.items() if k in cls.__dataclass_fields__})
