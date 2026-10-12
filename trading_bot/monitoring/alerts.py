"""Alert system for trading monitoring."""

import logging
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)


@dataclass
class Alert:
    """Represents a single alert."""
    alert_type: str
    symbol: str
    message: str
    severity: str = "info"  # info, warning, critical
    timestamp: datetime = field(default_factory=datetime.now)
    details: dict = field(default_factory=dict)


class AlertManager:
    """Manage trading system alerts.

    Supports multiple alert channels:
    - Console logging
    - Email notifications
    - File logging
    """

    SEVERITY_LEVELS = {
        'info': 0,
        'warning': 1,
        'critical': 2
    }

    def __init__(
        self,
        email_config: Optional[dict] = None,
        min_severity: str = "info",
        log_file: str = "alerts.log"
    ):
        """Initialize alert manager.

        Args:
            email_config: Email configuration dict with 'to', 'from', 'smtp'
            min_severity: Minimum severity to process
            log_file: File to append alerts to
        """
        self.email_config = email_config
        self.min_severity = min_severity
        self.log_file = log_file

        self.alerts: list[Alert] = []
        self.email_alerts: list[Alert] = []

        # Setup file handler
        self._setup_file_handler()

    def _setup_file_handler(self):
        """Setup file handler for alert logging."""
        self.file_handler = logging.FileHandler(self.log_file)
        self.file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        self.file_handler.setFormatter(formatter)

        self.alert_logger = logging.getLogger('alerts')
        self.alert_logger.addHandler(self.file_handler)
        self.alert_logger.setLevel(logging.INFO)

    def _should_alert(self, severity: str) -> bool:
        """Check if alert should be processed based on severity.

        Args:
            severity: Alert severity level

        Returns:
            True if alert should be processed
        """
        current_level = self.SEVERITY_LEVELS.get(severity, 0)
        min_level = self.SEVERITY_LEVELS.get(self.min_severity, 0)
        return current_level >= min_level

    def create_alert(
        self,
        alert_type: str,
        symbol: str,
        message: str,
        severity: str = "info",
        details: dict = None
    ) -> Alert:
        """Create a new alert.

        Args:
            alert_type: Type of alert (risk, order, signal, etc.)
            symbol: Stock symbol
            message: Alert message
            severity: Alert severity (info, warning, critical)
            details: Additional details

        Returns:
            Created Alert object
        """
        if not self._should_alert(severity):
            return None

        alert = Alert(
            alert_type=alert_type,
            symbol=symbol,
            message=message,
            severity=severity,
            details=details or {}
        )

        self.alerts.append(alert)

        # Log to file
        self.alert_logger.info(
            f"[{severity.upper()}] {alert_type}/{symbol}: {message}"
        )

        # Send email if critical
        if severity == "critical" and self.email_config:
            self._send_email_alert(alert)

        return alert

    def _send_email_alert(self, alert: Alert):
        """Send email notification for critical alert.

        Args:
            alert: Alert to send
        """
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_config['from']
            msg['To'] = self.email_config['to']
            msg['Subject'] = f"[TRADING ALERT] {alert.severity.upper()}: {alert.message}"

            body = f"""
Trading Alert
=============

Type: {alert.alert_type}
Symbol: {alert.symbol}
Severity: {alert.severity}
Time: {alert.timestamp.isoformat()}

Message:
{alert.message}

Details:
{alert.details}
"""

            msg.attach(MIMEText(body, 'plain'))

            # Send email
            smtp = smtplib.SMTP(self.email_config['smtp'])
            smtp.starttls()
            if 'username' in self.email_config and 'password' in self.email_config:
                smtp.login(
                    self.email_config['username'],
                    self.email_config['password']
                )
            smtp.sendmail(
                self.email_config['from'],
                self.email_config['to'],
                msg.as_string()
            )
            smtp.quit()

            self.email_alerts.append(alert)
            logger.info(f"Sent email alert for {alert.alert_type}/{alert.symbol}")

        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")

    def log_risk_alert(
        self,
        symbol: str,
        risk_type: str,
        current_value: float,
        limit_value: float
    ):
        """Log a risk-related alert.

        Args:
            symbol: Stock symbol
            risk_type: Type of risk (drawdown, position, daily_loss)
            current_value: Current value
            limit_value: Limit that was exceeded
        """
        message = f"{risk_type} alert: {current_value:.2%} exceeds {limit_value:.2%} limit"
        self.create_alert(
            alert_type='risk',
            symbol=symbol,
            message=message,
            severity='warning',
            details={'risk_type': risk_type, 'current': current_value, 'limit': limit_value}
        )

    def log_order_alert(
        self,
        symbol: str,
        order_id: str,
        status: str,
        details: dict = None
    ):
        """Log an order-related alert.

        Args:
            symbol: Stock symbol
            order_id: Order ID
            status: Order status
            details: Order details
        """
        self.create_alert(
            alert_type='order',
            symbol=symbol,
            message=f"Order {status}: {order_id}",
            severity='info',
            details={'order_id': order_id, 'status': status, **(details or {})}
        )

    def get_alerts(
        self,
        alert_type: str = None,
        severity: str = None
    ) -> list[Alert]:
        """Get filtered alerts.

        Args:
            alert_type: Filter by alert type
            severity: Filter by severity

        Returns:
            List of matching alerts
        """
        filtered = self.alerts

        if alert_type:
            filtered = [a for a in filtered if a.alert_type == alert_type]

        if severity:
            filtered = [a for a in filtered if a.severity == severity]

        return filtered

    def clear_alerts(self, before: datetime = None):
        """Clear old alerts.

        Args:
            before: Clear alerts before this time
        """
        if before:
            self.alerts = [a for a in self.alerts if a.timestamp >= before]
        else:
            self.alerts = []

    def get_summary(self) -> dict:
        """Get alert summary.

        Returns:
            Dictionary with alert counts by type and severity
        """
        summary = {
            'total_alerts': len(self.alerts),
            'by_type': {},
            'by_severity': {},
            'unprocessed': len([a for a in self.alerts if a.severity >= self.min_severity])
        }

        for alert in self.alerts:
            # Count by type
            if alert.alert_type not in summary['by_type']:
                summary['by_type'][alert.alert_type] = 0
            summary['by_type'][alert.alert_type] += 1

            # Count by severity
            if alert.severity not in summary['by_severity']:
                summary['by_severity'][alert.severity] = 0
            summary['by_severity'][alert.severity] += 1

        return summary

    def send_trade_alert(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        order_id: str
    ):
        """Send a trade alert for significant trades.

        Args:
            symbol: Stock symbol
            side: buy/sell
            quantity: Trade quantity
            price: Trade price
            order_id: Order ID
        """
        trade_value = quantity * price
        severity = "warning" if trade_value > 5000 else "info"

        message = f"{side.upper()} {quantity} {symbol} @ ${price:.2f} (Value: ${trade_value:.2f})"

        self.create_alert(
            alert_type='trade',
            symbol=symbol,
            message=message,
            severity=severity,
            details={
                'side': side,
                'quantity': quantity,
                'price': price,
                'order_id': order_id,
                'trade_value': trade_value
            }
        )


# Global alert manager instance
_alert_manager: Optional[AlertManager] = None


def get_alert_manager(email_config: dict = None) -> AlertManager:
    """Get or create global alert manager.

    Args:
        email_config: Optional email configuration

    Returns:
        AlertManager instance
    """
    global _alert_manager

    if _alert_manager is None:
        _alert_manager = AlertManager(email_config=email_config)

    return _alert_manager


def log_alert(
    alert_type: str,
    symbol: str,
    message: str,
    severity: str = "info"
):
    """Convenience function to log an alert.

    Args:
        alert_type: Type of alert
        symbol: Stock symbol
        message: Alert message
        severity: Alert severity
    """
    manager = get_alert_manager()
    manager.create_alert(alert_type, symbol, message, severity)


def log_risk_violation(
    symbol: str,
    risk_type: str,
    current_value: float,
    limit_value: float
):
    """Log a risk violation alert.

    Args:
        symbol: Stock symbol
        risk_type: Type of risk
        current_value: Current value
        limit_value: Limit exceeded
    """
    manager = get_alert_manager()
    manager.log_risk_alert(symbol, risk_type, current_value, limit_value)
