#!/usr/bin/env python3
"""Test Phase 7 execution with live API keys (not synthetic/simulation data)."""

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

# Set up logging to see what's happening
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('phase7_live_test')

# Test the Phase 7 Webull executor with real API
try:
    from trading_bot.execution.webull_execution import WebullExecution

    logger.info("Creating WebullExecution...")
    executor = WebullExecution(
        app_key=os.environ.get('WEBULL_APP_KEY'),
        app_secret=os.environ.get('WEBULL_APP_SECRET'),
        environment="uat"  # Using UAT (paper trading) as before
    )

    logger.info(f"Executor created. Environment: {executor.environment}")

    # Load sample data (approved trades from Phase 5/6)
    logger.info("Loading Phase 5/6 approved trades data...")
    with open('sample_phase56_output.json', 'r') as f:
        sample_data = json.load(f)

    approved_trades = sample_data['result']['approved_trades']
    logger.info(f"Loaded {len(approved_trades)} approved trades")

    # Display the trades we'll be executing
    logger.info("Trades to execute:")
    for i, trade in enumerate(approved_trades):
        logger.info(f"  {i+1}. {trade['symbol']} {trade['strategy_type']} "
                   f"{trade['long_strike']}/{trade['short_strike']} "
                   f"exp:{trade['days_to_expiry']}days qty:{trade['recommended_shares']}")

    # Execute the trades using REAL API (not simulation) - Bull Call Spread: Buy lower strike, Sell higher strike
    logger.info("Executing approved trades using LIVE API...")

    successful_trades = 0
    failed_trades = 0
    all_results = []

    for i, trade in enumerate(approved_trades):
        logger.info(f"Executing trade {i+1}: {trade['symbol']} {trade['strategy_type']} "
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

            # Construct option symbols
            long_option_symbol = f"{trade['symbol']}{exp_date}C{long_strike_str}"
            short_option_symbol = f"{trade['symbol']}{exp_date}C{short_strike_str}"

            logger.info(f"  Long option symbol: {long_option_symbol}")
            logger.info(f"  Short option symbol: {short_option_symbol}")

            # Place long call (buy)
            long_order_request = OrderRequest(
                symbol=long_option_symbol,
                qty=trade['recommended_shares'],
                side="buy",
                order_type="market",
                time_in_force="day"
            )

            logger.info(f"  Placing long call BUY order for {trade['recommended_shares']} contracts...")
            long_success, long_error, long_order = executor.submit_order(long_order_request)

            if long_success:
                logger.info(f"    Long order SUCCESS: {long_order.id if long_order else 'No order object'}")
            else:
                logger.error(f"    Long order FAILED: {long_error}")

            # Place short call (sell)
            short_order_request = OrderRequest(
                symbol=short_option_symbol,
                qty=trade['recommended_shares'],
                side="sell",
                order_type="market",
                time_in_force="day"
            )

            logger.info(f"  Placing short call SELL order for {trade['recommended_shares']} contracts...")
            short_success, short_error, short_order = executor.submit_order(short_order_request)

            if short_success:
                logger.info(f"    Short order SUCCESS: {short_order.id if short_order else 'No order object'}")
            else:
                logger.error(f"    Short order FAILED: {short_error}")

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
                logger.info(f"  Trade {i+1} ({trade['symbol']}): SUCCESS - Bull call spread executed")
            else:
                failed_trades += 1
                all_results.append({
                    'success': False,
                    'trade_symbol': trade['symbol'],
                    'error': f"Long order: {long_error}, Short order: {short_error}"
                })
                logger.error(f"  Trade {i+1} ({trade['symbol']}): FAILED - Long: {long_error}, Short: {short_error}")

        except Exception as e:
            failed_trades += 1
            logger.error(f"  Trade {i+1} ({trade.get('symbol', 'unknown')}): EXCEPTION - {e}")
            all_results.append({
                'success': False,
                'trade_symbol': trade.get('symbol', 'unknown'),
                'error': str(e)
            })

    logger.info(f"Execution complete. Processed {len(all_results)} trades.")
    logger.info(f"FINAL RESULT: {successful_trades} successful, {failed_trades} failed out of {len(all_results)} trades")

    if successful_trades > 0:
        logger.info("SUCCESS: Phase 7 execution completed with live API!")
    else:
        logger.warning("All trades failed - checking for issues...")

except Exception as e:
    logger.error(f"Error in Phase 7 live test: {e}")
    import traceback
    logger.error(traceback.format_exc())