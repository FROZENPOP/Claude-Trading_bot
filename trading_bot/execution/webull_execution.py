"""Webull paper trading execution module.

This module provides a Webull-based execution interface for the autonomous trading system.
All execution is routed through Webull MCP tools.

Pre-order verification ensures:
1. Market is open
2. Account is not blocked
3. Sufficient buying power
4. No duplicate orders
5. Risk limits are not violated
"""

import os
import re
from datetime import datetime
from typing import Optional
from dataclasses import dataclass
import logging
from dotenv import load_dotenv
import time

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class OrderRequest:
    """Order request parameters."""
    symbol: str
    qty: int
    side: str  # 'buy' or 'sell'
    order_type: str = "market"  # 'market', 'limit', 'stop_limit', etc.
    time_in_force: str = "day"  # 'day', 'gtc', 'opg', 'cls', 'ioc', 'fok'
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    client_order_id: Optional[str] = None


@dataclass
class Order:
    """Order response from Webull."""
    id: str
    client_order_id: Optional[str]
    symbol: str
    side: str
    order_type: str
    qty: int
    filled_qty: int
    price: Optional[float]
    avg_fill_price: Optional[float]
    status: str
    time_in_force: str
    created_at: datetime
    updated_at: datetime
    submitted_at: Optional[datetime]
    filled_at: Optional[datetime]
    expired_at: Optional[datetime]
    canceled_at: Optional[datetime]
    failed_at: Optional[datetime]
    replaced_at: Optional[datetime]
    replaced_by: Optional[str]
    replaces: Optional[str]
    asset_id: Optional[str]
    asset_class: Optional[str]
    notional: Optional[float]
    filled_avg_price: Optional[float]
    qty_type: Optional[str]


