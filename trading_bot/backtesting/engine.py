"""Event-driven backtesting engine for trend following strategies."""

import pandas as pd
import numpy as np
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum
import logging

from trading_bot.strategies.trend_following import TrendFollowingStrategy
from trading_bot.backtesting.costs import TransactionCostModel

logger = logging.getLogger(__name__)


class PositionState(Enum):
    """Possible position states."""
    CASH = "cash"
    LONG = "long"


@dataclass
class Position:
    """Represents a position in a stock."""
    symbol: str
    quantity: float
    average_cost: float

    def get_value(self, current_price: float) -> float:
        """Get current market value of position."""
        return self.quantity * current_price

    def get_unrealized_pnl(self, current_price: float) -> float:
        """Get unrealized profit/loss."""
        return self.get_value(current_price) - (self.quantity * self.average_cost)

    def get_return(self, current_price: float) -> float:
        """Get percentage return."""
        if self.average_cost == 0:
            return 0
        return (current_price - self.average_cost) / self.average_cost


@dataclass
class Trade:
    """Represents a trade execution."""
    symbol: str
    side: str  # 'buy' or 'sell'
    quantity: float
    price: float
    timestamp: pd.Timestamp
    cost: float = 0.0  # Transaction cost
    commission: float = 0.0


@dataclass
class PortfolioState:
    """Snapshot of portfolio state at a point in time."""
    timestamp: pd.Timestamp
    cash: float
    positions: dict[str, Position]
    portfolio_value: float
    daily_pnl: float = 0.0
    drawdown: float = 0.0
    peak_value: float = 0.0

    def get_total_exposure(self, prices: dict[str, float]) -> float:
        """Get total market exposure."""
        exposure = 0
        for symbol, position in self.positions.items():
            exposure += position.get_value(prices.get(symbol, 0))
        return exposure


