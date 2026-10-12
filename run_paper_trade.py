#!/usr/bin/env python3
"""Execute paper trading using Webull API.

This script connects to Webull paper trading and executes trades based on
the validated strategy from research. It includes extensive safeguards to
prevent unintended trading.

Usage:
    python run_paper_trade.py --symbol AAPL --strategy-config config/strategy.yaml
"""

import os
import sys
import yaml
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from trading_bot.execution.webull import WebullExecution, OrderRequest, create_order_request
from trading_bot.execution.reconciliation import PositionReconciler, validate_position_sync
from trading_bot.monitoring.logger import get_audit_logger, log_trade_decision
from trading_bot.monitoring.alerts import get_alert_manager, log_risk_violation
from trading_bot.strategies.trend_following import TrendFollowingStrategy
from trading_bot.data.downloader import DataDownloader
from trading_bot.data.validator import DataValidator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('paper_trade')


class PaperTradingEngine:
    """Main paper trading engine."""

    def __init__(
        self,
        app_key: str = None,
        app_secret: str = None,
        environment: str = "uat",
        region_id: str = "us",
        max_position_size: float = 0.10,
        max_daily_loss: float = 0.05,
        max_drawdown: float = 0.15,
        max_daily_trades: int = 10
    ):
        """Initialize paper trading engine.

        Args:
            app_key: Webull app key
            app_secret: Webull app secret
            environment: Trading environment ('uat' for paper/sandbox, 'prod' for live)
            region_id: Region identifier ('us', 'hk', 'jp', etc.)
            max_position_size: Maximum position size
            max_daily_loss: Maximum daily loss
            max_drawdown: Maximum drawdown
            max_daily_trades: Maximum daily trades
        """
        # Initialize Webull executor
        self.executor = WebullExecution(
            app_key=app_key,
            app_secret=app_secret,
            environment=environment,
            region_id=region_id,
            max_daily_loss=max_daily_loss,
            max_position_size=max_position_size,
            max_daily_trades=max_daily_trades
        )

        # Risk limits
        self.max_position_size = max_position_size
        self.max_daily_loss = max_daily_loss
        self.max_drawdown = max_drawdown
        self.max_daily_trades = max_daily_trades

        # Monitoring
        self.audit_logger = get_audit_logger()
        self.alert_manager = get_alert_manager()

        # State
        self.positions: dict[str, dict] = {}
        self.daily_start_value = None
        self.daily_trades = 0

        logger.info("Paper trading engine initialized")

    def check_market_status(self) -> bool:
        """Check if market is currently open.

        Returns:
            True if market is open
        """
        is_open, msg = self.executor.verify_market_open()

        if not is_open:
            logger.warning(f"Market closed: {msg}")
            return False

        logger.info(f"Market open: {msg}")
        return True

    def check_account_status(self) -> bool:
        """Check if account is ready for trading.

        Returns:
            True if account is ready
        """
        is_ok, msg = self.executor.verify_account_status()

        if not is_ok:
            logger.error(f"Account issue: {msg}")
            return False

        logger.info(f"Account status: {msg}")
        return True

    def get_account_info(self) -> dict:
        """Get current account information.

        Returns:
            Account info dictionary
        """
        return self.executor.get_account_info()

    def get_positions(self) -> dict[str, dict]:
        """Get current positions from broker.

        Returns:
            Dictionary of {symbol: {quantity, avg_cost, price}}
        """
        broker_positions = self.executor.get_positions()

        self.positions = {}
        for pos in broker_positions:
            symbol = pos.symbol
            self.positions[symbol] = {
                'quantity': int(float(pos['quantity'])),
                'avg_cost': float(pos['avg_cost']) if pos['avg_cost'] else 0.0,
                'price': float(pos['current_price']) if pos['current_price'] else 0.0
            }

        return self.positions

    def calculate_signal(
        self,
        symbol: str,
        data: dict,
        strategy: TrendFollowingStrategy
    ) -> float:
        """Calculate strategy signal for symbol.

        Args:
            symbol: Stock symbol
            data: Historical price data
            strategy: Strategy instance

        Returns:
            Signal value
        """
        # Calculate all indicators
        signal = strategy.calculate_signal(data)
        return signal

    def check_risk_limits(
        self,
        symbol: str,
        new_position_value: float,
        current_exposure: float
    ) -> tuple[bool, str]:
        """Check if trade complies with risk limits.

        Args:
            symbol: Stock symbol
            new_position_value: Value of new position
            current_exposure: Current total exposure

        Returns:
            Tuple of (passes, reason)
        """
        # Get account for portfolio value
        account_info = self.get_account_info()
        portfolio_value = account_info.get('portfolio_value', 0)

        if portfolio_value == 0:
            return False, "Unable to determine portfolio value"

        # Check max position size
        position_pct = new_position_value / portfolio_value
        if position_pct > self.max_position_size:
            return False, f"Position {position_pct:.1%} exceeds max {self.max_position_size:.1%}"

        # Check max exposure
        max_exposure = portfolio_value * 1.0  # 100%
        if current_exposure + new_position_value > max_exposure:
            return False, "Exceeds max portfolio exposure"

        # Check daily trades limit
        if self.daily_trades >= self.max_daily_trades:
            return False, "Daily trade limit reached"

        return True, "OK"

    def execute_trade(
        self,
        symbol: str,
        signal: float,
        entry_threshold: float,
        exit_threshold: float,
        portfolio_value: float
    ) -> Optional[dict]:
        """Execute trade based on signal.

        Args:
            symbol: Stock symbol
            signal: Current signal value
            entry_threshold: Entry threshold
            exit_threshold: Exit threshold
            portfolio_value: Current portfolio value

        Returns:
            Trade execution result or None
        """
        # Check if we have position
        has_position = symbol in self.positions and self.positions[symbol]['quantity'] > 0

        # Determine action
        if signal > entry_threshold and not has_position:
            action = 'enter'
        elif signal < exit_threshold and has_position:
            action = 'exit'
        else:
            return None  # No action needed

        # Calculate position size
        account_info = self.get_account_info()
        current_exposure = account_info.get('portfolio_value', 0) - account_info.get('cash', 0)

        if action == 'enter':
            # Calculate shares based on 15% volatility targeting
            current_price = account_info.get('buying_power', 0) / 100  # Estimate

            # Get latest price
            try:
                latest_quote = self.executor._get_latest_quote(symbol)
                if latest_quote is None:
                    logger.warning(f"Could not get quote for {symbol}, using estimated price")
                    current_price = 100  # Fallback
                else:
                    current_price = latest_quote
            except Exception as e:
                logger.warning(f"Error getting quote for {symbol}: {e}, using estimated price")
                current_price = 100  # Fallback

            # Calculate position size (15% volatility targeting)
            target_value = 0.15 * portfolio_value
            shares = int(target_value / current_price)

            if shares < 1:
                logger.info(f"Calculated position too small for {symbol}")
                return None

            # Verify risk
            passes, reason = self.check_risk_limits(
                symbol, shares * current_price, current_exposure
            )
            if not passes:
                logger.warning(f"Risk check failed: {reason}")
                return None

            # Create order
            order_request = create_order_request(
                symbol=symbol,
                qty=shares,
                side='buy'
            )

            # Submit order
            success, error, order = self.executor.submit_order(order_request)

            if success:
                logger.info(f"Entered position: {shares} shares of {symbol}")
                log_trade_decision(
                    symbol=symbol,
                    direction='enter',
                    signal_value=signal,
                    entry_threshold=entry_threshold,
                    exit_threshold=exit_threshold,
                    position_size=shares,
                    portfolio_value=portfolio_value,
                    reason="Entry signal triggered"
                )

                self.daily_trades += 1
                self.positions[symbol] = {
                    'quantity': shares,
                    'avg_cost': current_price,
                    'price': current_price
                }

                return {'action': 'enter', 'symbol': symbol, 'qty': shares}
            else:
                logger.error(f"Order failed: {error}")
                return None

        elif action == 'exit':
            current_qty = self.positions[symbol]['quantity']

            # Create sell order
            order_request = create_order_request(
                symbol=symbol,
                qty=current_qty,
                side='sell'
            )

            # Submit order
            success, error, order = self.executor.submit_order(order_request)

            if success:
                logger.info(f"Exited position: {current_qty} shares of {symbol}")
                log_trade_decision(
                    symbol=symbol,
                    direction='exit',
                    signal_value=signal,
                    entry_threshold=entry_threshold,
                    exit_threshold=exit_threshold,
                    position_size=current_qty,
                    portfolio_value=portfolio_value,
                    reason="Exit signal triggered"
                )

                self.daily_trades += 1
                del self.positions[symbol]

                return {'action': 'exit', 'symbol': symbol, 'qty': current_qty}
            else:
                logger.error(f"Order failed: {error}")
                return None

        return None

    def run_trading_day(
        self,
        symbol: str,
        strategy: TrendFollowingStrategy,
        data: dict,
        entry_threshold: float,
        exit_threshold: float
    ) -> list:
        """Run trading for a single day.

        Args:
            symbol: Stock symbol
            strategy: Strategy instance
            data: Historical price data
            entry_threshold: Entry threshold
            exit_threshold: Exit threshold

        Returns:
            List of trade executions
        """
        executions = []

        # Check market status
        if not self.check_market_status():
            logger.info("Market closed - skipping trading")
            return executions

        # Get current positions
        self.get_positions()

        # Get account info
        account_info = self.get_account_info()
        portfolio_value = account_info.get('portfolio_value', 0)

        if portfolio_value == 0:
            logger.error("Unable to get portfolio value")
            return executions

        # Calculate signal
        signal = self.calculate_signal(symbol, data, strategy)

        logger.info(f"Signal for {symbol}: {signal:.4f} (entry={entry_threshold}, exit={exit_threshold})")

        # Execute trade if needed
        execution = self.execute_trade(
            symbol=symbol,
            signal=signal,
            entry_threshold=entry_threshold,
            exit_threshold=exit_threshold,
            portfolio_value=portfolio_value
        )

        if execution:
            executions.append(execution)

        return executions

    def daily_reset(self):
        """Reset daily counters."""
        self.daily_trades = 0
        self.executor.reset_daily()
        logger.info("Daily reset complete")


