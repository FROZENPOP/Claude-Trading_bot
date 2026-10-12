"""Structured logging for audit trail."""

import logging
import json
from datetime import datetime
from typing import Optional
from pathlib import Path
import os


class AuditLogger:
    """Structured logger for trading system audit trail.

    All trading decisions and actions are logged with:
    - Timestamp
    - Event type
    - Symbol (if applicable)
    - Context information
    - Actor (system/trader)
    """

    def __init__(
        self,
        log_dir: str = "logs",
        log_level: int = logging.INFO
    ):
        """Initialize audit logger.

        Args:
            log_dir: Directory for log files
            log_level: Logging level
        """
        self.log_dir = log_dir
        self.log_level = log_level

        # Create log directory
        Path(log_dir).mkdir(parents=True, exist_ok=True)

        # Setup logger
        self.logger = logging.getLogger("audit")
        self.logger.setLevel(log_level)

        # File handler with JSON format
        log_file = f"{log_dir}/audit_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)

        # JSON formatter
        json_formatter = AuditJsonFormatter()
        file_handler.setFormatter(json_formatter)

        # Console handler for human-readable output
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def log_event(
        self,
        event_type: str,
        symbol: str,
        action: str,
        details: dict,
        actor: str = "system"
    ):
        """Log a trading event.

        Args:
            event_type: Type of event (order, position, risk, etc.)
            symbol: Stock symbol
            action: Action taken
            details: Event details
            actor: Who/what triggered the event
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'symbol': symbol,
            'action': action,
            'details': details,
            'actor': actor
        }

        self.logger.info(json.dumps(log_entry))

    def log_order(
        self,
        symbol: str,
        side: str,
        qty: int,
        price: float,
        order_id: str,
        status: str = "placed"
    ):
        """Log an order event.

        Args:
            symbol: Stock symbol
            side: buy/sell
            qty: Quantity
            price: Order price
            order_id: Order ID
            status: Order status
        """
        details = {
            'side': side,
            'quantity': qty,
            'price': price,
            'order_id': order_id,
            'status': status
        }
        self.log_event('order', symbol, f'order_{status}', details)

    def log_position(
        self,
        symbol: str,
        action: str,
        qty: int,
        price: float,
        new_quantity: int,
        new_cost_basis: float
    ):
        """Log a position event.

        Args:
            symbol: Stock symbol
            action: add/remove/update
            qty: Quantity changed
            price: Price per share
            new_quantity: New quantity
            new_cost_basis: New cost basis per share
        """
        details = {
            'action': action,
            'quantity_change': qty,
            'price': price,
            'new_quantity': new_quantity,
            'new_cost_basis': new_cost_basis
        }
        self.log_event('position', symbol, f'position_{action}', details)

    def log_risk_check(
        self,
        check_type: str,
        symbol: str,
        passed: bool,
        details: dict,
        action_taken: str = ""
    ):
        """Log a risk check event.

        Args:
            check_type: Type of check (position, drawdown, daily_loss)
            symbol: Stock symbol
            passed: Whether check passed
            details: Check details
            action_taken: Action taken if check failed
        """
        action = 'passed' if passed else f'failed_{action_taken}'
        details['check_type'] = check_type
        self.log_event('risk', symbol, action, details)

    def log_signal(
        self,
        symbol: str,
        signal_type: str,
        value: float,
        threshold: float,
        action: str
    ):
        """Log a signal calculation event.

        Args:
            symbol: Stock symbol
            signal_type: Type of signal (entry, exit, composite)
            value: Signal value
            threshold: Threshold used
            action: Action based on signal
        """
        details = {
            'signal_type': signal_type,
            'value': value,
            'threshold': threshold,
            'action': action
        }
        self.log_event('signal', symbol, f'signal_{action}', details)

    def log_trade(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        order_id: str,
        strategy: str = ""
    ):
        """Log a trade execution event.

        Args:
            symbol: Stock symbol
            side: buy/sell
            quantity: Trade quantity
            price: Trade price
            order_id: Order ID
            strategy: Strategy name
        """
        details = {
            'side': side,
            'quantity': quantity,
            'price': price,
            'order_id': order_id,
            'strategy': strategy
        }
        self.log_event('trade', symbol, 'trade_executed', details)

    def log_trade_error(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        error: str,
        strategy: str = ""
    ):
        """Log a trade execution error.

        Args:
            symbol: Stock symbol
            side: buy/sell
            quantity: Trade quantity
            price: Trade price
            error: Error message
            strategy: Strategy name
        """
        details = {
            'side': side,
            'quantity': quantity,
            'price': price,
            'error': error,
            'strategy': strategy
        }
        self.log_event('trade_error', symbol, 'trade_failed', details)


class AuditJsonFormatter(logging.Formatter):
    """JSON formatter for audit logs."""

    def format(self, record):
        """Format log record as JSON."""
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'message': record.getMessage()
        }
        return json.dumps(log_entry)


def get_audit_logger() -> AuditLogger:
    """Get or create global audit logger instance.

    Returns:
        AuditLogger instance
    """
    if not hasattr(get_audit_logger, '_instance'):
        get_audit_logger._instance = AuditLogger()
    return get_audit_logger._instance


def log_trade_decision(
    symbol: str,
    direction: str,
    signal_value: float,
    entry_threshold: float,
    exit_threshold: float,
    position_size: int,
    portfolio_value: float,
    reason: str = ""
):
    """Log a complete trade decision.

    Args:
        symbol: Stock symbol
        direction: enter/exit
        signal_value: Current signal value
        entry_threshold: Entry threshold
        exit_threshold: Exit threshold
        position_size: Number of shares
        portfolio_value: Current portfolio value
        reason: Additional context
    """
    logger = get_audit_logger()

    details = {
        'signal_value': signal_value,
        'threshold': entry_threshold if direction == 'enter' else exit_threshold,
        'position_size': position_size,
        'portfolio_value': portfolio_value,
        'reason': reason
    }

    logger.log_event('trade', symbol, f'trade_{direction}', details)


def log_risk_violation(
    violation_type: str,
    symbol: str,
    current_value: float,
    limit_value: float,
    action: str
):
    """Log a risk limit violation.

    Args:
        violation_type: Type of violation (position, drawdown, daily_loss)
        symbol: Stock symbol
        current_value: Current value that exceeded limit
        limit_value: Limit that was exceeded
        action: Action taken
    """
    logger = get_audit_logger()

    details = {
        'violation_type': violation_type,
        'current_value': current_value,
        'limit_value': limit_value,
        'action': action
    }

    logger.log_event('risk_violation', symbol, f'violation_{violation_type}', details)
