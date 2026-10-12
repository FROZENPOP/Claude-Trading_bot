#!/usr/bin/env python3
"""Debug what quote we're getting for an option symbol."""

import os
import sys
from dotenv import load_dotenv

# Add the trading_bot directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from trading_bot.execution.webull_execution import WebullExecution


def debug_quote():
    """Debug the quote for an option symbol."""

    load_dotenv()

    app_key = os.environ.get('WEBULL_APP_KEY')
    app_secret = os.environ.get('WEBULL_APP_SECRET')

    if not app_key or not app_secret:
        print("ERROR: Webull API credentials not found")
        return

    print("=== Debugging Option Quote ===")
    print()

    # Initialize executor
    executor = WebullExecution(
        app_key=app_key,
        app_secret=app_secret,
        environment="uat"  # Paper trading
    )

    # Test symbol
    symbol = "AAPL261016C00190000"  # AAPL call, strike 190, exp 2026-10-16
    print(f"Getting quote for: {symbol}")

    # Get a quote
    mid_price = executor._get_latest_quote(symbol)
    if mid_price is None:
        print("Could not get quote")
        return

    print(f"Mid price (from our _get_latest_quote): ${mid_price:.2f}")
    print(f"This is interpreted as: ${mid_price:.2f} per share")
    print(f"For 1 contract (100 shares): ${mid_price * 100:.2f}")
    print()

    # Let's also try to get the raw quote data to see bid/ask using MCP tools directly
    try:
        # Try to get quote via MCP
        quote_result = mcp__webull__get_option_latest_quote(symbols=symbol)
        if quote_result and 'data' in quote_result and len(quote_result['data']) > 0:
            quote_data = quote_result['data'][0]
            bid_price = quote_data.get('bid_price')
            ask_price = quote_data.get('ask_price')
            if bid_price is not None and ask_price is not None:
                bid = float(bid_price)
                ask = float(ask_price)
                mid = (bid + ask) / 2
                print(f"Raw quote data (MCP):")
                print(f"  Bid: ${bid:.2f} per share")
                print(f"  Ask: ${ask:.2f} per share")
                print(f"  Mid: ${mid:.2f} per share")
                print(f"  Contract cost (100 shares): ${mid * 100:.2f}")
            else:
                print("Could not get bid/ask prices from MCP")
        else:
            print("No quote data returned from MCP")

    except Exception as e:
        print(f"Error getting raw quote via MCP: {e}")


if __name__ == "__main__":
    debug_quote()