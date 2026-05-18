"""
Activation Metrics - Tracks sprinkler activation performance
Monitors success rates, latency, and failure reasons
"""

import time
import logging
from collections import deque
from typing import Dict, List

logger = logging.getLogger(__name__)


class ActivationMetrics:
    """Tracks sprinkler activation performance metrics"""

    def __init__(self, max_history: int = 100):
        """
        Initialize metrics tracker.

        Args:
            max_history: Keep last N activation records
        """
        self.max_history = max_history
        self.activations = deque(maxlen=max_history)  # Recent activation records
        self.total_attempts = 0
        self.total_successful = 0
        self.total_failed = 0
        self.startup_time = time.time()

        logger.info(f"Activation Metrics initialized (tracking last {max_history} activations)")

    def record_activation(self, success: bool, verified: bool = False,
                         error: str = None, latency_ms: float = 0):
        """
        Record a sprinkler activation attempt.

        Args:
            success: Whether the command was sent successfully
            verified: Whether the state change was verified
            error: Error message if failed
            latency_ms: API response latency
        """
        now = time.time()

        record = {
            'timestamp': now,
            'success': success,
            'verified': verified,
            'error': error,
            'latency_ms': latency_ms
        }

        self.activations.append(record)
        self.total_attempts += 1

        if success:
            self.total_successful += 1
        else:
            self.total_failed += 1

        status = "✓" if success else "✗"
        verified_str = "verified" if verified else "unverified"
        logger.info(f"Activation recorded: {status} {verified_str} "
                   f"({latency_ms:.0f}ms) - Total: {self.total_attempts} "
                   f"(Success: {self.total_successful}, Failed: {self.total_failed})")

    def get_metrics(self) -> Dict:
        """Get comprehensive metrics"""
        if not self.activations:
            return {
                'total_attempts': 0,
                'total_successful': 0,
                'total_failed': 0,
                'success_rate_pct': 0.0,
                'verification_rate_pct': 0.0,
                'latency': {
                    'avg_ms': 0.0,
                    'min_ms': 0.0,
                    'max_ms': 0.0
                },
                'failure_reasons': {},
                'recent_activations': [],
                'uptime_seconds': int(time.time() - self.startup_time)
            }

        # Calculate rates
        success_rate = (self.total_successful / self.total_attempts * 100) if self.total_attempts > 0 else 0

        # Recent success rate (last 100 or fewer)
        recent_successful = sum(1 for a in self.activations if a['success'])
        recent_count = len(self.activations)
        recent_success_rate = (recent_successful / recent_count * 100) if recent_count > 0 else 0

        # Latency stats
        latencies = [a['latency_ms'] for a in self.activations if a['latency_ms'] > 0]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        min_latency = min(latencies) if latencies else 0
        max_latency = max(latencies) if latencies else 0

        # Verification stats
        verified_count = sum(1 for a in self.activations if a['verified'])
        verification_rate = (verified_count / recent_count * 100) if recent_count > 0 else 0

        # Failure reasons
        failure_reasons = {}
        for a in self.activations:
            if not a['success'] and a['error']:
                reason = a['error'][:50]  # Truncate long errors
                failure_reasons[reason] = failure_reasons.get(reason, 0) + 1

        # Recent activations (last 20)
        recent = list(self.activations)[-20:]
        recent_activations = [
            {
                'timestamp': a['timestamp'],
                'success': a['success'],
                'verified': a['verified'],
                'latency_ms': round(a['latency_ms'], 2),
                'error': a['error']
            }
            for a in recent
        ]

        return {
            'total_attempts': self.total_attempts,
            'total_successful': self.total_successful,
            'total_failed': self.total_failed,
            'success_rate_pct': round(success_rate, 1),
            'recent_success_rate_pct': round(recent_success_rate, 1),
            'verification_rate_pct': round(verification_rate, 1),
            'latency': {
                'avg_ms': round(avg_latency, 2),
                'min_ms': round(min_latency, 2),
                'max_ms': round(max_latency, 2)
            },
            'failure_reasons': failure_reasons,
            'recent_activations': recent_activations,
            'uptime_seconds': int(time.time() - self.startup_time)
        }

    def get_health_summary(self) -> Dict:
        """Get simplified health summary for dashboards"""
        metrics = self.get_metrics()

        # Determine health status
        if metrics['total_attempts'] == 0:
            health = 'unknown'
        elif metrics['success_rate_pct'] >= 95:
            health = 'healthy'
        elif metrics['success_rate_pct'] >= 80:
            health = 'warning'
        else:
            health = 'critical'

        return {
            'health': health,
            'success_rate_pct': metrics['success_rate_pct'],
            'total_attempts': metrics['total_attempts'],
            'total_failed': metrics['total_failed'],
            'avg_latency_ms': metrics['latency']['avg_ms'],
            'verification_rate_pct': metrics['verification_rate_pct']
        }


# Global metrics instance
_metrics = None


def get_metrics() -> ActivationMetrics:
    """Get or create global activation metrics tracker"""
    global _metrics
    if _metrics is None:
        _metrics = ActivationMetrics()
    return _metrics
