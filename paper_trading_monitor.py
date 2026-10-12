#!/usr/bin/env python3
"""
Paper trading results monitor for options trading system.
Tracks performance, calculates metrics, and provides reporting capabilities.
"""

import sys
import os
import json
import datetime
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

# Add project to path
sys.path.append(os.path.join(os.path.dirname(__file__)))


class PerformanceMetric(Enum):
    """Types of performance metrics to track."""
    TOTAL_RETURN = "total_return"
    ANNUALIZED_RETURN = "annualized_return"
    SHARPE_RATIO = "sharpe_ratio"
    SORTINO_RATIO = "sortino_ratio"
    MAX_DRAWDOWN = "max_drawdown"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    TOTAL_TRADES = "total_trades"
    WINNING_TRADES = "winning_trades"
    LOSING_TRADES = "losing_trades"
    AVG_WIN = "avg_win"
    AVG_LOSS = "avg_loss"
    LARGEST_WIN = "largest_win"
    LARGEST_LOSS = "largest_loss"
    AVG_DURATION_HOURS = "avg_duration_hours"


@dataclass
class TradeRecord:
    """Record of a single trade."""
    trade_id: str
    symbol: str
    strategy_name: str
    option_symbol: str
    side: str  # 'buy' or 'sell'
    quantity: int
    entry_price: float
    exit_price: Optional[float]
    entry_time: datetime.datetime
    exit_time: Optional[datetime.datetime]
    pnl: Optional[float]
    pnl_percent: Optional[float]
    commission: float
    fees: float
    status: str  # 'open', 'closed', 'cancelled', 'expired'
    tags: List[str]


@dataclass
class PerformanceSnapshot:
    """Snapshot of performance at a point in time."""
    timestamp: datetime.datetime
    period: str  # 'daily', 'weekly', 'monthly', 'ytd', 'all_time'
    starting_equity: float
    ending_equity: float
    total_return: float
    total_return_percent: float
    annualized_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    max_drawdown_percent: float
    win_rate: float
    profit_factor: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    avg_duration_hours: float
    total_commission: float
    total_fees: float


