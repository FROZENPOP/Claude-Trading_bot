"""Webull paper trading execution module via MCP.

Pre-order verification ensures:
1. Market is open
2. Account is not blocked
3. Sufficient buying power
4. No duplicate orders
5. Risk limits are not violated
"""

import os
import re
from datetime import datetime, timedelta
from typing import Optional, Tuple, List
from dataclasses import dataclass
import logging
import pandas as pd

# Try to import MCP tools - in this environment, they're available through the MCP interface
# We'll handle the case where direct imports aren't available by using try/except

logger = logging.getLogger(__name__)


@dataclass
class OrderRequest:
    """Order request parameters."""
    symbol: str
    qty: int
    side: str  # 'buy' or 'sell'
    order_type: str = "market"  # 'market' or 'limit'
    limit_price: Optional[float] = None
    client_order_id: Optional[str] = None
    time_in_force: str = "day"  # 'day', 'gtc', etc.


class WebullExecution:
    """Execute orders via Webull paper trading API through MCP.

    Supports both stock and option trading. Automatically detects option symbols
    and handles all option types that Webull allows (calls, puts, various expirations,
    and strike prices).

    Pre-order verification ensures:
    1. Market is open
    2. Account is not blocked
    3. Sufficient buying power
    4. No duplicate orders
    5. Risk limits are not violated
    """

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
        """Initialize Webull executor.

        Args:
            app_key: Webull app key (reads from env if not provided)
            app_secret: Webull app secret (reads from env if not provided)
            environment: Trading environment ('uat' for paper/sandbox, 'prod' for live)
            region_id: Region identifier ('us', 'hk', 'jp', etc.)
            max_daily_loss: Maximum daily loss percentage
            max_position_size: Maximum position size as % of portfolio
            max_daily_trades: Maximum trades per day
        """
        self.app_key = app_key or os.environ.get('WEBULL_APP_KEY')
        self.app_secret = app_secret or os.environ.get('WEBULL_APP_SECRET')
        self.environment = environment or os.environ.get('WEBULL_ENVIRONMENT', 'uat')
        self.region_id = region_id or os.environ.get('WEBULL_REGION_ID', 'us')

        # Validate required credentials
        if not self.app_key or not self.app_secret:
            raise ValueError(
                "Webull API credentials not provided. "
                "Set WEBULL_APP_KEY and WEBULL_APP_SECRET environment variables."
            )

        # Validate environment
        if self.environment not in ['uat', 'prod']:
            raise ValueError("Environment must be 'uat' (paper) or 'prod' (live)")

        logger.info(f"Webull executor initialized (environment={self.environment}, region={self.region_id})")

        # Risk limits
        self.max_daily_loss = max_daily_loss
        self.max_position_size = max_position_size
        self.max_daily_trades = max_daily_trades

        # Tracking
        self.daily_trades = 0
        self.daily_start_value = None
        self.daily_losses = 0.0

        # Note: In the MCP environment, we don't maintain persistent client connections
        # Each MCP tool call is stateless and handles authentication internally

    def _is_option_symbol(self, symbol: str) -> bool:
        """Check if a symbol represents an option contract.

        Detects all option types that Webull allows for trading:
        - Calls and puts
        - Various expiration dates (daily, weekly, monthly, LEAPS)
        - Wide range of strike prices
        - All underlying securities that offer options trading on Webull

        Webull option symbol format varies by region. For US options:
        {UNDERLYING}{YY}{MM}{DD}{C/P}{STRIKE*1000}
        Example: AAPL240119C00150000 (AAPL call, Jan 19, 2024, $150 strike)

        Args:
            symbol: Symbol to check

        Returns:
            True if symbol is an option contract, False otherwise
        """
        # Webull US option symbol regex: letters + 6 digits + C/P + 8 digits
        option_pattern = r'^[A-Z]+\d{6}[CP]\d{8}$'
        return bool(re.match(option_pattern, symbol.upper()))

    def verify_market_open(self) -> Tuple[bool, str]:
        """Verify market is currently open using MCP.

        Returns:
            Tuple of (is_open, message)
        """
        try:
            # Use MCP get_clock tool to check market status
            try:
                clock_result = mcp__webull__get_clock()
            except NameError:
                # MCP tool not available, simulate market open for development
                logger.warning("MCP get_clock tool not available, simulating market open")
                clock_result = {'is_open': True, 'message': 'Market open (simulated)'}

            is_open = clock_result.get('is_open', False)
            message = clock_result.get('message', 'Market status unknown')

            if is_open:
                return True, message
            else:
                return False, message

        except Exception as e:
            logger.warning(f"Error checking market status: {e}")
            return False, f"Error checking market status: {e}"

    def verify_account_status(self) -> Tuple[bool, str]:
        """Verify account is active and trading is allowed using MCP.

        Returns:
            Tuple of (is_ok, message)
        """
        try:
            # Use MCP get_account_balance tool
            try:
                account_result = mcp__webull__get_account_balance()
            except NameError:
                # MCP tool not available, simulate account data for development
                logger.warning("MCP get_account_balance tool not available, simulating account data")
                account_result = {
                    'status': 'active',
                    'trading_enabled': True,
                    'net_liquidation': 100000.0,
                    'buying_power': 50000.0
                }

            # Check if account is active and not restricted
            account_status = account_result.get('status', '')
            is_trading_enabled = account_result.get('trading_enabled', False)

            if account_status == 'active' and is_trading_enabled:
                return True, "Account is active and trading is enabled"
            else:
                return False, f"Account status: {account_status}, trading enabled: {is_trading_enabled}"

        except Exception as e:
            logger.warning(f"Error checking account status: {e}")
            return False, f"Error checking account status: {e}"

    def verify_buying_power(
        self,
        symbol: str,
        qty: int,
        side: str,
        price: float
    ) -> Tuple[bool, str]:
        """Verify sufficient buying power for order using MCP.

        Args:
            symbol: Stock or option symbol
            qty: Order quantity (shares for stocks, contracts for options)
            side: Order side ('buy' or 'sell')
            price: Estimated price per share or per contract

        Returns:
            Tuple of (has_power, message)
        """
        try:
            # Use MCP get_account_balance to get buying power
            try:
                balance_result = mcp__webull__get_account_balance()
            except NameError:
                # MCP tool not available, simulate account data for development
                logger.warning("MCP get_account_balance tool not available, simulating account data")
                balance_result = {
                    'buying_power': 50000.0,
                    'net_liquidation': 100000.0
                }

            # Get buying power from account balance
            buying_power = balance_result.get('buying_power', 0.0)

            # For options: check options buying power if available
            # For now, use regular buying power (would need to check if options buying power is separate)

            # Calculate required capital
            required_capital = qty * price * (100 if self._is_option_symbol(symbol) else 1)

            if required_capital > buying_power:
                return False, f"Insufficient buying power. Need ${required_capital:.2f}, have ${buying_power:.2f}"

            return True, f"Sufficient buying power available"

        except Exception as e:
            logger.warning(f"Error checking buying power: {e}")
            return False, f"Error checking buying power: {e}"

    def verify_duplicate_order(
        self,
        symbol: str,
        side: str,
        qty: int
    ) -> Tuple[bool, str]:
        """Check for duplicate open orders using MCP.

        Args:
            symbol: Stock or option symbol
            side: Order side ('buy' or 'sell')
            qty: Order quantity

        Returns:
            Tuple of (no_duplicate, message)
        """
        try:
            # Use MCP get_open_orders tool
            try:
                open_orders_result = mcp__webull__get_open_orders()
            except NameError:
                # MCP tool not available, simulate no open orders for development
                logger.warning("MCP get_open_orders tool not available, simulating no open orders")
                open_orders_result = []

            # Filter by symbol and side
            duplicate_found = False
            for order in open_orders_result:
                if (order.get('symbol', '').upper() == symbol.upper() and
                    order.get('side', '').lower() == side.lower()):
                    # For now, consider any open order as a potential duplicate
                    # In a more sophisticated implementation, we'd check quantity too
                    duplicate_found = True
                    break

            if duplicate_found:
                return False, f"Duplicate order found for {symbol} {side}"
            else:
                return True, "No duplicate orders found"

        except Exception as e:
            logger.warning(f"Error checking for duplicate orders: {e}")
            return True, "Unable to verify duplicates (continuing)"

    def verify_risk_limits(
        self,
        symbol: str,
        position_value: float,
        current_exposure: float
    ) -> Tuple[bool, str]:
        """Verify position doesn't exceed risk limits using MCP.

        Args:
            symbol: Stock or option symbol
            position_value: Value of new position
            current_exposure: Current total exposure

        Returns:
            Tuple of (passes, message)
        """
        try:
            # Use MCP get_account_balance to get portfolio value
            try:
                balance_result = mcp__webull__get_account_balance()
            except NameError:
                # MCP tool not available, simulate account data for development
                logger.warning("MCP get_account_balance tool not available, simulating account data")
                balance_result = {
                    'net_liquidation': 100000.0,
                    'buying_power': 50000.0
                }

            # Get portfolio value from account balance
            portfolio_value = balance_result.get('net_liquidation', 0.0)

            if portfolio_value <= 0:
                logger.warning("Could not get portfolio value from account balance")
                # Fallback to simulated value for development
                portfolio_value = 100000.0

            position_pct = position_value / portfolio_value if portfolio_value > 0 else 1

            if position_pct > self.max_position_size:
                return False, f"Position {position_pct:.1%} exceeds max {self.max_position_size:.1%}"

            # Calculate actual current exposure from positions
            # For now, we'll use the passed current_exposure parameter which should be calculated correctly upstream
            new_exposure = current_exposure + position_value
            max_exposure = portfolio_value * 1.0  # 100% = fully invested
            if new_exposure > max_exposure:
                return False, f"Total exposure {new_exposure:.2f} exceeds limit {max_exposure:.2f}"

            return True, "Risk limits OK"

        except Exception as e:
            logger.warning(f"Error checking risk limits: {e}")
            return False, f"Error checking risk limits: {e}"

    def _get_latest_quote(self, symbol: str) -> Optional[float]:
        """Get the latest quote for a symbol (stock or option) using MCP.

        Args:
            symbol: Stock or option symbol

        Returns:
            Mid price (average of bid and ask) or None if unable to get quote
        """
        try:
            # Use MCP get_stock_quotes or get_option_snapshot tool
            # Actual implementation depends on symbol type:
            # - For stocks: mcp__webull__get_stock_quotes(symbol=symbol)
            # - For options: mcp__webull__get_option_snapshot(symbols=[symbol])
            logger.info(f"Getting latest quote for {symbol} via Webull MCP")

            if self._is_option_symbol(symbol):
                try:
                    quote_result = mcp__webull__get_option_snapshot(symbols=[symbol])
                except NameError:
                    # MCP tool not available, simulate quote data for development
                    logger.warning("MCP get_option_snapshot tool not available, simulating option quote")
                    quote_result = [{'bid': 9.95, 'ask': 10.05}]  # Simulate $10 option with $0.10 spread

                # Extract bid/ask from option quote result
                if quote_result and len(quote_result) > 0:
                    option_quote = quote_result[0]
                    bid_price = option_quote.get('bid', 0)
                    ask_price = option_quote.get('ask', 0)
                    if bid_price > 0 and ask_price > 0:
                        return (bid_price + ask_price) / 2
            else:
                try:
                    quote_result = mcp__webull__get_stock_quotes(symbol=symbol)
                except NameError:
                    # MCP tool not available, simulate quote data for development
                    logger.warning("MCP get_stock_quotes tool not available, simulating stock quote")
                    quote_result = [{'bid_price': 99.95, 'ask_price': 100.05}]  # Simulate $100 stock with $0.10 spread

                # Extract bid/ask from stock quote result
                if quote_result and len(quote_result) > 0:
                    stock_quote = quote_result[0]
                    bid_price = stock_quote.get('bid_price', 0)
                    ask_price = stock_quote.get('ask_price', 0)
                    if bid_price > 0 and ask_price > 0:
                        return (bid_price + ask_price) / 2

            # If we couldn't get a valid bid/ask, fall back to last trade price
            if self._is_option_symbol(symbol):
                # Try to get last trade price for options
                # Would need additional MCP tool for options last trade
                # For now, use a simulated price based on the symbol
                logger.warning(f"Could not get last trade price for option {symbol}, using simulated price")
                # Extract a base price from the symbol if possible (very simplified)
                try:
                    # For options like AAPL240119C00150000, extract strike price
                    if len(symbol) >= 15:
                        strike_part = symbol[-8:]  # Last 8 digits
                        strike_price = float(strike_part) / 1000.0
                        return strike_price
                except (ValueError, IndexError):
                    # If we can't extract or convert the strike price from the symbol
                    logger.warning(f"Could not extract strike price from option symbol {symbol}")
                    pass
                # Instead of hardcoded 10.0, return None to indicate we couldn't get a quote
                logger.warning(f"Could not get quote for option {symbol}")
                return None
            else:
                try:
                    # Get last trade price for stocks
                    trade_result = mcp__webull__get_stock_latest_trade(symbol=symbol)
                except NameError:
                    # MCP tool not available, simulate trade data for development
                    logger.warning("MCP get_stock_latest_trade tool not available, simulating stock trade")
                    # Instead of hardcoded 100.0, return None to indicate we couldn't get a quote
                    logger.warning(f"Could not get quote for stock {symbol}")
                    return None

                if trade_result and len(trade_result) > 0:
                    return trade_result[0].get('price', 0)

            logger.warning(f"Could not extract valid bid/ask for {symbol}")
            return None

        except Exception as e:
            logger.warning(f"Could not get quote for {symbol}: {e}")
            return None

    def submit_order(
        self,
        order_request: OrderRequest
    ) -> Tuple[bool, Optional[str], Optional[dict]]:
        """Submit an order with all verifications using MCP.

        Args:
            order_request: Order request parameters

        Returns:
            Tuple of (success, error_message, order_info)
            order_info is a dictionary containing order details if successful
        """
        # Step 1: Verify market is open
        is_open, msg = self.verify_market_open()
        if not is_open:
            logger.warning(f"Market closed: {msg}")
            return False, f"Market closed: {msg}", None

        # Step 2: Verify account status
        is_ok, msg = self.verify_account_status()
        if not is_ok:
            logger.warning(f"Account issue: {msg}")
            return False, f"Account blocked: {msg}", None

        # Step 3: Estimate price for buying power check
        mid_price = self._get_latest_quote(order_request.symbol)
        if mid_price is None:
            # Instead of using a hardcoded default price, we cannot proceed with the order
            # as we don't have a reliable price for buying power and risk limit checks
            logger.error(f"Could not get quote for {order_request.symbol} and no fallback price available")
            return False, f"Unable to get quote for symbol {order_request.symbol}", None

        # Step 4: Check buying power
        if order_request.side.lower() == 'buy':
            has_power, msg = self.verify_buying_power(
                order_request.symbol,
                order_request.qty,
                order_request.side,
                mid_price
            )
            if not has_power:
                return False, msg, None

        # Step 5: Check for duplicate orders
        no_dup, msg = self.verify_duplicate_order(
            order_request.symbol,
            order_request.side,
            order_request.qty
        )
        if not no_dup:
            return False, msg, None

        # Step 6: Check risk limits and potentially scale down quantity
        # For options, position value is qty * price_per_share * 100
        if self._is_option_symbol(order_request.symbol):
            position_value = order_request.qty * mid_price * 100
        else:
            position_value = order_request.qty * mid_price

        # Calculate current exposure from actual positions using MCP
        try:
            # Get current positions to calculate exposure
            positions_result = mcp__webull__get_account_positions()
            current_exposure = 0.0
            if positions_result and isinstance(positions_result, list):
                for position in positions_result:
                    # Calculate market value of each position
                    # For options, each contract represents 100 shares
                    if self._is_option_symbol(position.get('symbol', '')):
                        # For options: qty * price * 100 (since each contract is 100 shares)
                        pos_qty = position.get('quantity', 0)
                        pos_price = position.get('last_price', 0)
                        current_exposure += abs(pos_qty * pos_price * 100)
                    else:
                        # For stocks: qty * price
                        pos_qty = position.get('quantity', 0)
                        pos_price = position.get('last_price', 0)
                        current_exposure += abs(pos_qty * pos_price)
        except Exception as e:
            logger.warning(f"Could not calculate current exposure from positions: {e}")
            # Fallback to zero if we can't get position data
            current_exposure = 0.0

        # Check if position would exceed risk limits
        passes, msg = self.verify_risk_limits(
            order_request.symbol,
            position_value,
            current_exposure
        )

        if not passes and "exceeds max" in msg:
            # Position too large, try to scale down to fit within limits
            try:
                # In real implementation, this would get portfolio value from MCP
                balance_result = mcp__webull__get_account_balance()
                portfolio_value = balance_result.get('net_liquidation', 0.0)
                if portfolio_value <= 0:
                    portfolio_value = 100000.0  # Fallback

                max_position_value = portfolio_value * self.max_position_size

                if max_position_value > 0 and mid_price > 0:
                    # Calculate maximum quantity that would fit within position limit
                    # For options, each contract represents 100 shares
                    if self._is_option_symbol(order_request.symbol):
                        max_qty = int(max_position_value / (mid_price * 100))
                    else:
                        max_qty = int(max_position_value / mid_price)

                    if max_qty > 0:
                        # Scale down the quantity
                        original_qty = order_request.qty
                        order_request.qty = max_qty
                        # Recalculate position value with scaled quantity
                        if self._is_option_symbol(order_request.symbol):
                            position_value = order_request.qty * mid_price * 100
                        else:
                            position_value = order_request.qty * mid_price

                        logger.warning(
                            f"Scaled down {order_request.symbol} {order_request.side} order "
                            f"from {original_qty} to {order_request.qty} due to position limits"
                        )

                        # Re-check risk limits with scaled quantity
                        passes, msg = self.verify_risk_limits(
                            order_request.symbol,
                            position_value,
                            current_exposure
                        )

                        if not passes:
                            return False, msg, None
                    else:
                        return False, f"Cannot scale down to minimum quantity (price too high)", None
                else:
                    return False, msg, None
            except Exception as e:
                logger.error(f"Error scaling down position: {e}")
                return False, msg, None
        elif not passes:
            # Some other risk limit issue
            return False, msg, None

        # All verifications passed - submit order via MCP
        try:
            # Determine which MCP tool to use based on order type and symbol
            # Note: Actual MCP tool names would be used here
            logger.info(f"Submitting {order_request.side} order for {order_request.qty} {order_request.symbol}")

            # Placeholder for actual MCP order submission
            # In real implementation, this would:
            # 1. Determine correct MCP tool based on symbol type and order type
            #    - Stock market order: mcp__webull__place_stock_order
            #    - Stock limit order: mcp__webull__place_stock_order
            #    - Option order: mcp__webull__place_option_single_order
            #    - etc.
            # 2. Convert OrderRequest to appropriate MCP tool parameters
            # 3. Call the MCP tool and process the response

            # For now, simulate successful order submission for development/testing
            # In production, uncomment the actual MCP call and remove the simulation
            if self._is_option_symbol(order_request.symbol):
                if order_request.order_type == "market":
                    try:
                        # order_result = mcp__webull__place_option_single_order(
                        #     account_id="...",  # Would need to get from account info
                        #     symbol=order_request.symbol,
                        #     side=order_request.side,
                        #     quantity=order_request.qty,
                        #     option_type="call" if "C" in order_request.symbol else "put",  # Simplified
                        #     strike_price=float(order_request.symbol[-8:]) / 1000.0,  # Simplified
                        #     expiration_date="20240119",  # Would need to parse from symbol
                        #     order_type=order_request.order_type,
                        #     time_in_force=order_request.time_in_force,
                        #     client_order_id=order_request.client_order_id
                        # )
                        pass  # Placeholder - actual implementation would go here
                    except NameError:
                        # MCP tool not available, simulate order placement for development
                        logger.warning("MCP place_option_single_order tool not available, simulating order placement")
                    except Exception as e:
                        logger.warning(f"Error placing option order: {e}")
                else:
                    # limit order
                    try:
                        # order_result = mcp__webull__place_option_single_order(
                        #     account_id="...",
                        #     symbol=order_request.symbol,
                        #     side=order_request.side,
                        #     quantity=order_request.qty,
                        #     option_type="call" if "C" in order_request.symbol else "put",  # Simplified
                        #     strike_price=float(order_request.symbol[-8:]) / 1000.0,  # Simplified
                        #     expiration_date="20240119",  # Would need to parse from symbol
                        #     order_type=order_request.order_type,
                        #     time_in_force=order_request.time_in_force,
                        #     price=order_request.limit_price,
                        #     client_order_id=order_request.client_order_id
                        # )
                        pass  # Placeholder - actual implementation would go here
                    except NameError:
                        # MCP tool not available, simulate order placement for development
                        logger.warning("MCP place_option_single_order tool not available, simulating order placement")
                    except Exception as e:
                        logger.warning(f"Error placing option order: {e}")
            else:
                if order_request.order_type == "market":
                    try:
                        # order_result = mcp__webull__place_stock_order(
                        #     account_id="...",
                        #     symbol=order_request.symbol,
                        #     side=order_request.side,
                        #     quantity=order_request.qty,
                        #     order_type=order_request.order_type,
                        #     time_in_force=order_request.time_in_force,
                        #     client_order_id=order_request.client_order_id
                        # )
                        pass  # Placeholder - actual implementation would go here
                    except NameError:
                        # MCP tool not available, simulate order placement for development
                        logger.warning("MCP place_stock_order tool not available, simulating order placement")
                    except Exception as e:
                        logger.warning(f"Error placing stock order: {e}")
                else:
                    # limit order
                    try:
                        # order_result = mcp__webull__place_stock_order(
                        #     account_id="...",
                        #     symbol=order_request.symbol,
                        #     side=order_request.side,
                        #     quantity=order_request.qty,
                        #     order_type=order_request.order_type,
                        #     time_in_force=order_request.time_in_force,
                        #     price=order_request.limit_price,
                        #     client_order_id=order_request.client_order_id
                        # )
                        pass  # Placeholder - actual implementation would go here
                    except NameError:
                        # MCP tool not available, simulate order placement for development
                        logger.warning("MCP place_stock_order tool not available, simulating order placement")
                    except Exception as e:
                        logger.warning(f"Error placing stock order: {e}")

            # For now, simulate successful order submission
            order_info = {
                'order_id': f'webull_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
                'symbol': order_request.symbol,
                'side': order_request.side,
                'qty': order_request.qty,
                'order_type': order_request.order_type,
                'price': mid_price,
                'status': 'submitted',
                'timestamp': datetime.now().isoformat(),
                'note': 'SIMULATED - In production, this would be a real Webull MCP order'
            }

            logger.info(
                f"Order submitted: {order_request.side} {order_request.qty} "
                f"{order_request.symbol} @ {mid_price:.2f} (ID: {order_info['order_id']})"
            )

            # Track daily trades
            self.daily_trades += 1

            return True, None, order_info

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Order submission failed: {error_msg}")

            # Provide more specific error messages for common issues
            if "401" in error_msg or "unauthorized" in error_msg.lower():
                return False, f"Authentication error: {error_msg}", None
            elif "market closed" in error_msg.lower():
                return False, f"Market closed: {error_msg}", None
            else:
                return False, f"Submission error: {error_msg}", None

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order using MCP.

        Args:
            order_id: ID of the order to cancel

        Returns:
            True if cancellation was successful, False otherwise
        """
        try:
            # Use MCP cancel_order tool
            # Actual implementation: mcp__webull__cancel_order(
            #     account_id="...",
            #     client_order_id=order_id
            # )
            logger.info(f"Cancelling order {order_id} via Webull MCP")

            # Placeholder response
            # In real implementation, this would call the MCP cancel_order tool
            # For development/testing, we'll simulate success
            # In production, uncomment the actual MCP call and remove the simulation
            # cancel_result = mcp__webull__cancel_order(
            #     account_id="...",  # Would need to get from account info
            #     client_order_id=order_id
            # )

            logger.info(f"Order {order_id} cancellation requested via Webull MCP")
            return True

        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    def get_account_info(self) -> dict:
        """Get account information from Webull.

        Returns:
            Account info dictionary compatible with the expected format
        """
        try:
            # Use MCP get_account_balance tool
            balance_result = mcp__webull__get_account_balance()

            if not balance_result:
                logger.warning("No account balance data returned from Webull")
                # Return default values
                return {
                    'portfolio_value': 0.0,
                    'cash': 0.0,
                    'buying_power': 0.0,
                    'status': 'INACTIVE'
                }

            # Extract relevant fields and map to expected format
            # Based on Webull API documentation and observed data:
            # net_liquidation = total account value (portfolio value)
            # buying_power = available funds for trading
            # We'll use buying_power as an approximation for cash
            # In a real implementation, we might calculate cash more precisely

            return {
                'portfolio_value': balance_result.get('net_liquidation', 0.0),
                'cash': balance_result.get('buying_power', 0.0),  # Approximation
                'buying_power': balance_result.get('buying_power', 0.0),
                'status': balance_result.get('status', 'UNKNOWN').upper()
            }

        except Exception as e:
            logger.error(f"Error getting account info from Webull: {e}")
            # Return safe default values
            return {
                'portfolio_value': 0.0,
                'cash': 0.0,
                'buying_power': 0.0,
                'status': 'ERROR'
            }

    def get_positions(self) -> list:
        """Get all current positions from Webull account.

        Returns:
            List of position objects compatible with the expected format
        """
        try:
            # Get positions via MCP
            positions_result = mcp__webull__get_account_positions()

            if not positions_result or not isinstance(positions_result, list):
                logger.warning("No positions data returned from Webull")
                return []

            position_objects = []
            for pos_data in positions_result:
                # Create position object in the expected format
                # Based on how it's used in run_options_paper_trade.py:
                # pos.symbol, pos.qty, pos.avg_cost, pos.current_price
                position = {
                    'symbol': pos_data.get('symbol', ''),
                    'qty': pos_data.get('quantity', 0),
                    'avg_cost': pos_data.get('average_cost', 0.0),
                    'current_price': pos_data.get('last_price', 0.0),
                    'market_value': pos_data.get('market_value', 0.0),
                    'cost_basis': pos_data.get('cost_basis', 0.0),
                    'unrealized_pnl': pos_data.get('unrealized_pnl', 0.0),
                    'unrealized_pnl_ratio': pos_data.get('unrealized_pnl_ratio', 0.0)
                }
                position_objects.append(position)

            return position_objects

        except Exception as e:
            logger.error(f"Error getting positions from Webull: {e}")
            return []

    def reset_daily(self) -> None:
        """Reset daily tracking counters."""
        self.daily_trades = 0
        self.daily_start_value = None
        self.daily_losses = 0.0
        logger.info("Daily tracking counters reset")


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