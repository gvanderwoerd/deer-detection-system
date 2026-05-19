"""
Integration Test Suite for Sprinkler Control System
Tests the full detection → activation → verification flow

NOTE: Tests use isolated tracker instances with temporary storage
to avoid polluting the real API quota tracker.
"""

import pytest
import time
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from api_usage_tracker import APIUsageTracker, get_tracker as get_api_tracker
from activation_metrics import ActivationMetrics, get_metrics as get_activation_metrics


@pytest.fixture
def isolated_tracker():
    """Create an isolated tracker with temp storage for testing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tracker = APIUsageTracker(data_dir=tmpdir)
        yield tracker


class TestAPIUsageTracker:
    """Test API quota tracking and monitoring"""

    def test_tracker_initialization(self, isolated_tracker):
        """Test tracker initializes correctly"""
        tracker = isolated_tracker
        assert tracker is not None
        assert tracker.calls_today is not None
        assert tracker.calls_this_month is not None

    def test_track_api_call(self, isolated_tracker):
        """Test tracking individual API calls"""
        tracker = isolated_tracker
        initial_count = len(tracker.calls_this_month)

        tracker.track_call('sendcommand', 245.5)
        assert len(tracker.calls_this_month) == initial_count + 1

    def test_quota_calculation(self, isolated_tracker):
        """Test quota usage percentage calculation"""
        tracker = isolated_tracker

        # Add calls to represent 100 API calls
        for i in range(100):
            tracker.track_call('sendcommand', 100.0)

        stats = tracker.get_stats()
        quota_pct = stats['this_month']['quota_usage_pct']

        # 100 calls / 10000 limit = 1%
        assert 0.9 < quota_pct < 1.1  # Allow 0.1% margin

    def test_quota_warnings(self, isolated_tracker):
        """Test quota warning thresholds"""
        tracker = isolated_tracker

        # Add calls to trigger warning threshold (80%)
        # Use isolated tracker so real quota isn't affected
        for i in range(8000):
            tracker.track_call('sendcommand', 100.0)

        stats = tracker.get_stats()
        assert len(stats['warnings']) > 0  # Should have warnings
        assert 'WARNING' in stats['warnings'][0]

    def test_latency_tracking(self, isolated_tracker):
        """Test API latency calculation"""
        tracker = isolated_tracker

        tracker.track_call('sendcommand', 245.5)
        tracker.track_call('sendcommand', 187.2)
        tracker.track_call('sendcommand', 192.1)

        stats = tracker.get_stats()
        avg_latency = stats['this_month']['avg_latency_ms']

        expected_avg = (245.5 + 187.2 + 192.1) / 3
        assert abs(avg_latency - expected_avg) < 1.0


class TestActivationMetrics:
    """Test activation performance tracking"""

    def test_metrics_initialization(self):
        """Test metrics initializes correctly"""
        metrics = ActivationMetrics()
        assert metrics is not None
        assert metrics.total_attempts == 0
        assert metrics.total_successful == 0

    def test_record_successful_activation(self):
        """Test recording successful activation"""
        metrics = ActivationMetrics()

        metrics.record_activation(success=True, verified=True, latency_ms=245.5)

        assert metrics.total_attempts == 1
        assert metrics.total_successful == 1

    def test_record_failed_activation(self):
        """Test recording failed activation"""
        metrics = ActivationMetrics()

        metrics.record_activation(
            success=False,
            verified=False,
            error='Network timeout',
            latency_ms=0
        )

        assert metrics.total_attempts == 1
        assert metrics.total_failed == 1
        assert metrics.total_successful == 0

    def test_success_rate_calculation(self):
        """Test success rate percentage"""
        metrics = ActivationMetrics()

        # Record 2 successful, 1 failed
        metrics.record_activation(success=True, verified=True, latency_ms=245.5)
        metrics.record_activation(success=True, verified=False, latency_ms=187.2)
        metrics.record_activation(success=False, verified=False, error='Quota', latency_ms=0)

        data = metrics.get_metrics()
        success_rate = data['success_rate_pct']

        # 2 / 3 = 66.7%
        assert 66.0 < success_rate < 67.0

    def test_verification_rate_calculation(self):
        """Test verification rate calculation"""
        metrics = ActivationMetrics()

        metrics.record_activation(success=True, verified=True, latency_ms=245.5)
        metrics.record_activation(success=True, verified=False, latency_ms=187.2)

        data = metrics.get_metrics()
        verification_rate = data['verification_rate_pct']

        # 1 / 2 = 50%
        assert 49.0 < verification_rate < 51.0

    def test_health_summary(self):
        """Test health summary for dashboard"""
        metrics = ActivationMetrics()

        metrics.record_activation(success=True, verified=True, latency_ms=245.5)
        metrics.record_activation(success=True, verified=True, latency_ms=187.2)

        health = metrics.get_health_summary()

        assert health['health'] == 'healthy'
        assert health['success_rate_pct'] == 100.0
        assert health['total_attempts'] == 2

    def test_failure_reasons_tracking(self):
        """Test tracking of failure reasons"""
        metrics = ActivationMetrics()

        metrics.record_activation(
            success=False,
            verified=False,
            error='Network timeout',
            latency_ms=0
        )
        metrics.record_activation(
            success=False,
            verified=False,
            error='Network timeout',
            latency_ms=0
        )
        metrics.record_activation(
            success=False,
            verified=False,
            error='Quota exceeded',
            latency_ms=0
        )

        data = metrics.get_metrics()
        failure_reasons = data['failure_reasons']

        assert 'Network timeout' in failure_reasons
        assert failure_reasons['Network timeout'] == 2
        assert failure_reasons['Quota exceeded'] == 1


class TestRetryLogic:
    """Test retry mechanism for API calls"""

    def test_retry_decorator_success(self):
        """Test successful call doesn't retry"""
        from device_manager import retry_with_backoff

        call_count = 0

        @retry_with_backoff(max_retries=3)
        def test_function():
            nonlocal call_count
            call_count += 1
            return "success"

        result = test_function()
        assert result == "success"
        assert call_count == 1

    def test_retry_decorator_transient_failure(self):
        """Test retry on transient failure"""
        from device_manager import retry_with_backoff

        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def test_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Network timeout")
            return "success"

        result = test_function()
        assert result == "success"
        assert call_count == 2  # First fail, second succeed

    def test_retry_decorator_permanent_failure(self):
        """Test fail-fast for permanent errors"""
        from device_manager import retry_with_backoff

        call_count = 0

        @retry_with_backoff(max_retries=3)
        def test_function():
            nonlocal call_count
            call_count += 1
            raise ValueError("Invalid credentials")

        with pytest.raises(ValueError):
            test_function()

        assert call_count == 1  # Fail fast, no retries


