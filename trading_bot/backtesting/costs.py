"""Transaction cost model for backtesting."""

from typing import Optional
import logging

logger = logging.getLogger(__name__)


class TransactionCostModel:
    """Transaction cost model for backtesting.

    Costs include:
    - Commission: Fixed cost per trade
    - Bid-ask spread: Cost from buying at ask, selling at bid
    - Slippage: Difference between expected and actual execution price
    """

    def __init__(
        self,
        commission: float = 0.0,
        slippage_bps: float = 5.0,
        bid_ask_spread_bps: float = 2.0
    ):
        """Initialize transaction cost model.

        Args:
            commission: Fixed commission per trade (in dollars)
            slippage_bps: Expected slippage in basis points
            bid_ask_spread_bps: Bid-ask spread in basis points
        """
        self.commission = commission
        self.slippage_bps = slippage_bps
        self.bid_ask_spread_bps = bid_ask_spread_bps

    def get_total_cost_bps(self) -> float:
        """Get total expected cost in basis points."""
        return self.slippage_bps + self.bid_ask_spread_bps

    def calculate_cost_amount(self, trade_value: float) -> float:
        """Calculate total transaction cost in dollars.

        Args:
            trade_value: Value of the trade (shares × price)

        Returns:
            Total transaction cost in dollars
        """
        cost_bps = self.get_total_cost_bps()
        cost_dollars = (cost_bps / 10000) * trade_value + self.commission
        return cost_dollars

    def calculate_execution_price(
        self,
        price: float,
        side: str,
        quantity: int = None
    ) -> float:
        """Calculate expected execution price with costs.

        Args:
            price: Mid price
            side: 'buy' or 'sell'
            quantity: Optional quantity for volume-based slippage

        Returns:
            Expected execution price
        """
        # Slippage component (volume-based if quantity provided)
        slippage_bps = self.slippage_bps
        if quantity is not None and quantity > 1000:
            # Larger orders have more slippage
            slippage_bps *= (1 + quantity / 10000)

        if side == 'buy':
            # Buy at ask = mid + spread/2 + slippage
            cost = (self.bid_ask_spread_bps / 2 + slippage_bps) / 10000
            return price * (1 + cost)
        else:
            # Sell at bid = mid - spread/2 - slippage
            cost = (self.bid_ask_spread_bps / 2 + slippage_bps) / 10000
            return price * (1 - cost)

    def get_effective_price(
        self,
        order_type: str,
        execution_price: float
    ) -> float:
        """Get effective price per share including costs.

        Args:
            order_type: Type of order ('market', 'limit', etc.)
            execution_price: Price per share

        Returns:
            Effective price per share including estimated costs
        """
        # For market orders, add estimated costs
        if order_type == 'market':
            cost_bps = self.get_total_cost_bps()
            return execution_price * (1 + cost_bps / 10000)
        return execution_price


class SensitivityAnalysis:
    """Run sensitivity analysis across different cost assumptions."""

    def __init__(self, base_costs: Optional[TransactionCostModel] = None):
        """Initialize sensitivity analyzer.

        Args:
            base_costs: Base transaction cost model
        """
        self.base_costs = base_costs or TransactionCostModel()

    def get_cost_scenarios(self) -> list[tuple[str, TransactionCostModel]]:
        """Get different cost scenarios for sensitivity analysis.

        Returns:
            List of (scenario_name, cost_model) tuples
        """
        scenarios = [
            ("Zero costs", TransactionCostModel()),
            ("Low costs", TransactionCostModel(
                commission=0.0,
                slippage_bps=2.0,
                bid_ask_spread_bps=1.0
            )),
            ("Base costs", self.base_costs),
            ("High costs", TransactionCostModel(
                commission=0.0,
                slippage_bps=10.0,
                bid_ask_spread_bps=5.0
            )),
            ("Very high costs", TransactionCostModel(
                commission=5.0,  # Per trade
                slippage_bps=20.0,
                bid_ask_spread_bps=10.0
            )),
        ]
        return scenarios

    def analyze_impact(
        self,
        total_return: float,
        annualized_return: float,
        num_trades: int,
        average_trade_value: float
    ) -> list[dict]:
        """Analyze how different costs impact strategy performance.

        Args:
            total_return: Total strategy return
            annualized_return: Annualized return
            num_trades: Number of trades
            average_trade_value: Average trade value

        Returns:
            List of results for each cost scenario
        """
        scenarios = self.get_cost_scenarios()
        results = []

        base_cost_model = self.base_costs

        for scenario_name, cost_model in scenarios:
            # Calculate total costs for this scenario
            total_costs = num_trades * cost_model.commission
            avg_cost_bps = cost_model.get_total_cost_bps()
            total_slippage_costs = (avg_cost_bps / 10000) * num_trades * average_trade_value
            total_costs += total_slippage_costs

            # Estimate impact on returns
            # Simple approximation: costs reduce returns proportionally
            base_total_costs = (
                num_trades * base_cost_model.commission +
                (base_cost_model.get_total_cost_bps() / 10000) *
                num_trades * average_trade_value
            )
            cost_ratio = total_costs / base_total_costs if base_total_costs > 0 else 1

            adjusted_return = total_return / cost_ratio if cost_ratio > 0 else total_return

            results.append({
                "scenario": scenario_name,
                "total_costs": total_costs,
                "cost_bps": cost_model.get_total_cost_bps(),
                "adjusted_return": adjusted_return,
                "net_return": adjusted_return - total_costs
            })

        return results
