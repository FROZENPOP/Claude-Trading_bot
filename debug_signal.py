#!/usr/bin/env python3
"""Debug the signal generation process."""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add project to path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from trading_bot.strategies.signals import SignalGenerator

def debug_signal_generation():
    """Debug why signals aren't being generated."""
    print("DEBUGGING SIGNAL GENERATION")
    print("=" * 40)

    # Create the same type of data as in the diagnostic backtest
    print("Creating test data similar to diagnostic backtest...")

    # Using the same date range as diagnostic: 2026-09-01 to 2026-09-30
    # But we need lookback data too, so let's create more data
    start_date = datetime(2026, 7, 13)  # 50 days before 2026-09-01
    end_date = datetime(2026, 9, 30)

    dates = pd.date_range(start=start_date, end=end_date, freq='D')
    # Filter to business days only (weekday < 5)
    dates = [d for d in dates if d.weekday() < 5]

    print(f"Created {len(dates)} business days from {start_date.date()} to {end_date.date()}")

    # Create price data with some trend and volatility
    base_price = 150.0  # AAPL-like price
    prices = []

    # Add some random walk with slight upward bias
    for i in range(len(dates)):
        # Small daily trend + noise
        daily_return = 0.0005 + np.random.normal(0, 0.02)  # 0.05% daily drift + 2% volatility
        if i == 0:
            price = base_price
        else:
            price = prices[-1] * (1 + daily_return)
        prices.append(max(price, 1.0))  # Ensure positive price

    # Create OHLCV data
    stock_data = pd.DataFrame({
        'date': dates,
        'open': [p * (1 + np.random.normal(0, 0.005)) for p in prices],
        'high': [p * (1 + abs(np.random.normal(0, 0.01))) for p in prices],
        'low': [p * (1 - abs(np.random.normal(0, 0.01))) for p in prices],
        'close': prices,
        'adjusted_close': prices,  # Our fix
        'volume': [np.random.randint(1000000, 10000000) for _ in range(len(dates))],
        'symbol': 'AAPL'
    })

    print(f"Generated stock data with shape: {stock_data.shape}")
    print(f"Date range: {stock_data['date'].min()} to {stock_data['date'].max()}")
    print(f"Price range: ${stock_data['close'].min():.2f} to ${stock_data['close'].max():.2f}")

    # Test signal generation for each day (like the backtest does)
    signal_generator = SignalGenerator()

    bullish_signals = 0
    bearish_signals = 0
    total_signals = 0

    print("\nTesting signal generation for each day...")

    for i, current_date in enumerate(dates):
        if i < 20:  # Need at least 20 days of history
            continue

        # Get available data up to current date (no look-ahead)
        available_data = stock_data[stock_data['date'] <= current_date].copy()

        if len(available_data) < 20:
            continue

        # Generate signal
        signal = signal_generator.get_signal(available_data, current_date)

        if signal is not None:
            total_signals += 1
            if signal.signal_type == 'bullish':
                bullish_signals += 1
                if bullish_signals <= 3:  # Show first few bullish signals
                    print(f"  Bullish signal on {current_date.date()}: strength {signal.signal_strength:.3f}")
                    print(f"    Details: {signal.metadata.get('details', 'No details')}")
                    if 'bullish_score' in signal.metadata:
                        print(f"    Scores - Bullish: {signal.metadata['bullish_score']:.3f}, "
                              f"Bearish: {signal.metadata['bearish_score']:.3f}, "
                              f"Neutral: {signal.metadata['neutral_score']:.3f}")
            elif signal.signal_type == 'bearish':
                bearish_signals += 1
                if bearish_signals <= 3:  # Show first few bearish signals
                    print(f"  Bearish signal on {current_date.date()}: strength {signal.signal_strength:.3f}")
                    print(f"    Details: {signal.metadata.get('details', 'No details')}")

    print(f"\nRESULTS:")
    print(f"  Total signals: {total_signals}")
    print(f"  Bullish signals: {bullish_signals}")
    print(f"  Bearish signals: {bearish_signals}")

    if total_signals == 0:
        print("\n[FAIL] No signals generated - investigating why...")

        # Let's examine what the signal generator is seeing in the data
        print("\nExamining recent data for signal criteria...")

        # Test with the most recent data
        current_date = dates[-1]
        available_data = stock_data[stock_data['date'] <= current_date].copy()

        print(f"Most recent date: {current_date}")
        print(f"Available data points: {len(available_data)}")

        if len(available_data) >= 20:
            # Show some recent data
            recent = available_data.tail(10)
            print("\nRecent 10 days of data:")
            for idx, row in recent.iterrows():
                print(f"  {row['date'].date()}: O:{row['open']:.2f} H:{row['high']:.2f} L:{row['low']:.2f} C:{row['close']:.2f} V:{row['volume']:,}")

            # Calculate what the signal generator should see
            print("\nCalculating technical indicators that signal generator uses...")

            # Calculate moving averages
            close_series = available_data['close']
            ma_10 = close_series.rolling(window=10).mean()
            ma_20 = close_series.rolling(window=20).mean()

            print(f"  Current price: ${close_series.iloc[-1]:.2f}")
            print(f"  10-day MA: ${ma_10.iloc[-1]:.2f}")
            print(f"  20-day MA: ${ma_20.iloc[-1]:.2f}")
            print(f"  Price > MA10: {close_series.iloc[-1] > ma_10.iloc[-1]}")
            print(f"  Price > MA20: {close_series.iloc[-1] > ma_20.iloc[-1]}")
            print(f"  MA10 > MA20: {ma_10.iloc[-1] > ma_20.iloc[-1]}")

            # Calculate momentum
            if len(close_series) >= 11:
                momentum_10 = (close_series.iloc[-1] / close_series.iloc[-11] - 1) * 100
                print(f"  10-day momentum: {momentum_10:.2f}%")

            # Check if we have enough volume
            avg_volume = available_data['volume'].mean()
            current_volume = available_data['volume'].iloc[-1]
            print(f"  Average volume: {avg_volume:,.0f}")
            print(f"  Current volume: {current_volume:,.0f}")
            print(f"  Volume > average: {current_volume > avg_volume}")

            # Test the signal generator directly on this data
            print("\nTesting signal generator on this data...")
            signal = signal_generator.get_signal(available_data, current_date)
            if signal:
                print(f"  Signal generated: {signal.signal_type} (strength: {signal.signal_strength:.3f})")
            else:
                print(f"  No signal generated")

                # Let's manually check what the signal generator logic should produce
                print("\nManual signal calculation:")

                # Check if it's calling the internal methods
                try:
                    # Access private method to see what's happening
                    bullish_score = signal_generator._calculate_bullish_score(available_data)
                    bearish_score = signal_generator._calculate_bearish_score(available_data)
                    neutral_score = signal_generator._calculate_neutral_score(available_data)

                    print(f"  Bullish score: {bullish_score:.3f}")
                    print(f"  Bearish score: {bearish_score:.3f}")
                    print(f"  Neutral score: {neutral_score:.3f}")

                    # Determine what signal type would be generated
                    scores = {
                        'bullish': bullish_score,
                        'bearish': bearish_score,
                        'neutral': neutral_score
                    }
                    max_score_type = max(scores, key=scores.get)
                    max_score = scores[max_score_type]

                    print(f"  Highest score: {max_score_type} ({max_score:.3f})")
                    print(f"  Minimum threshold for signal: {signal_generator.min_signal_strength}")
                    print(f"  Would generate signal: {max_score >= signal_generator.min_signal_strength}")

                except Exception as e:
                    print(f"  Error accessing signal generator internals: {e}")
        else:
            print(f"  Not enough data: {len(available_data)} points")
    else:
        print(f"\n[SUCCESS] Signal generation is working!")

def main():
    """Main debug function."""
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    debug_signal_generation()

    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()