"""Phase 11: Execution Monitor for Autonomous Options Trading System.

This module monitors execution algorithm performance including:
- Execution algorithm performance tracking
- Slippage monitoring vs benchmarks
- Adaptive execution effectiveness
- Execution quality trends
- Integration with execution analysis and smart order routing
"""

import os
import sys
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
import statistics

# Add project root to path for imports
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
if project_root not in sys.path:
    sys.path.append(project_root)

logger = logging.getLogger(__name__)


@dataclass
class ExecutionRecord:
    """Record of an execution for monitoring purposes."""
    execution_id: str
    symbol: str
    side: str
    quantity: int
    executed_quantity: int
    fill_rate: float
    algorithm_used: str
    average_price: float
    benchmark_price: float
    slippage_bps: float
    execution_time_seconds: float
    timestamp: datetime
    success: bool
    market_conditions: Dict = field(default_factory=dict)
    metadata: Dict = field(default_factory=dict)


@dataclass
class AlgorithmPerformance:
    """Performance metrics for an execution algorithm."""
    algorithm_name: str
    total_executions: int
    successful_executions: int
    average_slippage_bps: float
    average_fill_rate: float
    average_execution_time_seconds: float
    success_rate: float
    quality_score: float
    recent_performance: List[float] = field(default_factory=list)  # Recent slippage values

    def __post_init__(self):
        if self.total_executions > 0:
            self.success_rate = self.successful_executions / self.total_executions


@dataclass
class ExecutionAlert:
    """Alert for execution monitoring."""
    alert_id: str
    symbol: str
    alert_type: str  # 'high_slippage', 'low_fill_rate', 'algorithm_degradation', etc.
    severity: str    # 'low', 'medium', 'high', 'critical'
    message: str
    timestamp: datetime
    execution_id: Optional[str] = None
    threshold_value: Optional[float] = None
    actual_value: Optional[float] = None