class EventDrivenBacktest:
    """Event-driven chronological backtester.

    This backtester processes data chronologically to prevent look-ahead bias:
    - Signal calculated at end of day T using data through day T
    - Order executed on day T+1 at market open
    """

    def __init__(
        self,
        strategy: TrendFollowingStrategy,
        initial_capital: float = 100000,
        cost_model: Optional[TransactionCostModel] = None
    ):
        """Initialize backtester.

        Args:
            strategy: Trend following strategy instance
            initial_capital: Initial capital in dollars
            cost_model: Transaction cost model
        """
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.cost_model = cost_model or TransactionCostModel()

        self.results = []
        self.trades = []
        self.daily_values = []

        # Track state
        self.portfolio = PortfolioState(
            timestamp=None,
            cash=initial_capital,
            positions={},
            portfolio_value=initial_capital,
            peak_value=initial_capital
        )

    def run(
        self,
        data: pd.DataFrame,
        symbol: str = "AAPL"
    ) -> dict:
        """Run backtest on historical data.

        Args:
            data: DataFrame with price data and calculated indicators
            symbol: Symbol being traded

        Returns:
            Dictionary with backtest results and metrics
        """
        # Calculate all indicators if not already done
        # Handle strategies that don't have calculate_all_indicators method
        if 'composite_score' not in data.columns:
            if hasattr(self.strategy, 'calculate_all_indicators'):
                data = self.strategy.calculate_all_indicators(data.copy())
            # If strategy doesn't have calculate_all_indicators, assume data already has needed columns
            # or that the strategy doesn't need indicator calculation (like options strategies)

        # Ensure data is sorted by date
        data = data.sort_values('date').reset_index(drop=True)

        # Track for performance calculation
        portfolio_values = []
        daily_returns = []

        logger.info(f"Starting backtest: {len(data)} trading days")

        for day in range(len(data)):
            row = data.iloc[day]
            current_date = row['date']
            current_price = row['adjusted_close']

            # Get signal for this day - handle missing columns gracefully
            signal = row.get('signal', 0)  # Default to no signal
            composite_score = row.get('composite_score', 0.0)  # Default to neutral score

            # Calculate current portfolio value
            current_value = self._calculate_portfolio_value(current_price)

            # Track daily P&L
            if day > 0:
                previous_value = portfolio_values[-1]
                daily_return = (current_value - previous_value) / previous_value if previous_value > 0 else 0
                daily_returns.append(daily_return)
            else:
                daily_return = 0

            # Update portfolio state
            self.portfolio.timestamp = current_date
            self.portfolio.portfolio_value = current_value
            self.portfolio.daily_pnl = current_value - previous_value if day > 0 else 0

            # Track peak for drawdown
            self.portfolio.peak_value = max(self.portfolio.peak_value, current_value)
            self.portfolio.drawdown = self._calculate_drawdown(current_value)

            # Record daily value
            self.daily_values.append({
                'date': current_date,
                'portfolio_value': current_value,
                'daily_return': daily_return,
                'composite_score': composite_score,
                'signal': signal
            })
            portfolio_values.append(current_value)

            # Generate and execute orders
            if day < len(data) - 1:  # Don't trade on last day
                next_day = day + 1
                self._generate_orders(data, next_day, symbol, current_price)

        # Finalize results
        results = self._calculate_metrics(
            data,
            portfolio_values,
            daily_returns,
            symbol
        )

        self.results = results
        return results

    def _calculate_portfolio_value(self, current_price: float) -> float:
        """Calculate current portfolio value."""
        position_value = 0
        for position in self.portfolio.positions.values():
            position_value += position.get_value(current_price)
        return self.portfolio.cash + position_value

    def _calculate_drawdown(self, current_value: float) -> float:
        """Calculate drawdown as percentage of peak."""
        if self.portfolio.peak_value == 0:
            return 0
        return (self.portfolio.peak_value - current_value) / self.portfolio.peak_value

    def _generate_orders(
        self,
        data: pd.DataFrame,
        day: int,
        symbol: str,
        current_price: float
    ):
        """Generate and execute orders based on signals.

        Args:
            data: Full data DataFrame
            day: Day index for execution
            symbol: Symbol being traded
            current_price: Current price
        """
        row = data.iloc[day]
        signal = row.get('signal', 0)  # Default to no signal

        if signal == 1:  # Entry signal
            self._enter_position(symbol, current_price, row)
        elif signal == -1:  # Exit signal
            self._exit_position(symbol, current_price, row)

    def _enter_position(
        self,
        symbol: str,
        price: float,
        row: pd.Series
    ):
        """Enter a new long position."""
        # Calculate position size
        # Using a simple approach: invest a fixed percentage of portfolio
        target_allocation = 0.10  # 10% of portfolio
        position_value = self.portfolio.cash * target_allocation

        # Calculate quantity
        quantity = position_value / price

        # Calculate cost
        cost = self.cost_model.calculate_cost_amount(position_value)

        # Update portfolio
        self.portfolio.cash -= (position_value + cost)

        if symbol in self.portfolio.positions:
            # Average cost for additional position
            existing = self.portfolio.positions[symbol]
            total_value = existing.get_value(price) + position_value
            total_qty = existing.quantity + quantity
            self.portfolio.positions[symbol] = Position(
                symbol=symbol,
                quantity=total_qty,
                average_cost=total_value / total_qty if total_qty > 0 else 0
            )
        else:
            self.portfolio.positions[symbol] = Position(
                symbol=symbol,
                quantity=quantity,
                average_cost=price
            )

        # Record trade
        self.trades.append(Trade(
            symbol=symbol,
            side='buy',
            quantity=quantity,
            price=price,
            timestamp=row['date'],
            cost=cost,
            commission=self.cost_model.commission
        ))

        logger.debug(f"BUY {quantity:.2f} {symbol} @ {price:.2f} (cost: {cost:.2f})")

    def _exit_position(
        self,
        symbol: str,
        price: float,
        row: pd.Series
    ):
        """Exit a long position."""
        if symbol not in self.portfolio.positions:
            return

        position = self.portfolio.positions[symbol]
        position_value = position.get_value(price)
        cost = self.cost_model.calculate_cost_amount(position_value)

        # Calculate P&L
        total_cost = position.quantity * position.average_cost
        pnl = position_value - total_cost - cost

        # Update portfolio
        self.portfolio.cash += (position_value - cost)
        del self.portfolio.positions[symbol]

        # Record trade
        self.trades.append(Trade(
            symbol=symbol,
            side='sell',
            quantity=position.quantity,
            price=price,
            timestamp=row['date'],
            cost=cost,
            commission=self.cost_model.commission
        ))

        logger.debug(f"SELL {position.quantity:.2f} {symbol} @ {price:.2f} (P&L: {pnl:.2f})")

    def _calculate_metrics(
        self,
        data: pd.DataFrame,
        portfolio_values: list[float],
        daily_returns: list[float],
        symbol: str
    ) -> dict:
        """Calculate backtest performance metrics.

        Args:
            data: Full data DataFrame
            portfolio_values: List of daily portfolio values
            daily_returns: List of daily returns
            symbol: Symbol being traded

        Returns:
            Dictionary of performance metrics
        """
        if not portfolio_values:
            return {}

        portfolio_series = pd.Series(portfolio_values)
        returns_series = pd.Series(daily_returns)

        # Basic metrics
        total_return = (portfolio_values[-1] - self.initial_capital) / self.initial_capital
        annualized_return = self._annualize_return(total_return, len(portfolio_values))

        # Risk metrics
        annualized_volatility = returns_series.std() * np.sqrt(252) if len(returns_series) > 1 else 0

        # Sharpe ratio (assuming 0% risk-free rate)
        sharpe_ratio = (
            annualized_return / annualized_volatility
            if annualized_volatility > 0 else 0
        )

        # Sortino ratio (downside deviation)
        negative_returns = returns_series[returns_series < 0]
        downside_volatility = (
            negative_returns.std() * np.sqrt(252)
            if len(negative_returns) > 1 else 0
        )
        sortino_ratio = (
            annualized_return / downside_volatility
            if downside_volatility > 0 else 0
        )

        # Drawdown metrics
        peak_values = portfolio_series.expanding().max()
        drawdowns = (peak_values - portfolio_series) / peak_values
        max_drawdown = drawdowns.max()
        max_drawdown_date = drawdowns.idxmax()

        # Trade metrics
        num_trades = len(self.trades)
        num_buys = len([t for t in self.trades if t.side == 'buy'])
        num_sells = len([t for t in self.trades if t.side == 'sell'])

        # Win rate and profit factor
        wins = []
        losses = []
        for t in self.trades:
            if t.side == 'sell':
                entry_price = self._get_entry_price(t.symbol)
                if entry_price > 0:
                    pnl = t.price - entry_price
                    if pnl > 0:
                        wins.append(pnl)
                    else:
                        losses.append(abs(pnl))

        win_rate = len(wins) / num_sells if num_sells > 0 else 0
        gross_profits = sum(wins) if wins else 0
        gross_losses = sum(losses) if losses else 0
        profit_factor = gross_profits / gross_losses if gross_losses > 0 else 0

        # Buy and hold benchmark
        buy_and_hold_return = (
            (data['adjusted_close'].iloc[-1] - data['adjusted_close'].iloc[0])
            / data['adjusted_close'].iloc[0]
        )

        return {
            'initial_capital': self.initial_capital,
            'final_portfolio_value': portfolio_values[-1],
            'total_return': total_return,
            'annualized_return': annualized_return,
            'annualized_volatility': annualized_volatility,
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'max_drawdown': max_drawdown,
            'max_drawdown_date': data.iloc[max_drawdown_date]['date'],
            'num_trades': num_trades,
            'num_buys': num_buys,
            'num_sells': num_sells,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_trading_costs': sum(t.cost for t in self.trades),
            'buy_and_hold_return': buy_and_hold_return,
            'excess_return': total_return - buy_and_hold_return,
            'trades': self.trades,
            'daily_values': self.daily_values
        }

    def _annualize_return(self, total_return: float, num_days: int) -> float:
        """Annualize a return over a number of trading days."""
        if num_days <= 0:
            return 0
        years = num_days / 252
        return (1 + total_return) ** (1 / years) - 1

    def _get_entry_price(self, symbol: str) -> float:
        """Get average entry price for a symbol from trades."""
        entry_prices = [
            t.price for t in self.trades
            if t.symbol == symbol and t.side == 'buy'
        ]
        return sum(entry_prices) / len(entry_prices) if entry_prices else 0
