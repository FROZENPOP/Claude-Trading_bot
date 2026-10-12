#!/usr/bin/env python3
"""Test simple stock buy to verify basic trading works."""

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

# Try to buy 1 share of a cheap stock
symbol = "F"  # Ford - usually pretty cheap
print(f"Attempting to BUY 1 share of {symbol}")

# Create order request
order_request = OrderRequest(
    symbol=symbol,
    qty=1,
    side="buy",
    order_type="market",
    time_in_force="day"
)

try:
    # Submit order via WebullExecution
    success, error_msg, order = executor.submit_order(order_request)

    if success:
        print(f"SUCCESS! Bought stock: {order.id}")
        print(f"Status: {order.status}")
        print(f"Filled at: {order.avg_fill_price}")
    else:
        print(f"FAILED to buy stock: {error_msg}")

    # Try to cancel it immediately to clean up (if not filled)
    if success and order:
        try:
            cancel_success, cancel_error = executor.cancel_order(order.id)
            if cancel_success:
                print("Cancelled order for cleanup")
            else:
                print(f"Note: Could not cancel (may already be filled): {cancel_error}")
        except Exception as e:
            print(f"Note: Could not cancel (may already be filled): {e}")

except Exception as e:
    print(f"FAILED to buy stock: {e}")
    import traceback
    traceback.print_exc()