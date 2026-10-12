#!/usr/bin/env python3
"""Debug what market data functions are available via Webull MCP tools."""

import os
from dotenv import load_dotenv

load_dotenv()

app_key = os.environ.get('WEBULL_APP_KEY')
app_secret = os.environ.get('WEBULL_APP_SECRET')

print("Available Webull MCP market data functions:")
print("  Stock data functions:")
print("    - get_stock_latest_quote: Get latest quote for stock(s)")
print("    - get_stock_bars: Get historical price bars for stock(s)")
print("    - get_stock_snapshot: Get comprehensive snapshot for stock(s)")
print("    - get_stock_trades: Get historical trade data for stock(s)")
print("    - get_stock_quotes: Get historical bid/ask quotes for stock(s)")
print("  Options data functions:")
print("    - get_option_latest_quote: Get latest quote for option contract(s)")
print("    - get_option_chain: Get option chain for underlying symbol")
print("    - get_option_snapshot: Get comprehensive snapshot for option contract(s)")
print("    - get_option_trades: Get historical trade data for option contract(s)")
print("  Crypto data functions:")
print("    - get_crypto_latest_quote: Get latest quote for crypto pair(s)")
print("    - get_crypto_bars: Get historical price bars for crypto pair(s)")
print("    - get_crypto_snapshot: Get comprehensive snapshot for crypto pair(s)")

# Note: Webull MCP doesn't expose client objects like Alpaca does
# Instead, it provides direct function calls for each data type
print("\nNote: Webull MCP uses direct function calls rather than client objects")
print("To get stock data, call mcp__webull__get_stock_* functions directly")
print("To get option data, call mcp__webull__get_option_* functions directly")
print("To get crypto data, call mcp__webull__get_crypto_* functions directly")