#!/usr/bin/env python3
"""Test Phase 7 full execution with sample data in simulation mode."""

import os
import sys
import json
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

# Test the Phase 7 Webull execution with sample data
try:
    from trading_bot.execution.webull_execution import WebullExecution

    print("Creating WebullExecution...")
    executor = WebullExecution(
        api_key=os.environ.get('WEBULL_APP_KEY'),
        secret_key=os.environ.get('WEBULL_APP_SECRET'),
        paper=True
    )

    print(f"Executor created. Environment: {executor.environment}")

    # Load sample data
    print("\nLoading sample Phase 5/6 output...")
    with open('sample_phase56_output.json', 'r') as f:
        sample_data = json.load(f)

    approved_trades = sample_data['result']['approved_trades']
    print(f"Loaded {len(approved_trades)} approved trades")

    # Execute the trades using Webull MCP tools - Bull Call Spread: Buy lower strike, Sell higher strike
    print("\nExecuting approved trades using Webull MCP tools...")

    successful_trades = 0
    failed_trades = 0
    all_results = []

    for i, trade in enumerate(approved_trades):
        print(f"Executing trade {i+1}: {trade['symbol']} {trade['strategy_type']} "
              f"{trade['long_strike']}/{trade['short_strike']} exp:{trade['days_to_expiry']}days")

        try:
            # For bull call spread: Buy long call, Sell short call
            # Format option symbols for Webull: typically like AAPL261016C00190000
            # We need to construct the option symbols from the trade data

            # Extract date from expiration_date (format: 2026-10-16T00:00:00Z)
            exp_date = trade['expiration_date'][:10].replace('-', '')  # 20261016
            # Format strikes: multiply by 1000 and pad to 8 digits (e.g., 190 -> 000190000)
            long_strike_str = f"{int(trade['long_strike'] * 1000):0>8}"
            short_strike_str = f"{int(trade['short_strike'] * 1000):0>8}"

            # Construct option symbols (Webull format: SYMBOLYYMMDD C/P########)
            long_option_symbol = f"{trade['symbol']}{exp_date}C{long_strike_str}"
            short_option_symbol = f"{trade['symbol']}{exp_date}C{short_strike_str}"

            print(f"  Long option symbol: {long_option_symbol}")
            print(f"  Short option symbol: {short_option_symbol}")

            # Place long call (buy)
            long_order_request = OrderRequest(
                symbol=long_option_symbol,
                qty=trade['recommended_shares'],
                side="buy",
                order_type="market",
                time_in_force="day"
            )

            print(f"  Placing long call BUY order for {trade['recommended_shares']} contracts...")
            long_success, long_error, long_order = executor.submit_order(long_order_request)

            if long_success:
                print(f"    Long order SUCCESS: {long_order.id if long_order else 'No order object'}")
            else:
                print(f"    Long order FAILED: {long_error}")

            # Place short call (sell)
            short_order_request = OrderRequest(
                symbol=short_option_symbol,
                qty=trade['recommended_shares'],
                side="sell",
                order_type="market",
                time_in_force="day"
            )

            print(f"  Placing short call SELL order for {trade['recommended_shares']} contracts...")
            short_success, short_error, short_order = executor.submit_order(short_order_request)

            if short_success:
                print(f"    Short order SUCCESS: {short_order.id if short_order else 'No order object'}")
            else:
                print(f"    Short order FAILED: {short_error}")

            # Consider trade successful if both orders succeeded
            if long_success and short_success:
                successful_trades += 1
                all_results.append({
                    'success': True,
                    'trade_symbol': trade['symbol'],
                    'orders': [
                        {'symbol': long_option_symbol, 'side': 'buy', 'qty': trade['recommended_shares'], 'order_id': long_order.id if long_order else ''},
                        {'symbol': short_option_symbol, 'side': 'sell', 'qty': trade['recommended_shares'], 'order_id': short_order.id if short_order else ''}
                    ]
                })
                print(f"  Trade {i+1} ({trade['symbol']}): SUCCESS - Bull call spread executed")
            else:
                failed_trades += 1
                all_results.append({
                    'success': False,
                    'trade_symbol': trade['symbol'],
                    'error': f"Long order: {long_error}, Short order: {short_error}"
                })
                print(f"  Trade {i+1} ({trade['symbol']}): FAILED - Long: {long_error}, Short: {short_error}")

        except Exception as e:
            failed_trades += 1
            print(f"  Trade {i+1} ({trade.get('symbol', 'unknown')}): EXCEPTION - {e}")
            all_results.append({
                'success': False,
                'trade_symbol': trade.get('symbol', 'unknown'),
                'error': str(e)
            })

    print(f"\nExecution complete. Results for {len(all_results)} trades:")
    successful_trades = 0
    for i, result in enumerate(all_results):
        if result['success']:
            successful_trades += 1
            print(f"  Trade {i+1} ({result['trade_symbol']}): SUCCESS")
            print(f"    Orders: {len(result['orders'])} real orders")
        else:
            print(f"  Trade {i+1} ({result.get('trade_symbol', 'unknown')}): FAILED - {result.get('error')}")

    print(f"\nSummary: {successful_trades}/{len(all_results)} trades successful")
    print(f"Environment: {executor.environment}")

    if executor.environment == "uat":
        print("SUCCESS: Phase 7 executed in UAT (paper trading) mode!")
    else:
        print("Phase 7 executed with live API connection.")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()