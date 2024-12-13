"""Script to execute load tests with different scenarios."""

import argparse
import subprocess
import time
from typing import Any, Dict

import requests


def run_locust(scenario: str, duration: str, host: str) -> None:
    """Run locust with specified parameters."""
    cmd = [
        "locust",
        "-f",
        "locustfile.py",
        "--headless",
        "-u",
        get_scenario_config(scenario)["users"],
        "-r",
        get_scenario_config(scenario)["spawn_rate"],
        "--run-time",
        duration,
        "--host",
        host,
    ]
    subprocess.run(cmd, check=True)


def get_scenario_config(scenario: str) -> Dict[str, Any]:
    """Get configuration for different test scenarios."""
    configs = {
        "baseline": {
            "users": "100",
            "spawn_rate": "10",
            "feeds_per_minute": "100",
            "queue_size": "1000",
            "webhook_rate": "5",
        },
        "normal": {
            "users": "500",
            "spawn_rate": "20",
            "feeds_per_minute": "500",
            "queue_size": "5000",
            "webhook_rate": "20",
        },
        "peak": {
            "users": "2000",
            "spawn_rate": "50",
            "feeds_per_minute": "2000",
            "queue_size": "10000",
            "webhook_rate": "50",
        },
    }
    return configs.get(scenario, configs["baseline"])


def check_metrics_endpoint() -> bool:
    """Verify that metrics endpoint is accessible."""
    try:
        response = requests.get("http://localhost:49152/metrics")
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run load tests for feed processing system")
    parser.add_argument(
        "--scenario",
        choices=["baseline", "normal", "peak", "recovery"],
        default="baseline",
        help="Test scenario to run",
    )
    parser.add_argument(
        "--duration", default="5m", help="Duration of the test (e.g., '1h', '30m', '5m')"
    )
    parser.add_argument(
        "--recovery-type",
        choices=["network_partition", "webhook_failure", "memory_pressure"],
        help="Type of recovery test to run",
    )
    parser.add_argument(
        "--host", default="http://localhost:8000", help="Host URL of the feed processing system"
    )

    args = parser.parse_args()

    # Check if metrics endpoint is accessible
    if not check_metrics_endpoint():
        print("Warning: Metrics endpoint is not accessible. Make sure Prometheus is running.")

    if args.scenario == "recovery":
        if not args.recovery_type:
            parser.error("--recovery-type is required when running recovery tests")
        # TODO: Implement recovery test scenarios
        pass
    else:
        run_locust(args.scenario, args.duration, args.host)


if __name__ == "__main__":
    main()