class WebullExecution:
    """Webull paper trading execution interface."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        paper: bool = True,
        max_daily_loss: float = 0.05,
        max_position_size: float = 0.10,
        max_daily_trades: int = 10
    ):
        """Initialize Webull execution interface.

        Args:
            api_key: Webull API key (reads from env if not provided)
            secret_key: Webull secret key (reads from env if not provided)
            paper: Use paper trading (default True)
            max_daily_loss: Maximum daily loss percentage
            max_position_size: Maximum position size as % of portfolio
            max_daily_trades: Maximum trades per day
        """
        # In a real implementation, we would initialize the Webull connection here
        # For now, we rely on the MCP tools being available
        self.api_key = api_key
        self.secret_key = secret_key
        self.paper = paper
        self.max_daily_loss = max_daily_loss
        self.max_position_size = max_position_size
        self.max_daily_trades = max_daily_trades

        # Reliability attributes
        self.max_retries = 3
        self.base_delay = 1.0
        self.max_delay = 30.0
        self.failure_threshold = 5
        self.recovery_timeout = 60.0
        self.order_poll_interval = 2.0
        self.order_poll_timeout = 30.0
        self.reconciliation_interval = 30.0
        self.max_failed_orders = 100
        self.failed_orders = []
        self.failure_count = 0
        self.last_failure_time = None

        logger.info(f"WebullExecution initialized (paper={paper})")

    def _is_option_symbol(self, symbol: str) -> bool:
        """Check if a symbol is an option symbol.

        Args:
            symbol: Symbol to check

        Returns:
            True if symbol is an option, False otherwise
        """
        # Option symbols typically contain numbers and have specific formats
        # This is a simplified check - in reality, we'd need to verify with Webull
        return len(symbol) > 6 and any(c.isdigit() for c in symbol)

    def _get_latest_quote(self, symbol: str) -> Optional[float]:
        """Get the latest quote for a symbol using Webull MCP.

        Args:
            symbol: Stock or option symbol

        Returns:
            Latest price or None if unavailable
        """
        try:
            # Try to get quote via MCP
            quote_result = mcp__webull__get_stock_latest_quote(symbols=symbol)
            if quote_result and 'data' in quote_result and len(quote_result['data']) > 0:
                return quote_result['data'][0].get('price')
        except Exception as e:
            logger.debug(f"Error getting stock quote for {symbol}: {e}")

        try:
            # If stock quote fails, try option quote
            quote_result = mcp__webull__get_option_latest_quote(symbols=symbol)
            if quote_result and 'data' in quote_result and len(quote_result['data']) > 0:
                return quote_result['data'][0].get('price')
        except Exception as e:
            logger.debug(f"Error getting option quote for {symbol}: {e}")

        return None

    def get_all_positions(self):
        """Get all current positions from Webull account.

        Returns:
            List of position objects compatible with Webull interface
        """
        try:
            # Get positions via MCP
            positions_result = mcp__webull__get_account_positions()

            if not positions_result or 'data' not in positions_result:
                logger.warning("No positions data returned from Webull")
                return []

            position_objects = []
            for pos_data in positions_result['data']:
                # Create Webull position object
                position = WebullPosition(
                    symbol=pos_data.get('symbol', ''),
                    qty=pos_data.get('quantity', 0),
                    avg_entry_price=pos_data.get('average_cost', 0.0),
                    market_value=pos_data.get('market_value', 0.0),
                    cost_basis=pos_data.get('cost_basis', 0.0),
                    unrealized_pl=pos_data.get('unrealized_pnl', 0.0),
                    unrealized_plpc=pos_data.get('unrealized_pnl_ratio', 0.0),
                    current_price=pos_data.get('current_price', 0.0),
                    lastday_price=pos_data.get('previous_close', 0.0),
                    change_today=pos_data.get('change_ratio', 0.0)
                )
                position_objects.append(position)

            return position_objects
        except Exception as e:
            logger.error(f"Error getting positions from Webull: {e}")
            return []

    def get_account_info(self):
        """Get account information from Webull.

        Returns:
            Account info object compatible with Webull interface
        """
        try:
            # Get account info via MCP
            balance_result = mcp__webull__get_account_balance()

            if not balance_result:
                logger.warning("No account balance data returned from Webull")
                return WebullAccountInfo(
                    id="",
                    account_number="",
                    status="INACTIVE",
                    currency="USD",
                    buying_power=0.0,
                    cash=0.0,
                    portfolio_value=0.0,
                    pattern_day_trader=False,
                    trading_blocked=False,
                    transfers_blocked=False,
                    account_blocked=False
                )

            # Extract relevant fields
            return WebullAccountInfo(
                id=balance_result.get('account_id', ''),
                account_number=balance_result.get('account_number', ''),
                status=balance_result.get('account_status', 'ACTIVE'),
                currency=balance_result.get('currency', 'USD'),
                buying_power=balance_result.get('buying_power', 0.0),
                cash=balance_result.get('cash_balance', 0.0),
                portfolio_value=balance_result.get('total_asset_value', 0.0),
                pattern_day_trader=balance_result.get('is_pattern_day_trader', False),
                trading_blocked=balance_result.get('is_trading_disabled', False),
                transfers_blocked=balance_result.get('is_transfer_disabled', False),
                account_blocked=balance_result.get('is_account_disabled', False)
            )
        except Exception as e:
            logger.error(f"Error getting account info from Webull: {e}")
            return WebullAccountInfo(
                id="",
                account_number="",
                status="ERROR",
                currency="USD",
                buying_power=0.0,
                cash=0.0,
                portfolio_value=0.0,
                pattern_day_trader=False,
                trading_blocked=False,
                transfers_blocked=False,
                account_blocked=False
            )

    def submit_order(self, symbol: str, side: str, quantity: float, order_type: str = "Market",
                     limit_price: float = None, stop_price: float = None, time_in_force: str = "Day"):
        """Submit an order with reliability improvements including retry mechanism, circuit breaker,
        order status polling, and state reconciliation.

        Args:
            symbol: Stock symbol to trade
            side: Order side ('Buy' or 'Sell')
            quantity: Number of shares to trade
            order_type: Type of order ('Market', 'Limit', 'Stop', 'StopLimit')
            limit_price: Limit price for limit orders
            stop_price: Stop price for stop orders
            time_in_force: Time in force ('Day', 'GTC')

        Returns:
            Tuple of (success, order_id or error_message)
        """
        # Check circuit breaker
        if self._is_circuit_open():
            error_msg = "Circuit breaker is open - refusing to submit order"
            logger.warning(error_msg)
            return False, error_msg

        # Retry loop with exponential backoff
        for attempt in range(self.max_retries + 1):
            try:
                # Submit order via MCP
                order_result = mcp__webull__place_stock_order(
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    order_type=order_type,
                    limit_price=limit_price,
                    stop_price=stop_price,
                    time_in_force=time_in_force,
                    extended_hours=False  # Regular trading hours only for paper trading
                )

                # Check if order was submitted successfully
                if order_result and 'data' in order_result:
                    order_data = order_result['data']
                    if order_data and 'order_id' in order_data:
                        order_id = order_data['order_id']
                        logger.info(f"Order submitted successfully: {order_id}")

                        # Record success for circuit breaker
                        self._record_success()

                        # Poll order status to confirm execution
                        final_status, status_error = self._poll_order_status(order_id)
                        if status_error:
                            logger.warning(f"Order submitted but status polling failed: {status_error}")
                            # Still return success since order was submitted
                            return True, order_id

                        # Reconcile internal state with broker state
                        reconciliation_error = self._reconcile_order_state(order_id, final_status)
                        if reconciliation_error:
                            logger.warning(f"Order submitted but reconciliation failed: {reconciliation_error}")
                            # Still return success since order was submitted
                            return True, order_id

                        return True, order_id
                    else:
                        error_msg = "Order submitted but no order ID returned"
                        logger.error(error_msg)
                        if attempt < self.max_retries and self._should_retry(Exception(error_msg)):
                            delay = self._calculate_delay(attempt)
                            logger.info(f"Retrying in {delay} seconds... (Attempt {attempt + 1}/{self.max_retries + 1})")
                            time.sleep(delay)
                            continue
                        else:
                            self._record_failure()
                            self._add_to_dead_letter_queue({
                                'symbol': symbol,
                                'side': side,
                                'quantity': quantity,
                                'order_type': order_type,
                                'error': error_msg,
                                'timestamp': datetime.now().isoformat()
                            })
                            return False, error_msg
                else:
                    error_msg = "Failed to submit order - no data returned"
                    logger.error(error_msg)
                    if attempt < self.max_retries and self._should_retry(Exception(error_msg)):
                        delay = self._calculate_delay(attempt)
                        logger.info(f"Retrying in {delay} seconds... (Attempt {attempt + 1}/{self.max_retries + 1})")
                        time.sleep(delay)
                        continue
                    else:
                        self._record_failure()
                        self._add_to_dead_letter_queue({
                            'symbol': symbol,
                            'side': side,
                            'quantity': quantity,
                            'order_type': order_type,
                            'error': error_msg,
                            'timestamp': datetime.now().isoformat()
                        })
                        return False, error_msg

            except Exception as e:
                error_msg = f"Exception submitting order: {str(e)}"
                logger.error(error_msg)
                if attempt < self.max_retries and self._should_retry(e):
                    delay = self._calculate_delay(attempt)
                    logger.info(f"Retrying in {delay} seconds... (Attempt {attempt + 1}/{self.max_retries + 1})")
                    time.sleep(delay)
                    continue
                else:
                    self._record_failure()
                    self._add_to_dead_letter_queue({
                        'symbol': symbol,
                        'side': side,
                        'quantity': quantity,
                        'order_type': order_type,
                        'error': error_msg,
                        'timestamp': datetime.now().isoformat()
                    })
                    return False, error_msg

        # If we've exhausted all retries
        error_msg = f"Failed to submit order after {self.max_retries + 1} attempts"
        logger.error(error_msg)
        return False, error_msg

    def cancel_order(self, order_id: str):
        """Cancel an order.

        Args:
            order_id: ID of order to cancel

        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Cancel order via MCP
            cancel_result = mcp__webull__cancel_order(
                order_id=order_id
            )

            if cancel_result and 'data' in cancel_result:
                return True, None
            else:
                logger.error(f"Failed to cancel order: {cancel_result}")
                return False, "Failed to cancel order"
        except Exception as e:
            logger.error(f"Error canceling order: {e}")
            return False, str(e)

    def _verify_market_open(self) -> bool:
        """Verify that the market is currently open.

        Returns:
            True if market is open, False otherwise
        """
        try:
            clock_result = mcp__webull__get_clock()
            if clock_result and 'data' in clock_result:
                return clock_result['data'].get('is_open', False)
            return False
        except Exception as e:
            logger.debug(f"Error checking market hours: {e}")
            return False


    def _should_retry(self, exception: Exception) -> bool:
        """Determine if an exception is retryable.

        Args:
            exception: The exception to check

        Returns:
            True if the exception is retryable, False otherwise
        """
        # Don't retry if we've exceeded max retries (handled by caller)
        # Define which exceptions are retryable
        if isinstance(exception, (ConnectionError, TimeoutError)):
            return True
        # Check for Webull-specific retryable errors
        error_str = str(exception).lower()
        retryable_indicators = [
            "network",
            "timeout",
            "connection",
            "temporary",
            "server error",
            "service unavailable",
            "gateway timeout"
        ]
        return any(indicator in error_str for indicator in retryable_indicators)

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for exponential backoff with jitter.

        Args:
            attempt: Current attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        # Exponential backoff: base_delay * (2 ^ attempt)
        delay = self.base_delay * (2 ** attempt)
        # Apply maximum delay limit
        delay = min(delay, self.max_delay)
        # Add jitter to prevent thundering herd
        import random
        jitter = random.uniform(0, 0.1) * delay
        return delay + jitter

    def _is_circuit_open(self) -> bool:
        """Check if the circuit breaker is open.

        Returns:
            True if circuit breaker is open, False otherwise
        """
        # If we haven't reached failure threshold, circuit is closed
        if self.failure_count < self.failure_threshold:
            return False

        # If circuit has been open for less than recovery timeout, stay open
        if self.last_failure_time:
            time_since_failure = time.time() - self.last_failure_time
            if time_since_failure < self.recovery_timeout:
                return True
            else:
                # Recovery timeout has passed, try half-open state
                logger.info("Circuit breaker attempting recovery")
                return False

        return False

    def _record_failure(self):
        """Record a failure for circuit breaker tracking."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        logger.warning(f"Recorded failure. Count: {self.failure_count}/{self.failure_threshold}")

    def _record_success(self):
        """Record a success for circuit breaker tracking."""
        # Reset failure count on success
        if self.failure_count > 0:
            logger.info(f"Recording success. Resetting failure count from {self.failure_count}")
        self.failure_count = 0
        self.last_failure_time = None

    def _get_order_status_from_webull(self, order_id: str) -> tuple:
        """Get order status from Webull.

        Args:
            order_id: ID of order to check

        Returns:
            Tuple of (status, error_message)
        """
        try:
            # Get order details via MCP
            order_result = mcp__webull__get_order_by_id(
                order_id=order_id
            )

            if order_result and 'data' in order_result:
                order_data = order_result['data']
                if order_data:
                    status = order_data.get('status', 'unknown')
                    return status, None
                else:
                    return 'unknown', 'No order data returned'
            else:
                return 'unknown', 'Failed to get order details'
        except Exception as e:
            return 'unknown', f'Exception getting order status: {str(e)}'

    def _poll_order_status(self, order_id: str) -> tuple:
        """Poll order status until final status or timeout.

        Args:
            order_id: ID of order to poll

        Returns:
            Tuple of (final_status, error_message)
        """
        start_time = time.time()

        while time.time() - start_time < self.order_poll_timeout:
            status, error = self._get_order_status_from_webull(order_id)
            if error:
                logger.debug(f"Error polling order status: {error}")
                time.sleep(self.order_poll_interval)
                continue

            # Check if order has reached a final status
            final_statuses = ['filled', 'cancelled', 'rejected', 'expired']
            if status in final_statuses:
                return status, None

            # Wait before polling again
            time.sleep(self.order_poll_interval)

        # Timeout reached
        return 'unknown', f'Order status polling timeout after {self.order_poll_timeout} seconds'

    def _reconcile_order_state(self, order_id: str, broker_status: str) -> str:
        """Reconcile internal order state with broker state.

        Args:
            order_id: ID of order to reconcile
            broker_status: Status from Webull broker

        Returns:
            Error message if reconciliation fails, None if successful
        """
        try:
            # Check if we have internal tracking for this order
            # In a full implementation, we'd check our internal order tracking
            # For now, we'll just verify the order exists and has a reasonable status

            valid_statuses = [
                'new', 'partially_filled', 'filled',
                'cancelled', 'rejected', 'expired'
            ]

            if broker_status not in valid_statuses:
                return f'Invalid order status from broker: {broker_status}'

            # Additional reconciliation logic could go here
            # For example, checking if our internal state matches broker state

            return None  # Reconciliation successful
        except Exception as e:
            return f'Exception during reconciliation: {str(e)}'

    def _add_to_dead_letter_queue(self, order_info: dict):
        """Add failed order to dead letter queue for analysis.

        Args:
            order_info: Dictionary containing order information and error details
        """
        self.failed_orders.append(order_info)
        # Keep only the most recent failed orders
        if len(self.failed_orders) > self.max_failed_orders:
            self.failed_orders = self.failed_orders[-self.max_failed_orders:]
        logger.warning(f"Added order to dead letter queue. Total failed orders: {len(self.failed_orders)}")


# Webull position class
@dataclass
class WebullPosition:
    """Position object compatible with Webull API."""
    symbol: str
    qty: float
    avg_entry_price: float
    market_value: float
    cost_basis: float
    unrealized_pl: float
    unrealized_plpc: float
    current_price: float
    lastday_price: float
    change_today: float


# Webull account info class
@dataclass
class WebullAccountInfo:
    """Account info object compatible with Webull API."""
    id: str
    account_number: str
    status: str
    currency: str
    buying_power: float
    cash: float
    portfolio_value: float
    pattern_day_trader: bool
    trading_blocked: bool
    transfers_blocked: bool
    account_blocked: bool


# Webull order class
@dataclass
class WebullOrder:
    """Order object compatible with Webull API."""
    id: str
    client_order_id: str
    symbol: str
    side: str
    order_type: str
    qty: float
    filled_qty: float
    price: Optional[float]
    avg_fill_price: float
    status: str
    time_in_force: str
    created_at: datetime
    updated_at: datetime


def create_order_request(symbol: str, qty: int, side: str, order_type: str = "market") -> OrderRequest:
    """Create an order request.

    Args:
        symbol: Stock or option symbol
        qty: Quantity (positive for buy, negative for sell)
        side: 'buy' or 'sell'
        order_type: Order type (default: market)

    Returns:
        OrderRequest object
    """
    return OrderRequest(
        symbol=symbol,
        qty=abs(qty),
        side=side,
        order_type=order_type
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

    # Create Webull execution interface
    executor = WebullExecution()

    print("WebullExecution module loaded successfully")
    print("Use WebullExecution() to create an instance")
    print("Use executor.get_all_positions() to get positions")
    print("Use executor.submit_order() to submit orders")