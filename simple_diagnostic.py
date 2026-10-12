#!/usr/bin/env python3
"""Simple diagnostic to test pipeline components."""

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

def test_price_data_semantics():
    """Test 1: Verify the price-data semantics."""
    print("=" * 50)
    print("TASK 1: VERIFY PRICE-DATA SEMANTICS")
    print("=" * 50)

    pipeline = OptionsDataPipeline(symbol="AAPL")
    stock_data = pipeline.get_stock_data("2026-09-01", "2026-09-30")

    print(f"Stock data columns: {list(stock_data.columns)}")
    print(f"Has 'adjusted_close': {'adjusted_close' in stock_data.columns}")
    print(f"Has 'close': {'close' in stock_data.columns}")

    if not stock_data.empty:
        # Check if adjusted_close equals close (as we set it)
        adjusted_equals_close = (stock_data['adjusted_close'] == stock_data['close']).all()
        print(f"adjusted_close equals close: {adjusted_equals_close}")

        if adjusted_equals_close:
            print("[PASS] Price data semantics: adjusted_close = close (appropriate for research simulation without dividends/splits)")
        else:
            print("[FAIL] Price data semantics issue: adjusted_close != close")

    return stock_data

def test_signal_generation(stock_data):
    """Test 2: Verify signal generation works."""
    print("\n" + "=" * 50)
    print("TASK 2: VERIFY SIGNAL GENERATION")
    print("=" * 50)

    signal_generator = SignalGenerator()

    # Get recent data for signal generation
    recent_data = stock_data.tail(50).copy()  # Last 50 days

    if len(recent_data) >= 20:
        # Ensure we have data up to a specific date
        current_date = recent_data['date'].iloc[-1]
        available_data = recent_data[recent_data['date'] <= current_date].copy()

        print(f"Testing signal generation for date: {current_date}")
        print(f"Available data points: {len(available_data)}")

        signal = signal_generator.get_signal(available_data, current_date)

        if signal is not None:
            print(f"[PASS] Signal generated: {signal.signal_type} with strength {signal.signal_strength:.3f}")
            print(f"  Details: {signal.metadata.get('details', 'No details')}")
            return True, signal
        else:
            print("[FAIL] No signal generated")
            return False, None
    else:
        print(f"[FAIL] Insufficient data for signal generation: {len(recent_data)} points")
        return False, None

def test_option_chain_and_spread_generation(stock_data):
    """Test 3: Verify option chain and spread generation."""
    print("\n" + "=" * 50)
    print("TASK 3: VERIFY OPTION CHAIN AND SPREAD GENERATION")
    print("=" * 50)

    # Get option chain for a recent date
    if not stock_data.empty:
        latest_date = stock_data['date'].iloc[-1]
        date_str = latest_date.strftime('%Y-%m-%d')

        pipeline = OptionsDataPipeline(symbol="AAPL")
        option_chain = pipeline.get_option_chain_data(date_str)

        print(f"Option chain date: {date_str}")
        print(f"Option chain size: {len(option_chain)} contracts")

        if not option_chain.empty:
            print("[PASS] Option chain data available")

            # Test spread generation
            strategy = VerticalSpreadStrategy('AAPL', max_risk_per_trade=0.02)

            # Get recent stock data for signal
            recent_stock = stock_data.tail(50).copy()
            current_date = recent_stock['date'].iloc[-1]
            available_stock = recent_stock[recent_stock['date'] <= current_date].copy()

            if len(available_stock) >= 20:
                signals = strategy.generate_spread_signals(available_stock, option_chain, current_date)
                print(f"Spread signals generated: {len(signals)}")

                if len(signals) > 0:
                    print("[PASS] Spread generation working")
                    # Try to create a position
                    portfolio_value = 100000.0
                    position = strategy.create_vertical_spread(signals[0], portfolio_value, current_date)
                    if position is not None:
                        print(f"[PASS] Position created: {position.option_type} spread {position.long_strike}/{position.short_strike}")
                        return True, signals, option_chain
                    else:
                        print("[FAIL] Failed to create position from signal")
                        return False, signals, option_chain
                else:
                    print("[FAIL] No spread signals generated")
                    return False, [], option_chain
            else:
                print("[FAIL] Insufficient stock data for signal generation")
                return False, [], option_chain
        else:
            print("[FAIL] No option chain data available")
            return False, [], None
    else:
        print("[FAIL] No stock data available")
        return False, [], None

def main():
    """Run simple diagnostic tests."""
    print("OPTIONS STRATEGY PIPELINE DIAGNOSTIC")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Task 1: Price data semantics
    stock_data = test_price_data_semantics()

    # Task 2: Signal generation
    signal_success, signal = test_signal_generation(stock_data)

    # Task 3: Option chain and spread generation
    spread_success, signals, option_chain = test_option_chain_and_spread_generation(stock_data)

    # Summary
    print("\n" + "=" * 50)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 50)
    print(f"Price data semantics: [PASS] if not stock_data.empty else [FAIL]")
    print(f"Signal generation: [PASS] if signal_success else [FAIL]")
    print(f"Option chain/spread generation: [PASS] if spread_success else [FAIL]")

    if signal_success and spread_success:
        print("\n[TARGET] PIPELINE VERIFIED: Core components are working")
        print("   The pipeline can generate signals and spreads.")
        print("   Next step would be to run a full backtest to verify trade execution.")
    else:
        print("\n[WARNING]  PIPELINE ISSUES: Some components are not working")
        if not signal_success:
            print("   - Signal generation is failing")
        if not spread_success:
            print("   - Option chain or spread generation is failing")

    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()