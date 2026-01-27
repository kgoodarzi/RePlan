"""
Performance Profiling Utilities for RePlan

Provides timing decorators and profiling tools to measure operation performance.
Target: All user-facing operations should complete in < 1-2 seconds.
"""

import time
import functools
import logging
from typing import Callable, Any, Dict, List, Optional
from dataclasses import dataclass, field
from contextlib import contextmanager
from pathlib import Path
import json

# Set up logging
logger = logging.getLogger("replan.profiling")


@dataclass
class TimingResult:
    """Result of a timed operation."""
    operation: str
    duration_ms: float
    timestamp: float
    success: bool = True
    details: Dict[str, Any] = field(default_factory=dict)


class PerformanceProfiler:
    """
    Centralized performance profiler for RePlan.
    
    Collects timing data and provides reports on operation performance.
    """
    
    # Performance targets (in milliseconds)
    TARGETS = {
        "app_startup": 3000,
        "pdf_load": 2000,
        "flood_fill": 1000,
        "polygon_mask": 500,
        "canvas_render": 100,
        "workspace_save": 1000,
        "workspace_load": 2000,
        "ocr_scan": 5000,
        "nesting_compute": 3000,
    }
    
    _instance: Optional['PerformanceProfiler'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.results: List[TimingResult] = []
        self.enabled = True
        self._start_times: Dict[str, float] = {}
    
    @classmethod
    def get_instance(cls) -> 'PerformanceProfiler':
        """Get the singleton profiler instance."""
        return cls()
    
    def start(self, operation: str):
        """Start timing an operation."""
        if self.enabled:
            self._start_times[operation] = time.perf_counter()
    
    def stop(self, operation: str, success: bool = True, **details) -> Optional[TimingResult]:
        """Stop timing an operation and record the result."""
        if not self.enabled:
            return None
            
        start_time = self._start_times.pop(operation, None)
        if start_time is None:
            logger.warning(f"No start time found for operation: {operation}")
            return None
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        result = TimingResult(
            operation=operation,
            duration_ms=duration_ms,
            timestamp=time.time(),
            success=success,
            details=details
        )
        self.results.append(result)
        
        # Log warning if exceeds target
        target = self.TARGETS.get(operation)
        if target and duration_ms > target:
            logger.warning(
                f"Performance warning: {operation} took {duration_ms:.1f}ms "
                f"(target: {target}ms)"
            )
        else:
            logger.debug(f"{operation}: {duration_ms:.1f}ms")
        
        return result
    
    @contextmanager
    def measure(self, operation: str, **details):
        """Context manager for measuring operation time."""
        self.start(operation)
        success = True
        try:
            yield
        except Exception:
            success = False
            raise
        finally:
            self.stop(operation, success=success, **details)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all timing results."""
        if not self.results:
            return {"message": "No timing data collected"}
        
        # Group by operation
        by_operation: Dict[str, List[float]] = {}
        for result in self.results:
            if result.operation not in by_operation:
                by_operation[result.operation] = []
            by_operation[result.operation].append(result.duration_ms)
        
        summary = {}
        for op, times in by_operation.items():
            target = self.TARGETS.get(op, None)
            avg = sum(times) / len(times)
            summary[op] = {
                "count": len(times),
                "avg_ms": round(avg, 2),
                "min_ms": round(min(times), 2),
                "max_ms": round(max(times), 2),
                "target_ms": target,
                "meets_target": avg <= target if target else None,
            }
        
        return summary
    
    def print_summary(self):
        """Print a formatted summary to console."""
        summary = self.get_summary()
        if "message" in summary:
            print(summary["message"])
            return
        
        print("\n" + "=" * 60)
        print("PERFORMANCE SUMMARY")
        print("=" * 60)
        
        for op, stats in sorted(summary.items()):
            status = ""
            if stats["target_ms"]:
                if stats["meets_target"]:
                    status = " [OK]"
                else:
                    status = " [SLOW]"
            
            print(f"\n{op}:{status}")
            print(f"  Count: {stats['count']}")
            print(f"  Avg: {stats['avg_ms']:.1f}ms")
            print(f"  Min: {stats['min_ms']:.1f}ms / Max: {stats['max_ms']:.1f}ms")
            if stats["target_ms"]:
                print(f"  Target: {stats['target_ms']}ms")
        
        print("\n" + "=" * 60)
    
    def save_report(self, path: Path):
        """Save timing data to a JSON file."""
        data = {
            "summary": self.get_summary(),
            "results": [
                {
                    "operation": r.operation,
                    "duration_ms": r.duration_ms,
                    "timestamp": r.timestamp,
                    "success": r.success,
                    "details": r.details,
                }
                for r in self.results
            ]
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def clear(self):
        """Clear all collected timing data."""
        self.results.clear()
        self._start_times.clear()


def timed(operation: str = None):
    """
    Decorator to time a function execution.
    
    Usage:
        @timed("flood_fill")
        def do_flood_fill(self, x, y):
            ...
    
    Or without explicit name (uses function name):
        @timed()
        def canvas_render(self):
            ...
    """
    def decorator(func: Callable) -> Callable:
        op_name = operation or func.__name__
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            profiler = PerformanceProfiler.get_instance()
            with profiler.measure(op_name):
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


def profile_block(operation: str):
    """
    Context manager for profiling a block of code.
    
    Usage:
        with profile_block("pdf_load"):
            pdf_data = load_pdf(path)
            render_pages(pdf_data)
    """
    return PerformanceProfiler.get_instance().measure(operation)


# Global profiler instance for convenience
profiler = PerformanceProfiler.get_instance()
