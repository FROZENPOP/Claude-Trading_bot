#!/usr/bin/env python3
"""Simple debug script to test the backtest with sample data."""

import pandas as pd
import numpy as np
from trading_bot.strategies.trend_following import TrendFollowingStrategy
from trading_bot.backtesting.engine import EventDrivenBacktest

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

def test_basic_backtest():
    """Test basic backtest functionality."""
    print("\nTESTING BASIC BACKTEST")
    print("=" * 50)

    # Create sample data
    data = create_sample_data()
    print(f"Data shape: {data.shape}")
    print(f"Columns: {list(data.columns)}")

    # Check if we have the required column
    if 'adjusted_close' not in data.columns:
        print("ERROR: 'adjusted_close' column missing!")
        return False

    # Create strategy
    strategy = TrendFollowingStrategy(
        short_window=10,
        medium_window=30,
        entry_threshold=0.5,
        exit_threshold=-0.3
    )

    # Run backtest
    print("Running backtest...")
    backtest = EventDrivenBacktest(
        strategy=strategy,
        initial_capital=100000
    )

    try:
        result_dict = backtest.run(data, 'TEST')
        print("Backtest completed successfully!")
        print(f"Result keys: {list(result_dict.keys())}")

        # Check daily values
        if 'daily_values' in result_dict:
            daily_values = result_dict['daily_values']
            print(f"Number of daily values: {len(daily_values)}")
            if len(daily_values) > 0:
                # Check first few values
                print("First 3 daily values:")
                for i, dv in enumerate(daily_values[:3]):
                    print(f"  {i}: date={dv['date']}, portfolio_value={dv['portfolio_value']}")

                # Check last few values
                print("Last 3 daily values:")
                for i, dv in enumerate(daily_values[-3:]):
                    idx = len(daily_values) - 3 + i
                    print(f"  {idx}: date={dv['date']}, portfolio_value={dv['portfolio_value']}")

                # Check if all values are the same
                values = [dv['portfolio_value'] for dv in daily_values]
                if len(set(values)) == 1:
                    print("WARNING: All portfolio values are identical!")
                else:
                    print(f"Portfolio value range: {min(values):.2f} to {max(values):.2f}")
            else:
                print("WARNING: No daily values recorded!")
        else:
            print("WARNING: No 'daily_values' in result!")

        return True
    except Exception as e:
        print(f"Backtest failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_basic_backtest()
    if success:
        print("\n[SUCCESS] Basic backtest test passed")
    else:
        print("\n[FAILURE] Basic backtest test failed")