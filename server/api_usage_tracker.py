"""
API Usage Tracker - Monitors Tuya Cloud API quota consumption
Prevents quota exhaustion by tracking calls and issuing warnings
"""

import time
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# Free tier quota estimate (conservative)
FREE_TIER_MONTHLY_QUOTA = 10000

# Warning thresholds
QUOTA_WARNING_THRESHOLD = 0.80  # Warn at 80%
QUOTA_CRITICAL_THRESHOLD = 0.95  # Critical at 95%


class APIUsageTracker:
    """Tracks API calls and quota usage"""

    def __init__(self, data_dir: str = 'logs'):
        """Initialize tracker with optional persistent storage"""
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.stats_file = self.data_dir / 'api_stats.json'

        # In-memory tracking
        self.calls_today = []  # List of (timestamp, endpoint, latency_ms)
        self.calls_this_month = []
        self.warnings = []
        self.current_month = datetime.now().strftime("%Y-%m")

        # Load previous stats if available
        self._load_stats()

        logger.info(f"API Usage Tracker initialized. Quota: {FREE_TIER_MONTHLY_QUOTA}/month")

    def track_call(self, endpoint: str, latency_ms: float = 0):
        """
        Record an API call.

        Args:
            endpoint: API endpoint called (e.g., 'sendcommand', 'getstatus', 'getdevices')
            latency_ms: Response time in milliseconds
        """
        now = time.time()
        current_month = datetime.now().strftime("%Y-%m")

        # Reset monthly stats if month changed
        if current_month != self.current_month:
            self._reset_monthly_stats(current_month)

        # Record call
        call_record = (now, endpoint, latency_ms)
        self.calls_today.append(call_record)
        self.calls_this_month.append(call_record)

        # Check quota and issue warnings if needed
        self._check_quota()

        # Clean up old data (keep only today)
        cutoff = now - 86400  # 24 hours
        self.calls_today = [(t, e, l) for t, e, l in self.calls_today if t >= cutoff]

        # Save stats periodically (every 10 calls)
        if len(self.calls_this_month) % 10 == 0:
            self._save_stats()

        logger.debug(f"API call tracked: {endpoint} ({latency_ms:.0f}ms) - "
                    f"Total this month: {len(self.calls_this_month)}")

    def get_stats(self) -> Dict:
        """Get comprehensive usage statistics"""
        now = time.time()

        # Today's stats
        today_calls = len(self.calls_today)
        today_latencies = [l for _, _, l in self.calls_today if l > 0]
        today_avg_latency = sum(today_latencies) / len(today_latencies) if today_latencies else 0

        # Monthly stats
        month_calls = len(self.calls_this_month)
        month_latencies = [l for _, _, l in self.calls_this_month if l > 0]
        month_avg_latency = sum(month_latencies) / len(month_latencies) if month_latencies else 0

        # Hourly rate
        hour_ago = now - 3600
        recent_calls = len([t for t, _, _ in self.calls_today if t >= hour_ago])

        # Quota projection
        quota_usage_pct = (month_calls / FREE_TIER_MONTHLY_QUOTA) * 100
        estimated_monthly_quota = FREE_TIER_MONTHLY_QUOTA
        quota_remaining = estimated_monthly_quota - month_calls

        # Build warnings
        warnings = []
        if quota_usage_pct >= QUOTA_CRITICAL_THRESHOLD * 100:
            warnings.append(f"🔴 CRITICAL: {quota_usage_pct:.1f}% of monthly quota used. "
                          f"Only {quota_remaining} API calls remaining.")
        elif quota_usage_pct >= QUOTA_WARNING_THRESHOLD * 100:
            warnings.append(f"🟡 WARNING: {quota_usage_pct:.1f}% of monthly quota used. "
                          f"Only {quota_remaining} API calls remaining.")

        # Endpoint breakdown
        endpoint_counts = {}
        for _, endpoint, _ in self.calls_this_month:
            endpoint_counts[endpoint] = endpoint_counts.get(endpoint, 0) + 1

        return {
            'today': {
                'count': today_calls,
                'avg_latency_ms': round(today_avg_latency, 2),
                'calls_per_hour': recent_calls
            },
            'this_month': {
                'count': month_calls,
                'avg_latency_ms': round(month_avg_latency, 2),
                'estimated_quota': estimated_monthly_quota,
                'quota_remaining': quota_remaining,
                'quota_usage_pct': round(quota_usage_pct, 1),
                'endpoints': endpoint_counts
            },
            'warnings': warnings,
            'health_status': 'critical' if quota_usage_pct >= QUOTA_CRITICAL_THRESHOLD * 100
                           else 'warning' if quota_usage_pct >= QUOTA_WARNING_THRESHOLD * 100
                           else 'healthy'
        }

    def _check_quota(self):
        """Check if quota warnings need to be issued"""
        stats = self.get_stats()
        current_warnings = stats['warnings']

        # Log warnings
        for warning in current_warnings:
            if warning not in self.warnings:
                logger.warning(f"API Quota: {warning}")
                self.warnings.append(warning)

    def _reset_monthly_stats(self, new_month: str):
        """Reset monthly stats when month changes"""
        logger.info(f"API stats month changed from {self.current_month} to {new_month}. Resetting monthly counters.")
        self.calls_this_month = []
        self.current_month = new_month
        self.warnings = []
        self._save_stats()

    def _save_stats(self):
        """Persist stats to file for recovery after restart"""
        try:
            data = {
                'current_month': self.current_month,
                'calls_this_month': [
                    {
                        'timestamp': t,
                        'endpoint': e,
                        'latency_ms': l
                    }
                    for t, e, l in self.calls_this_month
                ],
                'last_saved': time.time()
            }
            with open(self.stats_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.error(f"Failed to save API stats: {e}")

    def _load_stats(self):
        """Load previous stats from file"""
        try:
            if self.stats_file.exists():
                with open(self.stats_file, 'r') as f:
                    data = json.load(f)

                self.current_month = data.get('current_month', self.current_month)
                calls_data = data.get('calls_this_month', [])

                # Check if month has changed
                if self.current_month != datetime.now().strftime("%Y-%m"):
                    logger.info(f"Loaded stats from previous month ({self.current_month}). Discarding.")
                    self.calls_this_month = []
                else:
                    # Restore calls with some validation
                    for call in calls_data:
                        try:
                            t = call['timestamp']
                            e = call['endpoint']
                            l = call.get('latency_ms', 0)
                            self.calls_this_month.append((t, e, l))
                        except (KeyError, TypeError):
                            logger.warning("Skipping malformed call record")

                logger.info(f"Loaded {len(self.calls_this_month)} API calls from previous session")
        except Exception as e:
            logger.error(f"Failed to load API stats: {e}")
            self.calls_this_month = []


# Global tracker instance
_tracker = None


def get_tracker() -> APIUsageTracker:
    """Get or create global API usage tracker"""
    global _tracker
    if _tracker is None:
        _tracker = APIUsageTracker()
    return _tracker
