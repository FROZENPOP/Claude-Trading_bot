"""Position reconciliation for execution (works with broker position objects)."""

import pandas as pd
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ReconciliationReport:
    """Position reconciliation report."""
    timestamp: datetime
    system_positions: dict
    broker_positions: dict
    differences: list
    missing_in_system: list
    missing_in_broker: list
    total_value_discrepancy: float


class PositionReconciler:
    """Reconcile system positions with broker positions."""

    def __init__(self, broker_positions: list):
        """Initialize reconciler.

        Args:
            broker_positions: List of broker position objects (must have .symbol and .qty attributes)
        """
        self.broker_positions = broker_positions
        self.broker_by_symbol = {p.symbol: p for p in broker_positions}

    def reconcile(
        self,
        system_positions: dict[str, dict]
    ) -> ReconciliationReport:
        """Reconcile system positions with broker positions.

        Args:
            system_positions: Dictionary of {symbol: {quantity, avg_cost, price}}

        Returns:
            Reconciliation report
        """
        system_by_symbol = {k: v for k, v in system_positions.items()}
        broker_by_symbol = {
            p.symbol: {
                'quantity': int(float(p.qty)),
                'avg_cost': float(p.avg_cost) if hasattr(p, 'avg_cost') and p.avg_cost else None,
                'price': float(p.current_price) if hasattr(p, 'current_price') else None,
                'market_value': float(p.market_value) if hasattr(p, 'market_value') else None
            }
            for p in self.broker_positions
        }

        # Find differences
        all_symbols = set(system_by_symbol.keys()) | set(broker_by_symbol.keys())

        differences = []
        missing_in_system = []
        missing_in_broker = []

        for symbol in all_symbols:
            sys_pos = system_by_symbol.get(symbol)
            brk_pos = broker_by_symbol.get(symbol)

            if sys_pos and not brk_pos:
                missing_in_broker.append({
                    'symbol': symbol,
                    'quantity': sys_pos.get('quantity', 0),
                    'avg_cost': sys_pos.get('avg_cost')
                })
            elif brk_pos and not sys_pos:
                missing_in_system.append({
                    'symbol': symbol,
                    'quantity': brk_pos.get('quantity', 0),
                    'avg_cost': brk_pos.get('avg_cost')
                })
            else:
                # Both exist - check for discrepancies
                sys_qty = sys_pos.get('quantity', 0)
                brk_qty = brk_pos.get('quantity', 0)

                if sys_qty != brk_qty:
                    differences.append({
                        'symbol': symbol,
                        'system_qty': sys_qty,
                        'broker_qty': brk_qty,
                        'difference': brk_qty - sys_qty
                    })

                # Check avg cost if available
                sys_cost = sys_pos.get('avg_cost')
                brk_cost = brk_pos.get('avg_cost')

                if brk_cost is not None and sys_cost is not None:
                    if abs(sys_cost - brk_cost) > 0.01:
                        differences.append({
                            'symbol': symbol,
                            'type': 'avg_cost',
                            'system_cost': sys_cost,
                            'broker_cost': brk_cost,
                            'difference': brk_cost - sys_cost
                        })

        # Calculate total value discrepancy
        total_sys_value = sum(
            p.get('quantity', 0) * p.get('price', 0)
            for p in system_by_symbol.values()
        )
        total_broker_value = sum(
            float(p.market_value) for p in self.broker_positions
            if hasattr(p, 'market_value') and p.market_value
        )

        return ReconciliationReport(
            timestamp=datetime.now(),
            system_positions=system_by_symbol,
            broker_positions=broker_by_symbol,
            differences=differences,
            missing_in_system=missing_in_system,
            missing_in_broker=missing_in_broker,
            total_value_discrepancy=total_broker_value - total_sys_value
        )

    def find_discrepancies(
        self,
        system_positions: dict[str, dict]
    ) -> list[dict]:
        """Find discrepancies between system and broker.

        Args:
            system_positions: System position dictionary

        Returns:
            List of discrepancy dictionaries
        """
        report = self.reconcile(system_positions)
        return report.differences

    def get_missing_broker_positions(
        self,
        system_positions: dict[str, dict]
    ) -> list[dict]:
        """Get positions that exist in system but not in broker.

        Args:
            system_positions: System position dictionary

        Returns:
            List of missing broker positions
        """
        report = self.reconcile(system_positions)
        return report.missing_in_broker

    def get_missing_system_positions(
        self,
        broker_positions: list
    ) -> list[dict]:
        """Get positions that exist in broker but not in system.

        Args:
            broker_positions: List of broker position objects (must have .symbol and .qty attributes)

        Returns:
            List of missing system positions
        """
        # Update broker positions
        self.broker_positions = broker_positions
        self.broker_by_symbol = {p.symbol: p for p in broker_positions}

        # Get system positions from broker for comparison
        system_positions = {
            p.symbol: {
                'quantity': int(float(p.qty)),
                'avg_cost': float(p.avg_cost) if hasattr(p, 'avg_cost') and p.avg_cost else None,
                'price': float(p.current_price) if hasattr(p, 'current_price') else None
            }
            for p in broker_positions
        }

        report = self.reconcile(system_positions)
        return report.missing_in_system


def generate_reconciliation_entry(
    symbol: str,
    quantity: int,
    avg_cost: float,
    current_price: float,
    market_value: float
) -> dict:
    """Generate a system position entry for reconciliation.

    Args:
        symbol: Stock symbol
        quantity: Number of shares
        avg_cost: Average cost per share
        current_price: Current price per share
        market_value: Total market value

    Returns:
        Position dictionary
    """
    return {
        'quantity': quantity,
        'avg_cost': avg_cost,
        'price': current_price,
        'market_value': market_value
    }


def validate_position_sync(
    system_positions: dict[str, dict],
    broker_positions: list,
    tolerance: float = 0.01
) -> tuple[bool, list[str]]:
    """Validate that system and broker positions are synchronized.

    Args:
        system_positions: System position dictionary
        broker_positions: List of broker position objects (must have .symbol and .qty attributes)
        tolerance: Maximum allowed difference in quantities

    Returns:
        Tuple of (is_synced, list of warnings)
    """
    reconciler = PositionReconciler(broker_positions)
    report = reconciler.reconcile(system_positions)

    warnings = []

    if report.differences:
        for diff in report.differences:
            warnings.append(
                f"Position mismatch for {diff['symbol']}: "
                f"system={diff.get('system_qty', 'N/A')}, "
                f"broker={diff.get('broker_qty', 'N/A')}"
            )

    if abs(report.total_value_discrepancy) > tolerance:
        warnings.append(
            f"Total value discrepancy: ${report.total_value_discrepancy:.2f}"
        )

    is_synced = len(warnings) == 0

    return is_synced, warnings
