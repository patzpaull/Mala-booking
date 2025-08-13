import time
import logging
import asyncio
from typing import Dict, List
from functools import wraps
from contextlib import asynccontextmanager
import psutil
import threading
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class PerformanceMetrics:
    def __init__(self):
        self.metrics: Dict[str, List[float]] = {}
        self.error_counts: Dict[str, int] = {}
        self.start_time = time.time()
        self._lock = threading.Lock()
    
    def record_request_time(self, endpoint: str, duration: float):
        with self._lock:
            if endpoint not in self.metrics:
                self.metrics[endpoint] = []
            self.metrics[endpoint].append(duration)
            
            # Keep only last 1000 measurements per endpoint
            if len(self.metrics[endpoint]) > 1000:
                self.metrics[endpoint] = self.metrics[endpoint][-1000:]
    
    def record_error(self, endpoint: str):
        with self._lock:
            self.error_counts[endpoint] = self.error_counts.get(endpoint, 0) + 1
    
    def get_stats(self) -> Dict:
        with self._lock:
            stats = {}
            for endpoint, times in self.metrics.items():
                if times:
                    stats[endpoint] = {
                        'avg_response_time': sum(times) / len(times),
                        'min_response_time': min(times),
                        'max_response_time': max(times),
                        'request_count': len(times),
                        'error_count': self.error_counts.get(endpoint, 0)
                    }
            
            # Add system metrics
            stats['system'] = {
                'uptime_seconds': time.time() - self.start_time,
                'cpu_percent': psutil.cpu_percent(),
                'memory_percent': psutil.virtual_memory().percent,
                'memory_used_mb': psutil.virtual_memory().used / 1024 / 1024
            }
            
            return stats
    
    def get_slow_endpoints(self, threshold: float = 2.0) -> List[str]:
        with self._lock:
            slow_endpoints = []
            for endpoint, times in self.metrics.items():
                if times and sum(times) / len(times) > threshold:
                    slow_endpoints.append(endpoint)
            return slow_endpoints

# Global metrics instance
metrics = PerformanceMetrics()

def monitor_performance(endpoint_name: str = None):
    """Decorator to monitor function performance"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            name = endpoint_name or f"{func.__module__}.{func.__name__}"
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                metrics.record_error(name)
                raise
            finally:
                duration = time.time() - start_time
                metrics.record_request_time(name, duration)
                if duration > 1.0:  # Log slow operations
                    logger.warning(f"Slow operation {name}: {duration:.2f}s")
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            name = endpoint_name or f"{func.__module__}.{func.__name__}"
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                metrics.record_error(name)
                raise
            finally:
                duration = time.time() - start_time
                metrics.record_request_time(name, duration)
                if duration > 1.0:
                    logger.warning(f"Slow operation {name}: {duration:.2f}s")
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator

@asynccontextmanager
async def performance_context(operation_name: str):
    """Context manager for monitoring code blocks"""
    start_time = time.time()
    try:
        yield
    except Exception as e:
        metrics.record_error(operation_name)
        raise
    finally:
        duration = time.time() - start_time
        metrics.record_request_time(operation_name, duration)

async def log_performance_summary():
    """Log performance summary periodically"""
    while True:
        await asyncio.sleep(300)  # Log every 5 minutes
        stats = metrics.get_stats()
        slow_endpoints = metrics.get_slow_endpoints()
        
        logger.info("=== PERFORMANCE SUMMARY ===")
        logger.info(f"System uptime: {stats.get('system', {}).get('uptime_seconds', 0):.0f}s")
        logger.info(f"CPU usage: {stats.get('system', {}).get('cpu_percent', 0):.1f}%")
        logger.info(f"Memory usage: {stats.get('system', {}).get('memory_percent', 0):.1f}%")
        
        if slow_endpoints:
            logger.warning(f"Slow endpoints detected: {slow_endpoints}")
        
        # Log top 5 slowest endpoints
        endpoint_stats = [(k, v) for k, v in stats.items() if k != 'system']
        endpoint_stats.sort(key=lambda x: x[1].get('avg_response_time', 0), reverse=True)
        
        for endpoint, stat in endpoint_stats[:5]:
            logger.info(
                f"{endpoint}: avg={stat['avg_response_time']:.3f}s "
                f"max={stat['max_response_time']:.3f}s "
                f"requests={stat['request_count']} "
                f"errors={stat['error_count']}"
            )