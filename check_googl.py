#!/usr/bin/env python3
"""Check GOOGL stock price and option symbol validity."""

import os
import json
from dotenv import load_dotenv

load_dotenv()

app_key = os.environ.get('WEBULL_APP_KEY')
app_secret = os.environ.get('WEBULL_APP_SECRET')

# Check stock price using Webull MCP tools
try:
    # Get latest quote for GOOGL stock
    quote_result = mcp__webull__get_stock_latest_quote(symbols="GOOGL")
    if quote_result and 'data' in quote_result and len(quote_result['data']) > 0:
        quote_data = quote_result['data'][0]
        bid_price = quote_data.get('bid_price')
        ask_price = quote_data.get('ask_price')
        if bid_price is not None and ask_price is not None:
            bid = float(bid_price)
            ask = float(ask_price)
            mid_price = (bid + ask) / 2
            print(f"GOOGL stock price: Bid=${bid_price:.2f}, Ask=${ask_price:.2f}, Mid=${mid_price:.2f}")
        else:
            print("Could not get GOOGL bid/ask prices")
    else:
        print("No GOOGL quote data returned")
except Exception as e:
    print(f"Error getting GOOGL stock quote: {e}")
    import traceback
    traceback.print_exc()

# Check if we can get option chain data to see what options are available
try:
    # Get expiration date from the test data
    with open('sample_phase56_output.json', 'r') as f:
        data = json.load(f)

    googl_trade = None
    for trade in data['result']['approved_trades']:
        if trade['symbol'] == 'GOOGL':
            googl_trade = trade
            break

    if googl_trade:
        expiration_date = googl_trade['expiration_date']
        print(f"\nGOOGL expiration date from test: {expiration_date}")

        # Try to get option chain for this expiration using Webull MCP tools
        try:
            # Get option contracts for GOOGL
            contracts_result = mcp__webull__get_option_contracts(
                underlying_symbols="GOOGL",
                status="active"
            )

            if contracts_result and 'data' in contracts_result:
                contracts_data = contracts_result['data']

                # Filter contracts by expiration date if needed
                # For now, let's just get all active contracts and count them
                googl_options = [c for c in contracts_data if c.get('underlying_symbol') == 'GOOGL']
                print(f"Number of active GOOGL option symbols: {len(googl_options)}")
                if len(googl_options) > 0:
                    # Show first and last 5 symbols
                    symbols = [c.get('symbol') for c in googl_options if c.get('symbol')]
                    print(f"First 5 symbols: {symbols[:5]}")
                    print(f"Last 5 symbols: {symbols[-5:]}")
                else:
                    print("No active GOOGL option symbols found")
            else:
                print("No option contracts data returned")
        except Exception as e:
            print(f"Error getting option chain: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("Could not find GOOGL trade in test data")
except FileNotFoundError:
    print("sample_phase56_output.json not found - skipping option chain check")
except Exception as e:
    print(f"Error reading test data: {e}")
    import traceback
    traceback.print_exc()