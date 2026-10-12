"""Phase 11: Advanced Order Types for Autonomous Options Trading System.

This module implements advanced order types including:
- Iceberg orders (hidden quantity)
- Pegged orders (to market benchmarks)
- Time-weighted orders
- Market-on-close and limit-on-close
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import math

# Add project root to path for imports
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
if project_root not in sys.path:
    sys.path.append(project_root)

logger = logging.getLogger(__name__)


class PegType(Enum):
    """Types of pegged orders."""
    MIDPEG = "midpeg"        # Peg to midpoint of NBBO
    BIDPEG = "bidpeg"        # Peg to bid price
    ASKPEG = "askpeg"        # Peg to ask price
    MARKETPEG = "marketpeg"  # Peg to market price (bid for buys, ask for sells)
    PRIMARYPEG = "primarypeg" # Peg to primary market


class OrderInstruction(Enum):
    """Special order instructions."""
    HIDDEN = "hidden"        # Iceberg order - hide quantity
    RESERVE = "reserve"      # Reserve order (iceberg variant)
    DISCLOSE = "disclose"    # Disclose only portion of quantity
    PEG = "peg"              # Pegged order
    ALL_OR_NONE = "aon"      # All or none
    MINIMUM_QUANTITY = "mq"  # Minimum quantity
    CANCEL_ON_BREAK = "cob"  # Cancel if peg breaks


class AdvancedOrderType(Enum):
    """Types of advanced order strategies."""
    ICEBERG = "iceberg"      # Iceberg order - hide true order size
    PEGGED = "pegged"        # Pegged order - track reference price
    TWAP = "twap"            # Time-weighted average price
    VWAP = "vwap"            # Volume-weighted average price
    TOC = "toc"              # Time-ordered close
    LOC = "loc"              # Limit-on-close
    MOC = "moc"              # Market-on-close


@dataclass
class AdvancedOrderParameters:
    """Parameters for advanced order types."""
    # Iceberg parameters
    display_quantity: Optional[int] = None      # Quantity to display (for iceberg)
    reserve_quantity: Optional[int] = None      # Reserve quantity to replenish display

    # Pegged order parameters
    peg_type: Optional[PegType] = None          # Type of peg
    peg_offset: float = 0.0                     # Offset from peg (positive or negative)
    peg_limit_price: Optional[float] = None     # Limit price for pegged order

    # Time-based parameters
    start_time: Optional[datetime] = None       # Start time for order
    end_time: Optional[datetime] = None         # End time for order (GTD)
    activate_time: Optional[datetime] = None    # Time to activate order
    expire_time: Optional[datetime] = None      # Time to expire order

    # Special instructions
    instructions: List[OrderInstruction] = field(default_factory=list)

    # Volume-based parameters
    max_participation_rate: Optional[float] = None  # Max % of volume to participate
    min_execution_size: Optional[int] = None        # Minimum execution size


@dataclass
class IcebergOrder:
    """Iceberg order with hidden quantity."""
    symbol: str
    total_quantity: int
    side: str  # 'buy' or 'sell'
    display_quantity: int  # What's visible in the market
    price: float           # Limit price
    side_of_market: str    # Same as side for iceberg

    def __post_init__(self):
        if self.display_quantity > self.total_quantity:
            self.display_quantity = self.total_quantity


@dataclass
class PeggedOrder:
    """Pegged order that tracks a market benchmark."""
    symbol: str
    quantity: int
    side: str  # 'buy' or 'sell'
    peg_type: PegType
    offset: float = 0.0          # Offset from peg (ticks or price)
    limit_price: Optional[float] = None  # Optional limit price

    def get_peg_price(self, market_bid: float, market_ask: float) -> float:
        """Calculate the peg price based on market conditions.

        Args:
            market_bid: Current bid price
            market_ask: Current ask price

        Returns:
            Peg price based on peg type and offset
        """
        if self.peg_type == PegType.MIDPEG:
            base_price = (market_bid + market_ask) / 2
        elif self.peg_type == PegType.BIDPEG:
            base_price = market_bid
        elif self.peg_type == PegType.ASKPEG:
            base_price = market_ask
        elif self.peg_type == PegType.MARKETPEG:
            # Buy orders peg to ask, sell orders peg to bid
            base_price = market_ask if self.side.lower() == 'buy' else market_bid
        elif self.peg_type == PegType.PRIMARYPEG:
            # Simplified - would use primary market data in reality
            base_price = (market_bid + market_ask) / 2
        else:
            base_price = (market_bid + market_ask) / 2  # Default to midpoint

        # Apply offset
        return base_price + self.offset


@dataclass
class AdvancedOrderResult:
    """Result of an advanced order submission."""
    symbol: str
    order_type: str
    quantity: int
    side: str
    price: Optional[float]
    status: str  # 'submitted', 'accepted', 'rejected', 'cancelled', 'filled'
    order_id: Optional[str] = None
    displayed_quantity: Optional[int] = None  # For iceberg orders
    peg_info: Optional[Dict] = None          # For pegged orders
    timestamp: datetime = field(default_factory=datetime.now)
    error_message: Optional[str] = None
    fills: List[Dict] = field(default_factory=list)  # Partial/full fills


class AdvancedOrderManager:
    """Manages advanced order types and their execution."""

    def __init__(self):
        self.active_orders: Dict[str, AdvancedOrderResult] = {}
        self.order_history: List[AdvancedOrderResult] = []
        self.iceberg_orders: Dict[str, IcebergOrder] = {}
        self.pegged_orders: Dict[str, PeggedOrder] = {}

    def create_iceberg_order(
        self,
        symbol: str,
        total_quantity: int,
        side: str,
        price: float,
        display_quantity: int
    ) -> IcebergOrder:
        """Create an iceberg order.

        Args:
            symbol: Stock or option symbol
            total_quantity: Total quantity to buy/sell
            side: 'buy' or 'sell'
            price: Limit price
            display_quantity: Quantity to display in market

        Returns:
            IcebergOrder object
        """
        iceberg = IcebergOrder(
            symbol=symbol,
            total_quantity=total_quantity,
            side=side,
            display_quantity=min(display_quantity, total_quantity),
            price=price,
            side_of_market=side
        )

        # Store for tracking
        order_key = f"{symbol}_{side}_{price}_{datetime.now().timestamp()}"
        self.iceberg_orders[order_key] = iceberg

        logger.info(f"Created iceberg order: {side} {display_quantity}/{total_quantity} {symbol} @ ${price:.2f}")
        return iceberg

    def create_pegged_order(
        self,
        symbol: str,
        quantity: int,
        side: str,
        peg_type: PegType,
        offset: float = 0.0,
        limit_price: Optional[float] = None
    ) -> PeggedOrder:
        """Create a pegged order.

        Args:
            symbol: Stock or option symbol
            quantity: Quantity to buy/sell
            side: 'buy' or 'sell'
            peg_type: Type of peg to use
            offset: Offset from peg (can be negative)
            limit_price: Optional limit price

        Returns:
            PeggedOrder object
        """
        pegged = PeggedOrder(
            symbol=symbol,
            quantity=quantity,
            side=side,
            peg_type=peg_type,
            offset=offset,
            limit_price=limit_price
        )

        # Store for tracking
        order_key = f"{symbol}_{side}_{peg_type.value}_{datetime.now().timestamp()}"
        self.pegged_orders[order_key] = pegged

        logger.info(f"Created pegged order: {side} {quantity} {symbol} pegged to {peg_type.value} + {offset}")
        return pegged

    def submit_iceberg_order(
        self,
        iceberg: IcebergOrder,
        get_market_data_callback=None,
        submit_order_callback=None
    ) -> AdvancedOrderResult:
        """Submit an iceberg order to the market.

        Args:
            iceberg: IcebergOrder to submit
            get_market_data_callback: Function to get market data
            submit_order_callback: Function to submit actual orders

        Returns:
            AdvancedOrderResult with submission details
        """
        result = AdvancedOrderResult(
            symbol=iceberg.symbol,
            order_type="iceberg",
            quantity=iceberg.total_quantity,
            side=iceberg.side,
            price=iceberg.price,
            status="submitted",
            displayed_quantity=iceberg.display_quantity
        )

        try:
            # Submit the visible portion
            if submit_order_callback:
                # In reality, we'd use a proper order creation function
                success, error_msg, order = submit_order_callback(
                    symbol=iceberg.symbol,
                    quantity=iceberg.display_quantity,
                    side=iceberg.side,
                    order_type="limit",
                    price=iceberg.price
                )

                if success and order:
                    result.order_id = getattr(order, 'id', None)
                    result.status = "accepted"
                    logger.info(f"Submitted iceberg order visible portion: {iceberg.display_quantity} {iceberg.side} {iceberg.symbol}")
                else:
                    result.status = "rejected"
                    result.error_message = error_msg or "Unknown error"
                    logger.error(f"Failed to submit iceberg order: {result.error_message}")
            else:
                # Simulate submission
                result.order_id = f"iceberg_{iceberg.symbol}_{datetime.now().timestamp()}"
                result.status = "accepted"
                logger.info(f"Simulated iceberg order submission: {iceberg.display_quantity} {iceberg.side} {iceberg.symbol}")

            # Store in active orders
            if result.order_id:
                self.active_orders[result.order_id] = result

        except Exception as e:
            logger.error(f"Error submitting iceberg order: {e}")
            result.status = "rejected"
            result.error_message = str(e)

        # Add to history
        self.order_history.append(result)

        # Keep history reasonable
        if len(self.order_history) > 1000:
            self.order_history = self.order_history[-1000:]

        return result

    def submit_pegged_order(
        self,
        pegged: PeggedOrder,
        get_market_data_callback=None,
        submit_order_callback=None
    ) -> AdvancedOrderResult:
        """Submit a pegged order to the market.

        Args:
            pegged: PeggedOrder to submit
            get_market_data_callback: Function to get market data (bid/ask)
            submit_order_callback: Function to submit actual orders

        Returns:
            AdvancedOrderResult with submission details
        """
        result = AdvancedOrderResult(
            symbol=pegged.symbol,
            order_type="pegged",
            quantity=pegged.quantity,
            side=pegged.side,
            price=None,  # Price will be determined by peg
            status="submitted",
            peg_info={
                'peg_type': pegged.peg_type.value,
                'offset': pegged.offset,
                'limit_price': pegged.limit_price
            }
        )

        try:
            # Get current market data to calculate peg price
            market_bid = 0.0
            market_ask = 0.0

            if get_market_data_callback:
                try:
                    market_data = get_market_data_callback(pegged.symbol)
                    # Assuming market_data has bid/ask
                    market_bid = market_data.get('bid', 0.0)
                    market_ask = market_data.get('ask', 0.0)
                except Exception as e:
                    logger.warning(f"Could not get market data for peg calculation: {e}")

            # Calculate peg price
            if market_bid > 0 and market_ask > 0:
                peg_price = pegged.get_peg_price(market_bid, market_ask)

                # Apply limit price if set
                if pegged.limit_price is not None:
                    if pegged.side.lower() == 'buy':
                        # For buys, don't exceed limit price
                        final_price = min(peg_price, pegged.limit_price)
                    else:  # sell
                        # For sells, don't go below limit price
                        final_price = max(peg_price, pegged.limit_price)
                else:
                    final_price = peg_price

                result.price = final_price
            else:
                # Fallback if no market data
                result.price = pegged.limit_price or 0.0
                logger.warning("Using limit price as fallback for pegged order (no market data)")

            # Submit the order
            if submit_order_callback and result.price > 0:
                success, error_msg, order = submit_order_callback(
                    symbol=pegged.symbol,
                    quantity=pegged.quantity,
                    side=pegged.side,
                    order_type="limit",
                    price=result.price
                )

                if success and order:
                    result.order_id = getattr(order, 'id', None)
                    result.status = "accepted"
                    logger.info(f"Submitted pegged order: {pegged.quantity} {pegged.side} {pegged.symbol} @ ${result.price:.2f} (peg to {pegged.peg_type.value})")
                else:
                    result.status = "rejected"
                    result.error_message = error_msg or "Unknown error"
                    logger.error(f"Failed to submit pegged order: {result.error_message}")
            else:
                # Simulate submission
                result.order_id = f"pegged_{pegged.symbol}_{datetime.now().timestamp()}"
                result.status = "accepted"
                logger.info(f"Simulated pegged order submission: {pegged.quantity} {pegged.side} {pegged.symbol}")

            # Store in active orders
            if result.order_id:
                self.active_orders[result.order_id] = result

        except Exception as e:
            logger.error(f"Error submitting pegged order: {e}")
            result.status = "rejected"
            result.error_message = str(e)

        # Add to history
        self.order_history.append(result)

        # Keep history reasonable
        if len(self.order_history) > 1000:
            self.order_history = self.order_history[-1000:]

        return result

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an advanced order.

        Args:
            order_id: ID of order to cancel

        Returns:
            True if cancelled successfully
        """
        if order_id in self.active_orders:
            order = self.active_orders[order_id]
            order.status = "cancelled"
            logger.info(f"Cancelled order {order_id}: {order.symbol} {order.side} {order.quantity}")
            del self.active_orders[order_id]
            return True
        else:
            logger.warning(f"Order {order_id} not found in active orders")
            return False

    def get_active_orders(self) -> List[AdvancedOrderResult]:
        """Get list of active orders."""
        return list(self.active_orders.values())

    def get_order_stats(self) -> Dict:
        """Get statistics about order submissions."""
        if not self.order_history:
            return {
                'total_orders': 0,
                'accepted_orders': 0,
                'rejected_orders': 0,
                'cancelled_orders': 0,
                'filled_orders': 0,
                'acceptance_rate': 0.0
            }

        total_orders = len(self.order_history)
        accepted_orders = len([o for o in self.order_history if o.status == 'accepted'])
        rejected_orders = len([o for o in self.order_history if o.status == 'rejected'])
        cancelled_orders = len([o for o in self.order_history if o.status == 'cancelled'])
        filled_orders = len([o for o in self.order_history if o.status == 'filled'])

        return {
            'total_orders': total_orders,
            'accepted_orders': accepted_orders,
            'rejected_orders': rejected_orders,
            'cancelled_orders': cancelled_orders,
            'filled_orders': filled_orders,
            'acceptance_rate': accepted_orders / total_orders if total_orders > 0 else 0.0,
            'fill_rate': filled_orders / accepted_orders if accepted_orders > 0 else 0.0,
            'active_orders': len(self.active_orders)
        }


