"""Tests for container configuration and deployment."""
import os
import pytest
import docker
from pathlib import Path


@pytest.fixture
def docker_client():
    """Create a Docker client for testing."""
    return docker.from_env()


@pytest.fixture
def dockerfile_path():
    """Get the path to the Dockerfile."""
    return Path(__file__).parent.parent.parent / "Dockerfile"


def test_dockerfile_exists(dockerfile_path):
    """Test that Dockerfile exists."""
    assert dockerfile_path.exists(), "Dockerfile not found"


def test_dockerfile_content(dockerfile_path):
    """Test Dockerfile content and structure."""
    content = dockerfile_path.read_text()
    
    # Check for multi-stage build
    assert "FROM" in content and content.count("FROM") >= 2, "Multi-stage build not found"
    
    # Check for non-root user
    assert "USER" in content, "Non-root user not configured"
    
    # Check for health check
    assert "HEALTHCHECK" in content, "Health check not configured"
    
    # Check for exposed ports
    assert "EXPOSE" in content, "Ports not exposed"


def test_build_image(docker_client, dockerfile_path):
    """Test building the container image."""
    try:
        image, logs = docker_client.images.build(
            path=str(dockerfile_path.parent),
            dockerfile=str(dockerfile_path),
            rm=True
        )
        assert image is not None, "Failed to build image"
    except docker.errors.BuildError as e:
        pytest.fail(f"Failed to build image: {str(e)}")


def test_container_startup(docker_client, dockerfile_path):
    """Test container startup and basic functionality."""
    image_name = "feed-processor:test"
    
    # Build image
    image, _ = docker_client.images.build(
        path=str(dockerfile_path.parent),
        dockerfile=str(dockerfile_path),
        tag=image_name,
        rm=True
    )
    
    # Run container
    container = docker_client.containers.run(
        image_name,
        detach=True,
        environment={
            "FEED_PROCESSOR_DB_URL": "sqlite:///:memory:",
            "METRICS_PORT": "8080"
        },
        ports={'8080/tcp': None}
    )
    
    try:
        # Wait for container to be ready
        container.reload()
        assert container.status == "running", "Container failed to start"
        
        # Check logs for startup messages
        logs = container.logs().decode('utf-8')
        assert "Starting Feed Processor" in logs, "Startup message not found in logs"
        
    finally:
        # Cleanup
        container.stop()
        container.remove()
        docker_client.images.remove(image_name)
