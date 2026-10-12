#!/usr/bin/env python3
"""Check account details to understand position sizing issues."""

import os
from dotenv import load_dotenv

load_dotenv()

app_key = os.environ.get('WEBULL_APP_KEY')
app_secret = os.environ.get('WEBULL_APP_SECRET')

# Initialize Webull executor
from trading_bot.execution.webull_execution import WebullExecution
executor = WebullExecution(
    app_key=app_key,
    app_secret=app_secret,
    environment="uat"  # Paper trading
)

# Get account info via MCP
try:
    account_info = mcp__webull__get_account_info()
    if account_info:
        print("=== ACCOUNT INFO ===")
        print(f"Account ID: {account_info.get('account_id', 'NOT AVAILABLE')}")
        print(f"Status: {account_info.get('status', 'NOT AVAILABLE')}")
        buying_power = account_info.get('buying_power', 'NOT AVAILABLE')
        cash_balance = account_info.get('cash_balance', 'NOT AVAILABLE')
        market_value = account_info.get('market_value', 'NOT AVAILABLE')
        print(f"Buying Power: ${float(buying_power):.2f}" if buying_power != 'NOT AVAILABLE' else f"Buying Power: {buying_power}")
        print(f"Cash: ${float(cash_balance):.2f}" if cash_balance != 'NOT AVAILABLE' else f"Cash: {cash_balance}")
        print(f"Portfolio Value: ${float(market_value):.2f}" if market_value != 'NOT AVAILABLE' else f"Portfolio Value: {market_value}")

        # Day trading buying power might not be directly available in Webull
        # Let's check if we can get it from account info
        dtbp = account_info.get('daytrading_buying_power', None)
        if dtbp is not None:
            print(f"Day Trading Buying Power: ${float(dtbp):.2f}")
        else:
            print("Day Trading Buying Power: Not available in Webull account info")
    else:
        print("Could not retrieve account information")
except Exception as e:
    print(f"Error getting account info: {e}")
    import traceback
    traceback.print_exc()

# Get positions via MCP
try:
    print("\n=== GETTING POSITIONS ===")
    positions_info = mcp__webull__get_account_positions()
    if positions_info:
        print(f"=== POSITIONS ({len(positions_info)}) ===")
        for pos in positions_info:
            symbol = pos.get('symbol', 'UNKNOWN')
            qty = pos.get('quantity', 0)  # Webull uses 'quantity' instead of 'qty'
            current_price = pos.get('last_price', 0)  # Webull uses 'last_price'
            market_value = pos.get('market_value', 0)
            print(f"{symbol}: {qty} shares @ ${float(current_price):.2f} = ${float(market_value):.2f}")
    else:
        print("Could not retrieve position information")
except Exception as e:
    print(f"Error getting position info: {e}")
    import traceback
    traceback.print_exc()

# Try to get a quote for one of the option symbols we're having trouble with
try:
    print(f"\n=== QUOTE FOR AAPL261016C00190000 ===")
    # Get option quote via MCP
    quote_result = mcp__webull__get_option_latest_quote(symbols="AAPL261016C00190000")
    if quote_result and 'data' in quote_result and len(quote_result['data']) > 0:
        quote_data = quote_result['data'][0]
        bid_price = quote_data.get('bid_price')
        ask_price = quote_data.get('ask_price')
        if bid_price is not None and ask_price is not None:
            bid = float(bid_price)
            ask = float(ask_price)
            print(f"Bid: {bid_price}")
            print(f"Ask: {ask_price}")
            mid_price = (bid + ask) / 2
            print(f"Mid price: {mid_price}")
        else:
            print("Could not get bid/ask prices")
    else:
        print("No quote data returned")
except Exception as e:
    print(f"Error getting option quote: {e}")
    import traceback
    traceback.print_exc()

# Let's also check what the latest stock price is for AAPL
try:
    print(f"\n=== QUOTE FOR AAPL (STOCK) ===")
    # Get stock quote via MCP
    quote_result = mcp__webull__get_stock_latest_quote(symbols="AAPL")
    if quote_result and 'data' in quote_result and len(quote_result['data']) > 0:
        quote_data = quote_result['data'][0]
        bid_price = quote_data.get('bid_price')
        ask_price = quote_data.get('ask_price')
        if bid_price is not None and ask_price is not None:
            bid = float(bid_price)
            ask = float(ask_price)
            print(f"Bid: {bid_price}")
            print(f"Ask: {ask_price}")
            mid_price = (bid + ask) / 2
            print(f"Mid price: {mid_price}")
        else:
            print("Could not get bid/ask prices")
    else:
        print("No quote data returned")
except Exception as e:
    print(f"Error getting stock quote: {e}")
    import traceback
    traceback.print_exc()