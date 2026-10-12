#!/usr/bin/env python3
"""Debug how to properly get orders using Webull MCP tools."""

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

print("Testing order retrieval using Webull MCP tools:")

# Try getting orders via MCP
try:
    # Get all orders
    orders_result = mcp__webull__get_order_history()
    if orders_result:
        print(f"[OK] get_order_history: {len(orders_result)} orders")
        # Show first few orders if any
        if len(orders_result) > 0:
            print("First order:", orders_result[0])
    else:
        print("[INFO] get_order_history: No orders found or empty response")
except Exception as e:
    print(f"[ERROR] get_order_history failed: {e}")

# Try getting open orders
try:
    open_orders_result = mcp__webull__get_open_orders()
    if open_orders_result:
        print(f"[OK] get_open_orders: {len(open_orders_result)} open orders")
    else:
        print("[INFO] get_open_orders: No open orders found or empty response")
except Exception as e:
    print(f"[ERROR] get_open_orders failed: {e}")

# Note: Webull MCP doesn't have direct equivalent of GetOrdersRequest with filters
# Instead, we get all orders and filter them ourselves if needed
print("\nNote: Webull MCP returns all orders, filtering must be done client-side")
print("For example, to get OPEN orders, we get all orders and filter by status")