#!/usr/bin/env python3
"""Test script to verify .env file loading and Webull API connection."""

import os
from dotenv import load_dotenv

# Test 1: Check if we can load the .env file
print('=== Test 1: Loading .env file ===')
dotenv_loaded = load_dotenv()
print(f'Dotenv loaded: {dotenv_loaded}')

# Test 2: Check if environment variables are set
print('\n=== Test 2: Environment Variables ===')
app_key = os.environ.get('WEBULL_APP_KEY')
app_secret = os.environ.get('WEBULL_APP_SECRET')
print(f'WEBULL_APP_KEY: {"SET" if app_key else "NOT SET"}')
print(f'WEBULL_APP_SECRET: {"SET" if app_secret else "NOT SET"}')

if app_key and app_secret:
    print(f'App Key starts with: {app_key[:10]}...')
    print(f'App Secret starts with: {app_secret[:10]}...')
else:
    print('ERROR: Missing Webull credentials!')
    exit(1)

# Test 3: Try to initialize Webull client directly via MCP tools
print('\n=== Test 3: Webull API Connection ===')
try:
    # Try to get account info using Webull MCP tools
    account_info = mcp__webull__get_account_info()

    if account_info:
        print('Webull MCP tools connection successful')

        # Try to get account info
        account_id = account_info.get('account_id', 'NOT AVAILABLE')
        account_status = account_info.get('account_status', 'NOT AVAILABLE')
        buying_power = account_info.get('buying_power', 'NOT AVAILABLE')

        print(f'Account status: {account_status}')
        if buying_power != 'NOT AVAILABLE':
            print(f'Buying power: ${float(buying_power):.2f}')
        else:
            print(f'Buying power: {buying_power}')
        print(f'Account ID: {account_id}')

        print('SUCCESS: Webull MCP tools connection works!')

    else:
        print('ERROR: No account info returned from Webull MCP tools')
        exit(1)

except Exception as e:
    print(f'ERROR: Failed to connect to Webull API via MCP tools: {e}')
    import traceback
    traceback.print_exc()
    exit(1)