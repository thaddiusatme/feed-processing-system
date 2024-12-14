# Lessons Learned - Feed Processing System

## Architecture and Design

### Queue Management
- The system uses multiple queue implementations (`PriorityQueue` and `ContentQueue`) for different purposes
- **Important**: `ContentQueue` inherits from `PriorityQueue` but adds content-specific features like deduplication
- **Gotcha**: When adding new queue types, ensure they handle the `max_size` parameter correctly to prevent memory issues

### Error Handling
- The system uses a hierarchical error system with `FeedProcessingError` as the base
- **Critical**: Always use appropriate error categories for proper monitoring and alerting
- **Tip**: Use `RetryableError` for transient failures that can be automatically retried
- Circuit breaker patterns are implemented to prevent cascading failures
- **Best Practice**: Implement exponential backoff for retries to prevent overwhelming services
- **Important**: Track error history to identify patterns and adjust retry strategies

### Metrics and Monitoring
- Two separate metrics systems exist:
  1. Prometheus metrics for operational monitoring
  2. Processing metrics for internal performance tracking
- **Warning**: Avoid mixing these systems; they serve different purposes
- **Best Practice**: Always update both metric systems when adding new features
- **Critical**: Initialize metrics at startup to avoid null/missing values
- **Tip**: Use type-safe metric implementations to catch errors early

## Development Workflow

### Code Organization
- The project follows a modular structure with clear separation of concerns
- **Important**: Keep the directory structure clean:
  ```
  feed_processor/
  ├── config/      # All configuration classes
  ├── core/        # Core processing logic
  ├── queues/      # Queue implementations
  ├── metrics/     # Metrics handling
  ├── validation/  # Feed validation
  └── webhook/     # Webhook handling
  ```
- **Gotcha**: Avoid circular dependencies between modules
- **Best Practice**: Use dataclasses for structured data like responses and configurations

### Testing
- Test files mirror the source code structure
- **Critical**: Always include both unit and integration tests for new features
- **Best Practice**: Use the provided test fixtures for consistent testing
- **Warning**: Mock external services in tests to prevent unwanted API calls
- **Important**: Test concurrent operations thoroughly with proper thread safety
- **Tip**: Use parametrized tests for time-based logic to cover different scenarios

### Performance Considerations
1. Queue Operations
   - Queue operations are thread-safe but can be a bottleneck
   - **Tip**: Use batch operations where possible
   - **Warning**: Monitor queue sizes in production

2. Webhook Delivery
   - Implements retry logic with exponential backoff
   - **Important**: Respect rate limits of external services
   - **Best Practice**: Use the webhook batch sending feature for better throughput
   - **Critical**: Implement proper error handling for concurrent webhook deliveries
   - **Warning**: Always validate payloads before sending to prevent unnecessary retries

3. Memory Management
   - Queues have configurable size limits
   - **Critical**: Always set appropriate `max_size` values
   - **Warning**: Monitor memory usage when processing large feeds

## Common Pitfalls

### Feed Processing
1. Content Types
   - The system supports multiple content types (BLOG, VIDEO, SOCIAL)
   - **Gotcha**: Always validate content type before processing
   - **Tip**: Use the `content_analysis` module for type detection

2. Validation
   - Feed validation is strict by default
   - **Important**: Don't bypass validation checks
   - **Best Practice**: Add new validation rules to the existing validator
   - **Warning**: Validate all required fields before processing to fail fast

3. Rate Limiting
   - Built-in rate limiting for external services
   - **Warning**: Don't remove rate limiting without understanding dependencies
   - **Tip**: Configure rate limits based on external service documentation
   - **Best Practice**: Use time-based retry strategies (e.g., fewer retries during peak hours)

### Configuration
1. Environment Variables
   - Use `.env` for local development
   - **Critical**: Never commit sensitive values
   - **Best Practice**: Use `env.example` as a template

