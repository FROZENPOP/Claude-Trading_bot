#!/usr/bin/env python3
"""Test Webull MCP tools with basic logging."""

import os
import logging
from dotenv import load_dotenv

# Enable basic logging
logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv()

# Get credentials
app_key = os.environ.get('WEBULL_APP_KEY')
app_secret = os.environ.get('WEBULL_APP_SECRET')

print(f'APP Key: {app_key[:10]}...' if app_key else 'APP Key: NOT SET')
print(f'APP Secret: {app_secret[:10]}...' if app_secret else 'APP Secret: NOT SET')

print('\nTesting Webull MCP tools...')

try:
    print('\nCalling mcp__webull__get_account_info...')
    account_info = mcp__webull__get_account_info()
    if account_info:
        print(f'Success! Account info retrieved:')
        print(f'  Account ID: {account_info.get("account_id", "NOT AVAILABLE")}')
        print(f'  Account Status: {account_info.get("account_status", "NOT AVAILABLE")}')
        buying_power = account_info.get('buying_power', 'NOT AVAILABLE')
        if buying_power != 'NOT AVAILABLE':
            print(f'  Buying Power: ${float(buying_power):.2f}')
        else:
            print(f'  Buying Power: {buying_power}')
    else:
        print('No account info returned')

    print('\nCalling mcp__webull__get_account_positions...')
    positions = mcp__webull__get_account_positions()
    if positions is not None:
        print(f'Success! Positions retrieved: {len(positions) if isinstance(positions, list) else positions}')
        if isinstance(positions, list) and len(positions) > 0:
            print(f'  First position: {positions[0]}')
    else:
        print('No positions data returned')

    print('\nCalling mcp__webull__get_clock...')
    clock = mcp__webull__get_clock()
    if clock:
        print(f'Success! Clock retrieved:')
        if isinstance(clock, dict) and 'data' in clock:
            clock_data = clock['data']
            print(f'  Market Open: {clock_data.get("is_open", "UNKNOWN")}')
            print(f'  Next Open: {clock_data.get("next_open", "UNKNOWN")}')
            print(f'  Next Close: {clock_data.get("next_close", "UNKNOWN")}')
        else:
            print(f'  Clock data: {clock}')
    else:
        print('No clock data returned')

    print('\nSUCCESS: Webull MCP tools are working!')

except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()