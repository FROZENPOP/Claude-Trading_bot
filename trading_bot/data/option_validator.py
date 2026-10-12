"""Options data validator module for checking quality and completeness of option data."""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class OptionsDataValidator:
    """Validate options data quality and completeness."""

    def __init__(self):
        """Initialize options data validator."""
        self.validation_errors = []
        self.validation_warnings = []

    def validate_option_chain(
        self,
        df: pd.DataFrame,
        underlying_symbol: str
    ) -> Dict[str, any]:
        """Validate option chain data for completeness and correctness.

        Args:
            df: DataFrame with option chain data
            underlying_symbol: Expected underlying symbol

        Returns:
            Dictionary with validation results
        """
        self.validation_errors = []
        self.validation_warnings = []

        if df.empty:
            self.validation_errors.append("Option chain DataFrame is empty")
            return self._get_validation_result()

        # Check required columns
        required_columns = [
            'option_symbol', 'underlying_symbol', 'expiration_date',
            'option_type', 'strike_price', 'bid_price', 'ask_price'
        ]

        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            self.validation_errors.append(f"Missing required columns: {missing_columns}")

        # Validate underlying symbol
        if 'underlying_symbol' in df.columns:
            unexpected_underlyings = df[~df['underlying_symbol'].eq(underlying_symbol)]
            if not unexpected_underlyings.empty:
                self.validation_errors.append(
                    f"Found unexpected underlying symbols: {unexpected_underlyings['underlying_symbol'].unique()}"
                )

        # Validate option types
        if 'option_type' in df.columns:
            invalid_types = df[~df['option_type'].isin(['call', 'put'])]
            if not invalid_types.empty:
                self.validation_errors.append(
                    f"Invalid option types found: {invalid_types['option_type'].unique()}"
                )

        # Validate prices
        price_columns = ['bid_price', 'ask_price', 'last_price', 'strike_price']
        for col in price_columns:
            if col in df.columns:
                # Check for negative prices
                negative_prices = df[df[col] < 0]
                if not negative_prices.empty:
                    self.validation_errors.append(
                        f"Negative values found in {col}: {len(negative_prices)} instances"
                    )

                # Check for null prices in required fields
                if col in ['bid_price', 'ask_price']:
                    null_prices = df[df[col].isna()]
                    if not null_prices.empty:
                        self.validation_warnings.append(
                            f"Null values in {col}: {len(null_prices)} instances"
                        )

        # Validate bid-ask spread
        if 'bid_price' in df.columns and 'ask_price' in df.columns:
            # Calculate spread only where both prices exist
            valid_prices = df[df['bid_price'].notna() & df['ask_price'].notna()].copy()
            if not valid_prices.empty:
                valid_prices['spread'] = valid_prices['ask_price'] - valid_prices['bid_price']
                valid_prices['spread_pct'] = (
                    valid_prices['spread'] / valid_prices['bid_price'] * 100
                )

                # Check for negative spreads (ask < bid)
                negative_spread = valid_prices[valid_prices['spread'] < 0]
                if not negative_spread.empty:
                    self.validation_errors.append(
                        f"Negative bid-ask spread (ask < bid): {len(negative_spread)} instances"
                    )

                # Check for excessively wide spreads (>50% of bid price)
                wide_spread = valid_prices[valid_prices['spread_pct'] > 50]
                if not wide_spread.empty:
                    self.validation_warnings.append(
                        f"Excessively wide bid-ask spreads (>50%): {len(wide_spread)} instances"
                    )

        # Validate strike prices
        if 'strike_price' in df.columns:
            # Check for zero strikes
            zero_strikes = df[df['strike_price'] == 0]
            if not zero_strikes.empty:
                self.validation_warnings.append(
                    f"Zero strike prices found: {len(zero_strikes)} instances"
                )

        # Validate expiration dates
        if 'expiration_date' in df.columns:
            try:
                df['expiration_date_parsed'] = pd.to_datetime(df['expiration_date'])
                # Check for expired options
                today = pd.Timestamp.now().date()
                expired = df[df['expiration_date_parsed'].dt.date < today]
                if not expired.empty:
                    self.validation_warnings.append(
                        f"Expired options found: {len(expired)} instances"
                    )

                # Check for unreasonably far future expirations (>2 years)
                far_future = df[
                    df['expiration_date_parsed'].dt.date >
                    (today + timedelta(days=730))
                ]
                if not far_future.empty:
                    self.validation_warnings.append(
                        f"Expirations >2 years in future: {len(far_future)} instances"
                    )
            except Exception as e:
                self.validation_errors.append(f"Error parsing expiration dates: {e}")

        # Validate Greeks if present
        greek_columns = ['delta', 'gamma', 'theta', 'vega']
        for greek in greek_columns:
            if greek in df.columns:
                # Check for values outside reasonable ranges
                if greek == 'delta':
                    # Delta should be between -1 and 1
                    invalid_delta = df[
                        df[greek].notna() &
                        ((df[greek] < -1) | (df[greek] > 1))
                    ]
                    if not invalid_delta.empty:
                        self.validation_errors.append(
                            f"Invalid {greek} values (outside [-1,1]): {len(invalid_delta)} instances"
                        )
                elif greek == 'gamma':
                    # Gamma should be non-negative
                    negative_gamma = df[df[greek] < 0]
                    if not negative_gamma.empty:
                        self.validation_errors.append(
                            f"Negative {greek} values: {len(negative_gamma)} instances"
                        )
                elif greek in ['theta', 'vega']:
                    # These can be positive or negative but check for extreme values
                    extreme_values = df[
                        df[greek].notna() &
                        (abs(df[greek]) > 100)  # Arbitrary large value
                    ]
                    if not extreme_values.empty:
                        self.validation_warnings.append(
                            f"Extreme {greek} values: {len(extreme_values)} instances"
                        )

        # Check for duplicate option symbols
        if 'option_symbol' in df.columns:
            duplicates = df[df.duplicated(subset=['option_symbol'], keep=False)]
            if not duplicates.empty:
                self.validation_errors.append(
                    f"Duplicate option symbols found: {duplicates['option_symbol'].nunique()} unique symbols"
                )

        # Check data freshness if timestamp column exists
        if 'timestamp' in df.columns:
            try:
                df['timestamp_parsed'] = pd.to_datetime(df['timestamp'])
                # Check for stale data (>15 minutes old for US market hours)
                fifteen_min_ago = pd.Timestamp.now() - pd.Timedelta(minutes=15)
                stale_data = df[df['timestamp_parsed'] < fifteen_min_ago]
                if not stale_data.empty:
                    self.validation_warnings.append(
                        f"Stale data (>15 min old): {len(stale_data)} instances"
                    )
            except Exception as e:
                self.validation_warnings.append(f"Could not check data freshness: {e}")

        return self._get_validation_result()

    def validate_historical_option_data(
        self,
        data_dict: Dict[str, pd.DataFrame]
    ) -> Dict[str, any]:
        """Validate historical option data across multiple dates.

        Args:
            data_dict: Dictionary mapping dates to option chain DataFrames

        Returns:
            Dictionary with validation results
        """
        self.validation_errors = []
        self.validation_warnings = []

        if not data_dict:
            self.validation_errors.append("No historical option data provided")
            return self._get_validation_result()

        # Check for gaps in dates
        dates = sorted([pd.Timestamp(date) for date in data_dict.keys()])
        if len(dates) > 1:
            date_gaps = []
            for i in range(1, len(dates)):
                gap = (dates[i] - dates[i-1]).days
                # Expect 1 day gap for consecutive trading days, but allow for weekends
                if gap > 3:  # More than 3 days gap (accounts for weekends)
                    date_gaps.append((dates[i-1], dates[i], gap))

            if date_gaps:
                self.validation_warnings.append(
                    f"Gaps in historical data: {len(date_gaps)} gaps found"
                )
                for start_date, end_date, gap in date_gaps[:5]:  # Show first 5 gaps
                    self.validation_warnings.append(
                        f"  Gap: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} "
                        f"({gap} days)"
                    )

        # Validate each date's data
        for date_str, df in data_dict.items():
            if not df.empty:
                # Extract underlying symbol from first row if available
                underlying = df['underlying_symbol'].iloc[0] if 'underlying_symbol' in df.columns and not df.empty else "UNKNOWN"
                date_validation = self.validate_option_chain(df, underlying)

                # Collect errors and warnings
                self.validation_errors.extend([
                    f"[{date_str}] {error}" for error in date_validation['errors']
                ])
                self.validation_warnings.extend([
                    f"[{date_str}] {warning}" for warning in date_validation['warnings']
                ])

        return self._get_validation_result()

    def validate_option_bars(
        self,
        df: pd.DataFrame,
        option_symbol: str
    ) -> Dict[str, any]:
        """Validate historical option price bars.

        Args:
            df: DataFrame with option bars data
            option_symbol: Expected option symbol

        Returns:
            Dictionary with validation results
        """
        self.validation_errors = []
        self.validation_warnings = []

        if df.empty:
            self.validation_errors.append("Option bars DataFrame is empty")
            return self._get_validation_result()

        # Check required OHLCV columns
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            self.validation_errors.append(f"Missing required columns: {missing_columns}")

        # Validate OHLC relationships
        if all(col in df.columns for col in ['open', 'high', 'low', 'close']):
            # High should be >= Low
            invalid_hl = df[df['high'] < df['low']]
            if not invalid_hl.empty:
                self.validation_errors.append(
                    f"High < Low: {len(invalid_hl)} instances"
                )

            # High should be >= Open and Close
            invalid_ho = df[df['high'] < df['open']]
            if not invalid_ho.empty:
                self.validation_errors.append(
                    f"High < Open: {len(invalid_ho)} instances"
                )

            invalid_hc = df[df['high'] < df['close']]
            if not invalid_hc.empty:
                self.validation_errors.append(
                    f"High < Close: {len(invalid_hc)} instances"
                )

            # Low should be <= Open and Close
            invalid_lo = df[df['low'] > df['open']]
            if not invalid_lo.empty:
                self.validation_errors.append(
                    f"Low > Open: {len(invalid_lo)} instances"
                )

            invalid_lc = df[df['low'] > df['close']]
            if not invalid_lc.empty:
                self.validation_errors.append(
                    f"Low > Close: {len(invalid_lc)} instances"
                )

        # Validate volume
        if 'volume' in df.columns:
            negative_volume = df[df['volume'] < 0]
            if not negative_volume.empty:
                self.validation_errors.append(
                    f"Negative volume: {len(negative_volume)} instances"
                )

            zero_volume = df[df['volume'] == 0]
            if not zero_volume.empty:
                self.validation_warnings.append(
                    f"Zero volume bars: {len(zero_volume)} instances"
                )

        # Check for excessive price jumps (>50% change between consecutive bars)
        if 'close' in df.columns and len(df) > 1:
            df = df.sort_values('timestamp' if 'timestamp' in df.columns else df.index)
            price_changes = df['close'].pct_change().abs()
            extreme_changes = price_changes[price_changes > 0.5]  # >50% change
            if not extreme_changes.empty:
                self.validation_warnings.append(
                    f"Extreme price changes (>50%): {len(extreme_changes)} instances"
                )

        return self._get_validation_result()

    def _get_validation_result(self) -> Dict[str, any]:
        """Get the validation result dictionary.

        Returns:
            Dictionary with validation results
        """
        return {
            'valid': len(self.validation_errors) == 0,
            'errors': self.validation_errors.copy(),
            'warnings': self.validation_warnings.copy(),
            'error_count': len(self.validation_errors),
            'warning_count': len(self.validation_warnings)
        }

    def get_validation_summary(self) -> str:
        """Get a human-readable validation summary.

        Returns:
            Formatted validation summary string
        """
        result = self._get_validation_result()

        summary = []
        summary.append("Options Data Validation Results")
        summary.append("=" * 40)
        summary.append(f"Valid: {result['valid']}")
        summary.append(f"Errors: {result['error_count']}")
        summary.append(f"Warnings: {result['warning_count']}")

        if result['errors']:
            summary.append("\nErrors:")
            for i, error in enumerate(result['errors'], 1):
                summary.append(f"  {i}. {error}")

        if result['warnings']:
            summary.append("\nWarnings:")
            for i, warning in enumerate(result['warnings'], 1):
                summary.append(f"  {i}. {warning}")

        return "\n".join(summary)


def validate_option_data(
    df: pd.DataFrame,
    underlying_symbol: str
) -> Dict[str, any]:
    """Convenience function to validate option chain data.

    Args:
        df: DataFrame with option chain data
        underlying_symbol: Expected underlying symbol

    Returns:
        Dictionary with validation results
    """
    validator = OptionsDataValidator()
    return validator.validate_option_chain(df, underlying_symbol)


if __name__ == "__main__":
    # Example usage
    import pandas as pd

    # Create sample data for testing
    sample_data = pd.DataFrame({
        'option_symbol': ['AAPL240119C00150000', 'AAPL240119P00150000'],
        'underlying_symbol': ['AAPL', 'AAPL'],
        'expiration_date': ['2024-01-19', '2024-01-19'],
        'option_type': ['call', 'put'],
        'strike_price': [150.0, 150.0],
        'bid_price': [4.50, 3.75],
        'ask_price': [4.60, 3.85],
        'last_price': [4.55, 3.80],
        'volume': [100, 150],
        'open_interest': [1000, 800]
    })

    validator = OptionsDataValidator()
    result = validator.validate_option_chain(sample_data, 'AAPL')
    print(validator.get_validation_summary())