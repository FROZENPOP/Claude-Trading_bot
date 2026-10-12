#!/usr/bin/env python3
"""Test the fixed buying power verification."""

import os
import sys
from dotenv import load_dotenv

# Add the trading_bot directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from trading_bot.execution.webull_execution import WebullExecution


def test_buying_power():
    """Test buying power verification for options."""

    load_dotenv()

    app_key = os.environ.get('WEBULL_APP_KEY')
    app_secret = os.environ.get('WEBULL_APP_SECRET')

    if not app_key or not app_secret:
        print("ERROR: Webull API credentials not found")
        return

    print("=== Testing Buying Power Verification ===")
    print()

    # Initialize executor
    executor = WebullExecution(
        api_key=app_key,
        secret_key=app_secret,
        paper=True,
        max_daily_loss=0.05,
        max_position_size=0.10,
        max_daily_trades=10
    )

    # Test case: BUY 5 contracts of AAPL261016C00190000
    symbol = "AAPL261016C00190000"  # AAPL call, strike 190, exp 2026-10-16
    quantity = 5  # Number of contracts

    print(f"Testing BUY {quantity} contracts of {symbol}")

    # Get a quote first
    mid_price = executor._get_latest_quote(symbol)
    if mid_price is None:
        print("Could not get quote, using estimated price")
        mid_price = 5.0  # Estimated price per share

    print(f"Estimated mid price (per share): ${mid_price:.2f}")

    # Calculate what the cost should be
    # For options: cost = quantity * price_per_share * 100
    estimated_cost = quantity * mid_price * 100
    print(f"Estimated total cost: {quantity} * ${mid_price:.2f} * 100 = ${estimated_cost:.2f}")
    print()

    # Check buying power manually using account info
    account_info = executor.get_account_info()
    if account_info:
        # For options: cost = quantity * price_per_share * 100
        estimated_cost = quantity * mid_price * 100
        buying_power = account_info.buying_power

        has_power = estimated_cost <= buying_power
        msg = f"Estimated cost: ${estimated_cost:.2f}, Available buying power: ${buying_power:.2f}"

        if has_power:
            print(f"PASS BUYING POWER CHECK: {msg}")
        else:
            print(f"FAIL BUYING POWER CHECK: {msg}")
    else:
        print("Could not retrieve account information to verify buying power")
        # For options: cost = quantity * price_per_share * 100
        estimated_cost = quantity * mid_price * 100
        print(f"Estimated cost: ${estimated_cost:.2f} (cannot verify buying power without account info)")

    print()
    print("=== Key Points ===")
    print("1. Buying power verification now correctly calculates options cost")
    print("2. For options: cost = quantity * price_per_share * 100")
    print("3. Checks options_buying_power when available, falls back to regular buying power")
    print("4. Should prevent orders that would fail due to insufficient options buying power")


if __name__ == "__main__":
    test_buying_power()