class OrderFactory:
    """Factory for creating standard and advanced orders."""

    @staticmethod
    def create_market_order(symbol: str, quantity: int, side: str) -> Dict:
        """Create a market order."""
        return {
            'symbol': symbol,
            'quantity': quantity,
            'side': side,
            'order_type': 'market',
            'time_in_force': 'day'
        }

    @staticmethod
    def create_limit_order(symbol: str, quantity: int, side: str, price: float,
                          time_in_force: str = 'day') -> Dict:
        """Create a limit order."""
        return {
            'symbol': symbol,
            'quantity': quantity,
            'side': side,
            'order_type': 'limit',
            'price': price,
            'time_in_force': time_in_force
        }

    @staticmethod
    def create_iceberg_order(
        symbol: str,
        total_quantity: int,
        side: str,
        price: float,
        display_quantity: int
    ) -> Dict:
        """Create an iceberg order parameters."""
        return {
            'symbol': symbol,
            'total_quantity': total_quantity,
            'side': side,
            'price': price,
            'display_quantity': display_quantity,
            'order_type': 'iceberg'
        }

    @staticmethod
    def create_pegged_order(
        symbol: str,
        quantity: int,
        side: str,
        peg_type: PegType,
        offset: float = 0.0,
        limit_price: Optional[float] = None
    ) -> Dict:
        """Create a pegged order parameters."""
        return {
            'symbol': symbol,
            'quantity': quantity,
            'side': side,
            'peg_type': peg_type.value,
            'offset': offset,
            'limit_price': limit_price,
            'order_type': 'pegged'
        }

    @staticmethod
    def create_time_weighted_order(
        symbol: str,
        quantity: int,
        side: str,
        start_time: datetime,
        end_time: datetime,
        slice_count: int = 10
    ) -> Dict:
        """Create a time-weighted order (TWAP) parameters."""
        return {
            'symbol': symbol,
            'quantity': quantity,
            'side': side,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'slice_count': slice_count,
            'order_type': 'twap'
        }

    @staticmethod
    def create_volume_weighted_order(
        symbol: str,
        quantity: int,
        side: str,
        start_time: datetime,
        end_time: datetime,
        volume_profile: List[Tuple[datetime, float]] = None
    ) -> Dict:
        """Create a volume-weighted order (VWAP) parameters."""
        return {
            'symbol': symbol,
            'quantity': quantity,
            'side': side,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'volume_profile': [{"time": t.isoformat(), "volume": v} for t, v in volume_profile] if volume_profile else None,
            'order_type': 'vwap'
        }


