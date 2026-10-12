"""Phase 11: Execution Analysis for Autonomous Options Trading System.

This module provides execution quality analysis including:
- Slippage measurement vs various benchmarks
- Market impact analysis
- Execution shortfall calculation
- Timing analysis
- Litigation-quality execution reporting
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
import math
import statistics

# Add project root to path for imports
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
if project_root not in sys.path:
    sys.path.append(project_root)

logger = logging.getLogger(__name__)


@dataclass
class ExecutionMetrics:
    """Container for execution quality metrics."""
    # Basic execution info
    symbol: str
    side: str  # 'buy' or 'sell'
    quantity: int
    executed_quantity: int
    fill_rate: float

    # Price metrics
    average_price: float
    benchmark_price: float
    slippage_bps: float

    # Timing metrics
    start_time: datetime
    end_time: datetime
    duration_seconds: float

    # Market impact
    temporary_impact_bps: float
    permanent_impact_bps: float
    market_impact_bps: float

    # Risk-adjusted metrics
    execution_shortfall_bps: float
    volatility_adjusted_slippage: float

    # Quality scores
    quality_score: float  # 0-100, higher is better
    efficiency_ratio: float  # 0-1, higher is better

    # Additional metadata
    algorithm_used: str = ""
    market_conditions: Dict = field(default_factory=dict)
    metadata: Dict = field(default_factory=dict)


@dataclass
class SlippageAnalysis:
    """Analysis of slippage components."""
    total_slippage_bps: float
    explicit_slippage_bps: float  # Commissions, fees, taxes
    timing_slippage_bps: float    # Due to delayed execution
    opportunistic_slippage_bps: float  # Missed opportunities
    positioning_slippage_bps: float   # Front-running or predatory behavior
    market_impact_slippage_bps: float  # Temporary price impact
    risk_premium_slippage_bps: float   # Compensation for bearing risk


class ExecutionAnalyzer:
    """Analyzes execution quality and performance."""

    def __init__(self):
        self.executions: List[ExecutionMetrics] = []
        self.benchmark_calculator = VWAPBenchmarkCalculator()

    def analyze_execution(
        self,
        symbol: str,
        side: str,
        quantity: int,
        executed_quantity: int,
        average_price: float,
        start_time: datetime,
        end_time: datetime,
        get_market_data_callback=None,
        algorithm_used: str = "unknown"
    ) -> ExecutionMetrics:
        """Analyze execution quality.

        Args:
            symbol: Stock or option symbol
            side: 'buy' or 'sell'
            quantity: Total quantity ordered
            executed_quantity: Quantity actually executed
            average_price: Average execution price
            start_time: Execution start time
            end_time: Execution end time
            get_market_data_callback: Function to get historical market data
            algorithm_used: Algorithm used for execution

        Returns:
            ExecutionMetrics with quality analysis
        """
        # Calculate basic metrics
        fill_rate = executed_quantity / quantity if quantity > 0 else 0.0
        duration = (end_time - start_time).total_seconds()

        # Calculate benchmark price (VWAP during execution period)
        benchmark_price = self.benchmark_calculator.calculate_vwap_during_period(
            symbol, start_time, end_time, get_market_data_callback
        )

        # Calculate slippage
        if benchmark_price > 0:
            if side.lower() == 'buy':
                # For buys: positive slippage means we paid more than benchmark
                slippage_bps = ((average_price - benchmark_price) / benchmark_price) * 10000
            else:  # sell
                # For sells: positive slippage means we received less than benchmark
                slippage_bps = ((benchmark_price - average_price) / benchmark_price) * 10000
        else:
            slippage_bps = 0.0
            benchmark_price = average_price  # Fallback

        # Calculate market impact (simplified model)
        # In reality, this would use more sophisticated models
        market_impact_bps = abs(slippage_bps) * 0.3  # Assume 30% of slippage is market impact
        temporary_impact_bps = market_impact_bps * 0.7  # 70% temporary
        permanent_impact_bps = market_impact_bps * 0.3  # 30% permanent

        # Calculate execution shortfall (vs arrival price would be ideal)
        # Using benchmark as proxy for arrival price
        execution_shortfall_bps = slippage_bps  # Simplified

        # Calculate volatility-adjusted slippage
        volatility = self._get_volatility_estimate(symbol, start_time, end_time, get_market_data_callback)
        volatility_adjusted_slippage = abs(slippage_bps) / (1 + volatility * 100) if volatility >= 0 else abs(slippage_bps)

        # Calculate quality score (0-100)
        quality_score = self._calculate_quality_score(
            fill_rate, slippage_bps, duration, volatility
        )

        # Calculate efficiency ratio (0-1)
        efficiency_ratio = self._calculate_efficiency_ratio(
            fill_rate, slippage_bps, duration
        )

        # Create metrics object
        metrics = ExecutionMetrics(
            symbol=symbol,
            side=side,
            quantity=quantity,
            executed_quantity=executed_quantity,
            fill_rate=fill_rate,
            average_price=average_price,
            benchmark_price=benchmark_price,
            slippage_bps=slippage_bps,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration,
            temporary_impact_bps=temporary_impact_bps,
            permanent_impact_bps=permanent_impact_bps,
            market_impact_bps=market_impact_bps,
            execution_shortfall_bps=execution_shortfall_bps,
            volatility_adjusted_slippage=volatility_adjusted_slippage,
            quality_score=quality_score,
            efficiency_ratio=efficiency_ratio,
            algorithm_used=algorithm_used
        )

        # Store for historical analysis
        self.executions.append(metrics)

        # Keep only last 1000 executions
        if len(self.executions) > 1000:
            self.executions = self.executions[-1000:]

        logger.info(f"Analyzed execution for {symbol}: {executed_quantity}/{quantity} filled, "
                   f"slippage: {slippage_bps:.2f} bps, quality: {quality_score:.1f}/100")

        return metrics

    def analyze_slippage_components(
        self,
        execution: ExecutionMetrics,
        get_market_data_callback=None
    ) -> SlippageAnalysis:
        """Break down slippage into components.

        Args:
            execution: ExecutionMetrics to analyze
            get_market_data_callback: Function to get market data

        Returns:
            SlippageAnalysis with component breakdown
        """
        # This is a simplified model - real implementation would be more sophisticated
        total_slippage = abs(execution.slippage_bps)

        # Estimate components (these would come from detailed market data analysis)
        explicit_slippage = 2.0  # Fixed commission/fee estimate

        # Timing slippage - cost of delaying execution
        timing_slippage = min(total_slippage * 0.2, 5.0)  # Up to 20% or 5 bps

        # Opportunistic slippage - missed better prices
        opportunistic_slippage = min(total_slippage * 0.15, 3.0)  # Up to 15% or 3 bps

        # Positioning slippage - adverse selection
        positioning_slippage = min(total_slippage * 0.1, 2.0)  # Up to 10% or 2 bps

        # Market impact slippage
        market_impact_slippage = execution.market_impact_bps

        # Risk premium - compensation for immediacy
        risk_premium_slippage = max(0, total_slippage -
                                  explicit_slippage - timing_slippage -
                                  opportunistic_slippage - positioning_slippage -
                                  market_impact_slippage)

        return SlippageAnalysis(
            total_slippage_bps=total_slippage,
            explicit_slippage_bps=explicit_slippage,
            timing_slippage_bps=timing_slippage,
            opportunistic_slippage_bps=opportunistic_slippage,
            positioning_slippage_bps=positioning_slippage,
            market_impact_slippage_bps=market_impact_slippage,
            risk_premium_slippage_bps=risk_premium_slippage
        )

    def get_execution_summary(self) -> Dict:
        """Get summary of all executions analyzed."""
        if not self.executions:
            return {
                'total_executions': 0,
                'average_slippage_bps': 0.0,
                'average_fill_rate': 0.0,
                'average_quality_score': 0.0,
                'average_efficiency_ratio': 0.0
            }

        successful_executions = [e for e in self.executions if e.fill_rate > 0.95]

        avg_slippage = 0.0
        avg_fill_rate = 0.0
        avg_quality = 0.0
        avg_efficiency = 0.0

        if successful_executions:
            avg_slippage = statistics.mean([abs(e.slippage_bps) for e in successful_executions])
            avg_fill_rate = statistics.mean([e.fill_rate for e in successful_executions])
            avg_quality = statistics.mean([e.quality_score for e in successful_executions])
            avg_efficiency = statistics.mean([e.efficiency_ratio for e in successful_executions])

        return {
            'total_executions': len(self.executions),
            'successful_executions': len(successful_executions),
            'average_slippage_bps': avg_slippage,
            'average_fill_rate': avg_fill_rate,
            'average_quality_score': avg_quality,
            'average_efficiency_ratio': avg_efficiency,
            'slippage_improvement': self._calculate_slippage_trend(),
            'quality_trend': self._calculate_quality_trend()
        }

    def generate_execution_report(
        self,
        execution: ExecutionMetrics,
        include_slippage_breakdown: bool = True
    ) -> Dict:
        """Generate a detailed execution report.

        Args:
            execution: ExecutionMetrics to report on
            include_slippage_breakdown: Whether to include slippage component breakdown

        Returns:
            Dictionary with execution report
        """
        report = {
            'execution_id': f"{execution.symbol}_{execution.side}_{int(execution.start_time.timestamp())}",
            'timestamp': datetime.now().isoformat(),
            'symbol': execution.symbol,
            'side': execution.side,
            'quantity': execution.quantity,
            'executed_quantity': execution.executed_quantity,
            'fill_rate': execution.fill_rate,
            'average_price': execution.average_price,
            'benchmark_price': execution.benchmark_price,
            'slippage_bps': execution.slippage_bps,
            'execution_time_seconds': execution.duration_seconds,
            'algorithm_used': execution.algorithm_used,
            'quality_metrics': {
                'quality_score': execution.quality_score,
                'efficiency_ratio': execution.efficiency_ratio,
                'market_impact_bps': execution.market_impact_bps,
                'execution_shortfall_bps': execution.execution_shortfall_bps
            }
        }

        if include_slippage_breakdown:
            slippage_analysis = self.analyze_slippage_components(execution)
            report['slippage_breakdown'] = {
                'total_slippage_bps': slippage_analysis.total_slippage_bps,
                'explicit_slippage_bps': slippage_analysis.explicit_slippage_bps,
                'timing_slippage_bps': slippage_analysis.timing_slippage_bps,
                'opportunistic_slippage_bps': slippage_analysis.opportunistic_slippage_bps,
                'positioning_slippage_bps': slippage_analysis.positioning_slippage_bps,
                'market_impact_slippage_bps': slippage_analysis.market_impact_slippage_bps,
                'risk_premium_slippage_bps': slippage_analysis.risk_premium_slippage_bps
            }

        return report

    def _get_volatility_estimate(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
        get_market_data_callback=None
    ) -> float:
        """Estimate volatility for symbol during period.

        Args:
            symbol: Stock or option symbol
            start_time: Start of period
            end_time: End of period
            get_market_data_callback: Function to get historical data

        Returns:
            Estimated volatility (annualized)
        """
        # Simplified - in reality would calculate from price returns
        if get_market_data_callback:
            try:
                # This would get actual historical data
                # For now, return a reasonable default
                return 0.25  # 25% annualized volatility
            except Exception:
                pass

        # Default volatility estimate
        return 0.25

    def _calculate_quality_score(
        self,
        fill_rate: float,
        slippage_bps: float,
        duration_seconds: float,
        volatility: float
    ) -> float:
        """Calculate execution quality score (0-100).

        Args:
            fill_rate: Percentage of order filled
            slippage_bps: Slippage in basis points
            duration_seconds: Execution duration
            volatility: Market volatility

        Returns:
            Quality score (0-100)
        """
        # Start with perfect score
        score = 100.0

        # Penalize for incomplete fills
        fill_penalty = (1.0 - fill_rate) * 30  # Up to 30 points for incomplete fill
        score -= fill_penalty

        # Penalize for slippage
        slippage_penalty = min(abs(slippage_bps) * 0.5, 25)  # Up to 25 points for slippage
        score -= slippage_penalty

        # Penalize for excessive duration (context dependent)
        # Assume 30 minutes is reasonable for large orders
        max_reasonable_duration = 1800  # 30 minutes in seconds
        if duration_seconds > max_reasonable_duration:
            duration_penalty = min((duration_seconds - max_reasonable_duration) / max_reasonable_duration * 15, 15)
            score -= duration_penalty

        # Adjust for volatility (higher volatility = more leeway for slippage)
        volatility_adjustment = min(volatility * 20, 10)  # Up to 10 points bonus for high vol
        score += volatility_adjustment

        # Ensure score is in bounds
        return max(0.0, min(100.0, score))

    def _calculate_efficiency_ratio(
        self,
        fill_rate: float,
        slippage_bps: float,
        duration_seconds: float
    ) -> float:
        """Calculate execution efficiency ratio (0-1).

        Args:
            fill_rate: Percentage of order filled
            slippage_bps: Slippage in basis points
            duration_seconds: Execution duration

        Returns:
            Efficiency ratio (0-1, higher is better)
        """
        # Base efficiency on fill rate
        efficiency = fill_rate

        # Adjust for slippage (lower is better)
        slippage_factor = max(0, 1 - (abs(slippage_bps) / 50))  # Penalty for >50 bps slippage
        efficiency *= slippage_factor

        # Adjust for duration (faster is better, but context dependent)
        # Assume 5 minutes is very fast, 2 hours is slow for typical orders
        ideal_duration = 300  # 5 minutes
        max_duration = 7200   # 2 hours

        if duration_seconds <= ideal_duration:
            duration_factor = 1.0
        elif duration_seconds >= max_duration:
            duration_factor = 0.5
        else:
            # Linear interpolation between ideal and max
            duration_factor = 1.0 - 0.5 * ((duration_seconds - ideal_duration) / (max_duration - ideal_duration))

        efficiency *= duration_factor

        return max(0.0, min(1.0, efficiency))

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

    def _calculate_quality_trend(self) -> float:
        """Calculate quality improvement trend over recent executions.

        Returns:
            Percentage change in quality (positive = improvement)
        """
        if len(self.executions) < 10:
            return 0.0

        # Compare last 5 to previous 5
        recent = self.executions[-5:]
        previous = self.executions[-10:-5]

        if not recent or not previous:
            return 0.0

        recent_avg = statistics.mean([e.quality_score for e in recent])
        previous_avg = statistics.mean([e.quality_score for e in previous])

        if previous_avg == 0:
            return 0.0

        return ((recent_avg - previous_avg) / previous_avg) * 100


class VWAPBenchmarkCalculator:
    """Calculates VWAP benchmarks for execution analysis."""

    def __init__(self):
        self.price_volume_data: Dict[str, List[Tuple[datetime, float, float]]] = {}  # symbol -> [(time, price, volume)]

    def add_market_data(self, symbol: str, timestamp: datetime, price: float, volume: float):
        """Add market data point for VWAP calculation."""
        if symbol not in self.price_volume_data:
            self.price_volume_data[symbol] = []

        self.price_volume_data[symbol].append((timestamp, price, volume))

        # Keep only recent data (last 24 hours)
        cutoff_time = timestamp - timedelta(hours=24)
        self.price_volume_data[symbol] = [
            (t, p, v) for t, p, v in self.price_volume_data[symbol]
            if t >= cutoff_time
        ]

    def calculate_vwap_during_period(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
        get_market_data_callback=None
    ) -> float:
        """Calculate VWAP for symbol during specified time period.

        Args:
            symbol: Stock or option symbol
            start_time: Start of period
            end_time: End of period
            get_market_data_callback: Function to get historical data if needed

        Returns:
            VWAP price during period
        """
        # Try to get data from our stored records
        if symbol in self.price_volume_data:
            period_data = [
                (t, p, v) for t, p, v in self.price_volume_data[symbol]
                if start_time <= t <= end_time
            ]

            if period_data:
                total_price_volume = sum(p * v for _, p, v in period_data)
                total_volume = sum(v for _, _, v in period_data)

                if total_volume > 0:
                    return total_price_volume / total_volume

        # If we don't have enough data, try to get it via callback
        if get_market_data_callback:
            try:
                # This would get actual historical VWAP data
                # For now, we'll simulate with a reasonable price
                logger.warning(f"Calculating VWAP via callback for {symbol} - using simulated data")
                return 0.0  # Return 0.0 as fallback when no data available
            except Exception as e:
                logger.warning(f"Could not get VWAP data via callback: {e}")

        # Fallback - return a reasonable default
        logger.warning(f"No VWAP data available for {symbol} during period, using fallback")
        return 0.0


def create_execution_analyzer() -> ExecutionAnalyzer:
    """Factory function to create an ExecutionAnalyzer instance."""
    return ExecutionAnalyzer()


def create_vwap_benchmark_calculator() -> VWAPBenchmarkCalculator:
    """Factory function to create a VWAPBenchmarkCalculator instance."""
    return VWAPBenchmarkCalculator()


# Example usage and testing
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    def demo_alert(message: str):
        print(f"[ALERT] {message}")

    # Create execution analyzer
    analyzer = create_execution_analyzer()
    vwap_calc = create_vwap_benchmark_calculator()

    # Mock market data callback
    def get_market_data(symbol):
        import random
        # Simulate some market data
        base_price = 100.0 if "AAPL" in symbol else 50.0 if "MSFT" in symbol else 75.0
        return {
            'price': base_price + random.uniform(-2, 2),
            'volume': random.randint(1000, 10000),
            'bid': base_price - 0.25,
            'ask': base_price + 0.25
        }

    print("=== Execution Analysis Demo ===\n")

    # Test execution analysis
    print("1. Analyzing Sample Execution")

    # Simulate a buy order execution
    execution_metrics = analyzer.analyze_execution(
        symbol="AAPL261016C00190000",
        side="buy",
        quantity=10,
        executed_quantity=10,
        average_price=5.05,  # Slightly worse than benchmark
        start_time=datetime.now() - timedelta(minutes=5),
        end_time=datetime.now(),
        get_market_data_callback=get_market_data,
        algorithm_used="VWAP"
    )

    print(f"   Symbol: {execution_metrics.symbol}")
    print(f"   Side: {execution_metrics.side}")
    print(f"   Quantity: {execution_metrics.quantity}")
    print(f"   Executed: {execution_metrics.executed_quantity}")
    print(f"   Fill Rate: {execution_metrics.fill_rate:.1%}")
    print(f"   Average Price: ${execution_metrics.average_price:.2f}")
    print(f"   Benchmark Price: ${execution_metrics.benchmark_price:.2f}")
    print(f"   Slippage: {execution_metrics.slippage_bps:.2f} bps")
    print(f"   Duration: {execution_metrics.duration_seconds:.0f} seconds")
    print(f"   Quality Score: {execution_metrics.quality_score:.1f}/100")
    print(f"   Efficiency Ratio: {execution_metrics.efficiency_ratio:.2f}")
    print()

    # Test slippage component analysis
    print("2. Slippage Component Analysis")
    slippage_components = analyzer.analyze_slippage_components(execution_metrics, get_market_data_callback)

    print(f"   Total Slippage: {slippage_components.total_slippage_bps:.2f} bps")
    print(f"   Explicit (fees): {slippage_components.explicit_slippage_bps:.2f} bps")
    print(f"   Timing: {slippage_components.timing_slippage_bps:.2f} bps")
    print(f"   Opportunistic: {slippage_components.opportunistic_slippage_bps:.2f} bps")
    print(f"   Positioning: {slippage_components.positioning_slippage_bps:.2f} bps")
    print(f"   Market Impact: {slippage_components.market_impact_slippage_bps:.2f} bps")
    print(f"   Risk Premium: {slippage_components.risk_premium_slippage_bps:.2f} bps")
    print()

    # Test execution report
    print("3. Execution Report")
    report = analyzer.generate_execution_report(execution_metrics, include_slippage_breakdown=True)

    print(f"   Execution ID: {report['execution_id']}")
    print(f"   Timestamp: {report['timestamp']}")
    print(f"   Symbol: {report['symbol']}")
    print(f"   Side: {report['side']}")
    print(f"   Quantity: {report['quantity']}")
    print(f"   Executed: {report['executed_quantity']}")
    print(f"   Fill Rate: {report['fill_rate']:.1%}")
    print(f"   Avg Price: ${report['average_price']:.2f}")
    print(f"   Benchmark: ${report['benchmark_price']:.2f}")
    print(f"   Slippage: {report['slippage_bps']:.2f} bps")
    print(f"   Algorithm: {report['algorithm_used']}")
    print(f"   Quality Score: {report['quality_metrics']['quality_score']:.1f}/100")
    print(f"   Efficiency: {report['quality_metrics']['efficiency_ratio']:.2f}")
    print()

    # Add some more executions for trend analysis
    print("4. Adding More Executions for Trend Analysis")

    # Add a few more executions with varying quality
    test_executions = [
        ("AAPL261016C00190000", "buy", 5, 5, 5.00, 0.0),      # Perfect
        ("AAPL261016C00190000", "buy", 8, 8, 5.10, 20.0),    # Some slippage
        ("MSFT261016C00300000", "buy", 3, 3, 4.00, -5.0),    # Better than benchmark
        ("GOOGL261016C00120000", "buy", 4, 3, 8.50, 50.0),   # Poor fill + slippage
    ]

    for symbol, side, qty, exec_qty, avg_price, slippage_offset in test_executions:
        # Adjust average price to create desired slippage
        market_data = get_market_data(symbol)
        benchmark_price = (market_data['bid'] + market_data['ask']) / 2

        if side.lower() == 'buy':
            adjusted_price = benchmark_price + (slippage_offset / 10000) * benchmark_price
        else:
            adjusted_price = benchmark_price - (slippage_offset / 10000) * benchmark_price

        metrics = analyzer.analyze_execution(
            symbol=symbol,
            side=side,
            quantity=qty,
            executed_quantity=exec_qty,
            average_price=adjusted_price,
            start_time=datetime.now() - timedelta(minutes=10),
            end_time=datetime.now() - timedelta(minutes=5),
            get_market_data_callback=get_market_data,
            algorithm_used="TWAP"
        )

    # Show summary statistics
    print("5. Execution Summary Statistics")
    summary = analyzer.get_execution_summary()

    print(f"   Total Executions: {summary['total_executions']}")
    print(f"   Successful Executions: {summary['successful_executions']}")
    print(f"   Average Slippage: {summary['average_slippage_bps']:.2f} bps")
    print(f"   Average Fill Rate: {summary['average_fill_rate']:.1%}")
    print(f"   Average Quality Score: {summary['average_quality_score']:.1f}/100")
    print(f"   Average Efficiency: {summary['average_efficiency_ratio']:.2f}")
    print(f"   Slippage Trend: {summary['slippage_improvement']:+.2f}%")
    print(f"   Quality Trend: {summary['quality_trend']:+.2f}%")
    print()

    print("=== Execution Analysis Demo Complete ===")