def load_strategy_config(config_path: str) -> dict:
    """Load strategy configuration from YAML file."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def run_paper_trading(
    symbol: str = "AAPL",
    strategy_config: dict = None,
    entry_threshold: float = 0.5,
    exit_threshold: float = -0.3,
    short_window: int = 20,
    medium_window: int = 50,
    long_window: int = 200,
    check_interval_minutes: int = 15
):
    """Run paper trading loop.

    Args:
        symbol: Stock symbol to trade
        strategy_config: Strategy configuration dictionary
        entry_threshold: Entry threshold
        exit_threshold: Exit threshold
        short_window: Short MA window
        medium_window: Medium MA window
        long_window: Long MA window
        check_interval_minutes: How often to check for signals
    """
    # Load strategy config if provided
    if strategy_config:
        entry_threshold = strategy_config.get('entry_threshold', entry_threshold)
        exit_threshold = strategy_config.get('exit_threshold', exit_threshold)

    # Initialize components
    engine = PaperTradingEngine()
    downloader = DataDownloader()
    strategy = TrendFollowingStrategy(
        entry_threshold=entry_threshold,
        exit_threshold=exit_threshold,
        short_window=short_window,
        medium_window=medium_window,
        long_window=long_window
    )

    logger.info(f"Starting paper trading for {symbol}")
    logger.info(f"Entry threshold: {entry_threshold}")
    logger.info(f"Exit threshold: {exit_threshold}")

    # Main trading loop
    try:
        while True:
            logger.info("=" * 60)
            logger.info(f"Trading session: {datetime.now().isoformat()}")
            logger.info("=" * 60)

            # Check market status
            if not engine.check_market_status():
                # Wait until next market open
                logger.info("Waiting for market to open...")
                time.sleep(3600)  # Wait 1 hour
                continue

            # Get historical data for signal calculation
            data = downloader.download(symbol, '2020-01-01', '2026-10-03')

            # Run trading for the day
            engine.run_trading_day(
                symbol=symbol,
                strategy=strategy,
                data=data,
                entry_threshold=entry_threshold,
                exit_threshold=exit_threshold
            )

            # Print current status
            account_info = engine.get_account_info()
            logger.info(f"Portfolio value: ${account_info.get('portfolio_value', 0):,.2f}")
            logger.info(f"Cash: ${account_info.get('cash', 0):,.2f}")
            logger.info(f"Positions: {list(engine.positions.keys())}")

            # Daily reset at market close (check every hour)
            current_hour = datetime.now().hour
            if current_hour >= 16:  # 4 PM ET
                engine.daily_reset()
                logger.info("Daily reset performed")

            # Wait for next check
            logger.info(f"Waiting {check_interval_minutes} minutes for next check...")
            time.sleep(check_interval_minutes * 60)

    except KeyboardInterrupt:
        logger.info("Paper trading stopped by user")

    except Exception as e:
        logger.error(f"Error in paper trading: {e}")
        raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Run Webull paper trading')

    parser.add_argument('--symbol', default='AAPL',
                       help='Stock symbol to trade (default: AAPL)')
    parser.add_argument('--entry-threshold', type=float, default=0.5,
                       help='Entry threshold (default: 0.5)')
    parser.add_argument('--exit-threshold', type=float, default=-0.3,
                       help='Exit threshold (default: -0.3)')
    parser.add_argument('--short-window', type=int, default=20,
                       help='Short MA window (default: 20)')
    parser.add_argument('--medium-window', type=int, default=50,
                       help='Medium MA window (default: 50)')
    parser.add_argument('--long-window', type=int, default=200,
                       help='Long MA window (default: 200)')
    parser.add_argument('--config', default=None,
                       help='Path to strategy config YAML file')

    args = parser.parse_args()

    # Load strategy config if provided
    strategy_config = None
    if args.config:
        strategy_config = load_strategy_config(args.config)

    run_paper_trading(
        symbol=args.symbol,
        strategy_config=strategy_config,
        entry_threshold=args.entry_threshold,
        exit_threshold=args.exit_threshold,
        short_window=args.short_window,
        medium_window=args.medium_window,
        long_window=args.long_window
    )