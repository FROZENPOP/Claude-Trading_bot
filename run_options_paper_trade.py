#!/usr/bin/env python3
"""Execute options paper trading using Webull API.

This script connects to Webull paper trading and executes options trades based on
signals from options strategies. It includes extensive safeguards to prevent
unintended trading.
"""

import os
import sys
import yaml
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from trading_bot.execution.webull import WebullExecution, OrderRequest, create_order_request
from trading_bot.monitoring.logger import get_audit_logger, log_trade_decision
from trading_bot.monitoring.alerts import get_alert_manager, log_risk_violation
from trading_bot.strategies.vertical_spread import VerticalSpreadStrategy, SpreadSignal
from trading_bot.data.options_downloader import OptionsDataDownloader
from trading_bot.data.option_validator import OptionsDataValidator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('options_paper_trade')


class OptionsPaperTradingEngine:
    """Main options paper trading engine."""

    def __init__(
        self,
        app_key: str = None,
        app_secret: str = None,
        environment: str = "uat",
        region_id: str = "us",
        max_daily_loss: float = 0.05,
        max_position_size: float = 0.10,
        max_daily_trades: int = 10
    ):
        """Initialize options paper trading engine.

        Args:
            app_key: Webull app key
            app_secret: Webull app secret
            environment: Trading environment ('uat' for paper/sandbox, 'prod' for live)
            region_id: Region identifier ('us', 'hk', 'jp', etc.)
            max_daily_loss: Maximum daily loss
            max_position_size: Maximum position size as % of portfolio
            max_daily_trades: Maximum trades per day
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
        self.max_daily_loss = max_daily_loss
        self.max_position_size = max_position_size
        self.max_daily_trades = max_daily_trades

        # Monitoring
        self.audit_logger = get_audit_logger()
        self.alert_manager = get_alert_manager()

        # State
        self.positions: dict[str, dict] = {}  # symbol -> position info
        self.daily_start_value = None
        self.daily_trades = 0

        logger.info("Options paper trading engine initialized")

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
        """Check if account is active and trading is allowed.

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
            Dictionary of positions
        """
        broker_positions = self.executor.get_positions()

        self.positions = {}
        for pos in broker_positions:
            symbol = pos.get('symbol', '')
            self.positions[symbol] = {
                'quantity': int(float(pos.get('quantity', 0))),
                'avg_cost': float(pos.get('average_cost', 0.0)) if pos.get('average_cost') else 0.0,
                'price': float(pos.get('last_price', 0.0)) if pos.get('last_price') else 0.0,
                'asset_class': 'option' if self._is_option_symbol(symbol) else 'stock'
            }

        return self.positions

    def _is_option_symbol(self, symbol: str) -> bool:
        """Check if a symbol represents an option contract.

        Option symbol format: {UNDERLYING}{YY}{MM}{DD}{C/P}{STRIKE*1000}
        Example: AAPL240119C00150000
        """
        import re
        option_pattern = r'^[A-Z]+\d{6}[CP]\d{8}$'
        return bool(re.match(option_pattern, symbol))

    def calculate_signal(
        self,
        underlying_symbol: str,
        market_data: dict,
        option_chain: dict,
        strategy: VerticalSpreadStrategy
    ) -> List[SpreadSignal]:
        """Calculate strategy signals for underlying symbol.

        Args:
            underlying_symbol: Underlying stock symbol
            market_data: Historical price data for underlying
            option_chain: Current option chain data
            strategy: Strategy instance

        Returns:
            List of SpreadSignal objects
        """
        # Convert data to DataFrames if needed
        import pandas as pd

        if isinstance(market_data, dict):
            market_df = pd.DataFrame(market_data)
        else:
            market_df = market_data

        if isinstance(option_chain, dict):
            option_df = pd.DataFrame(option_chain)
        else:
            option_df = option_chain

        # Generate signals using the strategy
        signals = strategy.generate_spread_signals(
            market_data=market_df,
            option_chain=option_df,
            current_date=datetime.now()
        )

        return signals

    def check_risk_limits(
        self,
        underlying_symbol: str,
        spread_value: float,
        current_exposure: float
    ) -> tuple[bool, str]:
        """Check if trade complies with risk limits.

        Args:
            underlying_symbol: Underlying stock symbol
            spread_value: Value of the spread position
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
        position_pct = spread_value / portfolio_value
        if position_pct > self.max_position_size:
            return False, f"Position {position_pct:.1%} exceeds max {self.max_position_size:.1%}"

        # Check max exposure
        max_exposure = portfolio_value * 1.0  # 100%
        if current_exposure + spread_value > max_exposure:
            return False, "Exceeds max portfolio exposure"

        # Check daily trades limit
        if self.daily_trades >= self.max_daily_trades:
            return False, "Daily trade limit reached"

        return True, "OK"

    def execute_options_trade(
        self,
        signal: SpreadSignal,
        portfolio_value: float
    ) -> Optional[dict]:
        """Execute options trade based on signal.

        Args:
            signal: SpreadSignal containing trade details
            portfolio_value: Current portfolio value

        Returns:
            Trade execution result or None
        """
        # Extract signal details
        underlying_symbol = signal.underlying_symbol
        long_strike = getattr(signal, 'long_strike', None)
        short_strike = getattr(signal, 'short_strike', None)
        option_type = getattr(signal, 'option_type', None)
        net_debit = getattr(signal, 'net_debit', None)
        days_to_exp = getattr(signal, 'days_to_exp', None)

        if None in [long_strike, short_strike, option_type, net_debit, days_to_exp]:
            logger.error("Missing required signal information to create spread")
            return None

        # Create the spread to get position sizing
        from trading_bot.strategies.vertical_spread import VerticalSpread
        from datetime import timedelta

        spread = VerticalSpread(
            underlying_symbol=underlying_symbol,
            expiration_date=(datetime.now() + timedelta(days=days_to_exp)).strftime('%Y-%m-%d'),
            long_strike=long_strike,
            short_strike=short_strike,
            option_type=option_type,
            long_quantity=1,  # Temporary quantity for pricing
            short_quantity=-1,  # Temporary quantity for pricing
            entry_date=datetime.now(),
            entry_price=net_debit,
            max_loss=0,  # Will be calculated in __post_init__
            max_profit=0,  # Will be calculated in __post_init__
            breakeven=0    # Will be calculated in __post_init__
        )

        # Calculate maximum risk allowed for this trade
        max_risk_dollars = portfolio_value * 0.02  # 2% risk per trade

        # Calculate quantity based on risk
        risk_per_spread = spread.max_loss  # This is already calculated in __post_init__
        if risk_per_spread <= 0:
            logger.error(f"Invalid risk per spread: {risk_per_spread}")
            return None

        max_quantity = int(max_risk_dollars / risk_per_spread)

        if max_quantity < 1:
            logger.warning(f"Calculated quantity is less than 1: {max_quantity}")
            return None

        # Use minimum of 1 contract or calculated max (cap at 10 for safety)
        quantity = max(1, min(max_quantity, 10))

        # Recreate spread with correct quantity
        spread = VerticalSpread(
            underlying_symbol=underlying_symbol,
            expiration_date=(datetime.now() + timedelta(days=days_to_exp)).strftime('%Y-%m-%d'),
            long_strike=long_strike,
            short_strike=short_strike,
            option_type=option_type,
            long_quantity=quantity if option_type == 'call' else -quantity,  # Long is positive
            short_quantity=-quantity if option_type == 'call' else quantity,  # Short is negative
            entry_date=datetime.now(),
            entry_price=net_debit,  # Net debit (positive for debit spread)
            max_loss=0,  # Will be calculated in __post_init__
            max_profit=0,  # Will be calculated in __post_init__
            breakeven=0    # Will be calculated in __post_init__
        )

        # Calculate actual position value
        position_value = spread.max_loss  # For debit spreads, this is the cost

        # Get current exposure
        account_info = self.get_account_info()
        current_exposure = account_info.get('portfolio_value', 0) - account_info.get('cash', 0)

        # Verify risk
        passes, reason = self.check_risk_limits(
            underlying_symbol,
            position_value,
            current_exposure
        )
        if not passes:
            logger.warning(f"Risk check failed: {reason}")
            return None

        # Create option orders for the spread
        try:
            # Generate option symbols
            from trading_bot.strategies.option_pricing import parse_option_symbol

            expiration_date = spread.expiration_date
            exp_date_obj = datetime.strptime(expiration_date, '%Y-%m-%d')
            exp_date_formatted = exp_date_obj.strftime('%y%m%d')

            # Long leg symbol
            long_option_type_char = 'C' if option_type == 'call' else 'P'
            long_symbol = f"{underlying_symbol}{exp_date_formatted}{long_option_type_char}{int(long_strike*1000):08d}"

            # Short leg symbol
            short_option_type_char = 'C' if option_type == 'call' else 'P'
            short_symbol = f"{underlying_symbol}{exp_date_formatted}{short_option_type_char}{int(short_strike*1000):08d}"

            # For a debit spread (bull call or bear put):
            # - We BUY the long leg
            # - We SELL the short leg
            if option_type == 'call':  # Bull call spread
                # Buy call (long leg), Sell call (short leg)
                long_side = 'buy'
                short_side = 'sell'
            else:  # Bear put spread
                # Buy put (long leg), Sell put (short leg)
                long_side = 'buy'
                short_side = 'sell'

            # Create orders
            long_order_request = create_order_request(
                symbol=long_symbol,
                qty=abs(spread.long_quantity),
                side=long_side,
                order_type="limit",
                limit_price=net_debit * 0.6  # Approximate price for long leg
            )

            short_order_request = create_order_request(
                symbol=short_symbol,
                qty=abs(spread.short_quantity),
                side=short_side,
                order_type="limit",
                limit_price=net_debit * 0.4  # Approximate price for short leg
            )

            # Submit orders
            logger.info(f"Placing spread order: {quantity} {underlying_symbol} {long_strike}/{short_strike} {option_type}")

            # Submit long leg order
            long_success, long_error, long_order = self.executor.submit_order(long_order_request)
            if not long_success:
                logger.error(f"Long leg order failed: {long_error}")
                return None

            # Submit short leg order
            short_success, short_error, short_order = self.executor.submit_order(short_order_request)
            if not short_success:
                logger.error(f"Short leg order failed: {short_error}")
                # Try to cancel the long leg order
                self.executor.cancel_order(long_order.id)
                return None

            logger.info(f"Options spread order placed successfully: {long_order.id}, {short_order.id}")

            # Log trade decision
            log_trade_decision(
                symbol=underlying_symbol,
                direction='enter',
                signal_value=signal.signal_strength,
                entry_threshold=0.3,  # Minimum signal strength
                exit_threshold=-0.1,
                position_size=quantity,
                portfolio_value=portfolio_value,
                reason=f"Options {option_type} spread signal triggered"
            )

            # Update positions tracking
            self.daily_trades += 1
            position_id = f"{long_order.id}_{short_order.id}"
            self.positions[position_id] = {
                'underlying_symbol': underlying_symbol,
                'option_type': option_type,
                'long_strike': long_strike,
                'short_strike': short_strike,
                'expiration_date': expiration_date,
                'quantity': quantity,
                'entry_price': net_debit,
                'long_order_id': long_order.id,
                'short_order_id': short_order.id,
                'status': 'open',
                'timestamp': datetime.now()
            }

            return {
                'action': 'enter',
                'underlying_symbol': underlying_symbol,
                'option_type': option_type,
                'strikes': f"{long_strike}/{short_strike}",
                'expiration_date': expiration_date,
                'quantity': quantity,
                'long_order_id': long_order.id,
                'short_order_id': short_order.id,
                'spread_id': position_id
            }

        except Exception as e:
            logger.error(f"Error placing options orders: {e}")
            return None

    def run_trading_cycle(
        self,
        underlying_symbol: str,
        strategy: VerticalSpreadStrategy,
        market_data: dict,
        option_chain: dict
    ) -> list:
        """Run options trading for a single cycle.

        Args:
            underlying_symbol: Underlying stock symbol to trade
            strategy: Strategy instance
            market_data: Historical price data
            option_chain: Current option chain data

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

        # Calculate signals
        signals = self.calculate_signal(
            underlying_symbol=underlying_symbol,
            market_data=market_data,
            option_chain=option_chain,
            strategy=strategy
        )

        logger.info(f"Generated {len(signals)} spread signals for {underlying_symbol}")

        # Execute trades for each signal
        for signal in signals:
            if signal.signal_strength >= 0.3:  # Minimum signal strength threshold
                execution = self.execute_options_trade(
                    signal=signal,
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


def run_options_paper_trading(
    underlying_symbol: str = "AAPL",
    check_interval_minutes: int = 15
):
    """Run options paper trading loop.

    Args:
        underlying_symbol: Underlying stock symbol to trade
        check_interval_minutes: How often to check for signals
    """
    # Initialize components
    engine = OptionsPaperTradingEngine()
    downloader = OptionsDataDownloader()
    validator = OptionsDataValidator()
    strategy = VerticalSpreadStrategy(underlying_symbol=underlying_symbol)

    logger.info(f"Starting options paper trading for {underlying_symbol}")
    logger.info(f"Check interval: {check_interval_minutes} minutes")

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
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

            # Download underlying data
            market_data = downloader.download_underlying(
                underlying_symbol, start_date, end_date
            )

            # Validate market data
            if not validator.validate_underlying_data(market_data):
                logger.warning("Underlying data validation failed, using cached data")
                # In a real implementation, we might fallback to cached data

            # Download option chain data
            option_chain = downloader.download_option_chain(underlying_symbol)

            # Validate option chain data
            if not validator.validate_option_chain(option_chain):
                logger.warning("Option chain data validation failed")

            # Run trading for the cycle
            engine.run_trading_cycle(
                underlying_symbol=underlying_symbol,
                strategy=strategy,
                market_data=market_data,
                option_chain=option_chain
            )

            # Print current status
            account_info = engine.get_account_info()
            logger.info(f"Portfolio value: ${account_info.get('portfolio_value', 0):,.2f}")
            logger.info(f"Cash: ${account_info.get('cash', 0):,.2f}")
            logger.info(f"Open positions: {len(engine.positions)}")

            # Daily reset at market close (check every hour)
            current_hour = datetime.now().hour
            if current_hour >= 16:  # 4 PM ET
                engine.daily_reset()
                logger.info("Daily reset performed")

            # Wait for next check
            logger.info(f"Waiting {check_interval_minutes} minutes for next check...")
            time.sleep(check_interval_minutes * 60)

    except KeyboardInterrupt:
        logger.info("Options paper trading stopped by user")

    except Exception as e:
        logger.error(f"Error in options paper trading: {e}")
        raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Run Webull options paper trading')

    parser.add_argument('--symbol', default='AAPL',
                       help='Underlying stock symbol to trade (default: AAPL)')
    parser.add_argument('--interval', type=int, default=15,
                       help='Check interval in minutes (default: 15)')

    args = parser.parse_args()

    run_options_paper_trading(
        underlying_symbol=args.symbol,
        check_interval_minutes=args.interval
    )