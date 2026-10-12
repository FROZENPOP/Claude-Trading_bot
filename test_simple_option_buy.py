#!/usr/bin/env python3
"""Test simple option buy to isolate the issue."""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add the trading_bot directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'trading_bot'))

from trading_bot.execution.webull_execution import WebullExecution, OrderRequest

load_dotenv()

app_key = os.environ.get('WEBULL_APP_KEY')
app_secret = os.environ.get('WEBULL_APP_SECRET')

if not app_key or not app_secret:
    print("ERROR: Webull API credentials not found")
    sys.exit(1)

# Initialize executor
executor = WebullExecution(
    app_key=app_key,
    app_secret=app_secret,
    environment="uat"  # Paper trading
)

# Try to buy a simple option we know exists from earlier testing
# From our earlier debug, we know AAPL261016C00190000 exists and has a quote
symbol = "AAPL261016C00190000"  # AAPL call, strike 190, exp 2026-10-16

print(f"Attempting to BUY 1 contract of {symbol}")

# First, let's get a quote to see what it's worth
try:
    # Get quote via MCP
    quote_result = mcp__webull__get_option_latest_quote(symbols=symbol)
    if quote_result and 'data' in quote_result and len(quote_result['data']) > 0:
        quote_data = quote_result['data'][0]
        bid_price = quote_data.get('bid_price')
        ask_price = quote_data.get('ask_price')
        if bid_price is not None and ask_price is not None:
            mid_price = (float(bid_price) + float(ask_price)) / 2
            print(f"Option quote: Bid=${bid_price:.2f}, Ask=${ask_price:.2f}, Mid=${mid_price:.2f}")

            # Try to BUY 1 contract
            print(f"\nAttempting to BUY 1 contract of {symbol} at ${mid_price:.2f}")
            try:
                # Create limit order request
                order_request = OrderRequest(
                    symbol=symbol,
                    qty=1,
                    side="buy",
                    order_type="limit",
                    limit_price=round(mid_price, 2),
                    time_in_force="day"
                )

                success, error_msg, order = executor.submit_order(order_request)

                if success:
                    print(f"SUCCESS! Bought option: {order.id}")
                    print(f"Status: {order.status}")

                    # Try to cancel it immediately to clean up
                    try:
                        cancel_success, cancel_error = executor.cancel_order(order.id)
                        if cancel_success:
                            print("Cancelled order for cleanup")
                        else:
                            print(f"Note: Could not cancel (may already be filled): {cancel_error}")
                    except Exception as e:
                        print(f"Note: Could not cancel (may already be filled): {e}")
                else:
                    print(f"FAILED to buy option: {error_msg}")
            except Exception as e:
                print(f"FAILED to buy option: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("Could not get bid/ask for option")
    else:
        print("No quote data for option")

except Exception as e:
    print(f"Error getting option quote: {e}")
    import traceback
    traceback.print_exc()