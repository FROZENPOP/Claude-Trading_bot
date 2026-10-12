#!/usr/bin/env python3
"""Run multiple backtests across different symbols."""

import subprocess
import sys
import time

# List of symbols to test (from expanded watchlist)
symbols = [
    'AAPL', 'MSFT', 'GOOGL',  # Tech
    'JPM', 'BAC',             # Banking
    'JNJ', 'PFE',             # Healthcare
    'XOM', 'CVX',             # Energy
    'HD', 'MCD',              # Retail
    'SPY', 'QQQ'              # ETFs
]

def run_backtest(symbol):
    """Run a single backtest."""
    print(f"\n{'='*60}")
    print(f"Running backtest for {symbol}")
    print(f"{'='*60}")

    cmd = [
        sys.executable, 'run_backtest.py',
        '--symbol', symbol,
        '--train-start', '2015-01-01',
        '--train-end', '2020-12-31'
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"* Backtest for {symbol} completed successfully")
        # Show just the summary lines
        for line in result.stdout.split('\n'):
            if 'BACKTEST RESULTS:' in line or 'Total Return:' in line or 'Sharpe Ratio:' in line or 'Max Drawdown:' in line:
                print(line)
    else:
        print(f"! Backtest for {symbol} failed:")
        print(result.stdout)
        print(result.stderr)

    return result.returncode == 0

def main():
    """Run backtests for all symbols."""
    print("Running multi-symbol backtests...")
    print(f"Testing {len(symbols)} symbols")

    successful = 0
    failed = 0

    for symbol in symbols:
        if run_backtest(symbol):
            successful += 1
        else:
            failed += 1

        # Small delay between backtests
        time.sleep(1)

    print(f"\n{'='*60}")
    print(f"BACKTEST SUMMARY")
    print(f"{'='*60}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Total: {len(symbols)}")

    if failed > 0:
        sys.exit(1)
    else:
        print("All backtests completed successfully!")

if __name__ == "__main__":
    main()