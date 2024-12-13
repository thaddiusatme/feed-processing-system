import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ProcessingMetrics:
    total_processed: int = 0
    successful_processed: int = 0
    failed_processed: int = 0
    processing_times: List[float] = field(default_factory=list)
    error_counts: Dict[str, int] = field(default_factory=dict)
    start_time: Optional[float] = None
    end_time: Optional[float] = None

    def start_processing(self) -> None:
        self.start_time = time.time()

    def end_processing(self) -> None:
        self.end_time = time.time()

    def record_success(self, processing_time: float) -> None:
        self.total_processed += 1
        self.successful_processed += 1
        self.processing_times.append(processing_time)

    def record_failure(self, error_type: str, processing_time: float) -> None:
        self.total_processed += 1
        self.failed_processed += 1
        self.processing_times.append(processing_time)
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1

    def get_average_processing_time(self) -> float:
        if not self.processing_times:
            return 0.0
        return sum(self.processing_times) / len(self.processing_times)

    def get_success_rate(self) -> float:
        if self.total_processed == 0:
            return 0.0
        return self.successful_processed / self.total_processed * 100

    def get_total_processing_time(self) -> float:
        if self.start_time is None or self.end_time is None:
            return 0.0
        return self.end_time - self.start_time

    def get_throughput(self) -> float:
        total_time = self.get_total_processing_time()
        if total_time == 0:
            return 0.0
        return self.total_processed / total_time

    def reset(self) -> None:
        self.total_processed = 0
        self.successful_processed = 0
        self.failed_processed = 0
        self.processing_times.clear()
        self.error_counts.clear()
        self.start_time = None
        self.end_time = None
