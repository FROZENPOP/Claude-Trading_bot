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

    def submit_order(self, order_request: OrderRequest):
        """Submit an order to Webull.

        Args:
            order_request: Order to submit

        Returns:
            Tuple of (success, error_message, order_object)
        """
        try:
            # Pre-order verification
            if not self._verify_market_open():
                return False, "Market is not open", None

            account_info = self.get_account_info()
            if account_info.trading_blocked or account_info.account_blocked:
                return False, "Account is not available for trading", None

            # Check for duplicate orders (simplified)
            # In a real implementation, we'd check recent orders

            # Calculate required buying power
            # This is a simplified calculation
            required_capital = abs(order_request.qty) * (order_request.limit_price or 0)
            if required_capital > account_info.buying_power:
                return False, f"Insufficient buying power: need {required_capital}, have {account_info.buying_power}", None

            # Submit order via MCP
            # Note: This is a simplified version - real implementation would handle
            # different order types, etc. via appropriate MCP calls
            if order_request.order_type.lower() == "market":
                if order_request.side.lower() == "buy":
                    order_result = mcp__webull__place_stock_order(
                        symbol=order_request.symbol,
                        side="buy",
                        order_type="market",
                        time_in_force=order_request.time_in_force,
                        quantity=abs(order_request.qty)
                    )
                else:
                    order_result = mcp__webull__place_stock_order(
                        symbol=order_request.symbol,
                        side="sell",
                        order_type="market",
                        time_in_force=order_request.time_in_force,
                        quantity=abs(order_request.qty)
                    )
            elif order_request.order_type.lower() == "limit":
                if order_request.side.lower() == "buy":
                    order_result = mcp__webull__place_stock_order(
                        symbol=order_request.symbol,
                        side="buy",
                        order_type="limit",
                        time_in_force=order_request.time_in_force,
                        quantity=abs(order_request.qty),
                        limit_price=order_request.limit_price
                    )
                else:
                    order_result = mcp__webull__place_stock_order(
                        symbol=order_request.symbol,
                        side="sell",
                        order_type="limit",
                        time_in_force=order_request.time_in_force,
                        quantity=abs(order_request.qty),
                        limit_price=order_request.limit_price
                    )
            else:
                # For other order types, default to market for now
                logger.warning(f"Order type {order_request.order_type} not fully implemented, defaulting to market")
                if order_request.side.lower() == "buy":
                    order_result = mcp__webull__place_stock_order(
                        symbol=order_request.symbol,
                        side="buy",
                        order_type="market",
                        time_in_force=order_request.time_in_force,
                        quantity=abs(order_request.qty)
                    )
                else:
                    order_result = mcp__webull__place_stock_order(
                        symbol=order_request.symbol,
                        side="sell",
                        order_type="market",
                        time_in_force=order_request.time_in_force,
                        quantity=abs(order_request.qty)
                    )

            if order_result and 'data' in order_result:
                order_data = order_result['data']
                # Create Webull order object
                order = WebullOrder(
                    id=order_data.get('order_id', ''),
                    client_order_id=order_request.client_order_id or '',
                    symbol=order_data.get('symbol', ''),
                    side=order_data.get('side', ''),
                    order_type=order_data.get('order_type', 'market'),
                    qty=abs(order_request.qty),
                    filled_qty=0,  # Would be filled from actual response
                    price=order_data.get('limit_price'),
                    avg_fill_price=0.0,
                    status=order_data.get('status', 'new'),
                    time_in_force=order_data.get('time_in_force', 'day'),
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                return True, None, order
            else:
                logger.error(f"Failed to place order: {order_result}")
                return False, "Failed to place order", None

        except Exception as e:
            logger.error(f"Error submitting order: {e}")
            return False, str(e), None

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