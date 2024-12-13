"""Configuration settings for feed processor functionality."""

from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class ProcessorConfig:
    """Configuration for the feed processor.

    Attributes:
        batch_size: Number of items to process in each batch
        max_retries: Maximum number of retry attempts for failed operations
        processing_timeout: Maximum time in seconds for processing a batch
        concurrent_processors: Number of concurrent processing threads
        poll_interval: Time in seconds between feed polling
        metrics_port: Port for Prometheus metrics server
        test_mode: If True, won't start continuous processing
    """

    batch_size: int = 100
    max_retries: int = 3
    processing_timeout: int = 300
    concurrent_processors: int = 4
    poll_interval: int = 60
    metrics_port: int = 8000
    test_mode: bool = False

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "ProcessorConfig":
        """Create a ProcessorConfig instance from a dictionary.

        Args:
            config_dict: Dictionary containing configuration values

        Returns:
            ProcessorConfig instance with values from dictionary
        """
        return cls(**{
            k: v for k, v in config_dict.items()
            if k in cls.__dataclass_fields__
        })
