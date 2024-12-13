# Error Handling System Testing Guide

## Overview
This guide covers the testing infrastructure for the error handling system, including performance testing, edge cases, and common debugging procedures.

## Test Categories

### 1. Unit Tests
- Located in `tests/unit/`
- Cover individual components (ErrorHandler, CircuitBreaker, etc.)
- Run with: `pytest tests/unit/`

### 2. Integration Tests
- Located in `tests/integration/`
- Test component interactions and real API behavior
- Run with: `pytest tests/integration/`

### 3. Performance Tests
- Located in `tests/performance/`
- Measure latency, throughput, and resource usage
- Run with: `pytest tests/performance/`

## Setting Up Test Environment

### Prerequisites
```bash
# Install test dependencies
pip install pytest pytest-cov pytest-benchmark

# Set up environment variables
export INOREADER_TOKEN="your_token_here"
export AIRTABLE_API_KEY="your_key_here"
```

### Running Tests
```bash
# Run all tests
pytest

# Run specific test category
pytest tests/performance/

# Run with coverage
pytest --cov=feed_processor
```

## Common Failure Scenarios

### 1. Network Partition
```python
# Simulated in test_error_handling_edge_cases.py
# Key indicators:
- Multiple connection timeouts
- Circuit breaker opening for network-dependent services
- Rapid failure of external API calls

# Recovery steps:
1. Check network connectivity
2. Verify external service health
3. Monitor circuit breaker state transitions
```

### 2. Database Connection Failures
```python
# Simulated in test_error_handling_edge_cases.py
# Key indicators:
- Connection pool exhaustion
- Timeout errors
- Connection refused errors

# Recovery steps:
1. Check database connectivity
2. Verify connection pool settings
3. Monitor connection retry patterns
```

### 3. System Overload
```python
# Simulated in test_error_handling_stress.py
# Key indicators:
- Increased latency
- Memory usage spikes
- Error rate increases

# Recovery steps:
1. Check system resources
2. Monitor error distribution
3. Verify circuit breaker thresholds
```

## Performance Tuning

### 1. Circuit Breaker Configuration
```python
# Optimal settings for different scenarios:

# High-volume API
CIRCUIT_BREAKER_FAILURE_THRESHOLD=10
CIRCUIT_BREAKER_RESET_TIMEOUT=30

# Database Operations
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_RESET_TIMEOUT=15

# Webhook Delivery
CIRCUIT_BREAKER_FAILURE_THRESHOLD=3
CIRCUIT_BREAKER_RESET_TIMEOUT=45
```

### 2. Retry Strategy Optimization
```python
# Recommended retry intervals:

# Rate-limited API calls
- Initial delay: 1s
- Max delay: 30s
- Backoff factor: 2

# Database operations
- Initial delay: 0.1s
- Max delay: 5s
- Backoff factor: 1.5

# Network operations
- Initial delay: 0.5s
- Max delay: 15s
- Backoff factor: 2
```

### 3. Memory Management
```python
# Recommended settings:

ERROR_HISTORY_SIZE=1000  # Balance between memory usage and debugging needs
MAX_CONCURRENT_RETRIES=50  # Prevent resource exhaustion
LOGGING_BATCH_SIZE=100  # Optimize logging performance
```

## Debugging Procedures

### 1. Error Pattern Analysis
```python
# Get error distribution
metrics = error_handler.get_error_metrics()
print(metrics["errors_by_category"])
print(metrics["errors_by_severity"])

# Analyze circuit breaker states
for service, cb in error_handler.circuit_breakers.items():
    print(f"{service}: {cb.state}")
```

### 2. Performance Investigation
```python
# Monitor latency
pytest tests/performance/test_error_handling_performance.py::test_error_handling_latency

# Check memory usage
pytest tests/performance/test_error_handling_performance.py::test_memory_usage_under_load

# Analyze retry patterns
pytest tests/performance/test_error_handling_performance.py::test_retry_strategy_performance
```

### 3. System Health Checks
```python
# Verify component health
pytest tests/integration/test_error_handling_edge_cases.py::test_partial_system_failure

# Test recovery mechanisms
pytest tests/integration/test_error_handling_edge_cases.py::test_catastrophic_failure_recovery
```

## Best Practices

1. **Regular Testing**
   - Run performance tests weekly
   - Monitor error patterns daily
   - Review circuit breaker configurations monthly

2. **Error Handling**
   - Use appropriate error categories
   - Set meaningful severity levels
   - Maintain detailed error context

3. **Performance Monitoring**
   - Track error handling latency
   - Monitor memory usage
   - Analyze retry patterns

4. **Documentation**
   - Keep test cases updated
   - Document new error scenarios
   - Maintain debugging procedures
