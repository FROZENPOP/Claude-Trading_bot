"""Signal generation module for underlying market signals."""

import pandas as pd
import numpy as np
from typing import Optional
import logging
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    """Represents a trading signal."""
    signal_type: str  # 'bullish', 'bearish', 'neutral', 'weak_bullish', 'weak_bearish'
    signal_strength: float  # 0.0 to 1.0
    timestamp: datetime
    metadata: dict  # Additional signal information


class SignalGenerator:
    """Generates trading signals from market data."""

    def __init__(self):
        """Initialize signal generator."""
        logger.info("Signal generator initialized")

    def get_signal(self, market_data: pd.DataFrame, current_date: datetime) -> Optional[Signal]:
        """Generate a trading signal from market data.

        Args:
            market_data: DataFrame with market data (must have date column)
            current_date: Current date for signal generation

        Returns:
            Signal object or None if insufficient data
        """
        if market_data is None or market_data.empty:
            logger.warning("No market data provided for signal generation")
            return None

        # Ensure we have data up to current_date
        if 'date' not in market_data.columns:
            logger.error("Market data missing 'date' column")
            return None

        # Filter data to available history (don't peek into future)
        # Handle timezone issues by converting to timezone-naive for comparison
        market_date_series = pd.to_datetime(market_data['date'])
        # Remove timezone information if present for consistent comparison
        if hasattr(market_date_series, 'dt') and hasattr(market_date_series.dt, 'tz') and market_date_series.dt.tz is not None:
            market_date_dt = market_date_series.dt.tz_convert(None)
        else:
            market_date_dt = market_date_series

        current_date_dt = pd.to_datetime(current_date)
        # Remove timezone information from current_date if present
        if hasattr(current_date_dt, 'tz') and current_date_dt.tz is not None:
            current_date_dt = current_date_dt.tz_convert(None)

        available_data = market_data[market_date_dt <= current_date_dt].copy()

        if len(available_data) < 20:  # Need sufficient history for indicators
            logger.debug(f"Insufficient history for signal generation: {len(available_data)} days")
            return None

        # Sort by date ascending
        available_data = available_data.sort_values('date').reset_index(drop=True)

        # Generate signal using multiple methods
        signal = self._generate_composite_signal(available_data)

        return signal

    def _generate_composite_signal(self, data: pd.DataFrame) -> Signal:
        """Generate a composite signal from multiple indicators.

        Args:
            data: DataFrame with historical market data sorted by date

        Returns:
            Signal object
        """
        # Calculate various technical indicators
        signals = []

        # 1. Moving average crossover signal
        ma_signal = self._ma_crossover_signal(data)
        if ma_signal is not None:
            signals.append(ma_signal)

        # 2. Momentum signal
        momentum_signal = self._momentum_signal(data)
        if momentum_signal is not None:
            signals.append(momentum_signal)

        # 3. Price position relative to moving averages
        price_ma_signal = self._price_ma_position_signal(data)
        if price_ma_signal is not None:
            signals.append(price_ma_signal)

        # 4. Volatility-adjusted momentum
        vol_momentum_signal = self._volatility_adjusted_momentum_signal(data)
        if vol_momentum_signal is not None:
            signals.append(vol_momentum_signal)

        # If we have no signals, return neutral
        if not signals:
            return Signal(
                signal_type='neutral',
                signal_strength=0.0,
                timestamp=data['date'].iloc[-1],
                metadata={'reason': 'No signals generated'}
            )

        # Combine signals
        return self._combine_signals(signals, data['date'].iloc[-1])

    def _ma_crossover_signal(self, data: pd.DataFrame) -> Optional[dict]:
        """Generate signal based on moving average crossovers.

        Args:
            data: DataFrame with market data

        Returns:
            Signal component dictionary or None
        """
        if len(data) < 50:
            return None

        # Calculate moving averages if not present
        if 'short_ma' not in data.columns:
            data['short_ma'] = data['adjusted_close'].rolling(window=20).mean()
        if 'medium_ma' not in data.columns:
            data['medium_ma'] = data['adjusted_close'].rolling(window=50).mean()

        # Get latest values
        latest = data.iloc[-1]
        prev = data.iloc[-2] if len(data) >= 2 else None

        if prev is None:
            return None

        short_ma = latest['short_ma']
        medium_ma = latest['medium_ma']
        prev_short_ma = prev['short_ma']
        prev_medium_ma = prev['medium_ma']

        # Check for crossover
        if prev_short_ma <= prev_medium_ma and short_ma > medium_ma:
            # Bullish crossover
            strength = min(0.8, abs(short_ma - medium_ma) / medium_ma * 10)  # Scale strength
            return {
                'type': 'bullish',
                'strength': strength,
                'indicator': 'MA_Crossover',
                'details': f'Short MA crossed above Medium MA'
            }
        elif prev_short_ma >= prev_medium_ma and short_ma < medium_ma:
            # Bearish crossover
            strength = min(0.8, abs(short_ma - medium_ma) / medium_ma * 10)
            return {
                'type': 'bearish',
                'strength': strength,
                'indicator': 'MA_Crossover',
                'details': f'Short MA crossed below Medium MA'
            }

        # No crossover, but check current relationship
        if short_ma > medium_ma:
            # Short above medium - mild bullish
            strength = min(0.5, (short_ma - medium_ma) / medium_ma * 5)
            return {
                'type': 'bullish',
                'strength': strength,
                'indicator': 'MA_Position',
                'details': f'Short MA above Medium MA'
            }
        elif short_ma < medium_ma:
            # Short below medium - mild bearish
            strength = min(0.5, (medium_ma - short_ma) / medium_ma * 5)
            return {
                'type': 'bearish',
                'strength': strength,
                'indicator': 'MA_Position',
                'details': f'Short MA below Medium MA'
            }

        return None

    def _momentum_signal(self, data: pd.DataFrame) -> Optional[dict]:
        """Generate signal based on price momentum.

        Args:
            data: DataFrame with market data

        Returns:
            Signal component dictionary or None
        """
        if len(data) < 20:
            return None

        # Calculate multiple period momentum
        returns_1d = data['adjusted_close'].pct_change(1)
        returns_5d = data['adjusted_close'].pct_change(5)
        returns_20d = data['adjusted_close'].pct_change(20)

        latest_return_1d = returns_1d.iloc[-1]
        latest_return_5d = returns_5d.iloc[-1]
        latest_return_20d = returns_20d.iloc[-1]

        # Combine momentum signals
        momentum_score = (
            0.5 * np.tanh(latest_return_1d * 20) +  # Short term
            0.3 * np.tanh(latest_return_5d * 10) +  # Medium term
            0.2 * np.tanh(latest_return_20d * 5)    # Long term
        )

        # Convert to signal type and strength
        if momentum_score > 0.1:
            signal_type = 'bullish'
            strength = min(0.9, abs(momentum_score))
        elif momentum_score < -0.1:
            signal_type = 'bearish'
            strength = min(0.9, abs(momentum_score))
        else:
            signal_type = 'neutral'
            strength = abs(momentum_score)  # Strength of neutral signal

        return {
            'type': signal_type,
            'strength': strength,
            'indicator': 'Momentum',
            'details': f'1D: {latest_return_1d:.2%}, 5D: {latest_return_5d:.2%}, 20D: {latest_return_20d:.2%}'
        }

    def _price_ma_position_signal(self, data: pd.DataFrame) -> Optional[dict]:
        """Generate signal based on price position relative to moving averages.

        Args:
            data: DataFrame with market data

        Returns:
            Signal component dictionary or None
        """
        if len(data) < 50:
            return None

        # Calculate moving averages if not present
        if 'medium_ma' not in data.columns:
            data['medium_ma'] = data['adjusted_close'].rolling(window=50).mean()
        if 'long_ma' not in data.columns:
            data['long_ma'] = data['adjusted_close'].rolling(window=200).mean()

        latest = data.iloc[-1]
        price = latest['adjusted_close']
        medium_ma = latest['medium_ma']
        long_ma = latest['long_ma']

        # Calculate position as percentage above/below MAs
        if medium_ma > 0 and long_ma > 0:
            pos_vs_medium = (price - medium_ma) / medium_ma
            pos_vs_long = (price - long_ma) / long_ma

            # Combined position score
            position_score = 0.6 * pos_vs_medium + 0.4 * pos_vs_long

            if position_score > 0.02:
                signal_type = 'bullish'
                strength = min(0.7, abs(position_score) * 10)
            elif position_score < -0.02:
                signal_type = 'bearish'
                strength = min(0.7, abs(position_score) * 10)
            else:
                signal_type = 'neutral'
                strength = abs(position_score) * 10

            return {
                'type': signal_type,
                'strength': strength,
                'indicator': 'Price_MA_Position',
                'details': f'Price vs MA50: {pos_vs_medium:.2%}, vs MA200: {pos_vs_long:.2%}'
            }

        return None

    def _volatility_adjusted_momentum_signal(self, data: pd.DataFrame) -> Optional[dict]:
        """Generate signal based on volatility-adjusted momentum.

        Args:
            data: DataFrame with market data

        Returns:
            Signal component dictionary or None
        """
        if len(data) < 30:
            return None

        # Calculate volatility-adjusted momentum
        returns = data['adjusted_close'].pct_change()
        volatility = returns.rolling(window=20).std() * np.sqrt(252)  # Annualized

        # Avoid division by zero
        volatility = volatility.replace(0, 0.001)

        # Calculate volatility-adjusted returns
        vol_adj_returns = returns / volatility

        # Get recent average
        recent_vol_adj = vol_adj_returns.tail(10).mean()

        # Convert to signal
        if recent_vol_adj > 0.1:
            signal_type = 'bullish'
            strength = min(0.8, abs(recent_vol_adj) * 5)
        elif recent_vol_adj < -0.1:
            signal_type = 'bearish'
            strength = min(0.8, abs(recent_vol_adj) * 5)
        else:
            signal_type = 'neutral'
            strength = abs(recent_vol_adj) * 5

        return {
            'type': signal_type,
            'strength': strength,
            'indicator': 'Vol_Adjusted_Momentum',
            'details': f'Recent vol-adjusted momentum: {recent_vol_adj:.3f}'
        }

    def _combine_signals(self, signals: list, timestamp: datetime) -> Signal:
        """Combine multiple signal components into a single signal.

        Args:
            signals: List of signal component dictionaries
            timestamp: Timestamp for the combined signal

        Returns:
            Combined Signal object
        """
        # Count signals by type
        bullish_score = 0.0
        bearish_score = 0.0
        neutral_score = 0.0
        total_weight = 0.0

        details = []

        for signal in signals:
            weight = signal.get('strength', 0.5)
            signal_type = signal.get('type', 'neutral')

            if signal_type == 'bullish':
                bullish_score += weight
            elif signal_type == 'bearish':
                bearish_score += weight
            else:
                neutral_score += weight

            total_weight += weight
            details.append(f"{signal.get('indicator', 'Unknown')}: {signal.get('details', '')}")

        # Normalize scores
        if total_weight > 0:
            bullish_score /= total_weight
            bearish_score /= total_weight
            neutral_score /= total_weight

        # Determine final signal type
        if bullish_score > bearish_score and bullish_score > neutral_score:
            final_type = 'bullish'
            final_strength = bullish_score
        elif bearish_score > bullish_score and bearish_score > neutral_score:
            final_type = 'bearish'
            final_strength = bearish_score
        else:
            final_type = 'neutral'
            final_strength = max(neutral_score, 0.1)  # Ensure minimum strength for neutral

        # Adjust for weak signals
        if final_strength < 0.3:
            if final_type == 'bullish':
                final_type = 'weak_bullish'
            elif final_type == 'bearish':
                final_type = 'weak_bearish'

        return Signal(
            signal_type=final_type,
            signal_strength=final_strength,
            timestamp=timestamp,
            metadata={
                'bullish_score': bullish_score,
                'bearish_score': bearish_score,
                'neutral_score': neutral_score,
                'details': '; '.join(details[:3])  # Limit details length
            }
        )


