"""Phase 11: Adaptive Execution for Autonomous Options Trading System.

This module provides adaptive execution capabilities including:
- Market condition detection and adaptation
- Volatility-based algorithm selection
- Liquidity-aware execution
- Time-of-day execution optimization
- Dynamic parameter adjustment
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


class MarketCondition(Enum):
    """Market condition classifications."""
    LIQUID = "liquid"          # High volume, tight spreads
    NORMAL = "normal"          # Typical market conditions
    ILLIQUID = "illiquid"      # Low volume, wide spreads
    VOLATILE = "volatile"      # High volatility
    QUIET = "quiet"            # Low volatility, low volume
    TRADING = "trading"        # Strong directional movement
    RANGE_BOUND = "range_bound" # Trading in a range
    PRE_MARKET = "pre_market"  # Before regular trading hours
    POST_MARKET = "post_market" # After regular trading hours
    MARKET_OPEN = "market_open" # Market open period
    MARKET_CLOSE = "market_close" # Market close period
    LUNCH = "lunch"            # Lunch period (lower liquidity)


class ExecutionUrgency(Enum):
    """Execution urgency levels."""
    PATIENT = "patient"        # Can wait for better prices
    NORMAL = "normal"          # Standard urgency
    URGENT = "urgent"          # Need to execute soon
    FORCE = "force"            # Must execute immediately


@dataclass
class MarketConditions:
    """Container for current market condition data."""
    symbol: str
    timestamp: datetime

    # Liquidity metrics
    volume_ratio: float = 1.0              # Volume vs average
    spread_bps: float = 10.0               # Bid-ask spread in basis points
    depth_imbalance: float = 0.0           # Order book imbalance (-1 to 1)

    # Volatility metrics
    volatility: float = 0.25               # Annualized volatility
    volatility_change: float = 0.0         # Change in volatility

    # Price metrics
    price_momentum: float = 0.0            # Recent price momentum
    price_vs_vwap: float = 0.0             # Price vs VWAP deviation

    # Time-based metrics
    time_of_day: str = "unknown"           # Time of day classification
    minutes_to_open: Optional[float] = None # Minutes to market open
    minutes_to_close: Optional[float] = None # Minutes to market close

    # Derived metrics
    liquidity_score: float = 0.5           # 0-1 score (higher = more liquid)
    volatility_score: float = 0.5          # 0-1 score (higher = more volatile)
    condition: MarketCondition = MarketCondition.NORMAL

    def __post_init__(self):
        # Calculate derived scores
        self.liquidity_score = self._calculate_liquidity_score()
        self.volatility_score = self._calculate_volatility_score()
        self.condition = self._classify_condition()

    def _calculate_liquidity_score(self) -> float:
        """Calculate liquidity score based on volume ratio and spread.

        Returns:
            Liquidity score between 0 and 1 (higher = more liquid)
        """
        # Higher volume ratio = more liquid
        volume_score = min(self.volume_ratio / 2.0, 1.0)  # Normalize to 0-1, cap at 2x average volume

        # Lower spread = more liquid
        spread_score = max(0.0, 1.0 - (self.spread_bps / 50.0))  # Normalize to 0-1, zero at 50 bps spread

        # Combine scores (weighted average)
        return (volume_score * 0.6) + (spread_score * 0.4)

    def _calculate_volatility_score(self) -> float:
        """Calculate volatility score based on volatility.

        Returns:
            Volatility score between 0 and 1 (higher = more volatile)
        """
        # Higher volatility = higher score
        # Normalize assuming typical volatility range of 0.1 to 0.8 (10% to 80%)
        return min(max(self.volatility - 0.1, 0.0) / 0.7, 1.0)

    def _classify_condition(self) -> MarketCondition:
        """Classify market condition based on liquidity and volatility scores.

        Returns:
            MarketCondition enum representing the current market condition
        """
        # Simple classification based on liquidity and volatility scores
        liquidity = self.liquidity_score
        volatility = self.volatility_score

        # Define thresholds
        high_liquidity_threshold = 0.7
        low_liquidity_threshold = 0.3
        high_volatility_threshold = 0.7
        low_volatility_threshold = 0.3

        # Classify based on combinations
        if volatility >= high_volatility_threshold:
            if liquidity >= high_liquidity_threshold:
                return MarketCondition.VOLATILE  # High volatility, high liquidity
            else:
                return MarketCondition.VOLATILE  # High volatility, low liquidity -> still volatile
        elif volatility <= low_volatility_threshold:
            if liquidity >= high_liquidity_threshold:
                return MarketCondition.LIQUID  # Low volatility, high liquidity
            else:
                return MarketCondition.ILLIQUID  # Low volatility, low liquidity -> illiquid
        else:
            # Medium volatility
            if liquidity >= high_liquidity_threshold:
                return MarketCondition.NORMAL  # Medium volatility, high liquidity
            elif liquidity <= low_liquidity_threshold:
                return MarketCondition.ILLIQUID  # Medium volatility, low liquidity
            else:
                return MarketCondition.NORMAL  # Default to normal


class AdaptiveExecutionEngine:
    """Adaptive execution engine that adjusts strategy based on market conditions."""

    def __init__(self):
        self.market_history: Dict[str, List[MarketConditions]] = {}
        self.latest_market_data: Dict[str, Dict] = {}  # Store latest market data for each symbol
        self.adaptation_rules: List[Dict] = []
        self._initialize_adaptation_rules()

    def update_market_data(self, symbol: str, market_data: Dict):
        """Update market data for a symbol.

        Args:
            symbol: Stock or option symbol
            market_data: Dictionary containing market data (price, volume, etc.)
        """
        self.latest_market_data[symbol] = market_data

        # Also assess and store market conditions for historical tracking
        try:
            # Create simple callbacks that return the stored data
            def get_market_data_callback(sym):
                return self.latest_market_data.get(sym, {}) if sym == symbol else {}

            def get_volume_data_callback(sym):
                # For now, reuse market data as volume data - in reality this might be separate
                return self.latest_market_data.get(sym, {}) if sym == symbol else {}

            # Assess market conditions and store in history
            self.assess_market_conditions(
                symbol,
                get_market_data_callback=get_market_data_callback,
                get_volume_data_callback=get_volume_data_callback
            )
        except Exception as e:
            logger.warning(f"Could not assess market conditions for {symbol}: {e}")

    def detect_market_condition(self, symbol: str) -> MarketCondition:
        """Detect current market condition for a symbol based on latest data.

        Args:
            symbol: Stock or option symbol

        Returns:
            MarketCondition enum representing current market condition
        """
        # If we have market data for this symbol, assess current conditions
        if symbol in self.latest_market_data:
            market_data = self.latest_market_data[symbol]

            # Create simple callbacks that return the stored data
            def get_market_data_callback(sym):
                return self.latest_market_data.get(sym, {}) if sym == symbol else {}

            def get_volume_data_callback(sym):
                # For now, reuse market data as volume data - in reality this might be separate
                return self.latest_market_data.get(sym, {}) if sym == symbol else {}

            # Assess and return current market conditions
            conditions = self.assess_market_conditions(
                symbol,
                get_market_data_callback=get_market_data_callback,
                get_volume_data_callback=get_volume_data_callback
            )
            return conditions.condition
        else:
            # No data available, return unknown condition
            return MarketCondition.UNKNOWN

    def get_execution_parameters(self, symbol: str) -> Dict:
        """Get recommended execution parameters for a symbol based on current market conditions.

        Args:
            symbol: Stock or option symbol

        Returns:
            Dictionary with execution parameters (algorithm, urgency, etc.)
        """
        # Detect current market condition
        condition = self.detect_market_condition(symbol)

        # Get base parameters (these would typically come from configuration or defaults)
        base_params = {
            'algorithm': 'TWAP',  # Default algorithm
            'urgency': ExecutionUrgency.NORMAL,
            'participation_rate': 0.1,
            'max_slippage_bps': 20.0,
            'time_in_force': 'day'
        }

        # If we have adaptation rules, apply them based on market condition
        if self.adaptation_rules:
            for rule in self.adaptation_rules:
                if rule.get('condition') == condition:
                    # Apply adaptations from matching rule
                    adapted_params = base_params.copy()

                    # Adjust urgency if specified
                    if 'urgency_adjustment' in rule:
                        # This is simplified - in reality we'd adjust the urgency level
                        pass

                    # Adjust participation rate if specified
                    if 'participation_rate_adjustment' in rule:
                        adjustment = rule['participation_rate_adjustment']
                        adapted_params['participation_rate'] = max(
                            0.01,
                            min(0.5, base_params['participation_rate'] + adjustment)
                        )

                    # Prefer specific algorithms if specified
                    if 'preferred_algorithms' in rule:
                        adapted_params['algorithm'] = rule['preferred_algorithms'][0]

                    # Avoid specific algorithms if specified
                    if 'avoid_algorithms' in rule:
                        if base_params['algorithm'] in rule['avoid_algorithms']:
                            adapted_params['algorithm'] = 'TWAP'  # Fallback

                    return adapted_params

        # Return base parameters if no matching adaptation rules
        return base_params

    def update_market_data(self, symbol: str, market_data: Dict):
        """Update market data for a symbol.

        Args:
            symbol: Stock or option symbol
            market_data: Dictionary containing market data (price, volume, etc.)
        """
        self.latest_market_data[symbol] = market_data

        # Also assess and store market conditions for historical tracking
        try:
            # Create simple callbacks that return the stored data
            def get_market_data_callback(sym):
                return self.latest_market_data.get(sym, {}) if sym == symbol else {}

            def get_volume_data_callback(sym):
                # For now, reuse market data as volume data - in reality this might be separate
                return self.latest_market_data.get(sym, {}) if sym == symbol else {}

            # Assess market conditions and store in history
            self.assess_market_conditions(
                symbol,
                get_market_data_callback=get_market_data_callback,
                get_volume_data_callback=get_volume_data_callback
            )
        except Exception as e:
            logger.warning(f"Could not assess market conditions for {symbol}: {e}")

    def _initialize_adaptation_rules(self):
        """Initialize default adaptation rules."""
        self.adaptation_rules = [
            # High volatility - use more patient algorithms
            {
                'condition': MarketCondition.VOLATILE,
                'urgency_threshold': ExecutionUrgency.NORMAL,
                'preferred_algorithms': ['TWAP', 'VWAP'],
                'avoid_algorithms': ['POV_AGGRESSIVE'],
                'urgency_adjustment': -0.5,  # Reduce urgency
                'participation_rate_adjustment': -0.2  # Reduce participation
            },
            # Low liquidity - use more patient execution
            {
                'condition': MarketCondition.ILLIQUID,
                'urgency_threshold': ExecutionUrgency.NORMAL,
                'preferred_algorithms': ['TWAP', 'ICEBERG'],
                'avoid_algorithms': ['POV', 'MARKET'],
                'urgency_adjustment': -0.3,
                'participation_rate_adjustment': -0.4
            },
            # High liquidity - can be more aggressive
            {
                'condition': MarketCondition.LIQUID,
                'urgency_threshold': ExecutionUrgency.PATIENT,
                'preferred_algorithms': ['VWAP', 'POV'],
                'avoid_algorithms': [],
                'urgency_adjustment': 0.2,  # Increase urgency
                'participation_rate_adjustment': 0.1  # Increase participation
            },
            # Market open/close - be more careful
            {
                'condition': [MarketCondition.MARKET_OPEN, MarketCondition.MARKET_CLOSE],
                'urgency_threshold': ExecutionUrgency.NORMAL,
                'preferred_algorithms': ['TWAP', 'VWAP'],
                'avoid_algorithms': ['MARKET_AGGRESSIVE'],
                'urgency_adjustment': -0.4,
                'participation_rate_adjustment': -0.3
            },
            # Quiet market - can use more aggressive algorithms
            {
                'condition': MarketCondition.QUIET,
                'urgency_threshold': ExecutionUrgency.PATIENT,
                'preferred_algorithms': ['VWAP', 'POV_LITE'],
                'avoid_algorithms': [],
                'urgency_adjustment': 0.1,
                'participation_rate_adjustment': 0.05
            }
        ]

    def assess_market_conditions(
        self,
        symbol: str,
        get_market_data_callback=None,
        get_volume_data_callback=None
    ) -> MarketConditions:
        """Assess current market conditions for a symbol.

        Args:
            symbol: Stock or option symbol
            get_market_data_callback: Function to get current market data
            get_volume_data_callback: Function to get volume data

        Returns:
            MarketConditions object with current state
        """
        now = datetime.now()

        # Get market data
        market_data = {}
        volume_data = {}

        if get_market_data_callback:
            try:
                market_data = get_market_data_callback(symbol) or {}
            except Exception as e:
                logger.warning(f"Could not get market data for {symbol}: {e}")

        if get_volume_data_callback:
            try:
                volume_data = get_volume_data_callback(symbol) or {}
            except Exception as e:
                logger.warning(f"Could not get volume data for {symbol}: {e}")

        # Extract key metrics
        bid = market_data.get('bid', 0.0)
        ask = market_data.get('ask', 0.0)
        last = market_data.get('price', market_data.get('last', 0.0))
        volume = volume_data.get('volume', 0)

        # Calculate spread
        spread_bps = 0.0
        if bid > 0 and ask > 0:
            mid_price = (bid + ask) / 2
            spread_bps = ((ask - bid) / mid_price) * 10000 if mid_price > 0 else 0.0

        # Estimate volume ratio (would need average volume data)
        volume_ratio = volume_data.get('volume_ratio', 1.0)
        if volume_ratio == 1.0 and 'average_volume' in volume_data:
            avg_volume = volume_data['average_volume']
            volume_ratio = volume / avg_volume if avg_volume > 0 else 1.0

        # Estimate volatility (simplified)
        volatility = volume_data.get('volatility', 0.25)
        if volatility == 0.25 and 'historical_volatility' in volume_data:
            volatility = volume_data['historical_volatility']

        # Determine time of day
        time_of_day = self._get_time_of_day(now)

        # Calculate minutes to market open/close (simplified)
        minutes_to_open = self._minutes_to_market_open(now)
        minutes_to_close = self._minutes_to_market_close(now)

        # Calculate price momentum (would need price history)
        price_momentum = volume_data.get('price_momentum', 0.0)

        # Calculate price vs VWAP (would need VWAP calculation)
        price_vs_vwap = volume_data.get('price_vs_vwap', 0.0)

        # Create market conditions object
        conditions = MarketConditions(
            symbol=symbol,
            timestamp=now,
            volume_ratio=volume_ratio,
            spread_bps=spread_bps,
            volatility=volatility,
            price_momentum=price_momentum,
            price_vs_vwap=price_vs_vwap,
            time_of_day=time_of_day,
            minutes_to_open=minutes_to_open,
            minutes_to_close=minutes_to_close
        )

        # Store in history
        if symbol not in self.market_history:
            self.market_history[symbol] = []
        self.market_history[symbol].append(conditions)

        # Keep only recent history (last 100 readings)
        if len(self.market_history[symbol]) > 100:
            self.market_history[symbol] = self.market_history[symbol][-100:]

        return conditions

    def adapt_execution_parameters(
        self,
        base_params: 'ExecutionParameters',
        market_conditions: MarketConditions,
        urgency: ExecutionUrgency = ExecutionUrgency.NORMAL
    ) -> 'ExecutionParameters':
        """Adapt execution parameters based on market conditions.

        Args:
            base_params: Base execution parameters to adapt
            market_conditions: Current market conditions
            urgency: Base urgency level

        Returns:
            Adapted execution parameters
        """
        # Create a copy of base parameters to avoid modifying original
        from dataclasses import replace
        adapted_params = replace(base_params)

        # Apply adaptation rules
        total_urgency_adjustment = 0.0
        total_participation_adjustment = 0.0
        preferred_algorithms = []
        avoid_algorithms = []

        # Check each rule
        for rule in self.adaptation_rules:
            condition_match = False

            # Handle single condition or list of conditions
            rule_conditions = rule['condition']
            if isinstance(rule_conditions, list):
                condition_match = market_conditions.condition in rule_conditions
            else:
                condition_match = market_conditions.condition == rule_conditions

            if condition_match:
                # Check urgency threshold
                urgency_levels = [ExecutionUrgency.PATIENT, ExecutionUrgency.NORMAL,
                                ExecutionUrgency.URGENT, ExecutionUrgency.FORCE]
                base_urgency_idx = urgency_levels.index(urgency)
                threshold_idx = urgency_levels.index(rule['urgency_threshold'])

                if base_urgency_idx >= threshold_idx:  # Only apply if urgency meets threshold
                    total_urgency_adjustment += rule.get('urgency_adjustment', 0.0)
                    total_participation_adjustment += rule.get('participation_rate_adjustment', 0.0)

                    # Collect preferred and avoided algorithms
                    preferred_algorithms.extend(rule.get('preferred_algorithms', []))
                    avoid_algorithms.extend(rule.get('avoid_algorithms', []))

        # Apply urgency adjustment (clamp to valid range)
        urgency_levels = [ExecutionUrgency.PATIENT, ExecutionUrgency.NORMAL,
                         ExecutionUrgency.URGENT, ExecutionUrgency.FORCE]
        urgency_idx = urgency_levels.index(urgency)

        # Convert adjustment to index shift
        urgency_shift = int(round(total_urgency_adjustment))
        new_urgency_idx = max(0, min(len(urgency_levels) - 1, urgency_idx + urgency_shift))
        adapted_urgency = urgency_levels[new_urgency_idx]

        # Apply participation rate adjustment
        if adapted_params.participation_rate is not None:
            adjusted_rate = adapted_params.participation_rate + total_participation_adjustment
            adapted_params.participation_rate = max(0.01, min(0.5, adjusted_rate))  # Clamp 1%-50%

        # Log adaptations
        if total_urgency_adjustment != 0 or total_participation_adjustment != 0:
            logger.info(f"Adapted execution for {market_conditions.symbol}: "
                       f"urgency {urgency.value} -> {adapted_urgency.value} "
                       f"(adjustment: {total_urgency_adjustment:+.2f}), "
                       f"participation rate adjustment: {total_participation_adjustment:+.2f}")

        # Note: In a full implementation, we would also adjust the algorithm type
        # based on preferred/avoided lists, but that would require changing the
        # algorithm_type field which is more complex

        return adapted_params

    def select_optimal_algorithm(
        self,
        symbol: str,
        quantity: int,
        urgency: ExecutionUrgency,
        market_conditions: MarketConditions,
        max_participation_rate: Optional[float] = None
    ) -> str:
        """Select optimal execution algorithm based on conditions.

        Args:
            symbol: Stock or option symbol
            quantity: Quantity to execute
            urgency: Execution urgency
            market_conditions: Current market conditions
            max_participation_rate: Maximum allowed participation rate

        Returns:
            Selected algorithm name
        """
        # Start with urgency-based selection
        if urgency == ExecutionUrgency.FORCE:
            base_algorithm = "MARKET"
        elif urgency == ExecutionUrgency.URGENT:
            base_algorithm = "POV"
        elif urgency == ExecutionUrgency.NORMAL:
            base_algorithm = "VWAP"
        else:  # PATIENT
            base_algorithm = "TWAP"

        # Apply market condition adjustments
        if market_conditions.condition == MarketCondition.VOLATILE:
            # In volatile markets, prefer TWAP over VWAP/POV
            if base_algorithm in ["POV", "MARKET"]:
                base_algorithm = "TWAP"

        elif market_conditions.condition == MarketCondition.ILLIQUID:
            # In illiquid markets, avoid aggressive algorithms
            if base_algorithm in ["POV_AGGRESSIVE", "MARKET"]:
                base_algorithm = "TWAP"

            # For large orders in illiquid markets, consider iceberg
            if quantity > 1000 and base_algorithm == "TWAP":
                # Would consider iceberg in real implementation
                pass

        elif market_conditions.condition == MarketCondition.LIQUID:
            # In liquid markets, can be more aggressive
            if urgency in [ExecutionUrgency.PATIENT, ExecutionUrgency.NORMAL] and base_algorithm == "TWAP":
                # Might prefer VWAP in liquid markets
                base_algorithm = "VWAP"

        elif market_conditions.condition in [MarketCondition.MARKET_OPEN, MarketCondition.MARKET_CLOSE]:
            # Be careful at market open/close
            if base_algorithm in ["MARKET_AGGRESSIVE", "POV_AGGRESSIVE"]:
                base_algorithm = "VWAP"

        # Apply participation rate constraints
        if max_participation_rate is not None and max_participation_rate < 0.1:
            # Low participation preference favors TWAP over POV
            if base_algorithm.startswith("POV") and max_participation_rate < 0.05:
                base_algorithm = "TWAP"

        logger.info(f"Selected algorithm for {symbol}: {base_algorithm} "
                   f"(urgency: {urgency.value}, condition: {market_conditions.condition.value})")

        return base_algorithm

    def get_market_condition_summary(self, symbol: str) -> Dict:
        """Get summary of recent market conditions for a symbol.

        Args:
            symbol: Stock or option symbol

        Returns:
            Dictionary with market condition summary
        """
        if symbol not in self.market_history or not self.market_history[symbol]:
            return {
                'symbol': symbol,
                'readings': 0,
                'avg_liquidity_score': 0.0,
                'avg_volatility_score': 0.0,
                'condition_distribution': {},
                'trend': 'unknown'
            }

        history = self.market_history[symbol]
        recent_history = history[-20:] if len(history) >= 20 else history

        # Calculate averages
        avg_liquidity = statistics.mean([m.liquidity_score for m in recent_history]) if recent_history else 0.0
        avg_volatility = statistics.mean([m.volatility_score for m in recent_history]) if recent_history else 0.0

        # Condition distribution
        condition_counts = {}
        for m in recent_history:
            condition = m.condition.value
            condition_counts[condition] = condition_counts.get(condition, 0) + 1

        # Calculate trend (improving/deteriorating liquidity)
        trend = "stable"
        if len(history) >= 10:
            older_avg = statistics.mean([m.liquidity_score for m in history[-20:-10]]) if len(history) >= 20 else 0.0
            recent_avg = statistics.mean([m.liquidity_score for m in history[-10:]]) if len(history) >= 10 else 0.0

            if older_avg > 0:
                liquidity_change = ((recent_avg - older_avg) / older_avg) * 100
                if liquidity_change > 5:
                    trend = "improving"
                elif liquidity_change < -5:
                    trend = "deteriorating"
                else:
                    trend = "stable"

        return {
            'symbol': symbol,
            'readings': len(history),
            'recent_readings': len(recent_history),
            'avg_liquidity_score': avg_liquidity,
            'avg_volatility_score': avg_volatility,
            'condition_distribution': condition_counts,
            'trend': trend,
            'latest_condition': history[-1].condition.value if history else 'unknown'
        }

    def _get_time_of_day(self, dt: datetime) -> str:
        """Get time of day classification.

        Args:
            dt: DateTime to classify

        Returns:
            Time of day string
        """
        hour = dt.hour
        minute = dt.minute
        time_minutes = hour * 60 + minute

        # Market hours (simplified - 9:30 AM to 4:00 PM EST)
        market_open_minutes = 9 * 60 + 30  # 9:30 AM
        market_close_minutes = 16 * 60     # 4:00 PM
        lunch_start = 12 * 60              # 12:00 PM
        lunch_end = 13 * 60                # 1:00 PM

        if time_minutes < market_open_minutes - 30:  # More than 30 min before open
            return "pre_market"
        elif time_minutes < market_open_minutes:     # Within 30 min of open
            return "market_open"
        elif time_minutes < lunch_start:             # Morning session
            return "morning"
        elif time_minutes < lunch_end:               # Lunch
            return "lunch"
        elif time_minutes < market_close_minutes:    # Afternoon session
            return "afternoon"
        elif time_minutes < market_close_minutes + 30: # Within 30 min of close
            return "market_close"
        else:                                        # After hours
            return "post_market"

    def _minutes_to_market_open(self, dt: datetime) -> Optional[float]:
        """Calculate minutes to next market open.

        Args:
            dt: DateTime to calculate from

        Returns:
            Minutes to market open or None if during market hours
        """
        # Simplified calculation
        hour = dt.hour
        minute = dt.minute
        time_minutes = hour * 60 + minute

        market_open_minutes = 9 * 60 + 30  # 9:30 AM

        if time_minutes >= market_open_minutes:
            # Already past market open today, calculate for tomorrow
            # Simplified: assume next day same time
            return None  # During or after market hours
        else:
            return market_open_minutes - time_minutes

    def _minutes_to_market_close(self, dt: datetime) -> Optional[float]:
        """Calculate minutes to next market close.

        Args:
            dt: DateTime to calculate from

        Returns:
            Minutes to market close or None if after market hours
        """
        # Simplified calculation
        hour = dt.hour
        minute = dt.minute
        time_minutes = hour * 60 + minute

        market_close_minutes = 16 * 60     # 4:00 PM

        if time_minutes >= market_close_minutes:
            # Already past market close today
            return None  # After market hours
        else:
            return market_close_minutes - time_minutes

    def _calculate_liquidity_score(self) -> float:
        """Calculate liquidity score (0-1).

        Returns:
            Liquidity score
        """
        # This would use volume_ratio, spread_bps, depth_imbalance
        # Simplified implementation
        volume_score = min(self.volume_ratio / 2.0, 1.0)  # Normalize volume ratio
        spread_score = max(0, 1 - (self.spread_bps / 50.0))  # Penalize wide spreads
        depth_score = 1 - abs(self.depth_imbalance)  # Penalize imbalance

        # Weighted average
        return (volume_score * 0.4 + spread_score * 0.4 + depth_score * 0.2)

    def _calculate_volatility_score(self) -> float:
        """Calculate volatility score (0-1).

        Returns:
            Volatility score
        """
        # Normalize volatility to 0-1 score (assuming 0-100% range)
        # Typical volatilities: 10-40% for stocks
        volatility_clamped = max(0, min(self.volatility, 1.0))  # Clamp to 0-100%
        return volatility_clamped  # Simple linear mapping

    def _classify_condition(self) -> MarketCondition:
        """Classify overall market condition.

        Returns:
            MarketCondition enum
        """
        # Check time-based conditions first
        if self.time_of_day in ["pre_market", "post_market"]:
            return MarketCondition.PRE_MARKET if self.time_of_day == "pre_market" else MarketCondition.POST_MARKET

        if self.time_of_day in ["market_open", "market_close"]:
            return MarketCondition.MARKET_OPEN if self.time_of_day == "market_open" else MarketCondition.MARKET_CLOSE

        if self.time_of_day == "lunch":
            return MarketCondition.LUNCH

        # Check volatility-based conditions
        if self.volatility > 0.40:  # High volatility
            return MarketCondition.VOLATILE
        elif self.volatility < 0.15:  # Low volatility
            return MarketCondition.QUIET

        # Check liquidity-based conditions
        if self.liquidity_score > 0.7 and self.spread_bps < 15.0:
            return MarketCondition.LIQUID
        elif self.liquidity_score < 0.3 or self.spread_bps > 30.0:
            return MarketCondition.ILLIQUID

        # Default to normal
        return MarketCondition.NORMAL


@dataclass
class ExecutionParameters:
    """Parameters for execution algorithms."""
    algorithm_type: str  # 'vwap', 'twap', 'pov', 'market', 'limit', etc.
    start_time: datetime
    end_time: datetime
    participation_rate: Optional[float] = None  # For POV (0.0 to 1.0)
    max_slippage_bps: Optional[float] = None   # Maximum slippage in basis points
    min_fill_size: Optional[int] = None        # Minimum fill size
    max_duration_minutes: Optional[int] = None # Maximum execution duration
    urgency: float = 0.5                       # 0.0 (patient) to 1.0 (urgent)
    # Additional fields can be added as needed


class AdaptiveExecutionManager:
    """High-level manager for adaptive execution."""

    def __init__(self):
        self.engine = AdaptiveExecutionEngine()
        self.execution_history: List[Dict] = []

    def execute_adaptively(
        self,
        symbol: str,
        quantity: int,
        side: str,
        base_algorithm: str,
        get_market_data_callback=None,
        get_volume_data_callback=None,
        submit_order_callback=None,
        urgency: ExecutionUrgency = ExecutionUrgency.NORMAL,
        max_participation_rate: Optional[float] = None
    ) -> Dict:
        """Execute order with adaptive parameters.

        Args:
            symbol: Stock or option symbol
            quantity: Quantity to execute
            side: 'buy' or 'sell'
            base_algorithm: Base algorithm to use
            get_market_data_callback: Function to get market data
            get_volume_data_callback: Function to get volume data
            submit_order_callback: Function to submit orders
            urgency: Base urgency level
            max_participation_rate: Maximum participation rate for POV

        Returns:
            Execution result dictionary
        """
        start_time = datetime.now()

        # Assess current market conditions
        market_conditions = self.engine.assess_market_conditions(
            symbol, get_market_data_callback, get_volume_data_callback
        )

        # Select optimal algorithm based on conditions
        selected_algorithm = self.engine.select_optimal_algorithm(
            symbol, quantity, urgency, market_conditions, max_participation_rate
        )

        # Create base execution parameters
        end_time = start_time + timedelta(minutes=30)  # Default 30 minute window

        base_params = ExecutionParameters(
            algorithm_type=selected_algorithm,
            start_time=start_time,
            end_time=end_time,
            participation_rate=max_participation_rate,
            urgency=0.5 if urgency == ExecutionUrgency.NORMAL else
                     (0.2 if urgency == ExecutionUrgency.PATIENT else
                      (0.8 if urgency == ExecutionUrgency.URGENT else 1.0))
        )

        # Adapt parameters based on market conditions
        adapted_params = self.engine.adapt_execution_parameters(
            base_params, market_conditions, urgency
        )

        # Record the decision
        decision_record = {
            'timestamp': start_time.isoformat(),
            'symbol': symbol,
            'quantity': quantity,
            'side': side,
            'base_algorithm': base_algorithm,
            'selected_algorithm': selected_algorithm,
            'market_condition': market_conditions.condition.value,
            'liquidity_score': market_conditions.liquidity_score,
            'volatility_score': market_conditions.volatility_score,
            'urgency': urgency.value,
            'adapted_urgency': adapted_params.urgency,
            'participation_rate': adapted_params.participation_rate
        }

        logger.info(f"Adaptive execution decision for {symbol}: "
                   f"{base_algorithm} -> {selected_algorithm} "
                   f"(condition: {market_conditions.condition.value}, "
                   f"liquidity: {market_conditions.liquidity_score:.2f})")

        # In a full implementation, we would now execute using the selected algorithm
        # with the adapted parameters. For this demo, we'll return the decision.

        # Simulate execution result
        import random
        execution_success = random.random() > 0.1  # 90% success rate

        result = {
            'symbol': symbol,
            'quantity': quantity,
            'side': side,
            'algorithm_used': selected_algorithm,
            'market_conditions': {
                'condition': market_conditions.condition.value,
                'liquidity_score': market_conditions.liquidity_score,
                'volatility_score': market_conditions.volatility_score,
                'spread_bps': market_conditions.spread_bps,
                'volume_ratio': market_conditions.volume_ratio
            },
            'execution_parameters': {
                'start_time': adapted_params.start_time.isoformat(),
                'end_time': adapted_params.end_time.isoformat(),
                'participation_rate': adapted_params.participation_rate,
                'urgency': adapted_params.urgency
            },
            'decision_record': decision_record,
            'success': execution_success,
            'executed_quantity': quantity if execution_success else 0,
            'average_price': 100.0 if execution_success else 0.0,  # Placeholder
            'timestamp': datetime.now().isoformat()
        }

        # Add to history
        self.execution_history.append(result)

        # Keep history reasonable
        if len(self.execution_history) > 1000:
            self.execution_history = self.execution_history[-1000:]

        return result

    def get_adaptation_stats(self) -> Dict:
        """Get statistics about adaptation decisions.

        Returns:
            Dictionary with adaptation statistics
        """
        if not self.execution_history:
            return {
                'total_executions': 0,
                'algorithm_changes': 0,
                'avg_liquidity_score': 0.0,
                'avg_volatility_score': 0.0
            }

        total_executions = len(self.execution_history)
        algorithm_changes = sum(1 for e in self.execution_history
                              if e.get('base_algorithm') != e.get('selected_algorithm'))

        avg_liquidity = statistics.mean([e['market_conditions']['liquidity_score']
                                       for e in self.execution_history])
        avg_volatility = statistics.mean([e['market_conditions']['volatility_score']
                                        for e in self.execution_history])

        # Algorithm usage distribution
        algorithm_usage = {}
        for e in self.execution_history:
            alg = e.get('selected_algorithm', 'unknown')
            algorithm_usage[alg] = algorithm_usage.get(alg, 0) + 1

        return {
            'total_executions': total_executions,
            'algorithm_changes': algorithm_changes,
            'algorithm_change_rate': algorithm_changes / total_executions if total_executions > 0 else 0.0,
            'avg_liquidity_score': avg_liquidity,
            'avg_volatility_score': avg_volatility,
            'algorithm_usage': algorithm_usage,
            'recent_executions': len([e for e in self.execution_history
                                    if (datetime.now() - datetime.fromisoformat(e['timestamp'])).total_seconds() < 3600])
        }


def create_adaptive_execution_engine() -> AdaptiveExecutionEngine:
    """Factory function to create an AdaptiveExecutionEngine instance."""
    return AdaptiveExecutionEngine()


def create_adaptive_execution_manager() -> AdaptiveExecutionManager:
    """Factory function to create an AdaptiveExecutionManager instance."""
    return AdaptiveExecutionManager()


# Example usage and testing
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    def demo_alert(message: str):
        print(f"[ALERT] {message}")

    # Create adaptive execution manager
    adaptive_manager = create_adaptive_execution_manager()

    # Mock market data callback
    def get_market_data(symbol):
        import random
        base_price = 100.0 if "AAPL" in symbol else 50.0 if "MSFT" in symbol else 75.0
        return {
            'bid': base_price - random.uniform(0.1, 0.5),
            'ask': base_price + random.uniform(0.1, 0.5),
            'price': base_price + random.uniform(-0.5, 0.5),
            'last': base_price + random.uniform(-0.3, 0.3)
        }

    # Mock volume data callback
    def get_volume_data(symbol):
        import random
        return {
            'volume': random.randint(500, 5000),
            'average_volume': 2000,
            'volume_ratio': random.uniform(0.5, 2.5),
            'volatility': random.uniform(0.1, 0.5),
            'historical_volatility': random.uniform(0.1, 0.4),
            'price_momentum': random.uniform(-0.05, 0.05),
            'price_vs_vwap': random.uniform(-0.02, 0.02)
        }

    # Mock submit order callback (not used in this demo)
    def submit_order(symbol, quantity, side, order_type, price=None):
        class MockOrder:
            def __init__(self):
                self.id = f"{order_type}_{symbol}_{datetime.now().timestamp()}"
        return True, None, MockOrder()

    print("=== Adaptive Execution Demo ===\n")

    # Test different market scenarios
    test_symbols = ["AAPL261016C00190000", "MSFT261016C00300000", "GOOGL261016C00120000"]

    for i, symbol in enumerate(test_symbols):
        print(f"{i+1}. Testing {symbol}")

        # Test with different urgency levels
        for urgency in [ExecutionUrgency.PATIENT, ExecutionUrgency.NORMAL, ExecutionUrgency.URGENT]:
            result = adaptive_manager.execute_adaptively(
                symbol=symbol,
                quantity=10 + i*5,  # Vary quantity
                side="buy" if i % 2 == 0 else "sell",
                base_algorithm="VWAP",  # Start with VWAP as base
                get_market_data_callback=get_market_data,
                get_volume_data_callback=get_volume_data,
                submit_order_callback=submit_order,
                urgency=urgency,
                max_participation_rate=0.2 if urgency != ExecutionUrgency.FORCE else None
            )

            print(f"   Urgency: {urgency.value}")
            print(f"   Selected Algorithm: {result['algorithm_used']}")
            print(f"   Market Condition: {result['market_conditions']['condition']}")
            print(f"   Liquidity Score: {result['market_conditions']['liquidity_score']:.2f}")
            print(f"   Volatility Score: {result['market_conditions']['volatility_score']:.2f}")
            print(f"   Success: {result['success']}")
            if result['success']:
                print(f"   Executed: {result['executed_quantity']}/{result['quantity']}")
                print(f"   Avg Price: ${result['average_price']:.2f}")
            print()

    # Show market condition summary for one symbol
    print("3. Market Condition Summary (AAPL)")
    summary = adaptive_manager.engine.get_market_condition_summary("AAPL261016C00190000")
    print(f"   Symbol: {summary['symbol']}")
    print(f"   Readings: {summary['readings']}")
    print(f"   Avg Liquidity Score: {summary['avg_liquidity_score']:.2f}")
    print(f"   Avg Volatility Score: {summary['avg_volatility_score']:.2f}")
    print(f"   Trend: {summary['trend']}")
    print(f"   Latest Condition: {summary['latest_condition']}")
    print(f"   Condition Distribution: {summary['condition_distribution']}")
    print()

    # Show adaptation statistics
    print("4. Adaptation Statistics")
    stats = adaptive_manager.get_adaptation_stats()
    print(f"   Total Executions: {stats['total_executions']}")
    print(f"   Algorithm Changes: {stats['algorithm_changes']}")
    print(f"   Algorithm Change Rate: {stats['algorithm_change_rate']:.1%}")
    print(f"   Avg Liquidity Score: {stats['avg_liquidity_score']:.2f}")
    print(f"   Avg Volatility Score: {stats['avg_volatility_score']:.2f}")
    print(f"   Algorithm Usage: {stats['algorithm_usage']}")

    print("\n=== Adaptive Execution Demo Complete ===")