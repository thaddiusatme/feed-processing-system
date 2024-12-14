# Feed Processor Optimization System Diagrams

This document provides visual representations of the optimization system's architecture and workflows.

## System Architecture

```mermaid
graph TB
    subgraph Feed Processor
        FP[Feed Processor] --> PO[Performance Optimizer]
        PO --> SM[System Metrics]
        PO --> PM[Processing Metrics]

        subgraph Optimization Components
            SM --> BS[Batch Sizing]
            SM --> TC[Thread Control]
            PM --> BS
            PM --> TC
        end

        BS --> Q[Content Queue]
        TC --> T[Thread Pool]
    end

    subgraph External Systems
        IR[Inoreader API] --> FP
        FP --> WH[Webhook]
        M[Metrics System] --- PO
    end

    style FP fill:#f9f,stroke:#333
    style PO fill:#bbf,stroke:#333
    style Q fill:#bfb,stroke:#333
    style T fill:#bfb,stroke:#333
```

## Optimization Workflow

```mermaid
sequenceDiagram
    participant FP as Feed Processor
    participant PO as Performance Optimizer
    participant SM as System Monitor
    participant Q as Content Queue
    participant T as Thread Pool

    FP->>PO: Request optimization
    PO->>SM: Get system metrics
    SM-->>PO: Return metrics

    alt High CPU Load
        PO->>Q: Decrease batch size
        PO->>T: Reduce thread count
    else Low CPU Load
        PO->>Q: Increase batch size
        PO->>T: Increase thread count
    end

    PO-->>FP: Apply optimized settings
```

## Resource Usage Patterns

```mermaid
graph LR
    subgraph CPU Usage Patterns
        C1[Low CPU] -->|Increase| C2[Target CPU]
        C2 -->|Decrease| C3[High CPU]
    end

    subgraph Memory Usage
        M1[Available] -->|Consume| M2[In Use]
        M2 -->|Release| M1
    end

    subgraph Thread States
        T1[Idle] -->|Assign Work| T2[Active]
        T2 -->|Complete| T1
        T2 -->|Block on I/O| T3[Waiting]
        T3 -->|I/O Complete| T2
    end
```

## Batch Size Optimization

```mermaid
graph TD
    subgraph Inputs
        CPU[CPU Usage]
        MEM[Memory Usage]
        IO[I/O Wait]
        ER[Error Rate]
    end

    subgraph Calculation
        CPU --> CF[CPU Factor]
        MEM --> MF[Memory Factor]
        IO --> IF[I/O Factor]
        ER --> EF[Error Factor]

        CF --> OBS[Optimal Batch Size]
        MF --> OBS
        IF --> OBS
        EF --> OBS
    end

    subgraph Bounds
        OBS --> |Max| MAX[Maximum Size]
        OBS --> |Min| MIN[Minimum Size]
    end
```

## Thread Pool Management

```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> Active: New Work
    Active --> Idle: Work Complete
    Active --> Waiting: I/O Block
    Waiting --> Active: I/O Complete

    state Active {
        [*] --> Processing
        Processing --> Optimizing: Check Load
        Optimizing --> Processing: Apply Changes
    }
```

## Performance Metrics Flow

```mermaid
graph LR
    subgraph Metrics Collection
        PM[Processing Metrics] --> AG[Aggregation]
        SM[System Metrics] --> AG
        QM[Queue Metrics] --> AG
    end

    subgraph Analysis
        AG --> CALC[Calculations]
        CALC --> TREND[Trend Analysis]
    end

    subgraph Actions
        TREND --> ADJ[Adjustments]
        ADJ --> BS[Batch Size]
        ADJ --> TC[Thread Count]
        ADJ --> INT[Intervals]
    end

    subgraph Monitoring
        BS --> DASH[Dashboard]
        TC --> DASH
        INT --> DASH
    end
```

## Resource Utilization Zones

```mermaid
graph TD
    subgraph Optimization Zones
        Z1[Green Zone] -->|Increasing Load| Z2[Yellow Zone]
        Z2 -->|High Load| Z3[Red Zone]
        Z3 -->|Recovery| Z2
        Z2 -->|Load Reduction| Z1
    end

    subgraph Actions
        Z1 -->|"CPU < 50%"| A1[Increase Resources]
        Z2 -->|"CPU 50-80%"| A2[Maintain Balance]
        Z3 -->|"CPU > 80%"| A3[Reduce Load]
    end
```

## Error Handling and Recovery

```mermaid
graph TB
    subgraph Error Detection
        E1[Processing Error] --> EH[Error Handler]
        E2[System Error] --> EH
        E3[External Error] --> EH
    end

    subgraph Recovery Actions
        EH --> R1[Retry Logic]
        EH --> R2[Load Reduction]
        EH --> R3[Circuit Breaking]
    end

    subgraph Optimization Impact
        R1 --> OPT[Optimizer]
        R2 --> OPT
        R3 --> OPT
        OPT --> ADJ[Adjust Parameters]
    end
```

These diagrams provide visual representations of:
1. Overall system architecture
2. Optimization workflow
3. Resource usage patterns
4. Batch size optimization process
5. Thread pool management
6. Performance metrics flow
7. Resource utilization zones
8. Error handling and recovery

Each diagram helps explain different aspects of the optimization system, making it easier to understand how the components work together and how the system responds to different conditions.
