"""Phase 11: Smart Order Routing for Autonomous Options Trading System.

This module implements advanced execution algorithms including:
- VWAP (Volume Weighted Average Price) algorithm
- TWAP (Time Weighted Average Price) algorithm
- POV (Percentage of Volume) algorithm
- Smart order routing logic
- Execution quality analysis
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import math
import statistics

# Add project root to path for imports
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
if project_root not in sys.path:
    sys.path.append(project_root)

logger = logging.getLogger(__name__)


class AlgorithmType(Enum):
    """Types of execution algorithms."""
    VWAP = "vwap"
    TWAP = "twap"
    POV = "pov"
    MARKET = "market"
    LIMIT = "limit"


# Alias for backward compatibility
SliceAlgorithm = AlgorithmType


@dataclass
class ExecutionParameters:
    """Parameters for execution algorithms."""
    algorithm_type: AlgorithmType
    start_time: datetime
    end_time: datetime
    participation_rate: Optional[float] = None  # For POV (0.0 to 1.0)
    max_slippage_bps: Optional[float] = None   # Maximum slippage in basis points
    min_fill_size: Optional[int] = None        # Minimum fill size
    max_duration_minutes: Optional[int] = None # Maximum execution duration
    urgency: float = 0.5                       # 0.0 (patient) to 1.0 (urgent)


@dataclass
class ExecutionSlice:
    """A slice of an order to be executed."""
    symbol: str
    quantity: int
    side: str  # 'buy' or 'sell'
    target_price: Optional[float] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)
    executed_quantity: int = 0
    average_price: float = 0.0
    slippage_bps: float = 0.0
    status: str = "pending"  # pending, partial, filled, cancelled


# Alias for backward compatibility
OrderSlice = ExecutionSlice


@dataclass
class ExecutionResult:
    """Result of an execution algorithm."""
    symbol: str
    total_quantity: int
    executed_quantity: int
    remaining_quantity: int
    average_price: float
    slippage_bps: float
    execution_time_seconds: float
    slices: List[ExecutionSlice]
    market_impact_bps: float = 0.0
    success: bool = False
    error_message: Optional[str] = None


class VWAPCalculator:
    """Calculates VWAP and generates execution schedules."""

    def __init__(self, lookback_periods: int = 20):
        self.lookback_periods = lookback_periods
        self.volume_profile: List[Tuple[datetime, float]] = []  # (time, volume)
        self.price_volume: List[Tuple[datetime, float, float]] = []  # (time, price, volume)

    def update_market_data(self, timestamp: datetime, price: float, volume: float):
        """Update with new market data point."""
        self.volume_profile.append((timestamp, volume))
        self.price_volume.append((timestamp, price, volume))

        # Keep only lookback_periods of data
        if len(self.volume_profile) > self.lookback_periods:
            self.volume_profile = self.volume_profile[-self.lookback_periods:]
        if len(self.price_volume) > self.lookback_periods:
            self.price_volume = self.price_volume[-self.lookback_periods:]

    def calculate_vwap(self) -> Optional[float]:
        """Calculate VWAP from stored data."""
        if not self.price_volume:
            return None

        total_price_volume = sum(price * vol for _, price, vol in self.price_volume)
        total_volume = sum(vol for _, _, vol in self.price_volume)

        if total_volume == 0:
            return None

        return total_price_volume / total_volume

    def get_volume_distribution(self) -> List[float]:
        """Get volume distribution for slicing."""
        if not self.volume_profile:
            return []

        volumes = [vol for _, vol in self.volume_profile]
        total_volume = sum(volumes)

        if total_volume == 0:
            return [0.0] * len(volumes)

        return [vol / total_volume for vol in volumes]


class SmartOrderRouter:
    """Smart order routing engine for optimal execution."""

    def __init__(self):
        self.vwap_calculator = VWAPCalculator()
        self.execution_history: List[ExecutionResult] = []

    def execute_vwap(
        self,
        symbol: str,
        total_quantity: int,
        side: str,
        start_time: datetime,
        end_time: datetime,
        get_market_data_callback=None,
        submit_order_callback=None
    ) -> ExecutionResult:
        """Execute order using VWAP algorithm.

        Args:
            symbol: Stock or option symbol
            total_quantity: Total quantity to execute
            side: 'buy' or 'sell'
            start_time: Start time for execution
            end_time: End time for execution
            get_market_data_callback: Function to get current market data
            submit_order_callback: Function to submit orders

        Returns:
            ExecutionResult with execution details
        """
        start_execution = datetime.now()
        logger.info(f"Starting VWAP execution for {symbol}: {total_quantity} {side}")

        if total_quantity <= 0:
            return ExecutionResult(
                symbol=symbol,
                total_quantity=total_quantity,
                executed_quantity=0,
                remaining_quantity=total_quantity,
                average_price=0.0,
                slippage_bps=0.0,
                execution_time_seconds=0.0,
                slices=[],
                success=False,
                error_message="Invalid quantity"
            )

        # Initialize execution tracking
        remaining_quantity = total_quantity
        executed_quantity = 0
        total_cost = 0.0
        slices = []

        # Divide execution period into intervals
        duration = (end_time - start_time).total_seconds()
        num_intervals = max(1, int(duration / 300))  # 5-minute intervals
        interval_duration = duration / num_intervals if num_intervals > 0 else 0

        # Get historical volume profile for distribution
        volume_distribution = self.vwap_calculator.get_volume_distribution()
        if not volume_distribution:
            # Fallback to equal distribution
            volume_distribution = [1.0 / num_intervals] * num_intervals

        try:
            # Execute in intervals based on volume profile
            for i in range(num_intervals):
                if remaining_quantity <= 0:
                    break

                interval_start = start_time + timedelta(seconds=i * interval_duration)
                interval_end = interval_start + timedelta(seconds=interval_duration)

                # Skip if we're past the interval start
                if datetime.now() < interval_start:
                    # Wait until interval start (in real implementation)
                    pass

                # Calculate quantity for this interval
                interval_quantity = int(total_quantity * volume_distribution[i])
                interval_quantity = min(interval_quantity, remaining_quantity)

                if interval_quantity <= 0:
                    continue

                # Get current market data (simplified)
                if get_market_data_callback:
                    try:
                        market_data = get_market_data_callback(symbol)
                        current_price = market_data.get('price', 0.0) if market_data else 0.0
                    except Exception as e:
                        logger.warning(f"Could not get market data: {e}")
                        current_price = 0.0
                else:
                    current_price = 0.0

                # Create execution slice
                slice_obj = ExecutionSlice(
                    symbol=symbol,
                    quantity=interval_quantity,
                    side=side,
                    target_price=current_price,
                    timestamp=datetime.now()
                )

                # Simulate execution (in real implementation, would use submit_order_callback)
                executed_qty = interval_quantity  # Assume full fill for simulation
                avg_price = current_price if current_price > 0 else 10.0  # Fallback price

                slice_obj.executed_quantity = executed_qty
                slice_obj.average_price = avg_price
                slice_obj.status = "filled"

                # Update tracking
                executed_quantity += executed_qty
                remaining_quantity -= executed_qty
                total_cost += executed_qty * avg_price

                slices.append(slice_obj)

                logger.debug(f"VWAP slice {i+1}: {executed_qty} @ ${avg_price:.2f}")

            # Calculate final metrics
            average_price = total_cost / executed_quantity if executed_quantity > 0 else 0.0
            execution_time = (datetime.now() - start_execution).total_seconds()

            result = ExecutionResult(
                symbol=symbol,
                total_quantity=total_quantity,
                executed_quantity=executed_quantity,
                remaining_quantity=remaining_quantity,
                average_price=average_price,
                slippage_bps=0.0,  # Would calculate vs benchmark in real implementation
                execution_time_seconds=execution_time,
                slices=slices,
                success=(executed_quantity == total_quantity),
                error_message=None if executed_quantity == total_quantity else
                           f"Only executed {executed_quantity}/{total_quantity}"
            )

            self.execution_history.append(result)
            logger.info(f"VWAP execution completed: {executed_quantity}/{total_quantity} @ ${average_price:.2f}")
            return result

        except Exception as e:
            logger.error(f"Error in VWAP execution: {e}")
            return ExecutionResult(
                symbol=symbol,
                total_quantity=total_quantity,
                executed_quantity=executed_quantity,
                remaining_quantity=remaining_quantity,
                average_price=total_cost / executed_quantity if executed_quantity > 0 else 0.0,
                slippage_bps=0.0,
                execution_time_seconds=(datetime.now() - start_execution).total_seconds(),
                slices=slices,
                success=False,
                error_message=str(e)
            )

    def execute_twap(
        self,
        symbol: str,
        total_quantity: int,
        side: str,
        start_time: datetime,
        end_time: datetime,
        get_market_data_callback=None,
        submit_order_callback=None
    ) -> ExecutionResult:
        """Execute order using TWAP algorithm."""
        logger.info(f"Starting TWAP execution for {symbol}: {total_quantity} {side}")

        if total_quantity <= 0:
            return ExecutionResult(
                symbol=symbol,
                total_quantity=total_quantity,
                executed_quantity=0,
                remaining_quantity=total_quantity,
                average_price=0.0,
                slippage_bps=0.0,
                execution_time_seconds=0.0,
                slices=[],
                success=False,
                error_message="Invalid quantity"
            )

        # TWAP divides time equally, unlike VWAP which uses volume profile
        start_execution = datetime.now()
        remaining_quantity = total_quantity
        executed_quantity = 0
        total_cost = 0.0
        slices = []

        # Divide execution period into equal time intervals
        duration = (end_time - start_time).total_seconds()
        num_intervals = max(1, int(duration / 300))  # 5-minute intervals
        quantity_per_interval = total_quantity // num_intervals
        remainder = total_quantity % num_intervals

        try:
            for i in range(num_intervals):
                if remaining_quantity <= 0:
                    break

                # Distribute remainder across first few intervals
                interval_quantity = quantity_per_interval + (1 if i < remainder else 0)
                interval_quantity = min(interval_quantity, remaining_quantity)

                if interval_quantity <= 0:
                    continue

                # Get current market data
                if get_market_data_callback:
                    try:
                        market_data = get_market_data_callback(symbol)
                        current_price = market_data.get('price', 0.0) if market_data else 0.0
                    except Exception as e:
                        logger.warning(f"Could not get market data: {e}")
                        current_price = 0.0
                else:
                    current_price = 0.0

                # Create execution slice
                slice_obj = ExecutionSlice(
                    symbol=symbol,
                    quantity=interval_quantity,
                    side=side,
                    target_price=current_price,
                    timestamp=datetime.now()
                )

                # Simulate execution
                executed_qty = interval_quantity
                avg_price = current_price if current_price > 0 else 10.0

                slice_obj.executed_quantity = executed_qty
                slice_obj.average_price = avg_price
                slice_obj.status = "filled"

                # Update tracking
                executed_quantity += executed_qty
                remaining_quantity -= executed_qty
                total_cost += executed_qty * avg_price

                slices.append(slice_obj)

                logger.debug(f"TWAP slice {i+1}: {executed_qty} @ ${avg_price:.2f}")

            # Calculate final metrics
            average_price = total_cost / executed_quantity if executed_quantity > 0 else 0.0
            execution_time = (datetime.now() - start_execution).total_seconds()

            result = ExecutionResult(
                symbol=symbol,
                total_quantity=total_quantity,
                executed_quantity=executed_quantity,
                remaining_quantity=remaining_quantity,
                average_price=average_price,
                slippage_bps=0.0,
                execution_time_seconds=execution_time,
                slices=slices,
                success=(executed_quantity == total_quantity),
                error_message=None if executed_quantity == total_quantity else
                           f"Only executed {executed_quantity}/{total_quantity}"
            )

            self.execution_history.append(result)
            logger.info(f"TWAP execution completed: {executed_quantity}/{total_quantity} @ ${average_price:.2f}")
            return result

        except Exception as e:
            logger.error(f"Error in TWAP execution: {e}")
            return ExecutionResult(
                symbol=symbol,
                total_quantity=total_quantity,
                executed_quantity=executed_quantity,
                remaining_quantity=remaining_quantity,
                average_price=total_cost / executed_quantity if executed_quantity > 0 else 0.0,
                slippage_bps=0.0,
                execution_time_seconds=(datetime.now() - start_execution).total_seconds(),
                slices=slices,
                success=False,
                error_message=str(e)
            )

    def execute_pov(
        self,
        symbol: str,
        total_quantity: int,
        side: str,
        participation_rate: float,
        get_market_data_callback=None,
        submit_order_callback=None
    ) -> ExecutionResult:
        """Execute order using POV (Percentage of Volume) algorithm.

        Args:
            symbol: Stock or option symbol
            total_quantity: Total quantity to execute
            side: 'buy' or 'sell'
            participation_rate: Percentage of market volume to participate (0.0 to 1.0)
            get_market_data_callback: Function to get current market data including volume
            submit_order_callback: Function to submit orders

        Returns:
            ExecutionResult with execution details
        """
        logger.info(f"Starting POV execution for {symbol}: {total_quantity} {side} @ {participation_rate*100}%")

        if total_quantity <= 0:
            return ExecutionResult(
                symbol=symbol,
                total_quantity=total_quantity,
                executed_quantity=0,
                remaining_quantity=total_quantity,
                average_price=0.0,
                slippage_bps=0.0,
                execution_time_seconds=0.0,
                slices=[],
                success=False,
                error_message="Invalid quantity"
            )

        if not 0.0 <= participation_rate <= 1.0:
            return ExecutionResult(
                symbol=symbol,
                total_quantity=total_quantity,
                executed_quantity=0,
                remaining_quantity=total_quantity,
                average_price=0.0,
                slippage_bps=0.0,
                execution_time_seconds=0.0,
                slices=[],
                success=False,
                error_message="Participation rate must be between 0.0 and 1.0"
            )

        start_execution = datetime.now()
        remaining_quantity = total_quantity
        executed_quantity = 0
        total_cost = 0.0
        slices = []

        try:
            # In POV, we execute based on market volume
            # We'll simulate checking market volume periodically
            max_iterations = 100  # Prevent infinite loop
            iteration = 0

            while remaining_quantity > 0 and iteration < max_iterations:
                iteration += 1

                # Get current market data including volume
                if get_market_data_callback:
                    try:
                        market_data = get_market_data_callback(symbol)
                        current_price = market_data.get('price', 0.0)
                        current_volume = market_data.get('volume', 0)
                    except Exception as e:
                        logger.warning(f"Could not get market data: {e}")
                        current_price = 0.0
                        current_volume = 0
                else:
                    current_price = 0.0
                    current_volume = 0

                # Calculate target quantity based on participation rate
                if current_volume > 0:
                    target_quantity = int(current_volume * participation_rate)
                else:
                    target_quantity = 0

                # Don't exceed remaining quantity
                target_quantity = min(target_quantity, remaining_quantity)

                # Minimum quantity to avoid too small slices
                if target_quantity < 1:
                    # Wait a bit and try again (in real implementation)
                    # For simulation, we'll break if no volume
                    if current_volume == 0:
                        break
                    target_quantity = 1  # Minimum execution

                if target_quantity <= 0:
                    # No volume to participate in, wait
                    # In real implementation, we'd sleep and retry
                    break

                # Create execution slice
                slice_obj = ExecutionSlice(
                    symbol=symbol,
                    quantity=target_quantity,
                    side=side,
                    target_price=current_price,
                    timestamp=datetime.now()
                )

                # Simulate execution
                executed_qty = target_quantity
                avg_price = current_price if current_price > 0 else 10.0

                slice_obj.executed_quantity = executed_qty
                slice_obj.average_price = avg_price
                slice_obj.status = "filled"

                # Update tracking
                executed_quantity += executed_qty
                remaining_quantity -= executed_qty
                total_cost += executed_qty * avg_price

                slices.append(slice_obj)

                logger.debug(f"POV slice: {executed_qty} @ ${avg_price:.2f} (Vol: {current_volume}, Rate: {participation_rate*100:.1f}%)")

                # If we've executed everything, break
                if remaining_quantity <= 0:
                    break

            # Calculate final metrics
            average_price = total_cost / executed_quantity if executed_quantity > 0 else 0.0
            execution_time = (datetime.now() - start_execution).total_seconds()

            result = ExecutionResult(
                symbol=symbol,
                total_quantity=total_quantity,
                executed_quantity=executed_quantity,
                remaining_quantity=remaining_quantity,
                average_price=average_price,
                slippage_bps=0.0,
                execution_time_seconds=execution_time,
                slices=slices,
                success=(executed_quantity == total_quantity),
                error_message=None if executed_quantity == total_quantity else
                           f"Only executed {executed_quantity}/{total_quantity}"
            )

            self.execution_history.append(result)
            logger.info(f"POV execution completed: {executed_quantity}/{total_quantity} @ ${average_price:.2f}")
            return result

        except Exception as e:
            logger.error(f"Error in POV execution: {e}")
            return ExecutionResult(
                symbol=symbol,
                total_quantity=total_quantity,
                executed_quantity=executed_quantity,
                remaining_quantity=remaining_quantity,
                average_price=total_cost / executed_quantity if executed_quantity > 0 else 0.0,
                slippage_bps=0.0,
                execution_time_seconds=(datetime.now() - start_execution).total_seconds(),
                slices=slices,
                success=False,
                error_message=str(e)
            )

    def get_execution_stats(self) -> Dict:
        """Get statistics about past executions."""
        if not self.execution_history:
            return {
                'total_executions': 0,
                'successful_executions': 0,
                'average_slippage_bps': 0.0,
                'average_execution_time_seconds': 0.0
            }

        successful = [ex for ex in self.execution_history if ex.success]
        total_executions = len(self.execution_history)
        successful_executions = len(successful)

        avg_slippage = 0.0
        avg_time = 0.0

        if successful:
            avg_slippage = statistics.mean([ex.slippage_bps for ex in successful if ex.slippage_bps != 0])
            avg_time = statistics.mean([ex.execution_time_seconds for ex in successful])

        return {
            'total_executions': total_executions,
            'successful_executions': successful_executions,
            'success_rate': successful_executions / total_executions if total_executions > 0 else 0.0,
            'average_slippage_bps': avg_slippage,
            'average_execution_time_seconds': avg_time,
            'recent_executions': len([ex for ex in self.execution_history
                                    if (datetime.now() - datetime.fromisoformat(ex.slices[0].timestamp.isoformat())
                                        if ex.slices else datetime.min).total_seconds() < 3600])  # Last hour
        }


class ExecutionQualityAnalyzer:
    """Analyzes execution quality and measures slippage."""

    def __init__(self):
        self.execution_records: List[Dict] = []

    def calculate_slippage(
        self,
        execution_result: ExecutionResult,
        benchmark_price: float,
        side: str
    ) -> float:
        """Calculate slippage in basis points.

        Args:
            execution_result: Result from execution algorithm
            benchmark_price: Benchmark price (e.g., arrival price, VWAP)
            side: 'buy' or 'sell'

        Returns:
            Slippage in basis points (positive = worse than benchmark)
        """
        if execution_result.executed_quantity == 0 or benchmark_price == 0:
            return 0.0

        avg_price = execution_result.average_price

        if side.lower() == 'buy':
            # For buys: slippage = (avg_price - benchmark) / benchmark * 10000
            slippage = ((avg_price - benchmark_price) / benchmark_price) * 10000
        else:  # sell
            # For sells: slippage = (benchmark - avg_price) / benchmark * 10000
            slippage = ((benchmark_price - avg_price) / benchmark_price) * 10000

        return slippage

    def analyze_execution_quality(
        self,
        execution_result: ExecutionResult,
        market_data_during_execution: List[Dict] = None
    ) -> Dict:
        """Analyze execution quality metrics.

        Args:
            execution_result: Result from execution algorithm
            market_data_during_execution: Market data during execution period

        Returns:
            Dictionary with quality metrics
        """
        if execution_result.executed_quantity == 0:
            return {
                'slippage_bps': 0.0,
                'market_impact_bps': 0.0,
                'fill_rate': 0.0,
                'execution_shortfall_bps': 0.0,
                'quality_score': 0.0
            }

        # Calculate basic metrics
        fill_rate = execution_result.executed_quantity / execution_result.total_quantity

        # Calculate slippage vs VWAP if we have market data
        vwap_price = self._calculate_vwap_from_market_data(market_data_during_execution) if market_data_during_execution else 0.0
        slippage_bps = 0.0

        if vwap_price > 0:
            side = execution_result.slices[0].side if execution_result.slices else 'buy'
            slippage_bps = self.calculate_slippage(execution_result, vwap_price, side)

        # Estimate market impact (simplified)
        market_impact_bps = abs(slippage_bps) * 0.5  # Assume half of slippage is market impact

        # Execution shortfall vs arrival price (would need arrival price)
        execution_shortfall_bps = slippage_bps  # Simplified

        # Quality score (0-100, higher is better)
        # Penalize for slippage, reward for high fill rate
        slippage_penalty = min(abs(slippage_bps) * 2, 50)  # Cap penalty at 50 points
        fill_rate_reward = fill_rate * 50  # Up to 50 points for fill rate
        quality_score = max(0, 100 - slippage_penalty + fill_rate_reward - 50)  # Normalize to 0-100

        return {
            'slippage_bps': slippage_bps,
            'market_impact_bps': market_impact_bps,
            'fill_rate': fill_rate,
            'execution_shortfall_bps': execution_shortfall_bps,
            'quality_score': min(100, max(0, quality_score))
        }

    def _calculate_vwap_from_market_data(self, market_data: List[Dict]) -> float:
        """Calculate VWAP from market data points.

        Args:
            market_data: List of dicts with 'price' and 'volume' keys

        Returns:
            VWAP price
        """
        if not market_data:
            return 0.0

        total_price_volume = 0.0
        total_volume = 0.0

        for data_point in market_data:
            price = data_point.get('price', 0.0)
            volume = data_point.get('volume', 0.0)

            if price > 0 and volume >= 0:
                total_price_volume += price * volume
                total_volume += volume

        return total_price_volume / total_volume if total_volume > 0 else 0.0

    def record_execution(self, execution_result: ExecutionResult, market_data: List[Dict] = None):
        """Record an execution for quality analysis."""
        quality_metrics = self.analyze_execution_quality(execution_result, market_data)

        record = {
            'timestamp': datetime.now().isoformat(),
            'symbol': execution_result.symbol,
            'algorithm_type': 'unknown',  # Would be set by caller
            'total_quantity': execution_result.total_quantity,
            'executed_quantity': execution_result.executed_quantity,
            'fill_rate': execution_result.executed_quantity / execution_result.total_quantity if execution_result.total_quantity > 0 else 0.0,
            'average_price': execution_result.average_price,
            'slippage_bps': quality_metrics['slippage_bps'],
            'market_impact_bps': quality_metrics['market_impact_bps'],
            'quality_score': quality_metrics['quality_score'],
            'success': execution_result.success
        }

        self.execution_records.append(record)

        # Keep only last 1000 records
        if len(self.execution_records) > 1000:
            self.execution_records = self.execution_records[-1000:]

    def get_quality_stats(self) -> Dict:
        """Get execution quality statistics."""
        if not self.execution_records:
            return {
                'total_records': 0,
                'average_slippage_bps': 0.0,
                'average_quality_score': 0.0,
                'average_fill_rate': 0.0
            }

        successful_records = [r for r in self.execution_records if r['success']]

        avg_slippage = 0.0
        avg_quality = 0.0
        avg_fill_rate = 0.0

        if successful_records:
            avg_slippage = statistics.mean([r['slippage_bps'] for r in successful_records])
            avg_quality = statistics.mean([r['quality_score'] for r in successful_records])
            avg_fill_rate = statistics.mean([r['fill_rate'] for r in successful_records])

        return {
            'total_records': len(self.execution_records),
            'successful_records': len(successful_records),
            'success_rate': len(successful_records) / len(self.execution_records) if self.execution_records else 0.0,
            'average_slippage_bps': avg_slippage,
            'average_quality_score': avg_quality,
            'average_fill_rate': avg_fill_rate
        }


def create_smart_order_router() -> SmartOrderRouter:
    """Factory function to create a SmartOrderRouter instance."""
    return SmartOrderRouter()


def create_execution_quality_analyzer() -> ExecutionQualityAnalyzer:
    """Factory function to create an ExecutionQualityAnalyzer instance."""
    return ExecutionQualityAnalyzer()


# Example usage and testing
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    def demo_alert(message: str):
        print(f"[ALERT] {message}")

    # Create smart order router
    router = create_smart_order_router()
    analyzer = create_execution_quality_analyzer()

    # Mock market data callback
    def get_market_data(symbol):
        import random
        return {
            'price': 100.0 + random.uniform(-2, 2),
            'volume': random.randint(1000, 10000)
        }

    # Mock submit order callback
    def submit_order(symbol, quantity, side, order_type, price=None):
        class MockOrder:
            def __init__(self):
                self.id = f"mock_{symbol}_{datetime.now().timestamp()}"
        return True, None, MockOrder()

    print("=== Smart Order Router Demo ===\n")

    # Test VWAP execution
    print("1. Testing VWAP Algorithm")
    start_time = datetime.now()
    end_time = start_time + timedelta(minutes=30)

    vwap_result = router.execute_vwap(
        symbol="AAPL261016C00190000",
        total_quantity=10,
        side="buy",
        start_time=start_time,
        end_time=end_time,
        get_market_data_callback=get_market_data,
        submit_order_callback=submit_order
    )

    print(f"   Result: {vwap_result.executed_quantity}/{vwap_result.total_quantity} filled")
    print(f"   Average Price: ${vwap_result.average_price:.2f}")
    print(f"   Success: {vwap_result.success}")

    # Analyze execution quality
    market_data_during = [
        {'price': 100.0 + i*0.1, 'volume': 1000 + i*100}
        for i in range(20)
    ]
    quality_metrics = analyzer.analyze_execution_quality(vwap_result, market_data_during)
    print(f"   Slippage: {quality_metrics['slippage_bps']:.2f} bps")
    print(f"   Quality Score: {quality_metrics['quality_score']:.1f}/100\n")

    # Test TWAP execution
    print("2. Testing TWAP Algorithm")
    twap_result = router.execute_twap(
        symbol="MSFT261016C00300000",
        total_quantity=5,
        side="buy",
        start_time=start_time,
        end_time=end_time,
        get_market_data_callback=get_market_data,
        submit_order_callback=submit_order
    )

    print(f"   Result: {twap_result.executed_quantity}/{twap_result.total_quantity} filled")
    print(f"   Average Price: ${twap_result.average_price:.2f}")
    print(f"   Success: {twap_result.success}\n")

    # Test POV execution
    print("3. Testing POV Algorithm")
    pov_result = router.execute_pov(
        symbol="GOOGL261016C00120000",
        total_quantity=8,
        side="buy",
        participation_rate=0.1,  # 10% of volume
        get_market_data_callback=get_market_data,
        submit_order_callback=submit_order
    )

    print(f"   Result: {pov_result.executed_quantity}/{pov_result.total_quantity} filled")
    print(f"   Average Price: ${pov_result.average_price:.2f}")
    print(f"   Success: {pov_result.success}\n")

    # Show statistics
    print("4. Execution Statistics")
    stats = router.get_execution_stats()
    print(f"   Total Executions: {stats['total_executions']}")
    print(f"   Successful Executions: {stats['successful_executions']}")
    print(f"   Success Rate: {stats['success_rate']:.1%}")

    quality_stats = analyzer.get_quality_stats()
    print(f"   Quality Records: {quality_stats['total_records']}")
    print(f"   Average Slippage: {quality_stats['average_slippage_bps']:.2f} bps")
    print(f"   Average Quality Score: {quality_stats['average_quality_score']:.1f}/100")

    print("\n=== Smart Order Router Demo Complete ===")