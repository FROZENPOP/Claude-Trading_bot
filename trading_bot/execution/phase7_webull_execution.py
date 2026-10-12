#!/usr/bin/env python3
"""Phase 7: Webull Paper Execution for Options Trading.

This script takes the output from the combined Phase 5/6 workflow and executes
the approved trades via Webull paper trading API through MCP.

It processes bull call spread opportunities and converts them into actual
option orders using the WebullExecution class.
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# Setup logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('phase7_webull_execution')


@dataclass
class ApprovedTrade:
    """Represents an approved trade from the combined Phase 5/6 workflow."""
    symbol: str
    strategy_type: str
    long_strike: float
    short_strike: float
    expiration_date: str  # ISO format: YYYY-MM-DDTHH:MM:SSZ
    days_to_expiry: int
    net_debit: float
    max_profit: float
    max_loss: float
    expected_return: float
    probability_of_profit: float
    underlying_price: float
    volume_avg: int
    individual_trade_score: float
    trade_quality_score: float
    risk_score: float
    context_score: float
    liquidity_score: float
    ranking_factors: Dict
    passes_risk_check: bool
    risk_score_adjusted: float
    suggested_position_size_pct: float
    risk_reason: str
    risk_metrics: Dict
    recommended_shares: int  # Number of option contracts
    recommended_value: float  # Dollar value of position
    volatility_target_pct: float
    sizing_reason: str
    sizing_metrics: Dict


class Phase7WebullExecutor:
    """Executes approved trades from Phase 5/6 via Webull paper trading through MCP."""

    def __init__(self, app_key: str = None, app_secret: str = None,
                 environment: str = "uat", region_id: str = "us"):
        """Initialize the Phase 7 Webull executor.

        Args:
            app_key: Webull app key (reads from env if not provided)
            app_secret: Webull app secret (reads from env if not provided)
            environment: Trading environment ('uat' for paper/sandbox, 'prod' for live)
            region_id: Region identifier ('us', 'hk', 'jp', etc.)
        """
        # Import after ensuring we're in the right environment
        from trading_bot.execution.webull import WebullExecution, OrderRequest, create_order_request

        self.executor = WebullExecution(
            app_key=app_key,
            app_secret=app_secret,
            environment=environment,
            region_id=region_id,
            max_daily_loss=0.05,  # 5% max daily loss
            max_position_size=0.10,  # 10% max position size
            max_daily_trades=10  # Max 10 trades per day
        )

        # Store references for simulation mode
        self.OrderRequest = OrderRequest
        self.create_order_request = create_order_request

        # Track if we're in simulation mode due to API connection issues
        self.simulation_mode = False

        logger.info(f"Phase 7 Webull executor initialized (environment={environment}, region={region_id})")

    def _is_option_symbol(self, symbol: str) -> bool:
        """Check if a symbol represents an option contract using Webull format.

        Args:
            symbol: Symbol to check

        Returns:
            True if symbol is an option contract, False otherwise
        """
        return self.executor._is_option_symbol(symbol)

    def _create_option_symbol(self, underlying: str, expiration_date: str,
                            option_type: str, strike_price: float) -> str:
        """Create an option symbol from components.

        Args:
            underlying: Underlying stock symbol (e.g., 'AAPL')
            expiration_date: Expiration date in YYYY-MM-DD format
            option_type: 'call' or 'put'
            strike_price: Strike price (e.g., 150.0)

        Returns:
            Formatted option symbol (e.g., 'AAPL240119C00150000')
        """
        # Parse expiration date
        exp_date = datetime.fromisoformat(expiration_date.replace('Z', '+00:00'))
        exp_date_str = exp_date.strftime('%y%m%d')  # YYMMDD format

        # Option type character
        option_char = 'C' if option_type.lower() == 'call' else 'P'

        # Strike price * 1000, padded to 8 digits
        strike_int = int(strike_price * 1000)
        strike_str = f"{strike_int:08d}"

        # Construct symbol: {UNDERLYING}{YY}{MM}{DD}{C/P}{STRIKE*1000}
        return f"{underlying}{exp_date_str}{option_char}{strike_str}"

    def _parse_approved_trade(self, trade_data: Dict) -> ApprovedTrade:
        """Convert trade data dictionary to ApprovedTrade object.

        Args:
            trade_data: Dictionary containing trade information

        Returns:
            ApprovedTrade object
        """
        return ApprovedTrade(
            symbol=trade_data['symbol'],
            strategy_type=trade_data['strategy_type'],
            long_strike=trade_data['long_strike'],
            short_strike=trade_data['short_strike'],
            expiration_date=trade_data['expiration_date'],
            days_to_expiry=trade_data['days_to_expiry'],
            net_debit=trade_data['net_debit'],
            max_profit=trade_data['max_profit'],
            max_loss=trade_data['max_loss'],
            expected_return=trade_data['expected_return'],
            probability_of_profit=trade_data['probability_of_profit'],
            underlying_price=trade_data['underlying_price'],
            volume_avg=trade_data['volume_avg'],
            individual_trade_score=trade_data['individual_trade_score'],
            trade_quality_score=trade_data['trade_quality_score'],
            risk_score=trade_data['risk_score'],
            context_score=trade_data['context_score'],
            liquidity_score=trade_data['liquidity_score'],
            ranking_factors=trade_data['ranking_factors'],
            passes_risk_check=trade_data['passes_risk_check'],
            risk_score_adjusted=trade_data['risk_score_adjusted'],
            suggested_position_size_pct=trade_data['suggested_position_size_pct'],
            risk_reason=trade_data['risk_reason'],
            risk_metrics=trade_data['risk_metrics'],
            recommended_shares=trade_data['recommended_shares'],
            recommended_value=trade_data['recommended_value'],
            volatility_target_pct=trade_data['volatility_target_pct'],
            sizing_reason=trade_data['sizing_reason'],
            sizing_metrics=trade_data['sizing_metrics']
        )

    def _create_bull_call_spread_orders(self, trade: ApprovedTrade) -> Tuple[Optional[object], Optional[object]]:
        """Create option orders for a bull call spread.

        For a bull call spread:
        - Buy call option at long_strike
        - Sell call option at short_strike
        - Both options have same expiration date

        Args:
            trade: ApprovedTrade object containing trade details

        Returns:
            Tuple of (long_order_request, short_order_request)
        """
        # Create option symbols
        long_symbol = self._create_option_symbol(
            underlying=trade.symbol,
            expiration_date=trade.expiration_date,
            option_type='call',
            strike_price=trade.long_strike
        )

        short_symbol = self._create_option_symbol(
            underlying=trade.symbol,
            expiration_date=trade.expiration_date,
            option_type='call',
            strike_price=trade.short_strike
        )

        # For a bull call spread (debit spread):
        # - We BUY the long call (debit)
        # - We SELL the short call (credit)
        # The net debit is what we pay to enter the spread

        # Quantity is the number of spread contracts
        quantity = trade.recommended_shares

        # Estimate individual option prices (simplified)
        # In reality, we'd get current quotes or use pricing models
        long_option_price = trade.net_debit * 0.6  # Approximate: long leg is ~60% of debit
        short_option_price = trade.net_debit * 0.4  # Approximate: short leg is ~40% of debit

        long_order_request = self.create_order_request(
            symbol=long_symbol,
            qty=quantity,
            side='buy',  # Buy the long call
            order_type='limit',
            limit_price=round(long_option_price, 2)
        )

        short_order_request = self.create_order_request(
            symbol=short_symbol,
            qty=quantity,
            side='sell',  # Sell the short call
            order_type='limit',
            limit_price=round(short_option_price, 2)
        )

        return long_order_request, short_order_request

    def _verify_market_and_account(self) -> Tuple[bool, str]:
        """Verify market is open and account is ready for trading using Webull MCP.

        Returns:
            Tuple of (is_ready, message)
        """
        try:
            # Check market status
            is_open, market_msg = self.executor.verify_market_open()

            if not is_open:
                return False, f"Market closed: {market_msg}"

            # Check account status
            is_ok, account_msg = self.executor.verify_account_status()

            if not is_ok:
                return False, f"Account issue: {account_msg}"

            return True, f"Market open and account ready: {market_msg}"

        except Exception as e:
            logger.warning(f"Error checking market/account status: {e}")
            return False, f"Error checking market/account status: {e}"

    def execute_approved_trades(self, approved_trades_data: List[Dict]) -> List[Dict]:
        """Execute a list of approved trades from Phase 5/6 workflow.

        Args:
            approved_trades_data: List of dictionaries containing approved trade information

        Returns:
            List of execution results
        """
        # Verify market and account status
        is_ready, status_msg = self._verify_market_and_account()
        if not is_ready:
            logger.error(f"Cannot execute trades: {status_msg}")
            return [{
                'success': False,
                'error': status_msg,
                'trade_symbol': None,
                'strategy_type': None,
                'orders': []
            } for _ in approved_trades_data]

        logger.info(f"Market and account verification passed: {status_msg}")

        results = []

        for trade_data in approved_trades_data:
            trade_result = {
                'success': False,
                'trade_symbol': trade_data.get('symbol'),
                'strategy_type': trade_data.get('strategy_type'),
                'orders': [],
                'error': None
            }

            try:
                # Parse the trade data
                trade = self._parse_approved_trade(trade_data)

                logger.info(f"Processing approved trade: {trade.symbol} {trade.strategy_type} "
                           f"{trade.long_strike}/{trade.short_strike} exp:{trade.days_to_expiry}days "
                           f"qty:{trade.recommended_shares}")

                # Skip if trade doesn't pass risk check (should have been filtered earlier)
                if not trade.passes_risk_check:
                    trade_result['error'] = "Trade failed risk check"
                    results.append(trade_result)
                    continue

                # Create option orders for the bull call spread
                long_order_req, short_order_req = self._create_bull_call_spread_orders(trade)

                if not long_order_req or not short_order_req:
                    trade_result['error'] = "Failed to create option orders"
                    results.append(trade_result)
                    continue

                if self.simulation_mode:
                    # SIMULATION MODE: Simulate successful order submission
                    logger.info(f"SIMULATION: Submitting long leg order: {long_order_req.side} {long_order_req.qty} {long_order_req.symbol}")
                    # Create a mock order object
                    class MockOrder:
                        def __init__(self, symbol):
                            self.id = f"mock_{symbol}_{datetime.now().timestamp()}"

                    long_order = MockOrder(long_order_req.symbol)
                    short_order = MockOrder(short_order_req.symbol)

                    long_success, short_success = True, True
                    long_error, short_error = None, None

                    logger.info(f"SIMULATION: Submitting short leg order: {short_order_req.side} {short_order_req.qty} {short_order_req.symbol}")

                    # Add simulated orders to the orders list
                    trade_result['orders'].append({
                        'symbol': long_order_req.symbol,
                        'side': long_order_req.side,
                        'qty': long_order_req.qty,
                        'order_type': long_order_req.order_type,
                        'limit_price': long_order_req.limit_price,
                        'order_id': long_order.id,
                        'success': long_success
                    })

                    trade_result['orders'].append({
                        'symbol': short_order_req.symbol,
                        'side': short_order_req.symbol,
                        'qty': short_order_req.qty,
                        'order_type': short_order_req.order_type,
                        'limit_price': short_order_req.limit_price,
                        'order_id': short_order.id,
                        'success': short_success
                    })
                else:
                    # Submit long leg order (buy call)
                    logger.info(f"Submitting long leg order: {long_order_req.side} {long_order_req.qty} {long_order_req.symbol}")
                    long_success, long_error, long_order = self.executor.submit_order(long_order_req)

                    if not long_success:
                        trade_result['error'] = f"Long leg order failed: {long_error}"
                        results.append(trade_result)
                        continue

                    trade_result['orders'].append({
                        'symbol': long_order_req.symbol,
                        'side': long_order_req.side,
                        'qty': long_order_req.qty,
                        'order_type': long_order_req.order_type,
                        'limit_price': long_order_req.limit_price,
                        'order_id': long_order.id if long_order else None,
                        'success': long_success
                    })

                    # Submit short leg order (sell call)
                    logger.info(f"Submitting short leg order: {short_order_req.side} {short_order_req.qty} {short_order_req.symbol}")
                    short_success, short_error, short_order = self.executor.submit_order(short_order_req)

                    if not short_success:
                        # If short leg fails, try to cancel the long leg order
                        logger.warning(f"Short leg order failed: {short_error}. Attempting to cancel long leg order.")
                        if long_order:
                            self.executor.cancel_order(long_order.id)

                        trade_result['error'] = f"Short leg order failed: {short_error}"
                        results.append(trade_result)
                        continue

                    trade_result['orders'].append({
                        'symbol': short_order_req.symbol,
                        'side': short_order_req.side,
                        'qty': short_order_req.qty,
                        'order_type': short_order_req.order_type,
                        'limit_price': short_order_req.limit_price,
                        'order_id': short_order.id if short_order else None,
                        'success': short_success
                    })

                # Mark trade as successful
                trade_result['success'] = True
                trade_result['long_order_id'] = long_order.id if long_order else None
                trade_result['short_order_id'] = short_order.id if short_order else None

                if self.simulation_mode:
                    logger.info(f"SIMULATION: Successfully executed bull call spread for {trade.symbol}: "
                               f"Long({long_order.id}) Short({short_order.id})")
                else:
                    logger.info(f"Successfully executed bull call spread for {trade.symbol}: "
                               f"Long({long_order.id}) Short({short_order.id})")

            except Exception as e:
                logger.error(f"Error executing trade {trade_data.get('symbol', 'unknown')}: {e}")
                trade_result['error'] = str(e)

            results.append(trade_result)

        return results

    def get_execution_summary(self, results: List[Dict]) -> Dict:
        """Generate a summary of execution results.

        Args:
            results: List of execution results from execute_approved_trades

        Returns:
            Dictionary containing execution summary
        """
        total_trades = len(results)
        successful_trades = sum(1 for r in results if r['success'])
        failed_trades = total_trades - successful_trades

        total_orders = sum(len(r['orders']) for r in results)
        successful_orders = sum(
            sum(1 for o in r['orders'] if o['success'])
            for r in results
        )

        return {
            'total_trades': total_trades,
            'successful_trades': successful_trades,
            'failed_trades': failed_trades,
            'success_rate': successful_trades / total_trades if total_trades > 0 else 0,
            'total_orders': total_orders,
            'successful_orders': successful_orders,
            'order_success_rate': successful_orders / total_orders if total_orders > 0 else 0,
            'trades': [
                {
                    'symbol': r['trade_symbol'],
                    'success': r['success'],
                    'error': r['error'],
                    'orders_count': len(r['orders']),
                    'successful_orders_count': sum(1 for o in r['orders'] if o['success'])
                }
                for r in results
            ]
        }


def load_combined_workflow_output(file_path: str) -> List[Dict]:
    """Load the combined Phase 5/6 workflow output from a JSON file.

    Args:
        file_path: Path to the JSON file containing workflow output

    Returns:
        List of approved trade dictionaries
    """
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)

        # Extract approved trades from the workflow result
        if 'result' in data and 'approved_trades' in data['result']:
            return data['result']['approved_trades']
        elif isinstance(data, list):
            # If the file directly contains the list of trades
            return data
        else:
            logger.warning(f"Unexpected format in workflow output file: {file_path}")
            return []

    except Exception as e:
        logger.error(f"Error loading workflow output from {file_path}: {e}")
        return []


def main():
    """Main function to run Phase 7 Webull execution."""
    import argparse

    parser = argparse.ArgumentParser(description='Phase 7: Execute approved trades via Webull paper trading')
    parser.add_argument('--input', '-i', type=str,
                       help='Path to combined Phase 5/6 workflow output JSON file')
    parser.add_argument('--app-key', type=str, help='Webull app key (optional, reads from env)')
    parser.add_argument('--app-secret', type=str, help='Webull app secret (optional, reads from env)')
    parser.add_argument('--environment', type=str, default='uat',
                       help='Trading environment (uat for paper/sandbox, prod for live)')
    parser.add_argument('--region-id', type=str, default='us',
                       help='Region identifier (us, hk, jp, etc.)')

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("PHASE 7: WEBULL PAPER EXECUTION FOR OPTIONS TRADING")
    logger.info("=" * 60)
    logger.info(f"Environment: {args.environment}")
    logger.info(f"Region: {args.region_id}")

    # Load approved trades from workflow output
    if args.input:
        approved_trades_data = load_combined_workflow_output(args.input)
        if not approved_trades_data:
            logger.error(f"No approved trades found in {args.input}")
            return 1
        logger.info(f"Loaded {len(approved_trades_data)} approved trades from {args.input}")
    else:
        # If no input file specified, we might want to use the latest workflow output
        # For now, we'll show an error and ask for input
        logger.error("Please provide --input parameter pointing to combined workflow output")
        return 1

    # Initialize executor
    executor = Phase7WebullExecutor(
        app_key=args.app_key,
        app_secret=args.app_secret,
        environment=args.environment,
        region_id=args.region_id
    )

    # Execute the approved trades
    logger.info("Executing approved trades...")
    results = executor.execute_approved_trades(approved_trades_data)

    # Generate and display summary
    summary = executor.get_execution_summary(results)

    logger.info("=" * 60)
    logger.info("EXECUTION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total trades processed: {summary['total_trades']}")
    logger.info(f"Successful trades: {summary['successful_trades']}")
    logger.info(f"Failed trades: {summary['failed_trades']}")
    logger.info(f"Trade success rate: {summary['success_rate']:.1%}")
    logger.info(f"Total orders submitted: {summary['total_orders']}")
    logger.info(f"Successful orders: {summary['successful_orders']}")
    logger.info(f"Order success rate: {summary['order_success_rate']:.1%}")

    logger.info("\nTrade Details:")
    for trade in summary['trades']:
        status = "✓ SUCCESS" if trade['success'] else "✗ FAILED"
        logger.info(f"  {trade['symbol']}: {status} "
                   f"({trade['successful_orders_count']}/{trade['orders_count']} orders)")
        if trade['error']:
            logger.info(f"    Error: {trade['error']}")

    # Return appropriate exit code
    if summary['failed_trades'] == 0:
        logger.info("\nAll trades executed successfully!")
        return 0
    else:
        logger.warning(f"\n{summary['failed_trades']} trade(s) failed to execute.")
        return 1


if __name__ == "__main__":
    sys.exit(main())