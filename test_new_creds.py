#!/usr/bin/env python3
"""Test the new credentials from .env file using Webull MCP tools."""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get credentials
app_key = os.environ.get('WEBULL_APP_KEY')
app_secret = os.environ.get('WEBULL_APP_SECRET')

print(f'APP Key loaded: {bool(app_key)}')
print(f'APP Secret loaded: {bool(app_secret)}')
if app_key:
    print(f'APP Key prefix: {app_key[:6]}')

# Try to get account info using Webull MCP
try:
    account_info = mcp__webull__get_account_info()
    if account_info:
        print('Webull MCP connection successful')
        print(f'Account ID: {account_info.get("account_id", "NOT AVAILABLE")}')
        print(f'Account Status: {account_info.get("account_status", "NOT AVAILABLE")}')
        buying_power = account_info.get('buying_power', 'NOT AVAILABLE')
        if buying_power != 'NOT AVAILABLE':
            print(f'Buying Power: ${float(buying_power):.2f}')
        else:
            print(f'Buying Power: {buying_power}')
        print('SUCCESS: Webull MCP connection works!')
    else:
        print('Webull MCP returned no account info')

except Exception as e:
    print(f'ERROR: Failed to connect to Webull MCP: {e}')