class ExecutionMonitor:
    """Monitors execution algorithm performance and quality."""

    def __init__(self,
                 check_interval: int = 30,  # seconds
                 enable_alerts: bool = True,
                 slippage_warning_threshold: float = 50.0,  # bps
                 slippage_critical_threshold: float = 100.0,  # bps
                 fill_rate_warning_threshold: float = 0.8,   # 80%
                 fill_rate_critical_threshold: float = 0.6,   # 60%
                 max_history_size: int = 1000):
        """Initialize the execution monitor.

        Args:
            check_interval: How often to check for alerts (seconds)
            enable_alerts: Whether to generate alerts
            slippage_warning_threshold: Slippage threshold for warnings (bps)
            slippage_critical_threshold: Slippage threshold for critical alerts (bps)
            fill_rate_warning_threshold: Fill rate threshold for warnings
            fill_rate_critical_threshold: Fill rate threshold for critical alerts
            max_history_size: Maximum number of execution records to keep
        """
        self.check_interval = check_interval
        self.enable_alerts = enable_alerts
        self.slippage_warning_threshold = slippage_warning_threshold
        self.slippage_critical_threshold = slippage_critical_threshold
        self.fill_rate_warning_threshold = fill_rate_warning_threshold
        self.fill_rate_critical_threshold = fill_rate_critical_threshold
        self.max_history_size = max_history_size

        # Execution tracking
        self.executions: List[ExecutionRecord] = []
        self.algorithm_performance: Dict[str, AlgorithmPerformance] = {}
        self.alerts: List[ExecutionAlert] = []
        self.alert_callbacks: List[callable] = []

        # Control flags
        self.monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None

        logger.info(f"ExecutionMonitor initialized (check_interval={check_interval}s)")

    def add_alert_callback(self, callback: callable):
        """Add a callback function for alerts."""
        self.alert_callbacks.append(callback)

    def _send_alert(self, alert: ExecutionAlert):
        """Send alert via registered callbacks."""
        if self.enable_alerts:
            logger.warning(f"ALERT [{alert.severity.upper()}] {alert.message}")
            self.alerts.append(alert)

            # Keep alerts reasonable
            if len(self.alerts) > 500:
                self.alerts = self.alerts[-500:]

            # Call callbacks
            for callback in self.alert_callbacks:
                try:
                    callback(alert)
                except Exception as e:
                    logger.error(f"Error in alert callback: {e}")

    def record_execution(self, execution_data: Dict) -> str:
        """Record an execution for monitoring.

        Args:
            execution_data: Dictionary containing execution information

        Returns:
            Execution ID of the recorded execution
        """
        # Generate execution ID
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        execution_id = f"{execution_data.get('symbol', 'UNKNOWN')}_{timestamp_str}_{len(self.executions)}"

        # Extract data with defaults
        symbol = execution_data.get('symbol', 'UNKNOWN')
        side = execution_data.get('side', 'unknown')
        quantity = execution_data.get('quantity', 0)
        executed_quantity = execution_data.get('executed_quantity', 0)
        fill_rate = executed_quantity / quantity if quantity > 0 else 0.0
        algorithm_used = execution_data.get('algorithm_used', 'unknown')
        average_price = execution_data.get('average_price', 0.0)
        benchmark_price = execution_data.get('benchmark_price', average_price)
        slippage_bps = execution_data.get('slippage_bps', 0.0)
        execution_time_seconds = execution_data.get('execution_time_seconds', 0.0)
        success = execution_data.get('success', False)
        market_conditions = execution_data.get('market_conditions', {})
        metadata = execution_data.get('metadata', {})

        # Create execution record
        record = ExecutionRecord(
            execution_id=execution_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            executed_quantity=executed_quantity,
            fill_rate=fill_rate,
            algorithm_used=algorithm_used,
            average_price=average_price,
            benchmark_price=benchmark_price,
            slippage_bps=slippage_bps,
            execution_time_seconds=execution_time_seconds,
            timestamp=datetime.now(),
            success=success,
            market_conditions=market_conditions,
            metadata=metadata
        )

        # Add to executions
        self.executions.append(record)

        # Update algorithm performance
        self._update_algorithm_performance(record)

        # Check for alerts
        if self.enable_alerts:
            self._check_execution_alerts(record)

        # Trim history if needed
        if len(self.executions) > self.max_history_size:
            self.executions = self.executions[-self.max_history_size:]

        logger.debug(f"Recorded execution {execution_id}: {symbol} {side} {executed_quantity}/{quantity} "
                    f"via {algorithm_used}, slippage: {slippage_bps:.2f} bps")

        return execution_id

    def _update_algorithm_performance(self, record: ExecutionRecord):
        """Update performance metrics for an algorithm.

        Args:
            record: ExecutionRecord to update performance with
        """
        algorithm = record.algorithm_used

        if algorithm not in self.algorithm_performance:
            self.algorithm_performance[algorithm] = AlgorithmPerformance(
                algorithm_name=algorithm,
                total_executions=0,
                successful_executions=0,
                average_slippage_bps=0.0,
                average_fill_rate=0.0,
                average_execution_time_seconds=0.0,
                success_rate=0.0,
                quality_score=0.0
            )

        perf = self.algorithm_performance[algorithm]

        # Update counters
        perf.total_executions += 1
        if record.success and record.fill_rate > 0.95:  # Consider successful if high fill rate
            perf.successful_executions += 1

        # Update averages using incremental algorithm
        # Slippage
        if perf.total_executions == 1:
            perf.average_slippage_bps = abs(record.slippage_bps)
        else:
            perf.average_slippage_bps = (
                (perf.average_slippage_bps * (perf.total_executions - 1) + abs(record.slippage_bps))
                / perf.total_executions
            )

        # Fill rate
        if perf.total_executions == 1:
            perf.average_fill_rate = record.fill_rate
        else:
            perf.average_fill_rate = (
                (perf.average_fill_rate * (perf.total_executions - 1) + record.fill_rate)
                / perf.total_executions
            )

        # Execution time
        if perf.total_executions == 1:
            perf.average_execution_time_seconds = record.execution_time_seconds
        else:
            perf.average_execution_time_seconds = (
                (perf.average_execution_time_seconds * (perf.total_executions - 1) + record.execution_time_seconds)
                / perf.total_executions
            )

        # Success rate
        perf.success_rate = perf.successful_executions / perf.total_executions if perf.total_executions > 0 else 0.0

        # Quality score (simplified - based on slippage and fill rate)
        slippage_score = max(0, 100 - abs(record.slippage_bps) / 2)  # 0 slippage = 100, 200 bps = 0
        fill_score = record.fill_rate * 100
        quality = (slippage_score + fill_score) / 2
        if perf.total_executions == 1:
            perf.quality_score = quality
        else:
            perf.quality_score = (
                (perf.quality_score * (perf.total_executions - 1) + quality)
                / perf.total_executions
            )

        # Update recent performance (last 20 executions)
        perf.recent_performance.append(abs(record.slippage_bps))
        if len(perf.recent_performance) > 20:
            perf.recent_performance = perf.recent_performance[-20:]

    def _check_execution_alerts(self, record: ExecutionRecord):
        """Check if an execution triggers any alerts.

        Args:
            record: ExecutionRecord to check for alerts
        """
        # High slippage alert
        abs_slippage = abs(record.slippage_bps)
        if abs_slippage >= self.slippage_critical_threshold:
            alert = ExecutionAlert(
                alert_id=f"slippage_critical_{record.execution_id}",
                symbol=record.symbol,
                alert_type="high_slippage",
                severity="critical",
                message=f"Critical slippage detected: {abs_slippage:.2f} bps for {record.symbol} {record.side} "
                       f"{record.executed_quantity}/{record.quantity} via {record.algorithm_used}",
                execution_id=record.execution_id,
                threshold_value=self.slippage_critical_threshold,
                actual_value=abs_slippage
            )
            self._send_alert(alert)
        elif abs_slippage >= self.slippage_warning_threshold:
            alert = ExecutionAlert(
                alert_id=f"slippage_warning_{record.execution_id}",
                symbol=record.symbol,
                alert_type="high_slippage",
                severity="warning",
                message=f"High slippage detected: {abs_slippage:.2f} bps for {record.symbol} {record.side} "
                       f"{record.executed_quantity}/{record.quantity} via {record.algorithm_used}",
                execution_id=record.execution_id,
                threshold_value=self.slippage_warning_threshold,
                actual_value=abs_slippage
            )
            self._send_alert(alert)

        # Low fill rate alert
        if record.fill_rate <= self.fill_rate_critical_threshold:
            alert = ExecutionAlert(
                alert_id=f"fillrate_critical_{record.execution_id}",
                symbol=record.symbol,
                alert_type="low_fill_rate",
                severity="critical",
                message=f"Critical fill rate detected: {record.fill_rate:.1%} for {record.symbol} {record.side} "
                       f"{record.executed_quantity}/{record.quantity} via {record.algorithm_used}",
                execution_id=record.execution_id,
                threshold_value=self.fill_rate_critical_threshold,
                actual_value=record.fill_rate
            )
            self._send_alert(alert)
        elif record.fill_rate <= self.fill_rate_warning_threshold:
            alert = ExecutionAlert(
                alert_id=f"fillrate_warning_{record.execution_id}",
                symbol=record.symbol,
                alert_type="low_fill_rate",
                severity="warning",
                message=f"Low fill rate detected: {record.fill_rate:.1%} for {record.symbol} {record.side} "
                       f"{record.executed_quantity}/{record.quantity} via {record.algorithm_used}",
                execution_id=record.execution_id,
                threshold_value=self.fill_rate_warning_threshold,
                actual_value=record.fill_rate
            )
            self._send_alert(alert)

        # Algorithm degradation alert (check if recent performance is worse than historical)
        self._check_algorithm_degradation_alert(record)

    def _check_algorithm_degradation_alert(self, record: ExecutionRecord):
        """Check for algorithm performance degradation.

        Args:
            record: ExecutionRecord to check for degradation
        """
        algorithm = record.algorithm_used
        if algorithm not in self.algorithm_performance:
            return

        perf = self.algorithm_performance[algorithm]

        # Need sufficient history to detect degradation
        if perf.total_executions < 10:
            return

        # Check if recent performance is significantly worse than historical
        if len(perf.recent_performance) >= 5:
            recent_avg_slippage = statistics.mean(perf.recent_performance[-5:])  # Last 5 executions
            historical_avg_slippage = perf.average_slippage_bps

            # If recent slippage is 50% worse than historical, trigger alert
            if historical_avg_slippage > 0 and recent_avg_slippage > historical_avg_slippage * 1.5:
                alert = ExecutionAlert(
                    alert_id=f"degradation_{algorithm}_{int(time.time())}",
                    symbol=record.symbol,
                    alert_type="algorithm_degradation",
                    severity="warning",
                    message=f"Algorithm {algorithm} degradation detected: recent avg slippage {recent_avg_slippage:.2f} bps "
                           f"vs historical {historical_avg_slippage:.2f} bps",
                    execution_id=record.execution_id,
                    threshold_value=historical_avg_slippage * 1.5,
                    actual_value=recent_avg_slippage
                )
                self._send_alert(alert)

    def get_execution_summary(self) -> Dict:
        """Get summary of all executions.

        Returns:
            Dictionary with execution summary
        """
        if not self.executions:
            return {
                'total_executions': 0,
                'successful_executions': 0,
                'average_slippage_bps': 0.0,
                'average_fill_rate': 0.0,
                'average_execution_time_seconds': 0.0,
                'success_rate': 0.0
            }

        successful_executions = [e for e in self.executions if e.success and e.fill_rate > 0.95]

        total_executions = len(self.executions)
        successful_count = len(successful_executions)

        avg_slippage = 0.0
        avg_fill_rate = 0.0
        avg_time = 0.0

        if successful_executions:
            avg_slippage = statistics.mean([abs(e.slippage_bps) for e in successful_executions])
            avg_fill_rate = statistics.mean([e.fill_rate for e in successful_executions])
            avg_time = statistics.mean([e.execution_time_seconds for e in successful_executions])

        return {
            'total_executions': total_executions,
            'successful_executions': successful_count,
            'success_rate': successful_count / total_executions if total_executions > 0 else 0.0,
            'average_slippage_bps': avg_slippage,
            'average_fill_rate': avg_fill_rate,
            'average_execution_time_seconds': avg_time,
            'slippage_trend': self._calculate_slippage_trend(),
            'fill_rate_trend': self._calculate_fill_rate_trend()
        }

    def get_algorithm_performance_summary(self) -> Dict:
        """Get performance summary for all algorithms.

        Returns:
            Dictionary with algorithm performance summary
        """
        if not self.algorithm_performance:
            return {
                'total_algorithms': 0,
                'algorithms': {}
            }

        algorithms_summary = {}
        for alg_name, perf in self.algorithm_performance.items():
            algorithms_summary[alg_name] = {
                'total_executions': perf.total_executions,
                'successful_executions': perf.successful_executions,
                'success_rate': perf.success_rate,
                'average_slippage_bps': perf.average_slippage_bps,
                'average_fill_rate': perf.average_fill_rate,
                'average_execution_time_seconds': perf.average_execution_time_seconds,
                'quality_score': perf.quality_score,
                'recent_slippage_trend': self._calculate_algorithm_slippage_trend(perf)
            }

        return {
            'total_algorithms': len(self.algorithm_performance),
            'algorithms': algorithms_summary
        }

    def get_recent_alerts(self, limit: int = 50) -> List[Dict]:
        """Get recent alerts.

        Args:
            limit: Maximum number of alerts to return

        Returns:
            List of alert dictionaries
        """
        recent_alerts = self.alerts[-limit:] if len(self.alerts) > limit else self.alerts
        return [
            {
                'alert_id': alert.alert_id,
                'symbol': alert.symbol,
                'alert_type': alert.alert_type,
                'severity': alert.severity,
                'message': alert.message,
                'timestamp': alert.timestamp.isoformat(),
                'execution_id': alert.execution_id,
                'threshold_value': alert.threshold_value,
                'actual_value': alert.actual_value
            }
            for alert in recent_alerts
        ]

    def clear_alerts(self, alert_type: Optional[str] = None):
        """Clear alerts.

        Args:
            alert_type: If provided, only clear alerts of this type
        """
        if alert_type is None:
            self.alerts.clear()
        else:
            self.alerts = [alert for alert in self.alerts if alert.alert_type != alert_type]
        logger.info(f"Cleared alerts{f' of type {alert_type}' if alert_type else ''}")

    def start(self):
        """Start the execution monitor (for periodic checks)."""
        if self.monitoring:
            logger.warning("Execution monitor is already running")
            return

        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("Execution monitor started")

    def stop(self):
        """Stop the execution monitor."""
        self.monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5.0)
        logger.info("Execution monitor stopped")

    def _monitor_loop(self):
        """Background monitoring loop."""
        logger.info("Execution monitor loop started")

        while self.monitoring:
            try:
                # Perform periodic checks (e.g., check for stale executions, system health)
                self._perform_periodic_checks()

                # Sleep until next check
                time.sleep(self.check_interval)

            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                time.sleep(self.check_interval)  # Continue despite errors

    def _perform_periodic_checks(self):
        """Perform periodic system health checks."""
        # Check for executions that have been running too long (if we had start times)
        # Check system health, etc.
        # For now, just log that we're alive
        logger.debug("Execution monitor periodic check - system healthy")

    def _calculate_slippage_trend(self) -> float:
        """Calculate slippage improvement trend over recent executions.

        Returns:
            Percentage change in slippage (negative = improvement)
        """
        if len(self.executions) < 10:
            return 0.0

        # Compare last 5 to previous 5
        recent = self.executions[-5:]
        previous = self.executions[-10:-5]

        if not recent or not previous:
            return 0.0

        recent_avg = statistics.mean([abs(e.slippage_bps) for e in recent])
        previous_avg = statistics.mean([abs(e.slippage_bps) for e in previous])

        if previous_avg == 0:
            return 0.0

        return ((recent_avg - previous_avg) / previous_avg) * 100

    def _calculate_fill_rate_trend(self) -> float:
        """Calculate fill rate improvement trend over recent executions.

        Returns:
            Percentage change in fill rate (positive = improvement)
        """
        if len(self.executions) < 10:
            return 0.0

        # Compare last 5 to previous 5
        recent = self.executions[-5:]
        previous = self.executions[-10:-5]

        if not recent or not previous:
            return 0.0

        recent_avg = statistics.mean([e.fill_rate for e in recent])
        previous_avg = statistics.mean([e.fill_rate for e in previous])

        if previous_avg == 0:
            return 0.0

        return ((recent_avg - previous_avg) / previous_avg) * 100

    def _calculate_algorithm_slippage_trend(self, perf: AlgorithmPerformance) -> float:
        """Calculate slippage trend for a specific algorithm.

        Args:
            perf: AlgorithmPerformance object

        Returns:
            Percentage change in slippage (negative = improvement)
        """
        if len(perf.recent_performance) < 6:  # Need at least 6 to split into two groups
            return 0.0

        # Compare last 3 to previous 3
        recent = perf.recent_performance[-3:]
        previous = perf.recent_performance[-6:-3]

        if not recent or not previous:
            return 0.0

        recent_avg = statistics.mean(recent)
        previous_avg = statistics.mean(previous)

        if previous_avg == 0:
            return 0.0

        return ((recent_avg - previous_avg) / previous_avg) * 100


