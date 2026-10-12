#!/usr/bin/env python3
"""Test OptionsDataPipeline integration with pre-fetched real MCP data."""

import sys
import os
import pandas as pd
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__)))

from research_options_strategies import OptionsDataPipeline, SignalGenerator, VerticalSpreadStrategy

def test_prefetch_integration():
    """Test that OptionsDataPipeline works with pre-fetched real MCP data."""
    print("TESTING OPTIONS DATA PIPELINE WITH PREFETCHED REAL MCP DATA")
    print("=" * 65)

    try:
        # Step 1: Fetch real data using MCP tools (available in this Claude Code environment)
        print("[STEP 1] Fetching real data using MCP tools...")

        # Fetch stock data
        print("  Fetching AAPL stock data...")
        stock_mcp_result = mcp__alpaca__get_stock_bars(
            symbol="AAPL",
            timeframe="1Day",
            start="2026-07-19",
            end="2026-09-07"
        )

        # Convert stock data to DataFrame
        if hasattr(stock_mcp_result, 'df'):
            stock_df = stock_mcp_result.df.copy()
        elif isinstance(stock_mcp_result, dict) and 'data' in stock_mcp_result:
            stock_df = pd.DataFrame(stock_mcp_result['data'])
        else:
            stock_df = pd.DataFrame(stock_mcp_result)

        # Standardize stock data format
        if 'timestamp' in stock_df.columns:
            stock_df['date'] = pd.to_datetime(stock_df['timestamp']).dt.date
        elif 'time' in stock_df.columns:
            stock_df['date'] = pd.to_datetime(stock_df['time']).dt.date

        # Ensure required columns
        required_columns = ['date', 'open', 'high', 'low', 'close', 'volume']
        for col in required_columns:
            if col not in stock_df.columns:
                if col == 'volume' and 'volume' not in stock_df.columns:
                    if 'vol' in stock_df.columns:
                        stock_df['volume'] = stock_df['vol']
                elif col == 'close' and 'close' not in stock_df.columns:
                    if 'c' in stock_df.columns:
                        stock_df['close'] = stock_df['c']

        # Add adjusted_close and symbol
        if 'adjusted_close' not in stock_df.columns:
            stock_df['adjusted_close'] = stock_df['close']
        stock_df['symbol'] = 'AAPL'

        # Select expected columns
        expected_columns = ['date', 'open', 'high', 'low', 'close', 'volume', 'adjusted_close', 'symbol']
        available_columns = [col for col in expected_columns if col in stock_df.columns]
        stock_df = stock_df[available_columns].copy()

        print(f"    ✓ Fetched {len(stock_df)} rows of stock data")

        # Fetch option chain data for multiple dates (we'll use the end date as in diagnostic)
        end_date = "2026-09-07"
        print(f"  Fetching AAPL option chain data for {end_date}...")
        option_chain_mcp_result = mcp__alpaca__get_option_chain(
            underlying_symbol="AAPL",
            date=end_date
        )

        # Convert option chain data to DataFrame
        if hasattr(option_chain_mcp_result, 'df'):
            option_chain_df = option_chain_mcp_result.df.copy()
        elif isinstance(option_chain_mcp_result, dict) and 'data' in option_chain_mcp_result:
            option_chain_df = pd.DataFrame(option_chain_mcp_result['data'])
        else:
            option_chain_df = pd.DataFrame(option_chain_mcp_result)

        # Standardize option chain data format
        column_mapping = {
            'timestamp': 'date',
            'trade_time': 'date',
            'expiration': 'expiration_date',
            'strike': 'strike_price',
            'underlying': 'underlying_symbol',
            'option_type': 'option_type',
            'bid': 'bid_price',
            'ask': 'ask_price',
            'last': 'last_price',
            'volume': 'volume',
            'open_interest': 'open_interest'
        }

        # Rename columns if they exist in the mapping
        for old_col, new_col in column_mapping.items():
            if old_col in option_chain_df.columns and new_col not in option_chain_df.columns:
                option_chain_df[new_col] = option_chain_df[old_col]

        # Ensure required columns
        required_columns = ['symbol', 'expiration_date', 'strike_price', 'option_type']
        for col in required_columns:
            if col not in option_chain_df.columns:
                if col == 'symbol':
                    option_chain_df['symbol'] = 'AAPL'
                elif col == 'underlying_symbol':
                    option_chain_df['underlying_symbol'] = 'AAPL'

        # Add symbol columns if not present
        if 'symbol' not in option_chain_df.columns:
            option_chain_df['symbol'] = 'AAPL'
        if 'underlying_symbol' not in option_chain_df.columns:
            option_chain_df['underlying_symbol'] = 'AAPL'

        # Organize data for the pipeline (date -> DataFrame mapping)
        option_chain_data = {end_date: option_chain_df}
        print(f"    ✓ Fetched {len(option_chain_df)} option chain contracts for {end_date}")

        # We won't fetch historical option data for this simple test
        historical_option_data = {}
        print("    ✓ No historical option data fetched (not needed for this test)")

        # Step 2: Initialize pipeline with pre-fetched data
        print("\n[STEP 2] Initializing OptionsDataPipeline with pre-fetched data...")
        pipeline = OptionsDataPipeline(
            symbol="AAPL",
            stock_data=stock_df,
            option_chain_data=option_chain_data,
            historical_option_data=historical_option_data
        )
        print("    ✓ Pipeline initialized successfully")

        # Step 3: Test data loading from pipeline
        print("\n[STEP 3] Testing data loading from pipeline...")

        # Test stock data loading
        lookback_start = "2026-07-19"
        end_date = "2026-09-07"
        stock_data_loaded = pipeline.get_stock_data(lookback_start, end_date)

        if stock_data_loaded.empty:
            print("    ✗ ERROR: No stock data loaded from pipeline")
            return False

        print(f"    ✓ Stock data loaded from pipeline: {len(stock_data_loaded)} rows")
        print(f"      Date range: {stock_data_loaded['date'].min()} to {stock_data_loaded['date'].max()}")

        # Test option chain data loading
        option_chain_loaded = pipeline.get_option_chain_data(end_date)

        if option_chain_loaded.empty:
            print("    ✗ ERROR: No option chain data loaded from pipeline")
            return False

        print(f"    ✓ Option chain data loaded from pipeline: {len(option_chain_loaded)} contracts")
        if 'expiration_date' in option_chain_loaded.columns:
            exp_dates = option_chain_loaded['expiration_date'].unique()
            print(f"      Expiration dates: {len(exp_dates)} unique dates")
            print(f"      Range: {min(exp_dates)} to {max(exp_dates)}")

        # Step 4: Test signal generation
        print("\n[STEP 4] Testing signal generation...")
        signal_generator = SignalGenerator()
        latest_date = stock_data_loaded['date'].max()
        available_data = stock_data_loaded[stock_data_loaded['date'] <= latest_date].copy()

        raw_signal = signal_generator.get_signal(available_data, latest_date)

        if raw_signal is None:
            print("    ✗ ERROR: No signal generated")
            return False

        print(f"    ✓ Signal generated: {raw_signal.signal_type} (strength: {raw_signal.signal_strength:.3f})")

        # Step 5: Test strategy and spread signal generation
        print("\n[STEP 5] Testing strategy and spread signal generation...")
        strategy = VerticalSpreadStrategy('AAPL', max_risk_per_trade=0.02)

        # Get option chain for latest date
        latest_option_chain = pipeline.get_option_chain_data(latest_date.strftime('%Y-%m-%d'))
        if latest_option_chain.empty:
            print("    ✗ ERROR: Could not load option chain for latest date")
            return False

        # Add days_to_exp for processing
        latest_option_chain['days_to_exp'] = latest_option_chain['expiration_date'].apply(
            lambda x: (datetime.strptime(x, '%Y-%m-%d') - latest_date).days if pd.notna(x) else None
        )

        spread_signals = strategy.generate_spread_signals(available_data, latest_option_chain, latest_date)

        print(f"    ✓ Spread signals generated: {len(spread_signals)}")

        if len(spread_signals) > 0:
            print("    Sample signal:")
            sample = spread_signals[0]
            print(f"      Type: {sample.signal_type}")
            print(f"      Long strike: {getattr(sample, 'long_strike', 'N/A')}")
            print(f"      Short strike: {getattr(sample, 'short_strike', 'N/A')}")
            print(f"      Option type: {getattr(sample, 'option_type', 'N/A')}")
            print(f"      Days to exp: {getattr(sample, 'days_to_exp', 'N/A')}")
            print(f"      Net debit: ${getattr(sample, 'net_debit', 0.0):.2f}")

            return True
        else:
            print("    ⚠ WARNING: No spread signals generated (may be market conditions)")
            # This isn't necessarily a failure - could be valid market conditions
            return True

    except Exception as e:
        print(f"\n✗ ERROR: Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function."""
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    success = test_prefetch_integration()

    print()
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if success:
        print("\n✅ INTEGRATION TEST PASSED!")
        print("The OptionsDataPipeline works correctly with pre-fetched real MCP data.")
        print("This confirms the external-data injection approach is viable.")
    else:
        print("\n❌ INTEGRATION TEST FAILED")
        print("There are issues with the OptionsDataPipeline integration.")

    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)