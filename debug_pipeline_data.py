#!/usr/bin/env python3
"""Debug what data the OptionsDataPipeline is actually returning."""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add project to path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from research_options_strategies import OptionsDataPipeline
from trading_bot.strategies.signals import SignalGenerator

def debug_pipeline_data():
    """Debug what data the pipeline is returning."""
    print("DEBUGGING OPTIONS DATA PIPELINE OUTPUT")
    print("=" * 50)

    # Use the same pipeline as in the diagnostic backtest
    pipeline = OptionsDataPipeline(symbol="AAPL")

    # Test the same date range as one iteration in the diagnostic backtest
    # From the diagnostic: "Loading AAPL stock data from 2026-07-13 to 2026-09-01"
    lookback_start = "2026-07-13"
    end_date = "2026-09-01"

    print(f"Fetching stock data from {lookback_start} to {end_date}")

    stock_data = pipeline.get_stock_data(lookback_start, end_date)

    print(f"Stock data shape: {stock_data.shape}")
    print(f"Stock data columns: {list(stock_data.columns)}")

    if not stock_data.empty:
        print(f"Date range: {stock_data['date'].min()} to {stock_data['date'].max()}")
        print(f"Number of rows: {len(stock_data)}")

        # Show first and last few rows
        print("\nFirst 5 rows:")
        print(stock_data.head())
        print("\nLast 5 rows:")
        print(stock_data.tail())

        # Check for the adjusted_close column we added
        print(f"\nHas 'adjusted_close' column: {'adjusted_close' in stock_data.columns}")
        if 'adjusted_close' in stock_data.columns:
            print(f"Has 'close' column: {'close' in stock_data.columns}")
            adjusted_equals_close = (stock_data['adjusted_close'] == stock_data['close']).all()
            print(f"adjusted_close equals close: {adjusted_equals_close}")

            if not adjusted_equals_close:
                print("WARNING: adjusted_close does not equal close!")
                print("adjusted_close sample:", stock_data['adjusted_close'].head().tolist())
                print("close sample:", stock_data['close'].head().tolist())

        # Test signal generation on this data
        print("\n--- TESTING SIGNAL GENERATION ON PIPELINE DATA ---")
        signal_generator = SignalGenerator()

        # Test with the most recent data in this dataset
        current_date = stock_data['date'].iloc[-1]
        available_data = stock_data[stock_data['date'] <= current_date].copy()

        print(f"Testing signal for date: {current_date}")
        print(f"Available data points: {len(available_data)}")

        if len(available_data) >= 20:
            signal = signal_generator.get_signal(available_data, current_date)

            if signal is not None:
                print(f"[SUCCESS] Signal generated: {signal.signal_type} (strength: {signal.signal_strength:.3f})")
                print(f"  Details: {signal.metadata.get('details', 'No details')}")
            else:
                print("[FAIL] No signal generated from pipeline data")

                # Let's examine why by checking what the signal generator sees
                print("\nExamining data for signal generation issues...")

                # Show recent price action
                recent = available_data.tail(10)
                print("Recent 10 days:")
                for idx, row in recent.iterrows():
                    print(f"  {row['date'].date()}: O:{row['open']:.2f} H:{row['high']:.2f} L:{row['low']:.2f} C:{row['close']:.2f} V:{row['volume']:,}")

                # Calculate what should trigger signals
                close_series = available_data['close']
                if len(close_series) >= 20:
                    ma_10 = close_series.rolling(window=10).mean()
                    ma_20 = close_series.rolling(window=20).mean()

                    print(f"\nTechnical indicators:")
                    print(f"  Current price: ${close_series.iloc[-1]:.2f}")
                    print(f"  10-day MA: ${ma_10.iloc[-1]:.2f}")
                    print(f"  20-day MA: ${ma_20.iloc[-1]:.2f}")
                    print(f"  Price > MA10: {close_series.iloc[-1] > ma_10.iloc[-1]}")
                    print(f"  Price > MA20: {close_series.iloc[-1] > ma_20.iloc[-1]}")
                    print(f"  MA10 > MA20: {ma_10.iloc[-1] > ma_20.iloc[-1]}")

                    # Check momentum
                    if len(close_series) >= 11:
                        momentum_10 = (close_series.iloc[-1] / close_series.iloc[-11] - 1) * 100
                        print(f"  10-day momentum: {momentum_10:.2f}%")

                    # Check volume
                    avg_volume = available_data['volume'].mean()
                    current_volume = available_data['volume'].iloc[-1]
                    print(f"  Average volume: {avg_volume:,.0f}")
                    print(f"  Current volume: {current_volume:,.0f}")
                    print(f"  Volume > average: {current_volume > avg_volume}")

                    # Try to manually calculate what the signal generator should produce
                    print("\nTrying manual signal calculation...")
                    try:
                        bullish_score = signal_generator._calculate_bullish_score(available_data)
                        bearish_score = signal_generator._calculate_bearish_score(available_data)
                        neutral_score = signal_generator._calculate_neutral_score(available_data)

                        print(f"  Bullish score: {bullish_score:.3f}")
                        print(f"  Bearish score: {bearish_score:.3f}")
                        print(f"  Neutral score: {neutral_score:.3f}")

                        scores = {
                            'bullish': bullish_score,
                            'bearish': bearish_score,
                            'neutral': neutral_score
                        }
                        max_score_type = max(scores, key=scores.get)
                        max_score = scores[max_score_type]

                        print(f"  Highest score: {max_score_type} ({max_score:.3f})")
                        print(f"  Minimum threshold: {signal_generator.min_signal_strength}")
                        print(f"  Should generate signal: {max_score >= signal_generator.min_signal_strength}")

                    except Exception as e:
                        print(f"  Error calculating scores: {e}")
        else:
            print(f"[FAIL] Insufficient data for signal generation: {len(available_data)} points")
    else:
        print("[FAIL] No stock data returned from pipeline!")

