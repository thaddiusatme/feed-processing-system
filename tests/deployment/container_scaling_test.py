"""Tests for container scaling and resource management."""
import pytest
import docker
import time
import psutil
from pathlib import Path


@pytest.fixture
def docker_client():
    """Create a Docker client for testing."""
    return docker.from_env()


@pytest.fixture
def container_config():
    """Container configuration for testing."""
    return {
        "image": "feed-processor:test",
        "environment": {
            "FEED_PROCESSOR_DB_URL": "sqlite:///:memory:",
            "METRICS_PORT": "8080",
            "MAX_QUEUE_SIZE": "1000",
            "SCALE_CPU_THRESHOLD": "70",
            "SCALE_MEMORY_THRESHOLD": "80"
        },
        "mem_limit": "512m",
        "cpu_count": 1
    }


def test_resource_limits(docker_client, container_config):
    """Test container resource limits."""
    container = docker_client.containers.run(
        **container_config,
        detach=True
    )
    
    try:
        container.reload()
        assert container.status == "running"
        
        # Check memory limit
        stats = container.stats(stream=False)
        mem_limit = stats["memory_stats"]["limit"]
        assert mem_limit <= 512 * 1024 * 1024, "Memory limit not enforced"
        
        # Check CPU limit
        cpu_count = len(stats["cpu_stats"]["cpu_usage"]["percpu_usage"])
        assert cpu_count == 1, "CPU limit not enforced"
        
    finally:
        container.stop()
        container.remove()


def test_scaling_triggers(docker_client, container_config):
    """Test scaling triggers based on resource usage."""
    container = docker_client.containers.run(
        **container_config,
        detach=True
    )
    
    try:
        container.reload()
        
        # Generate load
        container.exec_run(
            "python3 -c 'import time; [x*x for x in range(1000000)]'"
        )
        
        # Check metrics
        time.sleep(5)
        stats = container.stats(stream=False)
        
        cpu_percent = calculate_cpu_percent(stats)
        mem_percent = calculate_memory_percent(stats)
        
        assert cpu_percent <= float(container_config["environment"]["SCALE_CPU_THRESHOLD"]), \
            "CPU usage exceeds threshold"
        assert mem_percent <= float(container_config["environment"]["SCALE_MEMORY_THRESHOLD"]), \
            "Memory usage exceeds threshold"
        
    finally:
        container.stop()
        container.remove()


def calculate_cpu_percent(stats):
    """Calculate CPU usage percentage."""
    cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - \
                stats["precpu_stats"]["cpu_usage"]["total_usage"]
    system_delta = stats["cpu_stats"]["system_cpu_usage"] - \
                   stats["precpu_stats"]["system_cpu_usage"]
    
    if system_delta > 0:
        return (cpu_delta / system_delta) * 100.0
    return 0.0


def calculate_memory_percent(stats):
    """Calculate memory usage percentage."""
    usage = stats["memory_stats"]["usage"]
    limit = stats["memory_stats"]["limit"]
    
    if limit > 0:
        return (usage / limit) * 100.0
    return 0.0
