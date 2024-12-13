"""Configuration settings for webhook functionality."""

class WebhookConfig:
    def __init__(self):
        self.retry_attempts = 3
        self.timeout = 30
        self.max_concurrent = 10
        
    @classmethod
    def from_dict(cls, config_dict):
        instance = cls()
        for key, value in config_dict.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        return instance
