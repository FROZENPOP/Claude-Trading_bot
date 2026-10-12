"""Phase 8: Execution monitoring and position tracking for autonomous options trading system.

This module handles:
- Monitoring open positions and orders
- Tracking P&L (realized and unrealized)
- Implementing exit logic (stop loss, take profit, time-based exits)
- Position reconciliation with Webull account
- Alert generation for significant events
"""

import os
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
import logging

from trading_bot.execution.webull_execution import WebullExecution, OrderRequest, create_order_request

logger = logging.getLogger(__name__)


@dataclass
class PositionInfo:
    """Information about an open position."""
    symbol: str
    qty: int                    # Number of contracts/shares
    side: str                   # 'buy' or 'sell'
    entry_price: float          # Average entry price
    current_price: float        # Current market price
    unrealized_pnl: float       # Unrealized profit/loss
    realized_pnl: float         # Realized profit/loss (from partial closes)
    entry_time: datetime        # When position was opened
    stop_loss: Optional[float] = None   # Stop loss price
    take_profit: Optional[float] = None # Take profit price
    max_hold_time: Optional[timedelta] = None  # Maximum time to hold position
    tags: List[str] = field(default_factory=list)  # Custom tags for position


@dataclass
class ExitSignal:
    """Signal to exit a position."""
    position_symbol: str
    exit_reason: str  # 'stop_loss', 'take_profit', 'time_exit', 'manual', etc.
    exit_price: float
    qty_to_exit: int
    timestamp: datetime


