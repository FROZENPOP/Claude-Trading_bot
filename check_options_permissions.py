#!/usr/bin/env python3
"""Check account options trading permissions."""

import os
import json
from dotenv import load_dotenv

load_dotenv()

app_key = os.environ.get('WEBULL_APP_KEY')
app_secret = os.environ.get('WEBULL_APP_SECRET')

if not app_key or not app_secret:
    print("ERROR: Webull API credentials not found")
    exit(1)

# Initialize Webull executor
from trading_bot.execution.webull_execution import WebullExecution
executor = WebullExecution(
    app_key=app_key,
    app_secret=app_secret,
    environment="uat"  # Paper trading
)

# Get account info to see options trading level
try:
    # Get account info via MCP
    account_info = mcp__webull__get_account_info()

    if account_info:
        print("=== ACCOUNT INFO ===")
        # Print key account information
        print(f"Account ID: {account_info.get('account_id', 'NOT AVAILABLE')}")
        print(f"Net Liquidation: {account_info.get('net_liquidation', 'NOT AVAILABLE')}")
        print(f"Buying Power: {account_info.get('buying_power', 'NOT AVAILABLE')}")
        print(f"Cash Balance: {account_info.get('cash_balance', 'NOT AVAILABLE')}")
        print(f"Market Value: {account_info.get('market_value', 'NOT AVAILABLE')}")
        print(f"Unrealized P&L: {account_info.get('unrealized_pnl', 'NOT AVAILABLE')}")
        print(f"Realized P&L: {account_info.get('realized_pnl', 'NOT AVAILABLE')}")

        # Check if there are options-related fields
        # Look for options-related attributes in the account info
        options_related = []
        for key, value in account_info.items():
            if 'option' in key.lower():
                options_related.append((key, value))

        print(f"\nOptions-related fields: {options_related}")

        # Print all attributes and their values (first 20)
        print("\n=== ALL ACCOUNT ATTRIBUTES (first 20) ===")
        attrs = list(account_info.keys())
        for i, attr in enumerate(attrs[:20]):
            value = account_info.get(attr)
            print(f"{attr}: {value} ({type(value).__name__})")

        if len(attrs) > 20:
            print(f"... and {len(attrs) - 20} more attributes")
    else:
        print("Could not retrieve account information")

except Exception as e:
    print(f"Error getting account info: {e}")
    import traceback
    traceback.print_exc()

# Also check account configurations which might have options info
try:
    # Try to get account configuration via MCP
    config_info = mcp__webull__get_account_config()
    print("\n=== ACCOUNT CONFIGURATIONS ===")
    print(f"Config: {json.dumps(config_info, indent=2) if config_info else 'NOT AVAILABLE'}")
except Exception as e:
    print(f"Error getting account configurations: {e}")
    import traceback
    traceback.print_exc()