def test_multiple_dates():
    """Test the pipeline across multiple dates like the backtest does."""
    print("\n" + "=" * 50)
    print("TESTING MULTIPLE DATES (LIKE BACKTEST)")
    print("=" * 50)

    pipeline = OptionsDataPipeline(symbol="AAPL")
    signal_generator = SignalGenerator()

    # Test a few dates from the backtest range
    test_dates = [
        "2026-09-01",
        "2026-09-02",
        "2026-09-07",  # First Monday after weekend
        "2026-09-15",
        "2026-09-30"
    ]

    total_signals = 0

    for date_str in test_dates:
        print(f"\nTesting date: {date_str}")

        # Get lookback data (50 days before)
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        lookback_start = (dt - timedelta(days=50)).strftime('%Y-%m-%d')

        stock_data = pipeline.get_stock_data(lookback_start, date_str)

        if not stock_data.empty:
            current_date = stock_data['date'].iloc[-1]
            available_data = stock_data[stock_data['date'] <= current_date].copy()

            if len(available_data) >= 20:
                signal = signal_generator.get_signal(available_data, current_date)
                if signal is not None:
                    print(f"  [SIGNAL] {signal.signal_type} (strength: {signal.signal_strength:.3f})")
                    total_signals += 1
                else:
                    print(f"  [NO SIGNAL]")

                    # Show why by examining the data briefly
                    if len(available_data) >= 5:
                        recent_close = available_data['close'].tail(3).tolist()
                        print(f"    Recent closes: [${recent_close[0]:.2f}, ${recent_close[1]:.2f}, ${recent_close[2]:.2f}]")
            else:
                print(f"  [INSUFFICIENT DATA] {len(available_data)} points")
        else:
            print(f"  [NO DATA]")

    print(f"\nTotal signals generated across test dates: {total_signals}")

def main():
    """Main debug function."""
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    debug_pipeline_data()
    test_multiple_dates()

    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()