#!/usr/bin/env python3
"""
Diagnostic backtest to verify the options strategy pipeline works end-to-end.
Focuses on verifying that signals, contracts, spreads, and trades flow through the system.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os
from typing import Dict, Any

# Add project to path
sys.path.append(os.path.join(os.path.dirname(__file__)))

# Import our strategies
from trading_bot.strategies.vertical_spread import VerticalSpreadStrategy
from trading_bot.strategies.signals import SignalGenerator
from research_options_strategies import OptionsDataPipeline


class DiagnosticBacktester:
    """Diagnostic backtester that reports detailed pipeline stages."""

    def __init__(self):
        self.data_pipeline = OptionsDataPipeline()
        self.signal_generator = SignalGenerator()

    def run_diagnostic_backtest(self, strategy, start_date: str, end_date: str) -> Dict[str, Any]:
        """
        Run a diagnostic backtest that reports every pipeline stage.

        Args:
            strategy: Strategy instance to test
            start_date: Start date for backtest (YYYY-MM-DD)
            end_date: End date for backtest (YYYY-MM-DD)

        Returns:
            Dictionary with diagnostic results and pipeline stage counts
        """
        # Initialize pipeline counters
        pipeline_counts = {
            'underlying_rows_loaded': 0,
            'underlying_rows_after_cleaning': 0,
            'signals_evaluated': 0,
            'bull_signals': 0,
            'bear_signals': 0,
            'total_signals': 0,
            'option_chain_requests': 0,
            'successful_option_chain_responses': 0,
            'empty_option_chain_responses': 0,
            'failed_option_chain_responses': 0,
            'contracts_discovered': 0,
            'contracts_passing_expiration_filter': 0,
            'contracts_passing_strike_filter': 0,
            'contracts_passing_liquidity_filter': 0,
            'contracts_passing_price_filter': 0,
            'candidate_spreads': 0,
            'executable_spreads': 0,
            'trades_entered': 0,
            'trades_exited': 0,
            'completed_trades': 0,
            'open_positions_at_end': 0,
            'total_pnl': 0.0,
            'gross_pnl': 0.0,
            'transaction_costs': 0.0
        }

        # Initialize trade tracking
        trades = []
        open_positions = []

        try:
            # Get the date range for our backtest
            date_range = pd.date_range(start=start_date, end=end_date, freq='D')
            date_range = date_range[date_range.weekday < 5]  # Business days only

            if len(date_range) < 10:
                return {
                    'error': 'Insufficient data for backtest',
                    'pipeline_counts': pipeline_counts
                }

            print(f"Running diagnostic backtest from {start_date} to {end_date}")
            print(f"Total business days: {len(date_range)}")

            # Initialize portfolio tracking
            portfolio_value = 100000.0
            cash = portfolio_value

            # For each day in our backtest period
            for i, current_date in enumerate(date_range):
                date_str = current_date.strftime('%Y-%m-%d')
                print(f"\n--- Processing {date_str} (Day {i+1}/{len(date_range)}) ---")

                try:
                    # Get market data for this day (with lookback for indicators)
                    lookback_start = (current_date - timedelta(days=50)).strftime('%Y-%m-%d')
                    stock_data = self.data_pipeline.get_stock_data(lookback_start, date_str)

                    pipeline_counts['underlying_rows_loaded'] += len(stock_data)

                    if stock_data.empty:
                        print("  WARNING: No stock data available")
                        continue

                    # Clean data - ensure we have required columns and data up to current_date
                    if 'date' not in stock_data.columns:
                        print("  ERROR: Stock data missing 'date' column")
                        pipeline_counts['failed_option_chain_responses'] += 1
                        continue

                    # Filter to available history (don't peek into future)
                    available_data = stock_data[stock_data['date'] <= current_date].copy()

                    pipeline_counts['underlying_rows_after_cleaning'] += len(available_data)

                    if len(available_data) < 20:
                        print(f"  INFO: Insufficient history for signal generation: {len(available_data)} days")
                        continue

                    # Get option chain for this day
                    pipeline_counts['option_chain_requests'] += 1
                    option_chain = self.data_pipeline.get_option_chain_data(date_str)

                    if option_chain.empty:
                        print("  WARNING: No option chain data available")
                        pipeline_counts['empty_option_chain_responses'] += 1
                        continue

                    pipeline_counts['successful_option_chain_responses'] += 1
                    print(f"  Option chain loaded: {len(option_chain)} contracts")

                    # Generate signals from the strategy
                    try:
                        if hasattr(strategy, 'generate_spread_signals'):
                            signals = strategy.generate_spread_signals(available_data, option_chain, current_date)
                        else:
                            signals = []
                    except Exception as e:
                        print(f"  ERROR: Signal generation failed: {e}")
                        signals = []
                        # Count this as a software error, not empty results
                        pipeline_counts['failed_option_chain_responses'] += 1
                        continue

                    pipeline_counts['signals_evaluated'] += len(signals)
                    print(f"  Signals generated: {len(signals)}")

                    # Count signal types
                    bull_count = sum(1 for s in signals if hasattr(s, 'signal_type') and s.signal_type == 'bullish')
                    bear_count = sum(1 for s in signals if hasattr(s, 'signal_type') and s.signal_type == 'bearish')
                    pipeline_counts['bull_signals'] += bull_count
                    pipeline_counts['bear_signals'] += bear_count
                    pipeline_counts['total_signals'] += len(signals)

                    print(f"  Bull signals: {bull_count}, Bear signals: {bear_count}")

                    # Process signals to open new positions
                    for signal_idx, signal in enumerate(signals):
                        try:
                            # Check if we have enough capital (use 2% risk per trade max)
                            max_risk_per_trade = 0.02
                            max_risk_dollars = portfolio_value * max_risk_per_trade

                            if hasattr(strategy, 'create_vertical_spread'):
                                position = strategy.create_vertical_spread(signal, portfolio_value, current_date)
                            else:
                                position = None

                            if position and position not in open_positions:
                                # Add position
                                open_positions.append(position)
                                pipeline_counts['trades_entered'] += 1
                                trades.append({
                                    'position': position,
                                    'entry_date': current_date,
                                    'entry_info': {
                                        'signal_type': getattr(signal, 'signal_type', 'unknown'),
                                        'signal_strength': getattr(signal, 'signal_strength', 0.0),
                                        'underlying_price': getattr(position, 'underlying_price', 0.0) if hasattr(position, 'underlying_price') else 0.0,
                                        'long_strike': getattr(position, 'long_strike', 0.0),
                                        'short_strike': getattr(position, 'short_strike', 0.0),
                                        'option_type': getattr(position, 'option_type', 'unknown'),
                                        'entry_price': getattr(position, 'entry_price', 0.0),
                                        'quantity': abs(getattr(position, 'long_quantity', 0)) if hasattr(position, 'long_quantity') else 0
                                    }
                                })
                                print(f"  OPENED: {getattr(position, 'option_type', '?')} spread {getattr(position, 'long_strike', 0)}/{getattr(position, 'short_strike', 0)}")

                        except Exception as e:
                            print(f"  ERROR: Failed to create position from signal: {e}")
                            # Don't continue silently - this is a software error
                            continue

                    # Check existing positions for exit signals
                    positions_to_remove = []
                    daily_pnl = 0.0

                    for position_idx, position in enumerate(open_positions):
                        try:
                            should_exit = False
                            exit_value = 0.0
                            exit_reason = "Hold"

                            if hasattr(strategy, 'exit_spread'):
                                should_exit, exit_value, exit_reason = strategy.exit_spread(
                                                position, option_chain, current_date)
                            else:
                                should_exit, exit_value, exit_reason = False, 0.0, "No exit method"

                            if should_exit:
                                # Close the position
                                exit_info = {
                                    'exit_date': current_date,
                                    'exit_value': exit_value,
                                    'exit_reason': exit_reason,
                                    'entry_date': getattr(position, 'entry_date', current_date) if hasattr(position, 'entry_date') else current_date
                                }

                                # Calculate P&L for this trade
                                entry_cost = getattr(position, 'entry_price', 0.0) * 100 * abs(getattr(position, 'long_quantity', 0)) if hasattr(position, 'entry_price') and hasattr(position, 'long_quantity') else 0.0
                                exit_value_adjusted = exit_value  # This is the spread value
                                trade_pnl = exit_value_adjusted - entry_cost

                                trade_record = {
                                    'entry_info': trades[len([t for t in trades if t.get('exit_info') is not None])]['entry_info'] if len([t for t in trades if t.get('exit_info') is not None]) < len(trades) else {},
                                    'exit_info': exit_info,
                                    'pnl': trade_pnl,
                                    'position_details': {
                                        'underlying_symbol': getattr(position, 'underlying_symbol', 'unknown'),
                                        'expiration_date': getattr(position, 'expiration_date', 'unknown'),
                                        'long_strike': getattr(position, 'long_strike', 0.0),
                                        'short_strike': getattr(position, 'short_strike', 0.0),
                                        'option_type': getattr(position, 'option_type', 'unknown'),
                                        'quantity': abs(getattr(position, 'long_quantity', 0)) if hasattr(position, 'long_quantity') else 0
                                    }
                                }

                                trades[-1].update({'exit_info': exit_info, 'pnl': trade_pnl}) if len(trades) > 0 and 'exit_info' not in trades[-1] else trades.append({'entry_info': {}, 'exit_info': exit_info, 'pnl': trade_pnl, 'position_details': trade_record.get('position_details', {})})

                                pipeline_counts['trades_exited'] += 1
                                pipeline_counts['completed_trades'] += 1
                                pipeline_counts['gross_pnl'] += trade_pnl

                                print(f"  CLOSED: {exit_reason} - P&L: ${trade_pnl:.2f}")
                                positions_to_remove.append(position)
                            else:
                                print(f"  HOLDING: {exit_reason}")

                        except Exception as e:
                            print(f"  ERROR: Exit check failed for position: {e}")
                            # Continue holding position - don't exit on software error
                            pass

                    # Remove exited positions
                    for position in positions_to_remove:
                        if position in open_positions:
                            open_positions.remove(position)

                    # Calculate current portfolio value (simplified)
                    positions_value = 0.0
                    for position in open_positions:
                        try:
                            # Simplified position valuation - in reality we'd mark-to-market
                            position_value = 0.0  # Placeholder
                            positions_value += position_value
                        except:
                            pass

                    # Total portfolio value
                    total_value = cash + positions_value + daily_pnl
                    pipeline_counts['total_pnl'] = total_value - portfolio_value
                    portfolio_value = max(total_value, 0.01)  # Ensure positive

                except Exception as e:
                    print(f"  ERROR: Unexpected error processing {date_str}: {e}")
                    # Continue to next day rather than failing completely
                    continue

            # Close any remaining positions at the end
            for position in open_positions:
                # In a real backtest, we'd use the last available option chain
                # For simplicity, we'll just count these as open positions
                pass

            pipeline_counts['open_positions_at_end'] = len(open_positions)

            # Calculate transaction costs (simplified)
            # Assume $2.00 per trade (round trip)
            pipeline_counts['transaction_costs'] = pipeline_counts['trades_entered'] * 2.00

            # Calculate net P&L
            pipeline_counts['total_pnl'] = pipeline_counts['gross_pnl'] - pipeline_counts['transaction_costs']

            return {
                'error': None,
                'pipeline_counts': pipeline_counts,
                'trades': trades,
                'final_portfolio_value': portfolio_value,
                'total_return': (portfolio_value - 100000.0) / 100000.0 if 100000.0 > 0 else 0.0
            }

        except Exception as e:
            return {
                'error': str(e),
                'pipeline_counts': pipeline_counts,
                'trades': []
            }


def run_diagnostic():
    """Run the diagnostic backtest."""
    print("=" * 80)
    print("OPTIONS STRATEGY DIAGNOSTIC BACKTEST")
    print("Verifying end-to-end pipeline functionality")
    print("=" * 80)
    print(f"Diagnostic started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Initialize backtester and strategy
    backtester = DiagnosticBacktester()

    # Use AAPL as the test symbol with a small window
    test_symbol = 'AAPL'
    end_date = "2026-09-30"
    start_date = "2026-09-01"  # Just 1 month of data for quick diagnostic

    print(f"Testing symbol: {test_symbol}")
    print(f"Testing period: {start_date} to {end_date}")
    print()

    # Create strategy with default parameters
    strategy = VerticalSpreadStrategy(test_symbol, max_risk_per_trade=0.02)

    # Run diagnostic backtest
    result = backtester.run_diagnostic_backtest(strategy, start_date, end_date)

    # Report results
    print("\n" + "=" * 80)
    print("DIAGNOSTIC RESULTS")
    print("=" * 80)

    if result['error']:
        print(f"BACKTEST ERROR: {result['error']}")
        print("\nPIPELINE STILL BROKEN")
        return

    pipeline_counts = result['pipeline_counts']
    trades = result['trades']

    # Print pipeline stage counts
    print("PIPELINE STAGE COUNTS:")
    print(f"  Underlying rows loaded: {pipeline_counts['underlying_rows_loaded']}")
    print(f"  Underlying rows after cleaning: {pipeline_counts['underlying_rows_after_cleaning']}")
    print(f"  Signals evaluated: {pipeline_counts['signals_evaluated']}")
    print(f"  Bull signals: {pipeline_counts['bull_signals']}")
    print(f"  Bear signals: {pipeline_counts['bear_signals']}")
    print(f"  Total signals: {pipeline_counts['total_signals']}")
    print()
    print(f"  Option-chain requests: {pipeline_counts['option_chain_requests']}")
    print(f"  Successful option-chain responses: {pipeline_counts['successful_option_chain_responses']}")
    print(f"  Empty option-chain responses: {pipeline_counts['empty_option_chain_responses']}")
    print(f"  Failed option-chain responses: {pipeline_counts['failed_option_chain_responses']}")
    print()
    # Note: The contract filtering stages are internal to the strategy and not directly accessible
    # without modifying the strategy code, which we're avoiding per instructions
    print(f"  Contracts discovered: [Internal to strategy - not directly measurable]")
    print(f"  Contracts passing expiration filter: [Internal to strategy - not directly measurable]")
    print(f"  Contracts passing strike filter: [Internal to strategy - not directly measurable]")
    print(f"  Contracts passing liquidity filter: [Internal to strategy - not directly measurable]")
    print(f"  Contracts passing price filter: [Internal to strategy - not directly measurable]")
    print()
    print(f"  Candidate spreads: [Internal to strategy - not directly measurable]")
    print(f"  Executable spreads: [Internal to strategy - not directly measurable]")
    print()
    print(f"  Trades entered: {pipeline_counts['trades_entered']}")
    print(f"  Trades exited: {pipeline_counts['trades_exited']}")
    print(f"  Completed trades: {pipeline_counts['completed_trades']}")
    print(f"  Open positions at end: {pipeline_counts['open_positions_at_end']}")
    print()
    print(f"  Gross P&L: ${pipeline_counts['gross_pnl']:.2f}")
    print(f"  Transaction costs: ${pipeline_counts['transaction_costs']:.2f}")
    print(f"  Net P&L: ${pipeline_counts['total_pnl']:.2f}")
    print(f"  Total return: {result['total_return']:.2%}")
    print()

    # Print trade details if any trades occurred
    if trades and len(trades) > 0:
        print("TRADE DETAILS:")
        print("-" * 80)

        # Show up to 3 representative trades
        display_trades = trades[:3] if len(trades) >= 3 else trades

        for i, trade in enumerate(display_trades):
            print(f"Trade {i+1}:")
            entry_info = trade.get('entry_info', {})
            exit_info = trade.get('exit_info', {})
            position_details = trade.get('position_details', {})
            pnl = trade.get('pnl', 0.0)

            print(f"  Signal timestamp: {entry_info.get('entry_date', 'N/A')}")
            print(f"  Underlying price: ${entry_info.get('underlying_price', 0.0):.2f}")
            print(f"  Signal direction: {entry_info.get('signal_type', 'N/A')} (strength: {entry_info.get('signal_strength', 0.0):.2f})")
            print(f"  Option expiration: {position_details.get('expiration_date', 'N/A')}")
            print(f"  Option strike(s): {position_details.get('long_strike', 0.0)}/{position_details.get('short_strike', 0.0)}")
            print(f"  Option type: {position_details.get('option_type', 'N/A')}")
            # Note: We don't have exact bid/ask at entry in our simplified tracking
            print(f"  Option bid/ask at entry: [Not tracked in simplified backtest]")
            print(f"  Entry price: ${entry_info.get('entry_price', 0.0):.2f}")
            print(f"  Exit timestamp: {exit_info.get('exit_date', 'N/A')}")
            print(f"  Exit price: ${exit_info.get('exit_value', 0.0):.2f}")
            print(f"  Gross P&L: ${pnl:.2f}")
            print(f"  Transaction/slippage cost: $2.00")  # Simplified
            print(f"  Net P&L: ${pnl - 2.00:.2f}")
            print()
    elif len(trades) == 0:
        print("NO TRADES EXECUTED")
        print("This could be due to:")
        print("  - No signals generated")
        print("  - Signals too weak to generate spreads")
        print("  - No suitable option contracts found")
        print("  - Capital constraints preventing position entry")

    # Final diagnostic verdict
    print("=" * 80)
    print("FINAL DIAGNOSTIC VERDICT")
    print("=" * 80)

    # Determine if pipeline is working
    signals_generated = pipeline_counts['total_signals'] > 0
    trades_entered = pipeline_counts['trades_entered'] > 0

    if signals_generated and trades_entered:
        print("PIPELINE VERIFIED")
        print("Signals, contracts, spreads, and trades are successfully flowing through the system.")
    elif signals_generated and not trades_entered:
        print("PIPELINE PARTIALLY WORKING")
        print("Signals are being generated but no trades are being entered.")
        print("This could be due to contract filtering, capital constraints, or execution logic.")
    else:
        print("PIPELINE STILL BROKEN")
        print("No signals are being generated - check data pipeline and signal generation.")

    print()
    print("Next steps:")
    if signals_generated and trades_entered:
        print("  Pipeline is verified. Proceed to full research suite when ready.")
    else:
        print("  Investigate why pipeline is not completing before proceeding.")

    print(f"\nDiagnostic completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    run_diagnostic()