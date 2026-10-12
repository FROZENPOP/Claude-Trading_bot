#!/usr/bin/env python3
"""Check what buying power values are available in the account."""

import os
import sys
from dotenv import load_dotenv

# Add the trading_bot directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from trading_bot.execution.webull_execution import WebullExecution


def check_account_powers():
    """Check account buying power fields."""

    load_dotenv()

    app_key = os.environ.get('WEBULL_APP_KEY')
    app_secret = os.environ.get('WEBULL_APP_SECRET')

    if not app_key or not app_secret:
        print("ERROR: Webull API credentials not found")
        return

    print("=== Checking Account Buying Power ===")
    print()

    # Initialize Webull executor
    executor = WebullExecution(
        app_key=app_key,
        app_secret=app_secret,
        environment="uat"  # Paper trading
    )

    try:
        # Get account info via MCP
        account_info = mcp__webull__get_account_info()

        if account_info:
            print("Account information:")
            # Extract relevant fields from Webull account info
            # Webull returns specific field names for account information
            net_liquidation = account_info.get('net_liquidation', 'NOT AVAILABLE')
            buying_power = account_info.get('buying_power', 'NOT AVAILABLE')
            cash_balance = account_info.get('cash_balance', 'NOT AVAILABLE')
            market_value = account_info.get('market_value', 'NOT AVAILABLE')
            unrealized_pnl = account_info.get('unrealized_pnl', 'NOT AVAILABLE')
            realized_pnl = account_info.get('realized_pnl', 'NOT AVAILABLE')

            print(f"  net_liquidation: {net_liquidation}")
            print(f"  buying_power: {buying_power}")
            print(f"  cash_balance: {cash_balance}")
            print(f"  market_value: {market_value}")
            print(f"  unrealized_pnl: {unrealized_pnl}")
            print(f"  realized_pnl: {realized_pnl}")
            print()

            # Also get account positions to see long/short market values
            positions = mcp__webull__get_account_positions()
            if positions:
                print("Position information:")
                long_market_value = 0
                short_market_value = 0
                for pos in positions:
                    # Assuming positions have side and market_value
                    side = pos.get('side', '').lower()
                    market_val = float(pos.get('market_value', 0))
                    if side in ['long', 'buy']:
                        long_market_value += market_val
                    elif side in ['short', 'sell']:
                        short_market_value += market_val

                print(f"  long_market_value: {long_market_value}")
                print(f"  short_market_value: {short_market_value}")
            else:
                print("  Position information: NOT AVAILABLE")
        else:
            print("Could not retrieve account information")

        # Also check if we can get options trading status
        print("Account options trading status:")
        # Webull might have different endpoints for options permissions

    except Exception as e:
        print(f"Error getting account info: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    check_account_powers()