def create_execution_monitor(
    check_interval: int = 30,
    enable_alerts: bool = True,
    slippage_warning_threshold: float = 50.0,
    slippage_critical_threshold: float = 100.0,
    fill_rate_warning_threshold: float = 0.8,
    fill_rate_critical_threshold: float = 0.6,
    max_history_size: int = 1000
) -> ExecutionMonitor:
    """Factory function to create an ExecutionMonitor instance.

    Args:
        check_interval: How often to check for alerts (seconds)
        enable_alerts: Whether to generate alerts
        slippage_warning_threshold: Slippage threshold for warnings (bps)
        slippage_critical_threshold: Slippage threshold for critical alerts (bps)
        fill_rate_warning_threshold: Fill rate threshold for warnings
        fill_rate_critical_threshold: Fill rate threshold for critical alerts
        max_history_size: Maximum number of execution records to keep

    Returns:
        Configured ExecutionMonitor instance
    """
    return ExecutionMonitor(
        check_interval=check_interval,
        enable_alerts=enable_alerts,
        slippage_warning_threshold=slippage_warning_threshold,
        slippage_critical_threshold=slippage_critical_threshold,
        fill_rate_warning_threshold=fill_rate_warning_threshold,
        fill_rate_critical_threshold=fill_rate_critical_threshold,
        max_history_size=max_history_size
    )


