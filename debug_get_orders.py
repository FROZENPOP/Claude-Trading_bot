#!/usr/bin/env python3
"""Debug order retrieval using Webull MCP tools."""

import os
from dotenv import load_dotenv

load_dotenv()

app_key = os.environ.get('WEBULL_APP_KEY')
app_secret = os.environ.get('WEBULL_APP_SECRET')

# Initialize Webull executor
from trading_bot.execution.webull_execution import WebullExecution
executor = WebullExecution(
    app_key=app_key,
    app_secret=app_secret,
    environment="uat"  # Paper trading
)

print("Debugging order retrieval using Webull MCP tools:")

# Try getting order history via MCP
try:
    orders_result = mcp__webull__get_order_history()
    if orders_result is not None:
        print(f"[OK] get_order_history: {len(orders_result)} orders retrieved")
        if len(orders_result) > 0:
            print(f"First order example: {orders_result[0]}")
    else:
        print("[INFO] get_order_history: No orders found or empty response")
except Exception as e:
    print(f"[ERROR] get_order_history failed: {e}")

# Try getting open orders via MCP
try:
    open_orders_result = mcp__webull__get_open_orders()
    if open_orders_result is not None:
        print(f"[OK] get_open_orders: {len(open_orders_result)} open orders retrieved")
        if len(open_orders_result) > 0:
            print(f"First open order example: {open_orders_result[0]}")
    else:
        print("[INFO] get_open_orders: No open orders found or empty response")
except Exception as e:
    print(f"[ERROR] get_open_orders failed: {e}")

# Note: Webull MCP doesn't have parameterized order queries like Alpaca's GetOrdersRequest
# Instead, we get all orders and filter them ourselves if needed
print("\nNote: Webull MCP returns all orders, filtering must be done client-side")
print("Available MCP order functions:")
print("  - get_order_history: Gets historical orders (default last 7 days)")
print("  - get_open_orders: Gets all current open/pending orders")
print("  - get_order_detail: Gets details for a specific order by client_order_id")