class ExecutionMonitor:
    """Monitor and manage open positions for the autonomous trading system."""

    def __init__(
        self,
        webull_executor: WebullExecution,
        check_interval: int = 30,  # seconds
        enable_auto_exit: bool = True,
        enable_alerts: bool = True
    ):
        """Initialize the execution monitor.

        Args:
            webull_executor: Initialized WebullExecution instance
            check_interval: How often to check positions (seconds)
            enable_auto_exit: Whether to automatically execute exit signals
            enable_alerts: Whether to send alerts for position events
        """
        self.webull = webull_executor
        self.check_interval = check_interval
        self.enable_auto_exit = enable_auto_exit
        self.enable_alerts = enable_alerts

        # Position tracking
        self.positions: Dict[str, PositionInfo] = {}  # symbol -> PositionInfo
        self.exit_signals: List[ExitSignal] = []
        self.closed_positions: List[PositionInfo] = []  # History of closed positions

        # Control flags
        self.running = False
        self.monitor_thread: Optional[threading.Thread] = None

        # Alert callbacks
        self.alert_callbacks: List[Callable[[str], None]] = []

        logger.info(f"ExecutionMonitor initialized (check_interval={check_interval}s)")

    def add_alert_callback(self, callback: Callable[[str], None]):
        """Add a callback function for alerts."""
        self.alert_callbacks.append(callback)

    def _send_alert(self, message: str):
        """Send alert via registered callbacks."""
        if self.enable_alerts:
            logger.info(f"ALERT: {message}")
            for callback in self.alert_callbacks:
                try:
                    callback(message)
                except Exception as e:
                    logger.error(f"Error in alert callback: {e}")

    def _get_latest_quote(self, symbol: str) -> Optional[float]:
        """Get the latest quote for a symbol using the WebullExecution wrapper."""
        # Delegate to the WebullExecution wrapper's _get_latest_quote method
        # which handles the Webull MCP communication internally
        return self.webull._get_latest_quote(symbol)

    def update_positions_from_webull(self):
        """Synchronize position tracking with Webull account."""
        try:
            # Get current positions from WebullExecution wrapper
            webull_positions = self.webull.get_all_positions()

            # Create a set of current symbols from Webull
            webull_symbols = {pos.symbol for pos in webull_positions}

            # Update existing positions
            for position in webull_positions:
                symbol = position.symbol
                qty = int(float(position.qty))  # Can be fractional for some assets
                # Determine side based on quantity (positive = buy, negative = sell)
                side = "buy" if float(position.qty) > 0 else "sell"

                # Get current market price
                current_price = self._get_latest_quote(symbol) or 0.0

                if symbol in self.positions:
                    # Update existing position
                    pos_info = self.positions[symbol]
                    pos_info.qty = abs(qty)  # Store as positive quantity
                    pos_info.side = side
                    pos_info.current_price = current_price

                    # Calculate unrealized P&L
                    if side == "buy":
                        pos_info.unrealized_pnl = (current_price - pos_info.entry_price) * abs(qty) * self._contract_multiplier(symbol)
                    else:  # sell
                        pos_info.unrealized_pnl = (pos_info.entry_price - current_price) * abs(qty) * self._contract_multiplier(symbol)
                else:
                    # New position discovered
                    entry_price = float(position.avg_entry_price) if hasattr(position, 'avg_entry_price') else current_price
                    pos_info = PositionInfo(
                        symbol=symbol,
                        qty=abs(qty),
                        side=side,
                        entry_price=entry_price,
                        current_price=current_price,
                        unrealized_pnl=0.0,  # Will be calculated below
                        realized_pnl=0.0,
                        entry_time=getattr(position, 'updated_at', datetime.now())
                    )

                    # Calculate unrealized P&L for new position
                    if side == "buy":
                        pos_info.unrealized_pnl = (current_price - entry_price) * abs(qty) * self._contract_multiplier(symbol)
                    else:  # sell
                        pos_info.unrealized_pnl = (entry_price - current_price) * abs(qty) * self._contract_multiplier(symbol)

                    self.positions[symbol] = pos_info
                    self._send_alert(f"New position detected: {side} {abs(qty)} {symbol} @ ${entry_price:.2f}")

            # Check for closed positions
            tracked_symbols = set(self.positions.keys())
            closed_symbols = tracked_symbols - webull_symbols

            for symbol in closed_symbols:
                pos_info = self.positions[symbol]
                # Move to closed positions history
                self.closed_positions.append(pos_info)
                del self.positions[symbol]
                self._send_alert(f"Position closed: {symbol} (P&L: ${pos_info.unrealized_pnl + pos_info.realized_pnl:.2f})")

        except Exception as e:
            logger.error(f"Error updating positions from WebullExecution wrapper: {e}")

    def _contract_multiplier(self, symbol: str) -> int:
        """Get contract multiplier for symbol (100 for options, 1 for stocks)."""
        return 100 if self.webull._is_option_symbol(symbol) else 1

    def add_position(
        self,
        symbol: str,
        qty: int,
        side: str,
        entry_price: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        max_hold_time: Optional[timedelta] = None,
        tags: Optional[List[str]] = None
    ):
        """Add a new position to monitor.

        Args:
            symbol: Stock or option symbol
            qty: Quantity (positive integer)
            side: 'buy' or 'sell'
            entry_price: Entry price per share/contract
            stop_loss: Stop loss price (optional)
            take_profit: Take profit price (optional)
            max_hold_time: Maximum time to hold position (optional)
            tags: Custom tags for the position (optional)
        """
        if symbol in self.positions:
            logger.warning(f"Position {symbol} already exists, updating instead")
            # Update existing position
            pos_info = self.positions[symbol]
            pos_info.qty = qty
            pos_info.side = side
            pos_info.entry_price = entry_price
            pos_info.stop_loss = stop_loss
            pos_info.take_profit = take_profit
            pos_info.max_hold_time = max_hold_time
            pos_info.tags = tags or []
            pos_info.entry_time = datetime.now()
        else:
            # Add new position
            pos_info = PositionInfo(
                symbol=symbol,
                qty=qty,
                side=side,
                entry_price=entry_price,
                current_price=entry_price,  # Will be updated on first check
                unrealized_pnl=0.0,
                realized_pnl=0.0,
                entry_time=datetime.now(),
                stop_loss=stop_loss,
                take_profit=take_profit,
                max_hold_time=max_hold_time,
                tags=tags or []
            )
            self.positions[symbol] = pos_info

        logger.info(f"Added position: {side} {qty} {symbol} @ ${entry_price:.2f}")
        self._send_alert(f"Position added: {side} {qty} {symbol} @ ${entry_price:.2f}")

    def check_exit_conditions(self) -> List[ExitSignal]:
        """Check all positions for exit conditions.

        Returns:
            List of exit signals to execute
        """
        exit_signals = []
        current_time = datetime.now()

        for symbol, pos_info in self.positions.items():
            # Skip if no current price
            if pos_info.current_price <= 0:
                continue

            exit_reason = None
            exit_price = pos_info.current_price

            # Check stop loss
            if pos_info.stop_loss is not None:
                if pos_info.side == "buy" and pos_info.current_price <= pos_info.stop_loss:
                    exit_reason = "stop_loss"
                elif pos_info.side == "sell" and pos_info.current_price >= pos_info.stop_loss:
                    exit_reason = "stop_loss"

            # Check take profit
            if not exit_reason and pos_info.take_profit is not None:
                if pos_info.side == "buy" and pos_info.current_price >= pos_info.take_profit:
                    exit_reason = "take_profit"
                elif pos_info.side == "sell" and pos_info.current_price <= pos_info.take_profit:
                    exit_reason = "take_profit"

            # Check time-based exit
            if not exit_reason and pos_info.max_hold_time is not None:
                time_held = current_time - pos_info.entry_time
                if time_held >= pos_info.max_hold_time:
                    exit_reason = "time_exit"

            # If exit condition met, create exit signal
            if exit_reason:
                exit_signal = ExitSignal(
                    position_symbol=symbol,
                    exit_reason=exit_reason,
                    exit_price=exit_price,
                    qty_to_exit=pos_info.qty,  # Exit full position by default
                    timestamp=current_time
                )
                exit_signals.append(exit_signal)
                logger.info(f"Exit signal generated: {exit_reason} for {symbol} @ ${exit_price:.2f}")

        return exit_signals

    def execute_exit_signal(self, exit_signal: ExitSignal) -> bool:
        """Execute an exit signal by submitting a closing order.

        Args:
            exit_signal: The exit signal to execute

        Returns:
            True if order was submitted successfully
        """
        if exit_signal.position_symbol not in self.positions:
            logger.error(f"Position {exit_signal.position_symbol} not found for exit")
            return False

        pos_info = self.positions[exit_signal.position_symbol]

        # Determine exit order side (opposite of position side)
        exit_side = "sell" if pos_info.side == "buy" else "buy"

        # Create closing order
        order_request = create_order_request(
            symbol=exit_signal.position_symbol,
            qty=exit_signal.qty_to_exit,
            side=exit_side,
            order_type="market"
        )

        # Submit the order
        success, error_msg, order = self.webull.submit_order(order_request)

        if success:
            logger.info(f"Exit order submitted: {exit_signal.exit_reason} {exit_signal.qty_to_exit} {exit_signal.position_symbol}")
            self._send_alert(
                f"Exit executed: {exit_signal.exit_reason} {exit_signal.qty_to_exit} {exit_signal.position_symbol} "
                f"@ ${exit_signal.exit_price:.2f} (Reason: {exit_signal.exit_reason})"
            )

            # Update position to reflect partial close if needed
            if exit_signal.qty_to_exit < pos_info.qty:
                # Partial exit - reduce position size
                pos_info.qty -= exit_signal.qty_to_exit
                # Note: In a real system, we'd need to adjust entry_price for partial closes
                # For simplicity, we're keeping it as is and noting this is a limitation
            else:
                # Full exit - remove position
                self.closed_positions.append(pos_info)
                del self.positions[exit_signal.position_symbol]

            return True
        else:
            logger.error(f"Failed to submit exit order: {error_msg}")
            self._send_alert(f"Exit failed: {exit_signal.position_symbol} - {error_msg}")
            return False

    def _monitor_loop(self):
        """Main monitoring loop."""
        logger.info("Execution monitor loop started")

        while self.running:
            try:
                # Update positions from Webull
                self.update_positions_from_webull()

                # Check for exit conditions
                exit_signals = self.check_exit_conditions()

                # Execute exit signals if enabled
                if self.enable_auto_exit and exit_signals:
                    for signal in exit_signals:
                        self.execute_exit_signal(signal)

                # Log status
                if self.positions:
                    total_unrealized = sum(pos.unrealized_pnl for pos in self.positions.values())
                    logger.debug(
                        f"Monitor status: {len(self.positions)} open positions, "
                        f"Unrealized P&L: ${total_unrealized:.2f}"
                    )

                # Sleep until next check
                time.sleep(self.check_interval)

            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                time.sleep(self.check_interval)  # Continue despite errors

    def start(self):
        """Start the execution monitor."""
        if self.running:
            logger.warning("Execution monitor is already running")
            return

        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("Execution monitor started")

    def stop(self):
        """Stop the execution monitor."""
        self.running = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5.0)
        logger.info("Execution monitor stopped")

    def get_position_summary(self) -> Dict:
        """Get a summary of all open positions.

        Returns:
            Dictionary with position summary information
        """
        total_unrealized_pnl = sum(pos.unrealized_pnl for pos in self.positions.values())
        total_realized_pnl = sum(pos.realized_pnl for pos in self.positions.values())

        positions_data = []
        for symbol, pos_info in self.positions.items():
            positions_data.append({
                'symbol': symbol,
                'side': pos_info.side,
                'qty': pos_info.qty,
                'entry_price': pos_info.entry_price,
                'current_price': pos_info.current_price,
                'unrealized_pnl': pos_info.unrealized_pnl,
                'realized_pnl': pos_info.realized_pnl,
                'total_pnl': pos_info.unrealized_pnl + pos_info.realized_pnl,
                'entry_time': pos_info.entry_time.isoformat(),
                'stop_loss': pos_info.stop_loss,
                'take_profit': pos_info.take_profit,
                'tags': pos_info.tags
            })

        return {
            'timestamp': datetime.now().isoformat(),
            'open_positions_count': len(self.positions),
            'total_unrealized_pnl': total_unrealized_pnl,
            'total_realized_pnl': total_realized_pnl,
            'total_pnl': total_unrealized_pnl + total_realized_pnl,
            'positions': positions_data
        }

    def get_closed_positions_summary(self) -> List[Dict]:
        """Get summary of recently closed positions.

        Returns:
            List of closed position dictionaries
        """
        closed_data = []
        for pos_info in self.closed_positions[-50:]:  # Last 50 closed positions
            closed_data.append({
                'symbol': pos_info.symbol,
                'side': pos_info.side,
                'qty': pos_info.qty,
                'entry_price': pos_info.entry_price,
                'exit_price': pos_info.current_price,  # Approximate
                'unrealized_pnl': pos_info.unrealized_pnl,
                'realized_pnl': pos_info.realized_pnl,
                'total_pnl': pos_info.unrealized_pnl + pos_info.realized_pnl,
                'entry_time': pos_info.entry_time.isoformat(),
                'tags': pos_info.tags
            })
        return closed_data


