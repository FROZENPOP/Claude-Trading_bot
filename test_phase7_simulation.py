#!/usr/bin/env python3
"""Test Phase 7 Webull execution initialization."""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the project root to path so we can import trading_bot modules
project_root = os.path.join(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.append(project_root)

# Also add the trading_bot execution path
execution_path = os.path.join(project_root, 'trading_bot', 'execution')
if execution_path not in sys.path:
    sys.path.append(execution_path)

# Set up basic logging to see what's happening
import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Test the Phase 7 Webull executor
try:
    from trading_bot.execution.webull_execution import WebullExecution

    print("Creating WebullExecution...")
    executor = WebullExecution(
        api_key=os.environ.get('WEBULL_APP_KEY'),
        secret_key=os.environ.get('WEBULL_APP_SECRET'),
        paper=True
    )

    print(f"Executor created. Environment: {executor.environment}")
    print(f"Paper trading: {executor.paper}")

    # Test the market and account verification
    print("\nTesting market and account verification...")
    try:
        # Test getting account info
        account_info = executor.get_account_info()
        if account_info:
            print(f"Account retrieval: SUCCESS")
            print(f"  Account ID: {account_info.id}")
            print(f"  Status: {account_info.status}")
            print(f"  Buying Power: ${account_info.buying_power}")
        else:
            print(f"Account retrieval: FAILED - No data returned")
    except Exception as e:
        print(f"Account retrieval: ERROR - {e}")

    try:
        # Test market hours check
        market_open = executor._verify_market_open()
        print(f"Market hours check: {'OPEN' if market_open else 'CLOSED OR ERROR'}")
    except Exception as e:
        print(f"Market hours check: ERROR - {e}")

    print("\nSUCCESS: WebullExecution initialized and basic checks completed!")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()