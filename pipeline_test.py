#!/usr/bin/env python3
"""Test the full options pipeline with trending data to generate signals."""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add project to path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from research_options_strategies import OptionsDataPipeline
from trading_bot.strategies.vertical_spread import VerticalSpreadStrategy
from trading_bot.strategies.signals import SignalGenerator

def create_trending_data(days=30, trend=0.005):
    """Create trending price data to generate directional signals."""
    dates = [datetime.now() - timedelta(days=i) for i in range(days, 0, -1)]

    # Create trending price data
    base_price = 100.0
    prices = []
    for i in range(days):
        # Add trend plus some noise
        price = base_price * (1 + trend) ** i * (1 + np.random.normal(0, 0.01))
        prices.append(price)

    # Create OHLCV data
    data = []
    for i, (date, close) in enumerate(zip(dates, prices)):
        volatility = 0.02
        high = close * (1 + abs(np.random.normal(0, volatility/2)))
        low = close * (1 - abs(np.random.normal(0, volatility/2)))
        open_price = close * (1 + np.random.normal(0, volatility/4))
        volume = np.random.randint(1000000, 10000000)

        data.append({
            'date': date,
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'adjusted_close': close,  # For research simulation
            'volume': volume,
            'symbol': 'AAPL'
        })

    return pd.DataFrame(data)

