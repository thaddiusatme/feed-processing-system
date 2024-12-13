"""Recovery test scenarios for the feed processing system."""

import subprocess
import time
from typing import Any, Callable, Dict

import docker
import psutil


class RecoveryTest:
    def __init__(self):
        self.docker_client = docker.from_env()

    def network_partition(self, duration: int) -> None:
        """Simulate network partition by temporarily blocking network access."""
        try:
            # Create network isolation
            subprocess.run(
                ["sudo", "tc", "qdisc", "add", "dev", "lo", "root", "netem", "loss", "100%"]
            )
            print("Network partition created")

            time.sleep(duration)

            # Remove network isolation
            subprocess.run(["sudo", "tc", "qdisc", "del", "dev", "lo", "root"])
            print("Network partition removed")

        except subprocess.CalledProcessError as e:
            print(f"Failed to simulate network partition: {e}")

    def webhook_failure(self, duration: int) -> None:
        """Simulate webhook endpoint failures."""
        try:
            # Stop the mock webhook service
            containers = self.docker_client.containers.list(filters={"name": "mock-webhook"})
            if containers:
                containers[0].stop()
                print("Webhook service stopped")

            time.sleep(duration)

            # Restart the mock webhook service
            if containers:
                containers[0].start()
                print("Webhook service restarted")

        except docker.errors.DockerException as e:
            print(f"Failed to simulate webhook failure: {e}")

    def memory_pressure(self, target_percentage: int, duration: int) -> None:
        """Simulate memory pressure by allocating memory."""
        try:
            # Calculate target memory usage
            total_memory = psutil.virtual_memory().total
            target_bytes = (total_memory * target_percentage) // 100

            # Allocate memory
            memory_hog = b"x" * target_bytes
            print(f"Allocated {target_bytes / (1024*1024):.2f} MB of memory")

            time.sleep(duration)

            # Release memory
            del memory_hog
            print("Memory released")

        except Exception as e:
            print(f"Failed to simulate memory pressure: {e}")


def run_recovery_test(
    test_type: str,
    duration: int,
    config: Dict[str, Any],
    callback: Callable[[str, Dict[str, Any]], None],
) -> None:
    """
    Run a specific recovery test scenario.

    Args:
        test_type: Type of recovery test to run
        duration: Duration of the test in seconds
        config: Test configuration parameters
        callback: Function to call with test results
    """
    recovery_test = RecoveryTest()

    test_scenarios = {
        "network_partition": recovery_test.network_partition,
        "webhook_failure": recovery_test.webhook_failure,
        "memory_pressure": recovery_test.memory_pressure,
    }

    if test_type not in test_scenarios:
        raise ValueError(f"Unknown test type: {test_type}")

    print(f"Starting {test_type} recovery test")
    start_time = time.time()

    try:
        # Run the recovery test
        test_scenarios[test_type](duration)

        # Calculate recovery metrics
        recovery_time = time.time() - start_time
        results = {
            "test_type": test_type,
            "duration": duration,
            "recovery_time": recovery_time,
            "success": True,
        }

    except Exception as e:
        results = {"test_type": test_type, "duration": duration, "error": str(e), "success": False}

    callback(test_type, results)


if __name__ == "__main__":
    # Example usage
    def print_results(test_type: str, results: Dict[str, Any]) -> None:
        print(f"\nResults for {test_type}:")
        for key, value in results.items():
            print(f"{key}: {value}")

    # Run a network partition test for 60 seconds
    run_recovery_test("network_partition", 60, {"severity": "complete"}, print_results)
