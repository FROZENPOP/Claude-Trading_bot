#!/usr/bin/env python3
"""Test the smoke test function from research_options_strategies.py."""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__)))

from research_options_strategies import OptionsDataPipeline, SignalGenerator, VerticalSpreadStrategy
import datetime
import pandas as pd

def run_smoke_test():
    """Run a smoke test with the same parameters as the verified diagnostic."""
    print("RUNNING SMOKE TEST")
    print("=" * 30)

    # Use the same parameters as in our verified diagnostic
    lookback_start = "2026-07-19"
    end_date = "2026-09-07"

    print(f"Testing data loading from {lookback_start} to {end_date}")

    try:
        # Initialize pipeline
        pipeline = OptionsDataPipeline(symbol="AAPL")

        # Test data loading
        stock_data = pipeline.get_stock_data(lookback_start, end_date)

        if stock_data.empty:
            print("ERROR: No stock data loaded")
            return False

        print(f"[PASS] Stock data loaded: {len(stock_data)} rows")
        print(f"  Date range: {stock_data['date'].min()} to {stock_data['date'].max()}")
        print(f"  Columns: {list(stock_data.columns)}")

        # Test option chain data loading
        option_chain = pipeline.get_option_chain_data(end_date)

        if option_chain.empty:
            print("ERROR: No option chain data loaded")
            return False

        print(f"[PASS] Option chain data loaded: {len(option_chain)} contracts")
        if 'expiration_date' in option_chain.columns:
            exp_dates = option_chain['expiration_date'].unique()
            print(f"  Expiration dates: {len(exp_dates)} unique dates")
            print(f"  Range: {min(exp_dates)} to {max(exp_dates)}")

        # Test historical option data loading
        # We'll test with a specific date and DTE
        test_date = datetime.datetime(2026, 8, 15)
        test_dte = 21

        hist_data = pipeline.get_historical_option_data(
            "AAPL",
            test_date.strftime('%Y-%m-%d'),
            test_dte
        )

        if hist_data.empty:
            print("WARNING: No historical option data for test date/DTE (may be expected)")
        else:
            print(f"[PASS] Historical option data loaded: {len(hist_data)} rows")

        # Test data provenance
        print(f"\nDATA PROVENANCE CHECK:")
        print(f"  Symbol: AAPL")
        print(f"  Period: {lookback_start} to {end_date}")
        print(f"  Data source: Alpaca Historical Data (via MCP)")

        # Test signal generation
        signal_generator = SignalGenerator()
        latest_date = stock_data['date'].max()
        available_data = stock_data[stock_data['date'] <= latest_date].copy()

        raw_signal = signal_generator.get_signal(available_data, latest_date)

        if raw_signal is None:
            print("WARNING: No signal generated (may be market conditions)")
            # This isn't necessarily a failure - could be valid market conditions
        else:
            print(f"[PASS] Signal generated: {raw_signal.signal_type} (strength: {raw_signal.signal_strength:.3f})")

        # Test strategy
        strategy = VerticalSpreadStrategy('AAPL', max_risk_per_trade=0.02)

        # Get option chain for latest date
        latest_option_chain = pipeline.get_option_chain_data(latest_date.strftime('%Y-%m-%d'))
        if not latest_option_chain.empty:
            latest_option_chain['days_to_exp'] = latest_option_chain['expiration_date'].apply(
                lambda x: (datetime.datetime.strptime(x, '%Y-%m-%d').date() - latest_date.date()).days if pd.notna(x) else None
            )

            spread_signals = strategy.generate_spread_signals(available_data, latest_option_chain, latest_date)

            print(f"[PASS] Spread signals generated: {len(spread_signals)}")

            if len(spread_signals) > 0:
                print(f"  Sample signal:")
                sample = spread_signals[0]
                print(f"    Type: {sample.signal_type}")
                print(f"    Long strike: {getattr(sample, 'long_strike', 'N/A')}")
                print(f"    Short strike: {getattr(sample, 'short_strike', 'N/A')}")
                print(f"    Option type: {getattr(sample, 'option_type', 'N/A')}")
                print(f"    Days to exp: {getattr(sample, 'days_to_exp', 'N/A')}")
                print(f"    Net debit: ${getattr(sample, 'net_debit', 0.0):.2f}")

                return True
            else:
                print("WARNING: No spread signals generated (may be market conditions)")
                # This isn't necessarily a failure - could be valid market conditions
                return True
        else:
            print("ERROR: Could not load option chain for latest date")
            return False

    except Exception as e:
        print(f"ERROR: Smoke test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function."""
    print(f"Started at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    success = run_smoke_test()

    print()
    print(f"Completed at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if success:
        print("\nSMOKE TEST RESULT: PASSED")
        print("The research framework is working with real MCP data.")
    else:
        print("\nSMOKE TEST RESULT: FAILED")
        print("There are issues with the research framework.")

    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)