2. Webhook Configuration
   - Webhook settings are validated at startup
   - **Important**: Always include timeout settings
   - **Gotcha**: Auth tokens must be properly formatted
   - **Critical**: Use proper error categories for different webhook failures
   - **Tip**: Implement circuit breakers for webhook endpoints

## Maintenance and Debugging

### Logging
- Structured logging is used throughout
- **Best Practice**: Use appropriate log levels:
  - ERROR: For failures requiring immediate attention
  - WARNING: For unusual but handled situations
  - INFO: For normal operation events
  - DEBUG: For detailed troubleshooting
- **Important**: Include relevant context in log messages (payload, error details, attempt number)
- **Tip**: Use structured logging for better searchability and analysis

### Monitoring
1. Key Metrics to Watch
   - Webhook success/failure rates
   - Retry counts and patterns
   - Response times and latency
   - Rate limit hits and backoff times
   - Concurrent operation performance
   - Memory usage during batch operations

### Troubleshooting
1. Common Issues
   - Queue overflow: Check input rate and processing speed
   - High error rates: Check external service availability
   - Slow processing: Monitor system resources

2. Debug Tools
   - Use the CLI debug commands
   - Check prometheus metrics
   - Review application logs

### Technical Debt

#### Current Issues
1. Datetime Handling
   - **Critical**: Replace deprecated `datetime.now()` with timezone-aware alternatives
   - **Best Practice**: Use `datetime.now(timezone.utc)` consistently
   - **Warning**: Audit all datetime usage for timezone consistency

2. Metrics System
   - **Critical**: Complete Prometheus metrics server implementation
   - **Important**: Replace naive metrics implementation with proper Prometheus client
   - **Warning**: Ensure consistent metrics initialization across components
   - **Best Practice**: Add metric type validation and documentation

3. Code Duplication
   - **Important**: Consolidate duplicate validation methods
   - **Warning**: Standardize error handling patterns
   - **Best Practice**: Create shared validation utilities

4. Testing Infrastructure
   - **Critical**: Add tests for concurrent edge cases
   - **Important**: Make time-based tests deterministic
   - **Warning**: Improve metrics collection test coverage
   - **Best Practice**: Use test fixtures for common scenarios

5. Documentation
   - **Important**: Document retry strategies and backoff patterns
   - **Warning**: Keep API documentation up-to-date
   - **Best Practice**: Add examples for common usage patterns

#### Mitigation Strategy
1. Short-term
   - Fix datetime deprecation warnings
   - Consolidate validation methods
   - Add missing test cases

2. Medium-term
   - Implement proper Prometheus integration
   - Standardize error handling
   - Improve test infrastructure

3. Long-term
   - Complete metrics server implementation
   - Add comprehensive monitoring
   - Document all subsystems

## Future Considerations

### Scalability
- The system is designed for horizontal scaling
- **Important**: Consider queue persistence for high availability
- **Tip**: Monitor performance metrics when scaling

### Feature Additions
- Follow the established module structure
- **Best Practice**: Update documentation and tests
- **Important**: Consider backward compatibility

### Documentation
- Keep README.md updated with new features
- Update changelog.md for all changes
- **Best Practice**: Document breaking changes prominently
- **Tip**: Keep this document updated with new lessons learned

### TDD Implementation - Webhook Validation (2024-12-13)
1. Test-First Development
   - **Success**: Writing tests first helped clarify the validation requirements
   - **Benefit**: Clear error messages were defined before implementation
   - **Learning**: Test cases drove the design of the validation method

2. Error Handling Patterns
   - **Pattern**: Using ValueError with specific error messages improves debugging
   - **Best Practice**: Including missing field names in error messages helps troubleshooting
   - **Tip**: Structured logging of validation failures aids in monitoring

3. Environment Setup
   - **Important**: Virtual environment setup is crucial for consistent testing
   - **Note**: Keep requirements.txt updated with new dependencies
   - **Reminder**: Use absolute paths when running commands in virtual environments