# Example usage and testing
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    def demo_alert(alert: ExecutionAlert):
        print(f"[ALERT] {alert.severity.upper()}: {alert.message}")

    # Create execution monitor
    monitor = create_execution_monitor(
        check_interval=5,  # 5 seconds for demo
        enable_alerts=True,
        slippage_warning_threshold=30.0,
        slippage_critical_threshold=60.0,
        fill_rate_warning_threshold=0.7,
        fill_rate_critical_threshold=0.5
    )

    monitor.add_alert_callback(demo_alert)

    print("=== Execution Monitor Demo ===\n")

    # Record some sample executions
    print("1. Recording Sample Executions")

    # Successful execution
    exec1 = monitor.record_execution({
        'symbol': 'AAPL261016C00190000',
        'side': 'buy',
        'quantity': 10,
        'executed_quantity': 10,
        'algorithm_used': 'VWAP',
        'average_price': 5.02,
        'benchmark_price': 5.00,
        'slippage_bps': 4.0,  # 4 bps slippage
        'execution_time_seconds': 120.0,
        'success': True,
        'market_conditions': {
            'condition': 'liquid',
            'volatility': 0.25,
            'liquidity_score': 0.8
        }
    })

    # Execution with some slippage
    exec2 = monitor.record_execution({
        'symbol': 'MSFT261016C00300000',
        'side': 'sell',
        'quantity': 5,
        'executed_quantity': 5,
        'algorithm_used': 'TWAP',
        'average_price': 4.95,
        'benchmark_price': 5.00,
        'slippage_bps': -10.0,  # 10 bps slippage (we got better price)
        'execution_time_seconds': 180.0,
        'success': True,
        'market_conditions': {
            'condition': 'normal',
            'volatility': 0.30,
            'liquidity_score': 0.6
        }
    })

    # Execution with high slippage (should trigger warning)
    exec3 = monitor.record_execution({
        'symbol': 'GOOGL261016C00120000',
        'side': 'buy',
        'quantity': 8,
        'executed_quantity': 8,
        'algorithm_used': 'POV',
        'average_price': 8.50,
        'benchmark_price': 8.00,
        'slippage_bps': 62.5,  # 62.5 bps slippage - should trigger warning
        'execution_time_seconds': 300.0,
        'success': True,
        'market_conditions': {
            'condition': 'volatile',
            'volatility': 0.45,
            'liquidity_score': 0.4
        }
    })

    # Execution with low fill rate (should trigger warning)
    exec4 = monitor.record_execution({
        'symbol': 'TSLA261016P00250000',
        'side': 'sell',
        'quantity': 10,
        'executed_quantity': 4,  # Only 40% filled
        'algorithm_used': 'MARKET',
        'average_price': 4.20,
        'benchmark_price': 4.25,
        'slippage_bps': 11.8,
        'execution_time_seconds': 60.0,
        'success': False,  # Marked as unsuccessful due to low fill
        'market_conditions': {
            'condition': 'illiquid',
            'volatility': 0.35,
            'liquidity_score': 0.2
        }
    })

    # Execution with critical slippage (should trigger critical alert)
    exec5 = monitor.record_execution({
        'symbol': 'NVDA261016C00400000',
        'side': 'buy',
        'quantity': 3,
        'executed_quantity': 3,
        'algorithm_used': 'ICEBERG',
        'average_price': 12.50,
        'benchmark_price': 10.00,
        'slippage_bps': 250.0,  # 250 bps slippage - should trigger critical alert
        'execution_time_seconds': 900.0,
        'success': True,
        'market_conditions': {
            'condition': 'volatile',
            'volatility': 0.60,
            'liquidity_score': 0.1
        }
    })

    print(f"   Recorded 5 executions:")
    print(f"   - AAPL: {exec1}")
    print(f"   - MSFT: {exec2}")
    print(f"   - GOOGL: {exec3} (high slippage)")
    print(f"   - TSLA: {exec4} (low fill)")
    print(f"   - NVDA: {exec5} (critical slippage)")
    print()

    # Wait a bit for alerts to be processed
    print("2. Waiting for alert processing...")
    time.sleep(2)

    # Get execution summary
    print("3. Execution Summary")
    summary = monitor.get_execution_summary()
    print(f"   Total Executions: {summary['total_executions']}")
    print(f"   Successful Executions: {summary['successful_executions']}")
    print(f"   Success Rate: {summary['success_rate']:.1%}")
    print(f"   Average Slippage: {summary['average_slippage_bps']:.2f} bps")
    print(f"   Average Fill Rate: {summary['average_fill_rate']:.1%}")
    print(f"   Average Execution Time: {summary['average_execution_time_seconds']:.0f} seconds")
    print(f"   Slippage Trend: {summary['slippage_trend']:+.2f}%")
    print(f"   Fill Rate Trend: {summary['fill_rate_trend']:+.2f}%")
    print()

    # Get algorithm performance summary
    print("4. Algorithm Performance Summary")
    alg_summary = monitor.get_algorithm_performance_summary()
    print(f"   Total Algorithms Tracked: {alg_summary['total_algorithms']}")
    for alg_name, perf in alg_summary['algorithms'].items():
        print(f"   {alg_name}:")
        print(f"     Executions: {perf['total_executions']}")
        print(f"     Success Rate: {perf['success_rate']:.1%}")
        print(f"     Avg Slippage: {perf['average_slippage_bps']:.2f} bps")
        print(f"     Avg Fill Rate: {perf['average_fill_rate']:.1%}")
        print(f"     Quality Score: {perf['quality_score']:.1f}/100")
    print()

    # Get recent alerts
    print("5. Recent Alerts")
    alerts = monitor.get_recent_alerts()
    print(f"   Total Alerts: {len(alerts)}")
    for alert in alerts:
        print(f"   [{alert['severity'].upper()}] {alert['message']}")
    print()

    # Start monitoring for a few seconds to show periodic checks
    print("6. Starting Monitoring (will run for 10 seconds)...")
    monitor.start()
    print("   Monitor is running - performing periodic checks every 5 seconds")
    time.sleep(10)
    monitor.stop()
    print("   Monitor stopped")

    print("\n=== Execution Monitor Demo Complete ===")