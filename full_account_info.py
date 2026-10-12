#!/usr/bin/env python3
"""Get full account info from Webull MCP tools to verify it's working correctly."""

import os
from dotenv import load_dotenv

load_dotenv()

# Get credentials from environment (for verification)
api_key = os.environ.get('WEBULL_APP_KEY')
secret_key = os.environ.get('WEBULL_APP_SECRET')

print(f'API Key loaded: {bool(api_key)}')
print(f'Secret Key loaded: {bool(secret_key)}')

# Get account info using Webull MCP tools
print('\n=== ACCOUNT INFO FROM WEBULL MCP TOOLS ===')
try:
    account_info = mcp__webull__get_account_info()

    if account_info:
        # Extract and display account information
        print(f'Account ID: {account_info.get("account_id", "N/A")}')
        print(f'Account Number: {account_info.get("account_number", "N/A")}')
        print(f'Status: {account_info.get("account_status", "N/A")}')

        # Handle buying power - might be string or numeric
        buying_power = account_info.get('buying_power', 'N/A')
        if buying_power != 'N/A':
            try:
                print(f'Buying Power: ${float(buying_power):.2f}')
            except:
                print(f'Buying Power: {buying_power}')
        else:
            print(f'Buying Power: {buying_power}')

        # Handle cash - might be string or numeric
        cash = account_info.get('cash_balance', 'N/A')
        if cash != 'N/A':
            try:
                print(f'Cash: ${float(cash):.2f}')
            except:
                print(f'Cash: {cash}')
        else:
            print(f'Cash: {cash}')

        # Handle portfolio value - might be string or numeric
        portfolio_value = account_info.get('market_value', 'N/A')
        if portfolio_value != 'N/A':
            try:
                print(f'Portfolio Value: ${float(portfolio_value):.2f}')
            except:
                print(f'Portfolio Value: {portfolio_value}')
        else:
            print(f'Portfolio Value: {portfolio_value}')

        # Additional fields that might be available
        print(f'Account Type: {account_info.get("account_type", "N/A")}')
        print(f'Is Paper Trading: {account_info.get("is_paper_trading", "N/A")}')

        # Show all available fields for debugging
        print('\n=== ALL AVAILABLE FIELDS ===')
        for key, value in sorted(account_info.items()):
            print(f'{key}: {value}')
    else:
        print('ERROR: No account info returned from Webull MCP tools')

except Exception as e:
    print(f'ERROR: Failed to get account info via Webull MCP tools: {e}')
    import traceback
    traceback.print_exc()