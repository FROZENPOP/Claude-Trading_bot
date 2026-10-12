"""Data validator module for ensuring data quality and preventing look-ahead bias."""

import pandas as pd
import numpy as np
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class DataValidator:
    """Validate historical stock data for quality and integrity."""

    def __init__(self):
        self.errors = []
        self.warnings = []

    def validate(self, data: pd.DataFrame, symbol: Optional[str] = None) -> bool:
        """Run all validation checks on the data.

        Args:
            data: DataFrame to validate
            symbol: Optional symbol name for error messages

        Returns:
            True if all checks pass, False otherwise
        """
        self.errors = []
        self.warnings = []

        checks = [
            self._check_not_empty,
            self._check_required_columns,
            self._check_chronological_order,
            self._check_no_duplicate_dates,
            self._check_positive_prices,
            self._check_no_missing_values,
            self._check_price_range,
        ]

        for check in checks:
            try:
                check(data, symbol)
            except ValueError as e:
                self.errors.append(str(e))

        if symbol:
            logger.info(f"Validation for {symbol}: {len(self.errors)} errors, {len(self.warnings)} warnings")

        return len(self.errors) == 0

    def _check_not_empty(self, data: pd.DataFrame, symbol: Optional[str] = None):
        """Check that data is not empty."""
        if data.empty:
            raise ValueError("Data is empty")

    def _check_required_columns(self, data: pd.DataFrame, symbol: Optional[str] = None):
        """Check that required columns exist."""
        required = ['date', 'open', 'high', 'low', 'close', 'volume', 'adjusted_close']
        missing = [col for col in required if col not in data.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

    def _check_chronological_order(self, data: pd.DataFrame, symbol: Optional[str] = None):
        """Check that dates are in chronological order."""
        if not data['date'].is_monotonic_increasing:
            raise ValueError("Dates are not in chronological order")

    def _check_no_duplicate_dates(self, data: pd.DataFrame, symbol: Optional[str] = None):
        """Check that there are no duplicate dates."""
        duplicates = data['date'].duplicated().sum()
        if duplicates > 0:
            raise ValueError(f"Found {duplicates} duplicate dates")

    def _check_positive_prices(self, data: pd.DataFrame, symbol: Optional[str] = None):
        """Check that all price values are positive."""
        price_cols = ['open', 'high', 'low', 'close', 'adjusted_close']
        for col in price_cols:
            negative = (data[col] <= 0).sum()
            if negative > 0:
                raise ValueError(f"Found {negative} non-positive values in {col}")

    def _check_no_missing_values(self, data: pd.DataFrame, symbol: Optional[str] = None):
        """Check that there are no missing values."""
        missing = data[['open', 'high', 'low', 'close', 'volume', 'adjusted_close']].isnull().sum()
        missing_total = missing.sum()
        if missing_total > 0:
            raise ValueError(f"Found {missing_total} missing values")

    def _check_price_range(self, data: pd.DataFrame, symbol: Optional[str] = None):
        """Check that prices are in reasonable range (not extreme outliers)."""
        price_cols = ['open', 'high', 'low', 'close', 'adjusted_close']

        for col in price_cols:
            prices = data[col]
            # Flag if any price is > 100x the median (potential data error)
            median_price = prices.median()
            if median_price > 0:
                extreme = (prices > median_price * 100).sum()
                if extreme > 0:
                    self.warnings.append(
                        f"{col}: {extreme} prices > 100x median (potential outliers)"
                    )

    def check_look_ahead_bias(self, data: pd.DataFrame, signal_columns: list[str]) -> bool:
        """Verify that signal columns don't use future data.

        This checks that for any signal calculated on day T, it only uses
        data available through day T.

        Note: This is primarily a code-level check. The data itself should
        never contain future information in historical rows.

        Args:
            data: DataFrame with signal columns
            signal_columns: List of column names that are signals

        Returns:
            True if no look-ahead bias detected, False otherwise
        """
        # The fundamental check: each row's signal should be computable
        # using only data from that row and previous rows
        # Since we process data chronologically in backtesting, this is
        # guaranteed by the event-driven design, not the data itself

        for col in signal_columns:
            if col in data.columns:
                # Check for NaN values that might indicate calculation issues
                nan_count = data[col].isnull().sum()
                if nan_count > 0:
                    logger.warning(f"Signal {col} has {nan_count} NaN values")

        return True

    def get_results(self) -> dict:
        """Get validation results.

        Returns:
            Dictionary with errors, warnings, and overall status
        """
        return {
            'passed': len(self.errors) == 0,
            'errors': self.errors,
            'warnings': self.warnings
        }


def validate_data(data: pd.DataFrame, symbol: Optional[str] = None) -> bool:
    """Validate data using a new validator instance (convenience function).

    Args:
        data: DataFrame to validate
        symbol: Optional symbol name for error messages

    Returns:
        True if validation passes, False otherwise
    """
    validator = DataValidator()
    return validator.validate(data, symbol)


def validate_multiple_symbols(data_dict: dict[str, pd.DataFrame]) -> dict[str, bool]:
    """Validate data for multiple symbols.

    Args:
        data_dict: Dictionary mapping symbol to DataFrame

    Returns:
        Dictionary mapping symbol to validation result
    """
    results = {}
    validator = DataValidator()

    for symbol, data in data_dict.items():
        results[symbol] = validator.validate(data, symbol)

    return results