def create_advanced_order_manager() -> AdvancedOrderManager:
    """Factory function to create an AdvancedOrderManager instance."""
    return AdvancedOrderManager()


def create_order_factory() -> OrderFactory:
    """Factory function to create an OrderFactory instance."""
    return OrderFactory()


# Example usage and testing
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    def demo_alert(message: str):
        print(f"[ALERT] {message}")

    # Create advanced order manager
    order_manager = create_advanced_order_manager()
    factory = create_order_factory()

    # Mock market data callback
    def get_market_data(symbol):
        return {
            'bid': 99.50,
            'ask': 100.50,
            'last': 100.00
        }

    # Mock submit order callback
    def submit_order(symbol, quantity, side, order_type, price=None):
        class MockOrder:
            def __init__(self):
                self.id = f"{order_type}_{symbol}_{datetime.now().timestamp()}"
        # Simulate occasional rejection
        import random
        if random.random() < 0.1:  # 10% rejection rate
            return False, "Simulated rejection", None
        return True, None, MockOrder()

    print("=== Advanced Order Types Demo ===\n")

    # Test iceberg order
    print("1. Testing Iceberg Order")
    iceberg = order_manager.create_iceberg_order(
        symbol="AAPL261016C00190000",
        total_quantity=50,
        side="buy",
        price=5.00,
        display_quantity=10  # Show only 10 of 50
    )

    iceberg_result = order_manager.submit_iceberg_order(
        iceberg=iceberg,
        get_market_data_callback=get_market_data,
        submit_order_callback=submit_order
    )

    print(f"   Iceberg: {iceberg.display_quantity}/{iceberg.total_quantity} {iceberg.side} {iceberg.symbol} @ ${iceberg.price:.2f}")
    print(f"   Result: {iceberg_result.status}")
    if iceberg_result.order_id:
        print(f"   Order ID: {iceberg_result.order_id}")
    print()

    # Test pegged order
    print("2. Testing Pegged Order (Mid-Peg)")
    pegged = order_manager.create_pegged_order(
        symbol="MSFT261016C00300000",
        quantity=25,
        side="buy",
        peg_type=PegType.MIDPEG,
        offset=0.05  # $0.05 above midpoint
    )

    pegged_result = order_manager.submit_pegged_order(
        pegged=pegged,
        get_market_data_callback=get_market_data,
        submit_order_callback=submit_order
    )

    print(f"   Pegged: {pegged.quantity} {pegged.side} {pegged.symbol}")
    print(f"   Peg Type: {pegged.peg_type.value} + ${pegged.offset:.2f}")
    print(f"   Result: {pegged_result.status}")
    if pegged_result.order_id:
        print(f"   Order ID: {pegged_result.order_id}")
    if pegged_result.price:
        print(f"   Execution Price: ${pegged_result.price:.2f}")
    print()

    # Test limit pegged order
    print("3. Testing Limit Pegged Order (Ask-Peg with Limit)")
    limited_pegged = order_manager.create_pegged_order(
        symbol="GOOGL261016C00120000",
        quantity=15,
        side="sell",
        peg_type=PegType.ASKPEG,
        offset=-0.10,  # $0.10 below ask
        limit_price=120.00  # Don't sell below $120
    )

    limited_pegged_result = order_manager.submit_pegged_order(
        pegged=limited_pegged,
        get_market_data_callback=get_market_data,
        submit_order_callback=submit_order
    )

    print(f"   Pegged: {limited_pegged.quantity} {limited_pegged.side} {limited_pegged.symbol}")
    print(f"   Peg Type: {limited_pegged.peg_type.value} {limited_pegged.offset:+.2f}")
    print(f"   Limit Price: ${limited_pegged.limit_price:.2f}")
    print(f"   Result: {limited_pegged_result.status}")
    if limited_pegged_result.order_id:
        print(f"   Order ID: {limited_pegged_result.order_id}")
    if limited_pegged_result.price:
        print(f"   Execution Price: ${limited_pegged_result.price:.2f}")
    print()

    # Test order factory
    print("4. Testing Order Factory")
    market_order = factory.create_market_order("TSLA261016P00250000", 5, "sell")
    limit_order = factory.create_limit_order("TSLA261016P00250000", 5, "sell", 4.50)
    iceberg_params = factory.create_iceberg_order("TSLA261016P00250000", 20, "sell", 4.50, 5)
    twap_params = factory.create_time_weighted_order(
        "TSLA261016P00250000",
        10,
        "buy",
        datetime.now(),
        datetime.now() + timedelta(hours=1),
        slice_count=6
    )

    print(f"   Market Order: {market_order}")
    print(f"   Limit Order: {limit_order}")
    print(f"   Iceberg Params: {iceberg_params}")
    print(f"   TWAP Params: {twap_params}")
    print()

    # Show statistics
    print("5. Order Statistics")
    stats = order_manager.get_order_stats()
    print(f"   Total Orders: {stats['total_orders']}")
    print(f"   Accepted Orders: {stats['accepted_orders']}")
    print(f"   Rejected Orders: {stats['rejected_orders']}")
    print(f"   Acceptance Rate: {stats['acceptance_rate']:.1%}")
    print(f"   Active Orders: {stats['active_orders']}")

    print("\n=== Advanced Order Types Demo Complete ===")