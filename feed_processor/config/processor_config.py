"""Configuration settings for feed processor functionality."""

class ProcessorConfig:
    def __init__(self):
        self.batch_size = 100
        self.max_retries = 3
        self.processing_timeout = 300
        self.concurrent_processors = 4
        
    @classmethod
    def from_dict(cls, config_dict):
        instance = cls()
        for key, value in config_dict.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        return instance
