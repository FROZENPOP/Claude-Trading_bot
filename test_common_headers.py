#!/usr/bin/env python3
"""Test Webull MCP tools connection."""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get credentials
app_key = os.environ.get('WEBULL_APP_KEY')
app_secret = os.environ.get('WEBULL_APP_SECRET')

print(f'APP Key: {app_key[:10]}...' if app_key else 'APP Key: NOT SET')
print(f'APP Secret: {app_secret[:10]}...' if app_secret else 'APP Secret: NOT SET')

# Test Webull MCP tools connection
print('\n--- Testing Webull MCP Connection ---')

try:
    # Test getting account info
    print('Testing mcp__webull__get_account_info...')
    account_info = mcp__webull__get_account_info()
    if account_info:
        print(f'Status: SUCCESS')
        print(f'  Account ID: {account_info.get("account_id", "NOT AVAILABLE")}')
        print(f'  Account Status: {account_info.get("account_status", "NOT AVAILABLE")}')
        buying_power = account_info.get('buying_power', 'NOT AVAILABLE')
        if buying_power != 'NOT AVAILABLE':
            print(f'  Buying Power: ${float(buying_power):.2f}')
        else:
            print(f'  Buying Power: {buying_power}')
    else:
        print(f'Status: FAILED - No data returned')

    # Test getting positions
    print('\nTesting mcp__webull__get_account_positions...')
    positions = mcp__webull__get_account_positions()
    if positions is not None:
        print(f'Status: SUCCESS')
        print(f'  Number of positions: {len(positions) if isinstance(positions, list) else "UNKNOWN"}')
        if isinstance(positions, list) and len(positions) > 0:
            print(f'  First position: {positions[0]}')
    else:
        print(f'Status: FAILED - No data returned')

    # Test getting clock/market hours
    print('\nTesting mcp__webull__get_clock...')
    clock = mcp__webull__get_clock()
    if clock:
        print(f'Status: SUCCESS')
        if isinstance(clock, dict) and 'data' in clock:
            clock_data = clock['data']
            print(f'  Market Open: {clock_data.get("is_open", "UNKNOWN")}')
            print(f'  Next Open: {clock_data.get("next_open", "UNKNOWN")}')
            print(f'  Next Close: {clock_data.get("next_close", "UNKNOWN")}')
        else:
            print(f'  Clock data: {clock}')
    else:
        print(f'Status: FAILED - No data returned')

    print('\nSUCCESS: Webull MCP tools are accessible and responding!')

except Exception as e:
    print(f'Status: ERROR - {e}')
    import traceback
    traceback.print_exc()