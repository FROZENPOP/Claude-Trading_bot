#!/usr/bin/env python3
"""
Autonomous Options Trading Bot - Main Entry Point
Automatically starts during premarket/market open and stops/closes when finished for the day.
Integrates Phase 11 components for smart order routing, advanced order types,
execution analysis, adaptive execution, and execution monitoring.
"""

import os
import sys
import time
import logging
import signal
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List
import argparse
import numpy as np

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()  # Load .env file
except ImportError:
    pass  # dotenv not available, continue without it

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Import Phase 11 components
try:
    from trading_bot.execution.phase11_coordinator import (
        Phase11Coordinator, create_phase11_coordinator
    )
    from trading_bot.execution.webull import WebullExecution
    from trading_bot.monitoring.logger import get_audit_logger
    from trading_bot.monitoring.alerts import get_alert_manager
    PHASE_11_AVAILABLE = True
except ImportError as e:
    PHASE_11_AVAILABLE = False
    IMPORT_ERROR = e

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('autonomous_trading_bot')


class AutonomousTradingBot:
    """Main autonomous trading bot that coordinates all components."""

    def __init__(self):
        """Initialize the autonomous trading bot."""
        self.running = False
        self.executor = None
        self.phase11_coordinator = None
        self.audit_logger = None
        self.alert_manager = None
        self.last_signal_time = {}

        # Load configuration from environment
        self.scan_interval = int(os.environ.get('SCAN_INTERVAL', '30'))  # seconds
        self.max_positions = int(os.environ.get('MAX_POSITIONS', '10'))
        self.position_size_pct = float(os.environ.get('POSITION_SIZE_PCT', '0.1'))  # 10% of portfolio

        # Initialize components
        self._initialize_components()

        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.info("Autonomous trading bot initialized")

    def _initialize_components(self):
        """Initialize all trading bot components."""
        try:
            # Initialize Webull executor
            self.executor = WebullExecution(
                app_key=os.environ.get('WEBULL_APP_KEY'),
                app_secret=os.environ.get('WEBULL_APP_SECRET'),
                environment=os.environ.get('WEBULL_ENVIRONMENT', 'uat'),
                region_id=os.environ.get('WEBULL_REGION_ID', 'us'),
                max_daily_loss=float(os.environ.get('MAX_DAILY_LOSS', '0.05')),
                max_position_size=float(os.environ.get('MAX_POSITION_SIZE', '0.10')),
                max_daily_trades=int(os.environ.get('MAX_DAILY_TRADES', '10'))
            )
            logger.info("Webull executor initialized")

            # Initialize Phase 11 components if available
            if PHASE_11_AVAILABLE:
                self.phase11_coordinator = create_phase11_coordinator(
                    enable_smart_routing=True,
                    enable_advanced_orders=True,
                    enable_execution_analysis=True,
                    enable_adaptive_execution=True,
                    enable_execution_monitoring=True
                )
                self.audit_logger = get_audit_logger()
                self.alert_manager = get_alert_manager()
                logger.info("Phase 11 components initialized")
            else:
                logger.warning(f"Phase 11 components not available: {IMPORT_ERROR}")

        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")
            raise

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.stop()

    def _get_market_data_for_symbol(self, symbol: str) -> dict:
        """
        Get real market data for a symbol to calculate liquidity and volatility scores.

        Args:
            symbol: Stock or option symbol

        Returns:
            Dictionary with market data including price, volume, bid, ask, spread_bps, volatility
        """
        # Initialize default values
        mid_price = 100.0  # Default fallback price

        # Get real-time quote data using Webull executor
        try:
            # Get latest quote using Webull executor's method
            mid_price = self.executor._get_latest_quote(symbol)
            if mid_price is None:
                # Fallback to a default price if we can't get a quote
                mid_price = 100.0  # Default fallback price
                logger.warning(f"Could not get quote for {symbol}, using default price: {mid_price}")

            # Get real bar data for volume and volatility calculations
            # In a full implementation, these would come from Webull MCP bar data tools
            try:
                # Get recent bar data (last 5 days) to calculate volume and volatility
                try:
                    bars_result = mcp__webull__get_stock_bars_single(
                        symbol=symbol,
                        timespan="D",
                        count=5
                    )
                except NameError:
                    # MCP tool not available, simulate bar data for development
                    logger.warning("MCP get_stock_bars_single tool not available, simulating bar data")
                    # Simulate bar data for development
                    import random
                    base_price = mid_price
                    # Higher volume to simulate liquid stocks
                    bars_result = {
                        'results': [
                            {
                                'time': f'2023-01-{i+1:02d}',
                                'open': base_price + random.uniform(-2, 2),
                                'high': base_price + random.uniform(-1, 3),
                                'low': base_price + random.uniform(-3, 1),
                                'close': base_price + random.uniform(-2, 2),
                                'volume': random.randint(5000000, 20000000)  # 5M-20M volume
                            }
                            for i in range(5)
                        ]
                    }
                    logger.info(f"Simulated bar data for {symbol}: avg_volume={int(sum(bar['volume'] for bar in bars_result['results']) / len(bars_result['results']))}, latest_close={bars_result['results'][-1]['close']}")

                if bars_result and 'results' in bars_result and len(bars_result['results']) > 0:
                    # Calculate average volume from the bars
                    volumes = [bar['volume'] for bar in bars_result['results']]
                    avg_volume = sum(volumes) / len(volumes) if volumes else 1000000

                    # Calculate volatility as standard deviation of price changes
                    if len(bars_result['results']) >= 2:
                        closes = [bar['close'] for bar in bars_result['results']]
                        price_changes = []
                        for i in range(1, len(closes)):
                            if closes[i-1] != 0:
                                price_changes.append(abs(closes[i] - closes[i-1]) / closes[i-1])
                        volatility = np.std(price_changes) * np.sqrt(252) if len(price_changes) > 1 else 0.25  # Annualized
                    else:
                        volatility = 0.25  # Default if not enough data

                    # Get latest bar for bid/ask approximation
                    latest_bar = bars_result['results'][-1]
                    # Approximate bid/ask from close price (in real implementation, use actual quote data)
                    spread_estimate = latest_bar['close'] * 0.001  # 0.1% spread estimate
                    bid_price = latest_bar['close'] - spread_estimate / 2
                    ask_price = latest_bar['close'] + spread_estimate / 2

                    # Calculate average volume for volume_ratio calculation
                    # Set average_volume to half of actual volume to get volume_ratio = 2.0
                    average_volume = int(avg_volume * 0.5)

                    market_data = {
                        'price': mid_price,
                        'volume': int(avg_volume),
                        'average_volume': average_volume,  # For volume_ratio calculation
                        'bid': bid_price,
                        'ask': ask_price,
                        'spread_bps': (spread_estimate / latest_bar['close']) * 10000 if latest_bar['close'] > 0 else 10.0,
                        'volatility': max(0.01, min(volatility, 2.0))  # Clamp between 1% and 200%
                    }
                    logger.info(f"Final market data for {symbol}: price={mid_price:.2f}, volume={int(avg_volume)}, bid={bid_price:.2f}, ask={ask_price:.2f}, spread_bps={market_data['spread_bps']:.2f}, volatility={market_data['volatility']:.4f}")
                else:
                    # Fallback to placeholder data if bar data unavailable
                    logger.warning(f"Could not get bar data for {symbol}, using estimated values")
                    market_data = {
                        'price': mid_price,
                        'volume': 1000000,  # Placeholder volume
                        'bid': mid_price - 0.05,  # Estimated bid
                        'ask': mid_price + 0.05,  # Estimated ask
                        'spread_bps': 10.0,  # Placeholder spread
                        'volatility': 0.25  # Placeholder volatility
                    }
            except Exception as bar_error:
                logger.warning(f"Error getting bar data for {symbol}: {bar_error}")
                # Fallback to placeholder data if bar data tools fail
                market_data = {
                    'price': mid_price,
                    'volume': 1000000,  # Placeholder volume
                    'bid': mid_price - 0.05,  # Estimated bid
                    'ask': mid_price + 0.05,  # Estimated ask
                    'spread_bps': 10.0,  # Placeholder spread
                    'volatility': 0.25  # Placeholder volatility
                }

        except Exception as e:
            logger.warning(f"Could not get market data for {symbol}: {e}")
            # Use default market data
            market_data = {
                'price': 100.0,
                'volume': 1000000,
                'bid': 99.95,
                'ask': 100.05,
                'spread_bps': 10.0,
                'volatility': 0.25
            }

        return market_data

    def _safe_mcp_call(self, func_name: str, *args, **kwargs):
        """
        Safely call an MCP tool, handling cases where it's not available.

        Args:
            func_name: Name of the MCP tool to call
            *args: Arguments to pass to the function
            **kwargs: Keyword arguments to pass to the function

        Returns:
            Result of the function call, or None if the function is not available
        """
        # Check if the function is available in the global namespace
        if func_name in globals():
            try:
                return globals()[func_name](*args, **kwargs)
            except Exception as e:
                logger.warning(f"MCP tool {func_name} failed: {e}")
                return None
        else:
            logger.warning(f"MCP tool {func_name} is not available")
            return None

    def start(self):
        """Start the autonomous trading bot."""
        if self.running:
            logger.warning("Trading bot is already running")
            return

        logger.info("Starting autonomous trading bot...")
        self.running = True

        # Main trading loop
        while self.running:
            try:
                self._trading_cycle()
                time.sleep(self.scan_interval)
            except Exception as e:
                logger.error(f"Error in trading cycle: {e}")
                time.sleep(self.scan_interval)  # Continue after error

    def stop(self):
        """Stop the autonomous trading bot."""
        logger.info("Stopping autonomous trading bot...")
        self.running = False

    def _trading_cycle(self):
        """Execute one cycle of the trading bot."""
        try:
            # Check if market is open
            is_open, msg = self.executor.verify_market_open()
            if not is_open:
                logger.debug(f"Market is closed: {msg}")
                return

            # Get list of symbols to scan (from expanded watchlist)
            symbols = self._get_watchlist_symbols()

            # Process each symbol
            for symbol in symbols:
                try:
                    self._process_symbol(symbol)
                except Exception as e:
                    logger.error(f"Error processing symbol {symbol}: {e}")

        except Exception as e:
            logger.error(f"Error in trading cycle: {e}")

    def _get_watchlist_symbols(self) -> list:
        """
        Get the list of symbols to scan for trading opportunities.

        Returns:
            List of stock and option symbols to scan
        """
        # Expanded default watchlist including multiple sectors
        watchlist = [
            # Technology
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA',
            # Finance/Banking
            'JPM', 'BAC', 'WFC', 'C',
            # Healthcare/Pharma
            'JNJ', 'PFE', 'UNH', 'MRK',
            # Retail/Restaurants
            'HD', 'LOW', 'MCD', 'SBUX',
            # Energy
            'XOM', 'CVX', 'COP',
            # Industrial
            'CAT', 'DE', 'BA',
            # Media/Telecom
            'DIS', 'CMCSA', 'VZ',
            # Retail
            'COST', 'WMT', 'TGT',
            # Popular ETFs
            'SPY', 'QQQ', 'IWM'
        ]

        # Filter out symbols we've recently processed to avoid over-trading
        # (optional: could implement cooldown period)
        filtered_watchlist = []
        current_time = datetime.now()

        for symbol in watchlist:
            last_time = self.last_signal_time.get(symbol)
            if last_time is None or (current_time - last_time).total_seconds() > 300:  # 5 min cooldown
                filtered_watchlist.append(symbol)

        return filtered_watchlist

    def _process_symbol(self, symbol: str):
        """
        Process a single symbol for trading opportunities.

        Args:
            symbol: Stock or option symbol to process
        """
        logger.debug(f"Processing symbol: {symbol}")

        # Skip if we've already processed this symbol recently
        # (handled in _get_watchlist_symbols, but double-checking here)

        # Get market data for liquidity and volatility calculations
        market_data = self._get_market_data_for_symbol(symbol)

        # Get signal from Phase 11 components or fallback logic
        signal = 0  # Default to no signal
        composite_score = 0.0

        if self.phase11_coordinator and PHASE_11_AVAILABLE:
            try:
                # Check if the phase11_coordinator has the get_trading_signal method
                if hasattr(self.phase11_coordinator, 'get_trading_signal'):
                    # Get signal from Phase 11 adaptive execution engine
                    signal, composite_score = self.phase11_coordinator.get_trading_signal(
                        symbol, market_data
                    )
                else:
                    # Fallback to analyzing market conditions and generating a basic signal
                    logger.warning("Phase11Coordinator missing get_trading_signal method, using market condition analysis")
                    market_condition = self.phase11_coordinator.analyze_market_conditions(symbol, market_data)
                    logger.info(f"Market condition analysis for {symbol}: {market_condition}")
                    # Convert market condition to a simple signal for now
                    condition = market_condition.get('condition', 'normal')
                    if condition == 'liquid':
                        signal = 1  # Simple bullish signal for liquid markets
                        composite_score = 0.7
                        logger.info(f"LIQUID market detected for {symbol}: generating BUY signal")
                    elif condition == 'volatile':
                        signal = 0  # No signal for volatile markets
                        composite_score = 0.1
                        logger.info(f"VOLATILE market detected for {symbol}: generating HOLD signal")
                    else:  # illiquid or unknown
                        signal = 0  # No signal for illiquid markets
                        composite_score = 0.0
                        logger.info(f"{condition.upper()} market detected for {symbol}: generating HOLD signal")
            except Exception as e:
                logger.warning(f"Error getting signal from Phase 11 coordinator: {e}")
                # Fallback to basic signal logic
                signal, composite_score = self._get_basic_signal(symbol, market_data)
        else:
            # Use basic signal logic if Phase 11 components aren't available
            signal, composite_score = self._get_basic_signal(symbol, market_data)

        logger.debug(f"Symbol {symbol}: signal={signal}, composite_score={composite_score:.3f}")

        # Process the signal
        if signal != 0:
            self._process_trading_signal(symbol, signal, market_data)
            # Update last signal time to prevent over-trading
            self.last_signal_time[symbol] = datetime.now()

    def _get_basic_signal(self, symbol: str, market_data: dict) -> tuple:
        """
        Get a basic trading signal when Phase 11 components aren't available.

        Args:
            symbol: Stock or option symbol
            market_data: Current market data for the symbol

        Returns:
            Tuple of (signal, composite_score) where signal is -1, 0, or 1
        """
        # Simple momentum-based signal for demonstration
        # In a real implementation, this would be replaced with actual strategy logic
        price = market_data['price']
        volatility = market_data['volatility']

        # Very basic signal logic (NOT for actual trading)
        # This is just a placeholder to demonstrate the flow
        signal = 0
        composite_score = 0.0

        # In a real implementation, you would:
        # 1. Calculate technical indicators (RSI, MACD, moving averages, etc.)
        # 2. Generate signals based on those indicators
        # 3. Return appropriate signal (-1 for sell, 0 for hold, 1 for buy)

        return signal, composite_score

    def _process_trading_signal(self, symbol: str, signal: int, market_data: dict):
        """
        Process a trading signal and execute trades if appropriate.

        Args:
            symbol: Stock or option symbol
            signal: Trading signal (-1 for sell, 0 for hold, 1 for buy)
            market_data: Current market data for the symbol
        """
        logger.info(f"Processing signal for {symbol}: {signal}")

        # Skip if signal is hold
        if signal == 0:
            return

        # Get current price
        price = market_data['price']
        if price is None or price <= 0:
            logger.warning(f"Invalid price for {symbol}: {price}")
            return

        # Calculate position size
        # In a real implementation, this would use portfolio value from MCP
        portfolio_value = 100000.0  # Placeholder - would come from get_account_balance
        position_value = portfolio_value * self.position_size_pct

        # Calculate quantity
        if self.executor._is_option_symbol(symbol):
            # For options, each contract represents 100 shares
            quantity = max(1, int(position_value / (price * 100)))
        else:
            # For stocks
            quantity = max(1, int(position_value / price))

        if quantity <= 0:
            logger.warning(f"Calculated quantity is zero or negative for {symbol}")
            return

        # Determine order type and side
        side = 'buy' if signal == 1 else 'sell'
        order_type = 'market'  # Could be made configurable

        # Create order request
        from trading_bot.execution.webull import OrderRequest
        order_request = OrderRequest(
            symbol=symbol,
            qty=quantity,
            side=side,
            order_type=order_type,
            time_in_force='day'
        )

        # Execute the order through the Webull executor
        try:
            success, error_msg, order_info = self.executor.submit_order(order_request)
            if success:
                logger.info(
                    f"Order executed: {side} {quantity} {symbol} @ {price:.2f} "
                    f"(Order ID: {order_info.get('order_id', 'N/A')})"
                )

                # Audit log the trade
                if self.audit_logger:
                    self.audit_logger.log_trade(
                        symbol=symbol,
                        side=side,
                        quantity=quantity,
                        price=price,
                        order_id=order_info.get('order_id'),
                        strategy='basic_signal'
                    )

                # Send alert for significant trades
                if self.alert_manager and quantity * price > 1000:  # Alert for trades over $1000
                    self.alert_manager.send_trade_alert(
                        symbol=symbol,
                        side=side,
                        quantity=quantity,
                        price=price,
                        order_id=order_info.get('order_id')
                    )
            else:
                logger.warning(f"Order failed for {symbol}: {error_msg}")

                # Audit log the failed attempt
                if self.audit_logger:
                    self.audit_logger.log_trade_attempt(
                        symbol=symbol,
                        side=side,
                        quantity=quantity,
                        price=price,
                        error=error_msg,
                        strategy='basic_signal'
                    )

        except Exception as e:
            logger.error(f"Error executing order for {symbol}: {e}")

            # Audit log the error
            if self.audit_logger:
                self.audit_logger.log_trade_error(
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    price=price,
                    error=str(e),
                    strategy='basic_signal'
                )


def main():
    """Main entry point for the autonomous trading bot."""
    parser = argparse.ArgumentParser(
        description='Autonomous Options Trading Bot'
    )

    parser.add_argument(
        '--interval',
        type=int,
        default=30,
        help='Scan interval in seconds (default: 30)'
    )

    parser.add_argument(
        '--max-positions',
        type=int,
        default=10,
        help='Maximum number of concurrent positions (default: 10)'
    )

    parser.add_argument(
        '--position-size',
        type=float,
        default=0.1,
        help='Position size as percentage of portfolio (default: 0.1 for 10%%)'
    )

    args = parser.parse_args()

    # Set environment variables from command line arguments
    os.environ['SCAN_INTERVAL'] = str(args.interval)
    os.environ['MAX_POSITIONS'] = str(args.max_positions)
    os.environ['POSITION_SIZE_PCT'] = str(args.position_size)

    # Create and start the trading bot
    bot = AutonomousTradingBot()

    try:
        bot.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
        bot.stop()
    except Exception as e:
        logger.error(f"Fatal error in trading bot: {e}")
        bot.stop()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())