class PaperTradingMonitor:
    """Monitor for tracking paper trading performance."""

    def __init__(self, data_file: str = "paper_trading_data.json"):
        self.data_file = data_file
        self.trades: List[TradeRecord] = []
        self.performance_history: List[PerformanceSnapshot] = []
        self.starting_equity: float = 50000.0  # Default starting equity
        self.current_equity: float = 50000.0
        self.logger = self._setup_logger()
        self._load_data()

    def _setup_logger(self):
        """Setup logging for the monitor."""
        import logging
        logger = logging.getLogger("PaperTradingMonitor")
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    def _load_data(self):
        """Load trading data from file."""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r') as f:
                    data = json.load(f)

                # Load trades
                self.trades = []
                for trade_dict in data.get('trades', []):
                    # Convert datetime strings back to datetime objects
                    trade_dict['entry_time'] = datetime.datetime.fromisoformat(trade_dict['entry_time'])
                    if trade_dict['exit_time']:
                        trade_dict['exit_time'] = datetime.datetime.fromisoformat(trade_dict['exit_time'])
                    self.trades.append(TradeRecord(**trade_dict))

                # Load performance history
                self.performance_history = []
                for snap_dict in data.get('performance_history', []):
                    snap_dict['timestamp'] = datetime.datetime.fromisoformat(snap_dict['timestamp'])
                    self.performance_history.append(PerformanceSnapshot(**snap_dict))

                # Load equity info
                self.starting_equity = data.get('starting_equity', 50000.0)
                self.current_equity = data.get('current_equity', 50000.0)

                self.logger.info(f"Loaded {len(self.trades)} trades and {len(self.performance_history)} performance snapshots")
            else:
                self.logger.info("No existing data file found, starting fresh")
        except Exception as e:
            self.logger.error(f"Error loading data: {e}")
            # Initialize with empty data
            self.trades = []
            self.performance_history = []
            self.starting_equity = 50000.0
            self.current_equity = 50000.0

    def _save_data(self):
        """Save trading data to file."""
        try:
            # Convert trades to serializable format
            trades_data = []
            for trade in self.trades:
                trade_dict = asdict(trade)
                # Convert datetime objects to ISO strings
                trade_dict['entry_time'] = trade.entry_time.isoformat()
                if trade.exit_time:
                    trade_dict['exit_time'] = trade.exit_time.isoformat()
                trades_data.append(trade_dict)

            # Convert performance history to serializable format
            history_data = []
            for snap in self.performance_history:
                snap_dict = asdict(snap)
                snap_dict['timestamp'] = snap.timestamp.isoformat()
                history_data.append(snap_dict)

            data = {
                'trades': trades_data,
                'performance_history': history_data,
                'starting_equity': self.starting_equity,
                'current_equity': self.current_equity,
                'last_updated': datetime.datetime.now().isoformat()
            }

            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=2)

            self.logger.debug(f"Saved {len(self.trades)} trades and {len(self.performance_history)} performance snapshots")
        except Exception as e:
            self.logger.error(f"Error saving data: {e}")

    def add_trade(self, trade: TradeRecord):
        """Add a new trade to the monitoring system."""
        self.trades.append(trade)
        self._save_data()
        self.logger.info(f"Added trade: {trade.trade_id} - {trade.symbol} {trade.side} {trade.quantity}")

    def update_trade(self, trade_id: str, updates: Dict[str, Any]):
        """Update an existing trade."""
        for trade in self.trades:
            if trade.trade_id == trade_id:
                for key, value in updates.items():
                    if hasattr(trade, key):
                        setattr(trade, key, value)
                self._save_data()
                self.logger.info(f"Updated trade: {trade_id}")
                return True
        self.logger.warning(f"Trade not found for update: {trade_id}")
        return False

    def close_trade(self, trade_id: str, exit_price: float, exit_time: Optional[datetime.datetime] = None):
        """Close an open trade."""
        if exit_time is None:
            exit_time = datetime.datetime.now()

        for trade in self.trades:
            if trade.trade_id == trade_id and trade.status == 'open':
                trade.exit_price = exit_price
                trade.exit_time = exit_time
                trade.status = 'closed'

                # Calculate P&L
                if trade.side == 'buy':
                    trade.pnl = (exit_price - trade.entry_price) * trade.quantity * 100  # 100 shares per contract
                else:  # sell
                    trade.pnl = (trade.entry_price - exit_price) * trade.quantity * 100

                trade.pnl_percent = (trade.pnl / (abs(trade.entry_price) * trade.quantity * 100)) * 100

                self._save_data()
                self.logger.info(f"Closed trade: {trade.trade_id} - P&L: ${trade.pnl:.2f} ({trade.pnl_percent:.2f}%)")
                return True

        self.logger.warning(f"Open trade not found for closing: {trade_id}")
        return False

    def calculate_performance(self, period: str = "all_time") -> PerformanceSnapshot:
        """Calculate performance metrics for a given period."""
        now = datetime.datetime.now()

        # Filter trades based on period
        if period == "all_time":
            filtered_trades = self.trades
        elif period == "daily":
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            filtered_trades = [t for t in self.trades if t.entry_time >= start_date]
        elif period == "weekly":
            # Start of week (Monday)
            days_since_monday = now.weekday()
            start_date = now - datetime.timedelta(days=days_since_monday)
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            filtered_trades = [t for t in self.trades if t.entry_time >= start_date]
        elif period == "monthly":
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            filtered_trades = [t for t in self.trades if t.entry_time >= start_date]
        elif period == "ytd":
            start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            filtered_trades = [t for t in self.trades if t.entry_time >= start_date]
        else:
            filtered_trades = self.trades  # Default to all time

        # Filter to only closed trades for P&L calculations
        closed_trades = [t for t in filtered_trades if t.status == 'closed' and t.pnl is not None]

        if not closed_trades:
            # Return empty performance if no closed trades
            return PerformanceSnapshot(
                timestamp=now,
                period=period,
                starting_equity=self.starting_equity,
                ending_equity=self.current_equity,
                total_return=0.0,
                total_return_percent=0.0,
                annualized_return=0.0,
                sharpe_ratio=0.0,
                sortino_ratio=0.0,
                max_drawdown=0.0,
                max_drawdown_percent=0.0,
                win_rate=0.0,
                profit_factor=0.0,
                total_trades=len(filtered_trades),
                winning_trades=0,
                losing_trades=0,
                avg_win=0.0,
                avg_loss=0.0,
                largest_win=0.0,
                largest_loss=0.0,
                avg_duration_hours=0.0,
                total_commission=sum(t.commission for t in filtered_trades),
                total_fees=sum(t.fees for t in filtered_trades)
            )

        # Calculate basic metrics
        total_pnl = sum(t.pnl for t in closed_trades)
        winning_trades = [t for t in closed_trades if t.pnl > 0]
        losing_trades = [t for t in closed_trades if t.pnl <= 0]

        total_return = total_pnl
        total_return_percent = (total_return / self.starting_equity) * 100 if self.starting_equity > 0 else 0

        win_rate = len(winning_trades) / len(closed_trades) if closed_trades else 0

        # Calculate average win/loss
        avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.pnl for t in losing_trades]) if losing_trades else 0

        # Calculate profit factor
        gross_profit = sum(t.pnl for t in winning_trades) if winning_trades else 0
        gross_loss = abs(sum(t.pnl for t in losing_trades)) if losing_trades else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Calculate largest win/loss
        largest_win = max([t.pnl for t in winning_trades]) if winning_trades else 0
        largest_loss = min([t.pnl for t in losing_trades]) if losing_trades else 0

        # Calculate average duration
        durations = []
        for t in closed_trades:
            if t.exit_time and t.entry_time:
                duration = t.exit_time - t.entry_time
                durations.append(duration.total_seconds() / 3600)  # Convert to hours
        avg_duration = np.mean(durations) if durations else 0

        # Calculate more advanced metrics (simplified)
        # For a real implementation, we would need equity curve data
        annualized_return = total_return_percent * (252 / max(1, len(closed_trades)))  # Rough approximation
        sharpe_ratio = annualized_return / (max(1, np.std([t.pnl for t in closed_trades])) * np.sqrt(252)) if len(closed_trades) > 1 else 0
        sortino_ratio = annualized_return / (max(1, np.std([t.pnl for t in winning_trades])) * np.sqrt(252)) if len(winning_trades) > 1 else 0

        # Simplified drawdown calculation
        # In reality, we'd track equity curve
        max_drawdown = abs(min([t.pnl for t in closed_trades])) if any(t.pnl < 0 for t in closed_trades) else 0
        max_drawdown_percent = (max_drawdown / self.starting_equity) * 100 if self.starting_equity > 0 else 0

        return PerformanceSnapshot(
            timestamp=now,
            period=period,
            starting_equity=self.starting_equity,
            ending_equity=self.current_equity,
            total_return=total_return,
            total_return_percent=total_return_percent,
            annualized_return=annualized_return,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            max_drawdown=max_drawdown,
            max_drawdown_percent=max_drawdown_percent,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_trades=len(filtered_trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            avg_win=avg_win,
            avg_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            avg_duration_hours=avg_duration,
            total_commission=sum(t.commission for t in filtered_trades),
            total_fees=sum(t.fees for t in filtered_trades)
        )

    def record_performance_snapshot(self, period: str = "daily"):
        """Record a performance snapshot for the given period."""
        snapshot = self.calculate_performance(period)
        self.performance_history.append(snapshot)
        self._save_data()
        self.logger.info(f"Recorded {period} performance snapshot: {snapshot.total_return_percent:.2f}% return")
        return snapshot

    def get_performance_report(self, period: str = "all_time") -> Dict[str, Any]:
        """Get a formatted performance report."""
        snapshot = self.calculate_performance(period)

        report = {
            "period": period,
            "timestamp": snapshot.timestamp.isoformat(),
            "summary": {
                "starting_equity": f"${self.starting_equity:,.2f}",
                "ending_equity": f"${self.current_equity:,.2f}",
                "total_return": f"${snapshot.total_return:,.2f}",
                "total_return_percent": f"{snapshot.total_return_percent:.2f}%",
                "annualized_return": f"{snapshot.annualized_return:.2f}%",
            },
            "risk_metrics": {
                "sharpe_ratio": f"{snapshot.sharpe_ratio:.3f}",
                "sortino_ratio": f"{snapshot.sortino_ratio:.3f}",
                "max_drawdown": f"${snapshot.max_drawdown:,.2f}",
                "max_drawdown_percent": f"{snapshot.max_drawdown_percent:.2f}%"
            },
            "trade_metrics": {
                "total_trades": snapshot.total_trades,
                "winning_trades": snapshot.winning_trades,
                "losing_trades": snapshot.losing_trades,
                "win_rate": f"{snapshot.win_rate:.2%}",
                "profit_factor": f"{snapshot.profit_factor:.2f}",
                "avg_win": f"${snapshot.avg_win:.2f}",
                "avg_loss": f"${snapshot.avg_loss:.2f}",
                "largest_win": f"${snapshot.largest_win:.2f}",
                "largest_loss": f"${snapshot.largest_loss:.2f}",
                "avg_duration_hours": f"{snapshot.avg_duration_hours:.1f} hours"
            },
            "costs": {
                "total_commission": f"${snapshot.total_commission:.2f}",
                "total_fees": f"${snapshot.total_fees:.2f}"
            }
        }

        return report

    def print_performance_report(self, period: str = "all_time"):
        """Print a formatted performance report to console."""
        report = self.get_performance_report(period)

        print("\n" + "="*60)
        print(f"PAPER TRADING PERFORMANCE REPORT - {period.upper()}")
        print("="*60)

        print(f"Timestamp: {report['timestamp']}")
        print()

        print("SUMMARY:")
        for key, value in report['summary'].items():
            print(f"  {key.replace('_', ' ').title()}: {value}")
        print()

        print("RISK METRICS:")
        for key, value in report['risk_metrics'].items():
            print(f"  {key.replace('_', ' ').title()}: {value}")
        print()

        print("TRADE METRICS:")
        for key, value in report['trade_metrics'].items():
            print(f"  {key.replace('_', ' ').title()}: {value}")
        print()

        print("COSTS:")
        for key, value in report['costs'].items():
            print(f"  {key.replace('_', ' ').title()}: {value}")
        print()

        print("="*60)


def create_monitor() -> PaperTradingMonitor:
    """Create and return a paper trading monitor instance."""
    return PaperTradingMonitor()


def demonstrate_monitor():
    """Demonstrate the paper trading monitor functionality."""
    print("OPTIONS TRADING SYSTEM - PAPER TRADING MONITOR DEMO")
    print("=" * 60)

    # Create monitor
    monitor = create_monitor()

    # Add some sample trades to demonstrate functionality
    print("Adding sample trades for demonstration...")

    sample_trades = [
        TradeRecord(
            trade_id="TRADE001",
            symbol="AAPL",
            strategy_name="Vertical Spread",
            option_symbol="AAPL261015C00150000",
            side="buy",
            quantity=2,
            entry_price=5.25,
            exit_price=6.75,
            entry_time=datetime.datetime.now() - datetime.timedelta(days=5),
            exit_time=datetime.datetime.now() - datetime.timedelta(days=3),
            pnl=None,  # Will be calculated when closing
            pnl_percent=None,
            commission=1.00,
            fees=0.50,
            status="open",
            tags=["bullish", "earnings_play"]
        ),
        TradeRecord(
            trade_id="TRADE002",
            symbol="MSFT",
            strategy_name="Covered Call",
            option_symbol="MSFT261015C00300000",
            side="sell",
            quantity=1,
            entry_price=3.50,
            exit_price=1.25,
            entry_time=datetime.datetime.now() - datetime.timedelta(days=10),
            exit_time=datetime.datetime.now() - datetime.timedelta(days=5),
            pnl=None,
            pnl_percent=None,
            commission=1.00,
            fees=0.50,
            status="open",
            tags=["neutral", "income"]
        ),
        TradeRecord(
            trade_id="TRADE003",
            symbol="SPY",
            strategy_name="Iron Condor",
            option_symbol="SPY261015C00450000",
            side="buy",
            quantity=1,
            entry_price=4.20,
            exit_price=2.10,
            entry_time=datetime.datetime.now() - datetime.timedelta(days=15),
            exit_time=datetime.datetime.now() - datetime.timedelta(days=10),
            pnl=None,
            pnl_percent=None,
            commission=1.00,
            fees=0.50,
            status="open",
            tags=["range_bound", "low_volatility"]
        )
    ]

    # Add trades to monitor
    for trade in sample_trades:
        monitor.add_trade(trade)

    # Close the trades
    monitor.close_trade("TRADE001", 6.75)
    monitor.close_trade("TRADE002", 1.25)
    monitor.close_trade("TRADE003", 2.10)

    print(f"Added and closed {len(sample_trades)} sample trades")
    print()

    # Generate performance reports
    print("Generating performance reports...")
    print("-" * 40)

    # All-time performance
    monitor.print_performance_report("all_time")

    # Daily performance
    monitor.print_performance_report("daily")

    # Weekly performance
    monitor.print_performance_report("weekly")

    # Record a daily snapshot
    print("Recording daily performance snapshot...")
    snapshot = monitor.record_performance_snapshot("daily")
    print(f"Recorded snapshot: {snapshot.total_return_percent:.2f}% return")
    print()

    # Show data persistence
    print("Data persistence check:")
    print(f"  Trades in memory: {len(monitor.trades)}")
    print(f"  Performance snapshots: {len(monitor.performance_history)}")
    print(f"  Starting equity: ${monitor.starting_equity:,.2f}")
    print(f"  Current equity: ${monitor.current_equity:,.2f}")
    print()

    print("[SUCCESS] Paper trading monitor initialized and demonstrated")
    print("[READY] Monitor can track live paper trading performance")
    print()
    print("NEXT STEPS:")
    print("1. Integrate with actual trade execution system")
    print("2. Connect to real order fills and position updates")
    print("3. Add real-time performance alerts and notifications")
    print("4. Deploy in live environment with continuous monitoring")

    return monitor


if __name__ == "__main__":
    # Demonstrate the monitor
    monitor = demonstrate_monitor()

    # Show final status
    print("Final monitor status:")
    print(f"  Total trades tracked: {len(monitor.trades)}")
    print(f"  Closed trades: {len([t for t in monitor.trades if t.status == 'closed'])}")
    print(f"  Open trades: {len([t for t in monitor.trades if t.status == 'open'])}")
    print(f"  Performance snapshots: {len(monitor.performance_history)}")