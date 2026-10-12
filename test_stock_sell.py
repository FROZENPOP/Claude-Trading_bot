#!/usr/bin/env python3
"""Test simple stock sell to verify short selling works."""

import os
import sys
import time
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

# First, let's make sure we have a share to sell by buying one
symbol = "F"  # Ford
print(f"First buying 1 share of {symbol} to have something to sell...")

try:
    # Create buy order request
    buy_order = OrderRequest(
        symbol=symbol,
        qty=1,
        side="buy",
        order_type="market",
        time_in_force="day"
    )

    buy_success, buy_error, buy_order_obj = executor.submit_order(buy_order)

    if buy_success:
        print(f"Bought stock: {buy_order_obj.id}")

        # Wait a moment for it to potentially fill
        time.sleep(2)

        # Now try to sell it
        print(f"Attempting to SELL 1 share of {symbol}")
        sell_order = OrderRequest(
            symbol=symbol,
            qty=1,
            side="sell",
            order_type="market",
            time_in_force="day"
        )
        sell_success, sell_error, sell_order_obj = executor.submit_order(sell_order)
        if sell_success:
            print(f"SUCCESS! Sold stock: {sell_order_obj.id}")
            print(f"Status: {sell_order_obj.status}")

            # Clean up any remaining orders
            try:
                if buy_success and buy_order_obj:
                    cancel_success, cancel_error = executor.cancel_order(buy_order_obj.id)
                    if cancel_success:
                        print("Cancelled buy order")
                    else:
                        print(f"Note: Could not cancel buy order: {cancel_error}")
                if sell_success and sell_order_obj:
                    cancel_success, cancel_error = executor.cancel_order(sell_order_obj.id)
                    if cancel_success:
                        print("Cancelled sell order")
                    else:
                        print(f"Note: Could not cancel sell order: {cancel_error}")
            except Exception as e:
                print(f"Note: Error during cleanup: {e}")
        else:
            print(f"FAILED to sell stock: {sell_error}")

            # Try to cleanup the buy order if sell failed
            try:
                if buy_success and buy_order_obj:
                    cancel_success, cancel_error = executor.cancel_order(buy_order_obj.id)
                    if cancel_success:
                        print("Cancelled buy order")
                    else:
                        print(f"Note: Could not cancel buy order: {cancel_error}")
            except Exception as e:
                print(f"Note: Error during cleanup: {e}")
    else:
        print(f"FAILED to buy stock: {buy_error}")

except Exception as e:
    print(f"FAILED: {e}")
    import traceback
    traceback.print_exc()