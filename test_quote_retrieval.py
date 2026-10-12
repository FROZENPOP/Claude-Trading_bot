#!/usr/bin/env python3
"""Test quote retrieval for all option symbols in the test data using Webull MCP tools."""

import os
import json
from dotenv import load_dotenv

load_dotenv()

# Load the test data to get the option symbols
with open('sample_phase56_output.json', 'r') as f:
    data = json.load(f)

approved_trades = data['result']['approved_trades']

print("Testing quote retrieval for all option symbols in test data using Webull MCP tools:\n")

for i, trade in enumerate(approved_trades):
    symbol = trade['symbol']
    long_strike = trade['long_strike']
    short_strike = trade['short_strike']
    expiration_date = trade['expiration_date']

    # Create option symbols (this mimics what Phase7AlpacaExecutor does)
    from datetime import datetime
    exp_date = datetime.fromisoformat(expiration_date.replace('Z', '+00:00'))
    exp_date_str = exp_date.strftime('%y%m%d')  # YYMMDD format

    long_symbol = f"{symbol}{exp_date_str}C{int(long_strike * 1000):08d}"
    short_symbol = f"{symbol}{exp_date_str}C{int(short_strike * 1000):08d}"

    print(f"{i+1}. {symbol}:")
    print(f"   Long:  {long_symbol}")
    print(f"   Short: {short_symbol}")

    # Test long symbol using Webull MCP
    try:
        quote_result = mcp__webull__get_option_latest_quote(symbols=long_symbol)
        if quote_result and 'data' in quote_result and len(quote_result['data']) > 0:
            quote_data = quote_result['data'][0]
            bid_price = quote_data.get('bid_price')
            ask_price = quote_data.get('ask_price')
            if bid_price is not None and ask_price is not None:
                bid = float(bid_price)
                ask = float(ask_price)
                mid_price = (bid + ask) / 2
                print(f"   Long quote: Bid={bid_price:.2f}, Ask={ask_price:.2f}, Mid={mid_price:.2f}")
            else:
                print(f"   Long quote: Could not get bid/ask prices")
        else:
            print(f"   Long quote: No quote data returned")
    except Exception as e:
        print(f"   Long quote: Error - {e}")

    # Test short symbol using Webull MCP
    try:
        quote_result = mcp__webull__get_option_latest_quote(symbols=short_symbol)
        if quote_result and 'data' in quote_result and len(quote_result['data']) > 0:
            quote_data = quote_result['data'][0]
            bid_price = quote_data.get('bid_price')
            ask_price = quote_data.get('ask_price')
            if bid_price is not None and ask_price is not None:
                bid = float(bid_price)
                ask = float(ask_price)
                mid_price = (bid + ask) / 2
                print(f"   Short quote: Bid={bid_price:.2f}, Ask={ask_price:.2f}, Mid={mid_price:.2f}")
            else:
                print(f"   Short quote: Could not get bid/ask prices")
        else:
            print(f"   Short quote: No quote data returned")
    except Exception as e:
        print(f"   Short quote: Error - {e}")

    print()