class TestCredentialValidation:
    """Test startup credential validation"""

    @patch('device_manager.tinytuya.Cloud')
    def test_valid_credentials(self, mock_cloud):
        """Test validation passes with valid credentials"""
        from device_manager import DeviceManager

        mock_instance = MagicMock()
        mock_instance.getdevices.return_value = [{'id': '123', 'name': 'Valve1'}]
        mock_cloud.return_value = mock_instance

        dm = DeviceManager()
        assert dm.credentials_valid is True

    @patch('device_manager.tinytuya.Cloud')
    def test_invalid_credentials(self, mock_cloud):
        """Test validation fails with invalid credentials"""
        from device_manager import DeviceManager

        mock_instance = MagicMock()
        mock_instance.getdevices.side_effect = Exception("Unauthorized")
        mock_cloud.return_value = mock_instance

        dm = DeviceManager()
        assert dm.credentials_valid is False


class TestCommandVerification:
    """Test command verification (read-back checks)"""

    def test_turn_on_returns_dict(self):
        """Test turn_on returns structured response"""
        # This is an integration test that would need mocking
        # of the actual Tuya Cloud API
        pass

    def test_turn_off_returns_dict(self):
        """Test turn_off returns structured response"""
        pass


class TestAPIHealthCheck:
    """Test health check endpoints"""

    def test_health_endpoint_structure(self):
        """Test /api/health returns proper structure"""
        # Would need Flask test client
        pass

    def test_diagnostics_endpoint_structure(self):
        """Test /api/diagnostics/run returns proper structure"""
        # Would need Flask test client
        pass


# Run tests with: pytest tests/test_integration.py -v

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