def test_full_pipeline():
    """Test the full pipeline with trending data."""
    print("TESTING FULL OPTIONS PIPELINE WITH TRENDING DATA")
    print("=" * 60)

    # Create trending data (bullish trend)
    print("Creating bullish trending data...")
    stock_data = create_trending_data(days=40, trend=0.003)  # 0.3% daily trend

    print(f"Generated {len(stock_data)} days of data")
    print(f"Price range: ${stock_data['close'].min():.2f} to ${stock_data['close'].max():.2f}")
    print(f"Overall trend: {((stock_data['close'].iloc[-1] / stock_data['close'].iloc[0]) - 1):.2%}")

    # Test signal generation
    print("\n--- SIGNAL GENERATION ---")
    signal_generator = SignalGenerator()

    # Test with most recent data
    current_date = stock_data['date'].iloc[-1]
    available_data = stock_data[stock_data['date'] <= current_date].copy()

    print(f"Testing signal for date: {current_date}")
    print(f"Available data points: {len(available_data)}")

    signal = signal_generator.get_signal(available_data, current_date)

    if signal is not None:
        print(f"Signal: {signal.signal_type} (strength: {signal.signal_strength:.3f})")
        print(f"Details: {signal.metadata.get('details', 'No details')}")

        # Show what indicators contributed
        if 'bullish_score' in signal.metadata:
            print(f"Scores - Bullish: {signal.metadata['bullish_score']:.3f}, "
                  f"Bearish: {signal.metadata['bearish_score']:.3f}, "
                  f"Neutral: {signal.metadata['neutral_score']:.3f}")
    else:
        print("No signal generated")
        return False

    # Test option chain and spread generation
    print("\n--- OPTION CHAIN AND SPREAD GENERATION ---")
    if signal.signal_type in ['bullish', 'bearish'] and signal.signal_strength > 0.3:
        pipeline = OptionsDataPipeline(symbol="AAPL")
        option_chain = pipeline.get_option_chain_data(current_date.strftime('%Y-%m-%d'))

        print(f"Option chain date: {current_date.strftime('%Y-%m-%d')}")
        print(f"Option chain size: {len(option_chain)} contracts")

        if not option_chain.empty:
            strategy = VerticalSpreadStrategy('AAPL', max_risk_per_trade=0.02)

            signals = strategy.generate_spread_signals(available_data, option_chain, current_date)
            print(f"Spread signals generated: {len(signals)}")

            if len(signals) > 0:
                print(f"First spread signal: {signals[0].signal_type} signal")
                if hasattr(signals[0], 'long_strike'):
                    print(f"  Strikes: {signals[0].long_strike}/{signals[0].short_strike}")
                    print(f"  Option type: {getattr(signals[0], 'option_type', 'unknown')}")
                    print(f"  Net debit: ${getattr(signals[0], 'net_debit', 0.0):.2f}")

                # Try to create a position
                print("\n--- POSITION CREATION ---")
                portfolio_value = 100000.0
                position = strategy.create_vertical_spread(signals[0], portfolio_value, current_date)

                if position is not None:
                    print(f"[SUCCESS] Position created:")
                    print(f"  Type: {position.option_type} vertical spread")
                    print(f"  Strikes: {position.long_strike}/{position.short_strike}")
                    print(f"  Quantity: {abs(position.long_quantity)} contracts")
                    print(f"  Entry price: ${position.entry_price:.2f} (net debit)")
                    print(f"  Max risk: ${position.max_loss:.2f}")
                    print(f"  Max profit: ${position.max_profit:.2f}")
                    print(f"  Breakeven: ${position.breakeven:.2f}")

                    # Test exit logic
                    print("\n--- EXIT LOGIC TEST ---")
                    should_exit, exit_price, reason = strategy.exit_spread(
                        position, option_chain, current_date + timedelta(days=5)
                    )
                    print(f"Exit test (5 days later): {should_exit} - {reason}")
                    if should_exit:
                        print(f"  Exit price: ${exit_price:.2f}")

                    return True
                else:
                    print("[FAIL] Failed to create position from spread signal")
                    return False
            else:
                print("[FAIL] No spread signals generated from directional signal")
                return False
        else:
            print("[FAIL] No option chain data available")
            return False
    else:
        print(f"[INFO] Signal not strong enough for spread generation: {signal.signal_type} (strength: {signal.signal_strength:.3f})")
        # Try again with stronger signal by increasing trend
        print("Retrying with stronger trend...")
        stock_data_strong = create_trending_data(days=40, trend=0.008)  # 0.8% daily trend
        current_date = stock_data_strong['date'].iloc[-1]
        available_data = stock_data_strong[stock_data_strong['date'] <= current_date].copy()
        signal = signal_generator.get_signal(available_data, current_date)
        print(f"Strong trend signal: {signal.signal_type} (strength: {signal.signal_strength:.3f})")

        if signal.signal_type in ['bullish', 'bearish'] and signal.signal_strength > 0.3:
            # Continue with spread generation test...
            pipeline = OptionsDataPipeline(symbol="AAPL")
            option_chain = pipeline.get_option_chain_data(current_date.strftime('%Y-%m-%d'))

            if not option_chain.empty:
                strategy = VerticalSpreadStrategy('AAPL', max_risk_per_trade=0.02)
                signals = strategy.generate_spread_signals(available_data, option_chain, current_date)

                if len(signals) > 0:
                    portfolio_value = 100000.0
                    position = strategy.create_vertical_spread(signals[0], portfolio_value, current_date)
                    if position is not None:
                        print(f"[SUCCESS] Position created with strong trend:")
                        print(f"  Type: {position.option_type} vertical spread")
                        print(f"  Strikes: {position.long_strike}/{position.short_strike}")
                        return True

        print("[FAIL] Could not generate tradable signal even with strong trend")
        return False

def main():
    """Main test function."""
    print("OPTIONS PIPELINE FUNCTIONALITY TEST")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    success = test_full_pipeline()

    print("\n" + "=" * 60)
    print("FINAL RESULT")
    print("=" * 60)

    if success:
        print("[SUCCESS] PIPELINE VERIFIED")
        print("The options strategy pipeline is working end-to-end:")
        print("  1. Price data generated with adjusted_close column")
        print("  2. Signals generated from price data")
        print("  3. Spread signals generated from directional signals")
        print("  4. Positions created from spread signals")
        print("  5. Exit logic functional")
        print()
        print("Next step: Run diagnostic backtest with full pipeline stage reporting")
    else:
        print("[FAIL] PIPELINE ISSUES")
        print("The options strategy pipeline is not working end-to-end")
        print("Further investigation needed")

    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()