def create_execution_monitor(
    api_key: Optional[str] = None,
    secret_key: Optional[str] = None,
    paper: bool = True,
    check_interval: int = 30,
    max_daily_loss: float = 0.05,
    max_position_size: float = 0.10,
    max_daily_trades: int = 10
) -> ExecutionMonitor:
    """Factory function to create an ExecutionMonitor with Webull executor.

    Args:
        api_key: Webull API key (reads from env if not provided)
        secret_key: Webull secret key (reads from env if not provided)
        paper: Use paper trading (default True)
        check_interval: How often to check positions (seconds)
        max_daily_loss: Maximum daily loss percentage
        max_position_size: Maximum position size as % of portfolio
        max_daily_trades: Maximum trades per day

    Returns:
        Configured ExecutionMonitor instance
    """
    webull_executor = WebullExecution(
        api_key=api_key,
        secret_key=secret_key,
        paper=paper,
        max_daily_loss=max_daily_loss,
        max_position_size=max_position_size,
        max_daily_trades=max_daily_trades
    )

    return ExecutionMonitor(
        webull_executor=webull_executor,
        check_interval=check_interval,
        enable_auto_exit=True,
        enable_alerts=True
    )


# Example usage and testing
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    def simple_alert_callback(message: str):
        print(f"[ALERT] {message}")

    # Create execution monitor
    monitor = create_execution_monitor()
    monitor.add_alert_callback(simple_alert_callback)

    # Example: Add a position to monitor
    # monitor.add_position(
    #     symbol="AAPL261016C00190000",
    #     qty=1,
    #     side="buy",
    #     entry_price=5.50,
    #     stop_loss=4.50,
    #     take_profit=7.50,
    #     max_hold_time=timedelta(days=7),
    #     tags=["bull_call_spread", "phase8_test"]
    # )

    # Start monitoring
    # monitor.start()

    # Let it run for a bit, then stop
    # try:
    #     time.sleep(60)  # Run for 60 seconds
    # except KeyboardInterrupt:
    #     pass
    # finally:
    #     monitor.stop()

    print("ExecutionMonitor module loaded successfully")
    print("Use create_execution_monitor() to create an instance")
    print("Use monitor.start() to begin monitoring and monitor.stop() to end")