def generate_signal(market_data: pd.DataFrame, current_date: datetime) -> Optional[Signal]:
    """Convenience function to generate a trading signal.

    Args:
        market_data: DataFrame with market data
        current_date: Current date for signal generation

    Returns:
        Signal object or None
    """
    generator = SignalGenerator()
    return generator.get_signal(market_data, current_date)


if __name__ == "__main__":
    # Example usage
    import pandas as pd
    from datetime import datetime, timedelta

    # Create sample market data
    dates = [datetime.now() - timedelta(days=i) for i in range(30, 0, -1)]
    # Create a trending upward sequence
    prices = [100 + i * 0.5 + np.random.normal(0, 0.5) for i in range(30)]

    sample_data = pd.DataFrame({
        'date': dates,
        'adjusted_close': prices,
        'open': [p - 0.2 for p in prices],
        'high': [p + 0.3 for p in prices],
        'low': [p - 0.3 for p in prices],
        'close': prices,
        'volume': [1000000 + np.random.normal(0, 100000) for _ in range(30)]
    })

    # Generate signal
    signal_generator = SignalGenerator()
    signal = signal_generator.get_signal(sample_data, datetime.now())

    if signal:
        logger.info(f"Generated signal: {signal.signal_type} with strength {signal.signal_strength:.2f}")
        logger.info(f"Details: {signal.metadata.get('details', 'No details')}")
    else:
        logger.info("No signal generated")