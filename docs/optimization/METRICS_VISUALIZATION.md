# Feed Processor Metrics Visualization Guide

This guide shows how to interpret the various metrics visualizations available in the monitoring dashboard.

## Batch Size Optimization

```
Processing Batch Size Over Time
│
400 ┤                                 ╭─────
350 ┤                         ╭───────╯
300 ┤                 ╭───────╯
250 ┤         ╭───────╯
200 ┤ ╭───────╯
150 ┤─╯
    └─────────────────────────────────────────
    0min     10min     20min     30min     40min
```

This graph shows how batch size adapts to increasing load:
- Starts at default (150)
- Gradually increases as system proves stable
- Levels off at optimal size (400)

## Thread Count Adaptation

```
Active Processing Threads
│
8  ┤     ╭─╮       ╭─╮
6  ┤ ╭───╯ ╰───────╯ ╰────
4  ┤─╯
2  ┤
   └────────────────────────
   0min    10min    20min    30min
```

Shows thread count responding to load:
- Base level of 4 threads
- Spikes to 8 during high load
- Returns to baseline during normal operation

## CPU Usage vs Batch Size

```
     CPU Usage (%)    Batch Size
100% ┤      ╭╮         ╭─────    400
 80% ┤    ╭─╯╰─╮    ╭──╯        350
 60% ┤╭───╯    ╰────╯           300
 40% ┤╯                         250
     └───────────────────────
     0min    10min    20min
```

Demonstrates relationship between:
- CPU utilization (solid line)
- Batch size adjustments (dashed line)
- How they influence each other

## Error Rate Impact

```
Error Rate vs Processing Speed
│
5% ┤    ╭╮                  Errors
   ┤    ││
0% ┤────╯╰──────────────────
   │
400┤──────╯╰────────────    Speed
300┤────────────────────
   └─────────────────────────
   0min    10min    20min
```

Shows how error rates affect processing:
- Error spike causes speed reduction
- System recovers after error resolution
- Processing speed gradually increases

## Memory Usage Pattern

```
Memory Usage (MB)
│
800┤      ╭╮    ╭╮    ╭╮
600┤╭─────╯╰────╯╰────╯╰────
400┤╯
   └──────────────────────────
   0min    10min    20min    30min
```

Illustrates memory usage pattern:
- Baseline usage around 600MB
- Regular GC cycles
- Stable overall pattern

## Processing Throughput

```
Items Processed per Second
│
100┤         ╭────────────
 75┤    ╭────╯
 50┤────╯
 25┤
   └─────────────────────────
   0min    10min    20min
```

Shows processing rate improvements:
- Initial conservative rate
- Optimization increases throughput
- Stable high performance

## Dashboard Integration

These visualizations are available in the Grafana dashboard:

1. **Overview Panel**
   ```
   ┌──────────────┐ ┌──────────────┐
   │ Batch Size   │ │ Thread Count │
   └──────────────┘ └──────────────┘
   ┌──────────────┐ ┌──────────────┐
   │ CPU Usage    │ │ Memory Usage │
   └──────────────┘ └──────────────┘
   ```

2. **Performance Panel**
   ```
   ┌──────────────────────────────┐
   │ Processing Rate Over Time    │
   └──────────────────────────────┘
   ┌──────────────────────────────┐
   │ Error Rate and Recovery      │
   └──────────────────────────────┘
   ```

## Interpreting Patterns

### Normal Operation
```
Batch Size   ─────────────
Threads      ─────────────
CPU Usage    ─────────────
```

### High Load Response
```
Batch Size   ────╲
Threads      ────╱
CPU Usage    ─────────────
```

### Error Recovery
```
Batch Size   ────╱
Threads      ────╲
Error Rate   ──╭╮─────────
```

These visualizations help in:
1. Understanding system behavior
2. Identifying optimization patterns
3. Troubleshooting issues
4. Validating configuration changes

For live monitoring, refer to your Grafana dashboard at:
`http://your-server:3000/d/feed-processor-optimization`
