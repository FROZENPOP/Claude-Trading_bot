#!/usr/bin/env python3
"""Place a test order for Micron (MU) stock using Webull MCP tools."""

import os
from dotenv import load_dotenv

load_dotenv()

# Get credentials from environment
app_key = os.environ.get('WEBULL_APP_KEY')
app_secret = os.environ.get('WEBULL_APP_SECRET')

print(f'APP Key loaded: {bool(app_key)}')
print(f'APP Secret loaded: {bool(app_secret)}')

if not app_key or not app_secret:
    print('ERROR: Missing Webull API credentials!')
    exit(1)

print(f'APP Key starts with: {app_key[:10]}...' if app_key else 'APP Key: NOT SET')
print(f'APP Secret starts with: {app_secret[:10]}...' if app_secret else 'APP Secret: NOT SET')

# Test Webull MCP tools connection by getting account info first
print('\n=== Testing Webull API Connection ===')
try:
    account_info = mcp__webull__get_account_info()

    if account_info:
        print('Webull MCP tools connection successful')

        # Get account details
        account_id = account_info.get('account_id', 'NOT AVAILABLE')
        account_status = account_info.get('account_status', 'NOT AVAILABLE')
        buying_power = account_info.get('buying_power', 'NOT AVAILABLE')

        print(f'Account status: {account_status}')
        if buying_power != 'NOT AVAILABLE':
            print(f'Buying power: ${float(buying_power):.2f}')
        else:
            print(f'Buying power: {buying_power}')
        print(f'Account ID: {account_id}')

    else:
        print('ERROR: No account info returned from Webull MCP tools')
        exit(1)

except Exception as e:
    print(f'ERROR: Failed to connect to Webull API via MCP tools: {e}')
    import traceback
    traceback.print_exc()
    exit(1)

# Get current quote for MU to show the price
print('\n=== Getting MU Quote ===')
try:
    # Get quote for MU stock
    quote = mcp__webull__get_stock_latest_quote(symbols='MU')

    if quote and len(quote) > 0:
        mu_quote = quote[0] if isinstance(quote, list) else quote
        bid_price = mu_quote.get('bid_price', 'N/A')
        ask_price = mu_quote.get('ask_price', 'N/A')
        last_price = mu_quote.get('last_price', 'N/A')

        print(f'MU Quote:')
        print(f'  Bid: ${bid_price}')
        print(f'  Ask: ${ask_price}')
        print(f'  Last: ${last_price}')
    else:
        print('Could not get MU quote, proceeding with order anyway')

except Exception as e:
    print(f'Could not get MU quote: {e}')
    print('Proceeding with order anyway...')

# Place a market order for 1 share of MU using Webull MCP tools
print('\n=== Placing MU Order ===')
print('Placing market order to BUY 1 share of MU...')

try:
    # Place the order using Webull MCP tools
    # For market orders, we need to specify: symbol, side, qty, order_type, time_in_force
    order_result = mcp__webull__place_stock_order(
        symbol='MU',
        side='buy',
        qty=1,
        order_type='market',
        time_in_force='day'
    )

    if order_result:
        print('ORDER SUCCESSFULLY PLACED!')
        print(f'Order ID: {order_result.get("order_id", "N/A")}')
        print(f'Client Order ID: {order_result.get("client_order_id", "N/A")}')
        print(f'Symbol: MU')
        print(f'Qty: 1')
        print(f'Side: BUY')
        print(f'Order type: market')
        print(f'Time in force: day')
        print(f'Status: {order_result.get("status", "unknown")}')

        # Show any additional fields
        if 'filled_avg_price' in order_result:
            print(f'Filled average price: ${order_result["filled_avg_price"]}')
        if 'filled_quantity' in order_result:
            print(f'Filled quantity: {order_result["filled_quantity"]}')

    else:
        print('ERROR: No order result returned from Webull MCP tools')

except Exception as e:
    print(f'ERROR: Failed to place order via Webull MCP tools: {e}')
    import traceback
    traceback.print_exc()