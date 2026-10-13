#!/usr/bin/env python3
"""Debug script to test the strategy indicator calculation."""

import pandas as pd
import numpy as np
from trading_bot.strategies.trend_following import TrendFollowingStrategy

def create_sample_data():
    """Create sample stock data for testing."""
    print("Creating sample data for testing...")

    # Generate 100 days of data for simplicity
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
    # Remove weekends
    dates = dates[dates.weekday < 5]

    # Generate realistic price data
    np.random.seed(42)
    n_days = len(dates)
    returns = np.random.normal(0.0008, 0.015, n_days)  # Slight positive drift

    # Add some regime changes
    regime_change_point = n_days // 2
    returns[regime_change_point:] += 0.0003  # Slightly better second half

    prices = [100.0]  # Starting price
    for ret in returns[1:]:
        prices.append(prices[-1] * (1 + ret))

    # Create OHLCV data with adjusted_close
    data = []
    for i, (date, close) in enumerate(zip(dates, prices)):
        volatility = 0.015
        high = close * (1 + abs(np.random.normal(0, volatility/2)))
        low = close * (1 - abs(np.random.normal(0, volatility/2)))
        open_price = close * (1 + np.random.normal(0, volatility/4))
        volume = np.random.randint(500000, 5000000)
        adjusted_close = close  # Using close as adjusted_close for simplicity

        data.append({
            'date': date,
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'adjusted_close': adjusted_close,
            'volume': volume,
            'symbol': 'TEST'
        })

    df = pd.DataFrame(data)
    print(f"Created sample data: {len(df)} days")
    return df

def test_strategy_indicators():
    """Test strategy indicator calculation."""
    print("\nTESTING STRATEGY INDICATOR CALCULATION")
    print("=" * 50)

    # Create sample data
    data = create_sample_data()
    print(f"Data shape: {data.shape}")
    print(f"Columns: {list(data.columns)}")

    # Check if we have the required column
    if 'adjusted_close' not in data.columns:
        print("ERROR: 'adjusted_close' column missing!")
        return False

    # Create strategy with smaller windows for our limited data
    strategy = TrendFollowingStrategy(
        short_window=5,
        medium_window=15,
        long_window=25,
        entry_threshold=0.5,
        exit_threshold=-0.3
    )

    # Calculate indicators
    print("Calculating indicators...")
    try:
        data_with_indicators = strategy.calculate_all_indicators(data.copy())
        print("Indicators calculated successfully!")
        print(f"Columns after calculation: {list(data_with_indicators.columns)}")

        # Check for key indicator columns
        required_cols = ['short_ma', 'medium_ma', 'long_ma', 'composite_score', 'signal']
        for col in required_cols:
            if col in data_with_indicators.columns:
                print(f"Column '{col}' present")
                # Check for NaN values
                nan_count = data_with_indicators[col].isna().sum()
                if nan_count > 0:
                    print(f"  WARNING: {nan_count} NaN values in '{col}'")
                    if nan_count == len(data_with_indicators):
                        print(f"  ERROR: All values in '{col}' are NaN!")
                else:
                    print(f"  Value range: {data_with_indicators[col].min():.4f} to {data_with_indicators[col].max():.4f}")
            else:
                print(f"ERROR: Column '{col}' missing!")

        # Show first few rows with indicators
        print("\nFirst 10 rows with indicators:")
        print(data_with_indicators[['date', 'adjusted_close', 'short_ma', 'medium_ma', 'long_ma', 'composite_score', 'signal']].head(10))

        # Show last few rows with indicators
        print("\nLast 10 rows with indicators:")
        print(data_with_indicators[['date', 'adjusted_close', 'short_ma', 'medium_ma', 'long_ma', 'composite_score', 'signal']].tail(10))

        return True
    except Exception as e:
        print(f"Error calculating indicators: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_strategy_indicators()
    if success:
        print("\n[SUCCESS] Strategy indicator test passed")
    else:
        print("\n[FAILURE] Strategy indicator test failed")