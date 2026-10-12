#!/usr/bin/env python3
"""Debug what trading functions are available via Webull MCP tools."""

import os
from dotenv import load_dotenv

load_dotenv()

app_key = os.environ.get('WEBULL_APP_KEY')
app_secret = os.environ.get('WEBULL_APP_SECRET')

print("Available Webull MCP trading functions:")
print("  Account functions:")
print("    - get_account_info: Get account information")
print("    - get_account_positions: Get all current positions")
print("    - get_account_activities: Get account activities (fills, dividends, etc.)")
print("  Order functions:")
print("    - get_order_history: Get historical orders")
print("    - get_open_orders: Get all current open/pending orders")
print("    - get_order_detail: Get details for a specific order")
print("    - place_stock_order: Place a stock order")
print("    - place_option_order: Place an option order")
print("    - cancel_order: Cancel an order")
print("    - replace_order: Replace an existing order")
print("  Market data functions (for reference):")
print("    - get_stock_latest_quote: Get latest quote for stock(s)")
print("    - get_option_latest_quote: Get latest quote for option contract(s)")

# Note: Webull MCP doesn't expose client objects like Alpaca does
# Instead, it provides direct function calls for each operation
print("\nNote: Webull MCP uses direct function calls rather than client objects")
print("To get account info, call mcp__webull__get_account_info() directly")
print("To place an order, call mcp__webull__place_*_order functions directly")
print("To get positions, call mcp__webull__get_account_positions() directly")

# Let's also check what we can actually do by trying some basic calls
print("\n=== Testing basic Webull MCP functions ===")
try:
    # Test account info
    account_info = mcp__webull__get_account_info()
    if account_info:
        print(f"[OK] get_account_info: Retrieved account information")
        print(f"  Account ID: {account_info.get('account_id', 'NOT AVAILABLE')}")
    else:
        print("[INFO] get_account_info: No account data returned")
except Exception as e:
    print(f"[ERROR] get_account_info failed: {e}")

try:
    # Test getting positions
    positions = mcp__webull__get_account_positions()
    if positions is not None:
        print(f"[OK] get_account_positions: Retrieved {len(positions)} positions")
    else:
        print("[INFO] get_account_positions: No positions data returned")
except Exception as e:
    print(f"[ERROR] get_account_positions failed: {e}")