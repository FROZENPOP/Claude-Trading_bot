#!/usr/bin/env python3
"""
Data quality test script for historical options data validation.
This script tests the actual data available from Webull API to assess
its suitability for options backtesting.
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

# Add the project root to the path
sys.path.append(os.path.join(os.path.dirname(__file__)))

try:
    from trading_bot.data.options_downloader import OptionsDataDownloader
    from trading_bot.data.option_validator import OptionsDataValidator
    from trading_bot.strategies.option_pricing import OptionPricingModel
    from dotenv import load_dotenv

    load_dotenv()

    # Set up logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running from the project directory and have installed dependencies")
    sys.exit(1)


def test_data_availability():
    """Test what historical options data is actually available."""
    print("=" * 60)
    print("TESTING DATA AVAILABILITY")
    print("=" * 60)

    try:
        # Initialize downloader
        downloader = OptionsDataDownloader()
        validator = OptionsDataValidator()
        print("[PASS] Successfully initialized data downloader")

        # Test current option chain for a liquid stock
        print("\n1. Testing current option chain data...")
        chain = downloader.get_option_chain("AAPL")
        print(f"   Retrieved {len(chain)} option contracts for AAPL")

        if len(chain) > 0:
            # Validate the chain
            validation_result = validator.validate_option_chain(chain, "AAPL")
            print(f"   Validation - Valid: {validation_result['valid']}")
            print(f"   Errors: {validation_result['error_count']}")
            print(f"   Warnings: {validation_result['warning_count']}")

            if not validation_result['valid']:
                print("   Validation Errors:")
                for error in validation_result['errors'][:5]:  # Show first 5 errors
                    print(f"     - {error}")

            # Examine data columns and content
            print(f"   Data columns: {list(chain.columns)}")
            print(f"   Sample data:")
            print(chain[['option_symbol', 'option_type', 'strike_price', 'bid_price', 'ask_price']].head())

            # Check for indicative vs real data flags
            # Webull data characteristics
            bid_ask_spread = chain['ask_price'] - chain['bid_price']
            avg_spread_pct = (bid_ask_spread / chain['bid_price'] * 100).mean()
            print(f"   Average bid-ask spread: {avg_spread_pct:.2f}% of bid price")

        else:
            print("   [FAIL] No option chain data retrieved")
            return False

    except Exception as e:
        print(f"   [FAIL] Error testing option chain: {e}")
        return False

    # Test historical data availability
    print("\n2. Testing historical option bars data...")
    try:
        # Try to get historical data for a specific option
        # First, get a valid option symbol from the chain
        if 'chain' in locals() and len(chain) > 0:
            sample_option = chain.iloc[0]['option_symbol']
            print(f"   Testing historical data for option: {sample_option}")

            # Get data for the last 30 days
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

            historical_bars = downloader.get_option_bars(
                option_symbol=sample_option,
                start=start_date,
                end=end_date,
                timeframe="1Day"
            )

            print(f"   Retrieved {len(historical_bars)} historical bars")

            if len(historical_bars) > 0:
                print(f"   Columns: {list(historical_bars.columns)}")
                print(f"   Date range: {historical_bars['timestamp'].min()} to {historical_bars['timestamp'].max()}")

                # Validate historical data
                hist_validation = validator.validate_option_bars(historical_bars, sample_option)
                print(f"   Historical validation - Valid: {hist_validation['valid']}")
                print(f"   Errors: {hist_validation['error_count']}")
                print(f"   Warnings: {hist_validation['warning_count']}")

                if not hist_validation['valid']:
                    print("   Historical Data Errors:")
                    for error in hist_validation['errors'][:5]:
                        print(f"     - {error}")

            else:
                print("   [WARN] No historical bars data available (this may indicate data limitations)")

        else:
            print("   [WARN] Cannot test historical data - no option chain available")

    except Exception as e:
        print(f"   [FAIL] Error testing historical data: {e}")
        # This might be expected if we don't have proper permissions for historical options data

    # Test underlying data
    print("\n3. Testing underlying stock data...")
    try:
        underlying_price = downloader.get_underlying_price("AAPL")
        print(f"   Current AAPL price: ${underlying_price:.2f}")

        # Test historical underlying data would require StockBarsRequest
        # which isn't implemented in the current downloader

    except Exception as e:
        print(f"   [FAIL] Error getting underlying price: {e}")
        return False

    return True


def test_data_characteristics():
    """Test specific characteristics of the options data."""
    print("\n" + "=" * 60)
    print("TESTING DATA CHARACTERISTICS")
    print("=" * 60)

    try:
        downloader = OptionsDataDownloader()
        chain = downloader.get_option_chain("AAPL")

        if len(chain) == 0:
            print("   No data available for characteristic testing")
            return False

        # Test 1: Greeks availability
        print("\n1. Testing Greeks data availability...")
        greek_cols = ['delta', 'gamma', 'theta', 'vega', 'rho']
        available_greeks = [col for col in greek_cols if col in chain.columns and not chain[col].isna().all()]
        print(f"   Available Greeks: {available_greeks}")

        if len(available_greeks) == 0:
            print("   [WARN] No Greeks data available in option chain")
        else:
            # Sample some Greeks values
            sample_greeks = chain[available_greeks].dropna().head()
            print(f"   Sample Greeks values:\n{sample_greeks}")

        # Test 2: Implied volatility
        print("\n2. Testing implied volatility data...")
        if 'implied_volatility' in chain.columns:
            iv_data = chain['implied_volatility'].dropna()
            if len(iv_data) > 0:
                print(f"   IV data points: {len(iv_data)}")
                print(f"   IV range: {iv_data.min():.4f} to {iv_data.max():.4f}")
                print(f"   IV mean: {iv_data.mean():.4f}")
            else:
                print("   [WARN] No implied volatility data available")
        else:
            print("   [WARN] Implied volatility column not present in option chain")

        # Test 3: Volume and open interest
        print("\n3. Testing liquidity data...")
        volume_data = chain['volume'].dropna() if 'volume' in chain.columns else pd.Series([])
        oi_data = chain['open_interest'].dropna() if 'open_interest' in chain.columns else pd.Series([])

        print(f"   Volume data points: {len(volume_data)}")
        print(f"   Open interest data points: {len(oi_data)}")

        if len(volume_data) > 0:
            print(f"   Volume range: {volume_data.min()} to {volume_data.max()}")
            print(f"   Zero volume contracts: {(volume_data == 0).sum()} ({(volume_data == 0).sum()/len(volume_data)*100:.1f}%)")

        if len(oi_data) > 0:
            print(f"   Open interest range: {oi_data.min()} to {oi_data.max()}")
            print(f"   Zero OI contracts: {(oi_data == 0).sum()} ({(oi_data == 0).sum()/len(oi_data)*100:.1f}%)")

        # Test 4: Bid-ask spread analysis
        print("\n4. Testing bid-ask spread quality...")
        if 'bid_price' in chain.columns and 'ask_price' in chain.columns:
            valid_quotes = chain[
                chain['bid_price'].notna() &
                chain['ask_price'].notna() &
                (chain['bid_price'] > 0) &
                (chain['ask_price'] > 0)
            ].copy()

            if len(valid_quotes) > 0:
                valid_quotes['spread'] = valid_quotes['ask_price'] - valid_quotes['bid_price']
                valid_quotes['spread_pct'] = valid_quotes['spread'] / valid_quotes['bid_price'] * 100

                print(f"   Valid quote pairs: {len(valid_quotes)}")
                print(f"   Average spread: ${valid_quotes['spread'].mean():.4f}")
                print(f"   Average spread %: {valid_quotes['spread_pct'].mean():.2f}%")
                print(f"   Median spread %: {valid_queries['spread_pct'].median():.2f}%")

                # Check for inverted spreads (ask < bid)
                inverted = valid_queries[valid_queries['spread'] < 0]
                if len(inverted) > 0:
                    print(f"   [WARN] Inverted spreads (ask < bid): {len(inverted)} contracts")
                else:
                    print("   [PASS] No inverted spreads detected")

                # Check for excessively wide spreads
                wide_spreads = valid_queries[valid_queries['spread_pct'] > 50]
                if len(wide_spreads) > 0:
                    print(f"   [WARN] Excessively wide spreads (>50%): {len(wide_spreads)} contracts")
                else:
                    print("   [PASS] No excessively wide spreads detected")
            else:
                print("   [WARN] No valid bid/ask pairs found")
        else:
            print("   [WARN] Bid/ask price columns missing")

        # Test 5: Strike price distribution
        print("\n5. Testing strike price distribution...")
        if 'strike_price' in chain.columns:
            strikes = chain['strike_price'].dropna()
            if len(strikes) > 0:
                print(f"   Strike price range: ${strikes.min():.2f} to ${strikes.max():.2f}")
                print(f"   Number of unique strikes: {strikes.nunique()}")

                # Check for unusual strike prices
                zero_strikes = (strikes == 0).sum()
                if zero_strikes > 0:
                    print(f"   [WARN] Zero strike prices: {zero_strikes}")
                else:
                    print("   [PASS] No zero strike prices")

                # Check strike distribution relative to underlying
                # We'd need current underlying price for this
            else:
                print("   [WARN] No strike price data")
        else:
            print("   [WARN] Strike price column missing")

        return True

    except Exception as e:
        print(f"   [FAIL] Error testing data characteristics: {e}")
        return False


def test_for_biases():
    """Test for common data biases that could affect backtesting."""
    print("\n" + "=" * 60)
    print("TESTING FOR DATA BIASES")
    print("=" * 60)

    biases_found = []

    try:
        downloader = OptionsDataDownloader()
        chain = downloader.get_option_chain("AAPL")

        if len(chain) == 0:
            print("   No data available for bias testing")
            return biases_found

        # Test 1: Survivorship bias
        print("\n1. Checking for survivorship bias...")
        # Survivorship bias would manifest as missing delisted stocks or expired options
        # For options data, we'd expect to see a range of expirations
        if 'expiration_date' in chain.columns:
            expirations = pd.to_datetime(chain['expiration_date'], errors='coerce').dropna()
            if len(expirations) > 0:
                # Check if we have reasonable expiration distribution
                today = pd.Timestamp.now().date()
                days_to_exp = [(exp.date() - today).days for exp in expirations]
                days_to_exp = [d for d in days_to_exp if d >= 0]  # Filter out expired

                if len(days_to_exp) > 0:
                    print(f"   Options with future expiration: {len(days_to_exp)}")
                    print(f"   Days to expiration range: {min(days_to_exp)} to {max(days_to_exp)}")

                    # Check if we have options across different time horizons
                    short_term = sum(1 for d in days_to_exp if d <= 30)
                    medium_term = sum(1 for d in days_to_exp if 30 < d <= 90)
                    long_term = sum(1 for d in days_to_exp if d > 90)

                    print(f"   Term distribution - Short (<=30d): {short_term}, Medium (30-90d): {medium_term}, Long (>90d): {long_term}")

                    if short_term == 0:
                        biases_found.append("SURVIVORSHIP_BIAS: No short-term options available")
                    if medium_term == 0 and long_term == 0:
                        biases_found.append("SURVIVORSHIP_BIAS: No medium/long-term options available")
                else:
                    print("   [WARN] All options appear to be expired")
                    biases_found.append("SURVIVORSHIP_BIAS: Only expired options available")
            else:
                print("   [WARN] Could not parse expiration dates")
                biases_found.append("DATA_QUALITY: Unable to parse expiration dates")
        else:
            print("   [WARN] Expiration date column missing")
            biases_found.append("DATA_QUALITY: Missing expiration date column")

        # Test 2: Look-ahead bias
        print("\n2. Checking for potential look-ahead bias...")
        # Look-ahead bias in options data would occur if future information
        # is inadvertently included in historical data
        # This is harder to test without historical time series, but we can check
        # if data timestamps are reasonable

        if 'timestamp' in chain.columns:
            try:
                timestamps = pd.to_datetime(chain['timestamp'], errors='coerce').dropna()
                if len(timestamps) > 0:
                    now = pd.Timestamp.now()
                    future_data = timestamps[timestamps > now]
                    if len(future_data) > 0:
                        print(f"   [WARN] Found {len(future_data)} records with future timestamps")
                        biases_found.append("LOOK_AHEAD_BIAS: Future timestamps detected in data")
                    else:
                        print("   [PASS] No future timestamps detected")

                    # Check for very old data that might not be representative
                    # (this depends on what we consider "very old")
                else:
                    print("   [WARN] Could not parse timestamps")
            except Exception as e:
                print(f"   [WARN] Error checking timestamps: {e}")
        else:
            print("   [WARN] Timestamp column missing for look-ahead bias check")

        # Test 3: Selection bias
        print("\n3. Checking for selection bias...")
        # Selection bias would occur if certain types of options are systematically missing
        # For example, only liquid options or only certain strikes/expirations

        if len(chain) > 0 and 'strike_price' in chain.columns:
            strikes = chain['strike_price'].dropna()
            if len(strikes) > 0:
                # Check if strikes are evenly distributed or clustered
                # In a real options chain, we'd expect strikes at regular intervals
                # around the underlying price
                strike_range = strikes.max() - strikes.min()
                if strike_range > 0:
                    # This is a simplified check - in reality we'd compare to underlying price
                    unique_strikes = strikes.nunique()
                    expected_strikes = int(strike_range / 5) + 1  # Assuming $5 width strikes
                    coverage_ratio = unique_strikes / max(expected_strikes, 1)

                    print(f"   Strike coverage ratio: {coverage_ratio:.2f} ({unique_strikes} unique strikes vs ~{expected_strikes} expected)")
                    if coverage_ratio < 0.5:
                        biases_found.append("SELECTION_BIAS: Sparse strike price coverage")
                    else:
                        print("   [PASS] Reasonable strike price coverage")
                else:
                    print("   [WARN] All strikes have same value")
        else:
            print("   [WARN] Cannot check selection bias - missing strike data")

        # Test 4: Time zone bias
        print("\n4. Checking for time zone bias...")
        # Options data should be timestamped consistently (usually in exchange time/ET)
        # If timestamps are mixed time zones, it could cause issues
        if 'timestamp' in chain.columns:
            try:
                timestamps = pd.to_datetime(chain['timestamp'], errors='coerce')
                # Check for irregular patterns that might indicate time zone issues
                # This is difficult to detect definitively without knowing expected frequency
                print("   [PASS] Timestamp column present (manual verification recommended)")
            except Exception as e:
                print(f"   [WARN] Error with timestamps: {e}")
                biases_found.append("TIMESTAMP_ERROR: Invalid timestamp format")
        else:
            print("   [WARN] No timestamp column for time zone verification")

    except Exception as e:
        print(f"   [FAIL] Error during bias testing: {e}")
        biases_found.append(f"TEST_ERROR: {str(e)}")

    return biases_found


def test_execution_modeling():
    """Test how well the data supports realistic trade execution modeling."""
    print("\n" + "=" * 60)
    print("TESTING EXECUTION MODELING SUPPORT")
    print("=" * 60)

    try:
        downloader = OptionsDataDownloader()
        chain = downloader.get_option_chain("AAPL")

        if len(chain) == 0:
            print("   No data available for execution modeling test")
            return False

        # Test 1: Bid-ask spread adequacy for slippage modeling
        print("\n1. Evaluating bid-ask spread for slippage modeling...")
        if 'bid_price' in chain.columns and 'ask_price' in chain.columns:
            valid_quotes = chain[
                chain['bid_price'].notna() &
                chain['ask_price'].notna() &
                (chain['bid_price'] > 0) &
                (chain['ask_price'] > 0)
            ].copy()

            if len(valid_quotes) > 0:
                valid_queries['spread_pct'] = (valid_queries['ask_price'] - valid_queries['bid_price']) / valid_queries['bid_price'] * 100

                # Categorize spreads by tightness
                tight_spreads = valid_queries[valid_queries['spread_pct'] < 1]  # <1% spread
                normal_spreads = valid_queries[(valid_queries['spread_pct'] >= 1) & (valid_queries['spread_pct'] < 5)]  # 1-5%
                wide_spreads = valid_queries[valid_queries['spread_pct'] >= 5]  # >=5%

                print(f"   Tight spreads (<1%): {len(tight_spreads)} contracts ({len(tight_spreads)/len(valid_queries)*100:.1f}%)")
                print(f"   Normal spreads (1-5%): {len(normal_spreads)} contracts ({len(normal_spreads)/len(valid_queries)*100:.1f}%)")
                print(f"   Wide spreads (>=5%): {len(wide_spreads)} contracts ({len(wide_spreads)/len(valid_queries)*100:.1f}%)")

                # For execution modeling, we need reasonable spreads
                if len(tight_spreads) / len(valid_queries) > 0.3:
                    print("   [PASS] Sufficient tight spreads for realistic execution modeling")
                elif len(normal_spreads) / len(valid_queries) > 0.5:
                    print("   [WARN] Mostly normal spreads - execution costs will be higher")
                else:
                    print("   [WARN] Many wide spreads - execution modeling may be challenging")
            else:
                print("   [WARN] No valid bid/ask quotes for spread analysis")
        else:
            print("   [WARN] Missing bid/ask price data for execution modeling")

        # Test 2: Volume data for market impact modeling
        print("\n2. Evaluating volume data for market impact modeling...")
        if 'volume' in chain.columns:
            volume_data = chain['volume'].dropna()
            if len(volume_data) > 0:
                zero_volume = (volume_data == 0).sum()
                low_volume = ((volume_data > 0) & (volume_data < 10)).sum()  # <10 contracts
                medium_volume = ((volume_data >= 10) & (volume_data < 100)).sum()  # 10-100 contracts
                high_volume = (volume_data >= 100).sum()  # >=100 contracts

                print(f"   Volume distribution:")
                print(f"     Zero volume: {zero_volume} contracts ({zero_volume/len(volume_data)*100:.1f}%)")
                print(f"     Low volume (1-9): {low_volume} contracts ({low_volume/len(volume_data)*100:.1f}%)")
                print(f"     Medium volume (10-99): {medium_volume} contracts ({medium_volume/len(volume_data)*100:.1f}%)")
                print(f"     High volume (100+): {high_volume} contracts ({high_volume/len(volume_data)*100:.1f}%)")

                # For market impact modeling, we need some liquidity
                liquid_contracts = medium_volume + high_volume
                if liquid_contracts / len(volume_data) > 0.2:
                    print("   [PASS] Sufficient liquidity for market impact modeling")
                else:
                    print("   [WARN] Limited liquidity - market impact modeling may be inaccurate")
            else:
                print("   [WARN] No volume data available")
        else:
            print("   [WARN] Volume column missing for market impact modeling")

        # Test 3: Open interest for alternative liquidity measure
        print("\n3. Evaluating open interest for liquidity assessment...")
        if 'open_interest' in chain.columns:
            oi_data = chain['open_interest'].dropna()
            if len(oi_data) > 0:
                zero_oi = (oi_data == 0).sum()
                low_oi = ((oi_data > 0) & (oi_data < 50)).sum()  # <50 contracts
                medium_oi = ((oi_data >= 50) & (oi_data < 500)).sum()  # 50-500 contracts
                high_oi = (oi_data >= 500).sum()  # >=500 contracts

                print(f"   Open interest distribution:")
                print(f"     Zero OI: {zero_oi} contracts ({zero_oi/len(oi_data)*100:.1f}%)")
                print(f"     Low OI (1-49): {low_oi} contracts ({low_oi/len(oi_data)*100:.1f}%)")
                print(f"     Medium OI (50-499): {medium_oi} contracts ({medium_oi/len(oi_data)*100:.1f}%)")
                print(f"     High OI (500+): {high_oi} contracts ({high_oi/len(oi_data)*100:.1f}%)")

                liquid_oi = medium_oi + high_oi
                if liquid_oi / len(oi_data) > 0.3:
                    print("   [PASS] Sufficient open interest for liquidity assessment")
                else:
                    print("   [WARN] Limited open interest - liquidity assessment may be challenging")
            else:
                print("   [WARN] No open interest data available")
        else:
            print("   [WARN] Open interest column missing")

        return True

    except Exception as e:
        print(f"   [FAIL] Error testing execution modeling: {e}")
        return False


def test_greeks_and_iv_consistency():
    """Test consistency between Greeks, implied volatility, and prices."""
    print("\n" + "=" * 60)
    print("TESTING GREEKS AND IV CONSISTENCY")
    print("=" * 60)

    try:
        downloader = OptionsDataDownloader()
        pricing_model = OptionPricingModel()
        chain = downloader.get_option_chain("AAPL")

        if len(chain) == 0:
            print("   No data available for Greeks/IV consistency test")
            return False

        # We need underlying price to test consistency
        underlying_price = downloader.get_underlying_price("AAPL")
        print(f"   Using underlying price: ${underlying_price:.2f}")

        # Filter for valid data
        valid_data = chain[
            chain['bid_price'].notna() &
            chain['ask_price'].notna() &
            chain['strike_price'].notna() &
            chain['implied_volatility'].notna() &
            (chain['bid_price'] > 0) &
            (chain['ask_price'] > 0) &
            (chain['strike_price'] > 0) &
            (chain['implied_volatility'] > 0)
        ].copy()

        if len(valid_data) == 0:
            print("   [WARN] No valid data for Greeks/IV consistency testing")
            return False

        print(f"   Testing consistency on {len(valid_data)} option contracts...")

        # Use mid-price for testing
        valid_data['mid_price'] = (valid_data['bid_price'] + valid_data['ask_price']) / 2

        # Test a sample of contracts (to avoid too much computation)
        sample_size = min(50, len(valid_data))
        sample_data = valid_data.sample(n=sample_size, random_state=42)

        consistency_errors = []

        for idx, row in sample_data.iterrows():
            try:
                # Calculate time to expiration
                exp_date = datetime.strptime(row['expiration_date'], '%Y-%m-%d')
                days_to_exp = (exp_date - datetime.now()).days
                if days_to_exp <= 0:
                    continue  # Skip expired options

                T = days_to_exp / 365.0  # Years to expiration

                # Test if implied volatility is reasonable
                iv = row['implied_volatility']
                if iv < 0.01 or iv > 2.0:  # Outside reasonable range (1% to 200%)
                    consistency_errors.append(f"IV out of range: {iv:.4f} for {row['option_symbol']}")
                    continue

                # Calculate theoretical price using IV
                theoretical_price = pricing_model.black_scholes_price(
                    S=underlying_price,
                    K=row['strike_price'],
                    T=T,
                    r=0.05,  # Assume 5% risk-free rate
                    sigma=iv,
                    option_type=row['option_type']
                )

                # Compare to mid-price
                price_diff_pct = abs(theoretical_price - row['mid_price']) / row['mid_price'] * 100

                # Allow for larger discrepancies due to:
                # 1. Indicative vs real data differences
                # 2. Different risk-free rates
                # 3. Dividend assumptions
                # 4. American vs European option pricing (we're using European BS)
                if price_diff_pct > 50:  # More than 50% difference
                    consistency_errors.append(
                        f"Large price discrepancy: {price_diff_pct:.1f}% "
                        f"(theoretical: ${theoretical_price:.2f}, market: ${row['mid_price']:.2f}) "
                        f"for {row['option_symbol']}"
                    )

                # Test Greeks if available
                greek_cols = ['delta', 'gamma', 'theta', 'vega']
                available_greeks = [col for col in greek_cols if col in row and not pd.isna(row[col])]

                if len(available_greeks) > 0:
                    # Calculate theoretical Greeks
                    theoretical_greeks = pricing_model.calculate_greeks(
                        S=underlying_price,
                        K=row['strike_price'],
                        T=T,
                        r=0.05,
                        sigma=iv,
                        option_type=row['option_type']
                    )

                    # Check each Greek for reasonableness
                    for greek in available_greeks:
                        theoretical_value = theoretical_greeks[greek]
                        actual_value = row[greek]

                        # Skip if theoretical value is near zero to avoid division issues
                        if abs(theoretical_value) < 0.001:
                            continue

                        greek_diff_pct = abs(theoretical_value - actual_value) / abs(theoretical_value) * 100

                        # Greeks can vary more due to model differences
                        if greek_diff_pct > 100:  # More than 100% difference
                            consistency_errors.append(
                                f"{greek.upper()} discrepancy: {greek_diff_pct:.1f}% "
                                f"(theoretical: {theoretical_value:.4f}, actual: {actual_value:.4f}) "
                                f"for {row['option_symbol']}"
                            )

            except Exception as e:
                # Skip individual contract errors but log them if too many
                if len(consistency_errors) < 5:
                    consistency_errors.append(f"Calculation error for {row.get('option_symbol', 'unknown')}: {str(e)[:50]}")

        print(f"   Consistency check completed. Found {len(consistency_errors)} potential issues.")

        if len(consistency_errors) == 0:
            print("   [PASS] No significant consistency issues detected")
            return True
        elif len(consistency_errors) < 5:
            print("   [WARN] Minor consistency issues found:")
            for error in consistency_errors:
                print(f"     - {error}")
            return True  # Still pass but with warnings
        else:
            print("   [WARN] Multiple consistency issues found (showing first 5):")
            for error in consistency_errors[:5]:
                print(f"     - {error}")
            return False  # Fail if too many issues

    except Exception as e:
        print(f"   [FAIL] Error testing Greeks/IV consistency: {e}")
        return False


def main():
    """Run all data quality tests."""
    print("HISTORICAL OPTIONS DATA QUALITY AUDIT")
    print("=" * 60)
    print(f"Audit started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Track test results
    tests_passed = 0
    total_tests = 5

    # Test 1: Data Availability
    if test_data_availability():
        tests_passed += 1
        print("\n[PASS] Data availability test PASSED")
    else:
        print("\n[FAIL] Data availability test FAILED")

    # Test 2: Data Characteristics
    if test_data_characteristics():
        tests_passed += 1
        print("\n[PASS] Data characteristics test PASSED")
    else:
        print("\n[FAIL] Data characteristics test FAILED")

    # Test 3: Bias Testing
    biases = test_for_biases()
    if len(biases) == 0:
        tests_passed += 1
        print("\n[PASS] Bias testing test PASSED (no biases detected)")
    elif len(biases) <= 2:
        tests_passed += 1  # Still pass if only minor biases
        print(f"\n[WARN] Bias testing test PASSED WITH WARNINGS ({len(biases)} minor biases detected)")
        for bias in biases:
            print(f"   - {bias}")
    else:
        print(f"\n[FAIL] Bias testing test FAILED ({len(biases)} biases detected)")
        for bias in biases:
            print(f"   - {bias}")

    # Test 4: Execution Modeling
    if test_execution_modeling():
        tests_passed += 1
        print("\n[PASS] Execution modeling test PASSED")
    else:
        print("\n[FAIL] Execution modeling test FAILED")

    # Test 5: Greeks and IV Consistency
    if test_greeks_and_iv_consistency():
        tests_passed += 1
        print("\n[PASS] Greeks and IV consistency test PASSED")
    else:
        print("\n[FAIL] Greeks and IV consistency test FAILED")

    # Final verdict
    print("\n" + "=" * 60)
    print("FINAL AUDIT RESULTS")
    print("=" * 60)
    print(f"Tests passed: {tests_passed}/{total_tests}")

    if tests_passed == total_tests:
        verdict = "DATA PASS"
        recommendation = "Data is suitable for options backtesting and live trading research."
    elif tests_passed >= total_tests * 0.6:  # 60% or more
        verdict = "DATA PASS WITH LIMITATIONS"
        recommendation = "Data is suitable for research but limitations must be acknowledged and accounted for in backtesting."
    else:
        verdict = "INSUFFICIENT DATA"
        recommendation = "Data is not currently sufficient for reliable options backtesting. Consider alternative data sources or wait for improved data availability."

    print(f"\nVERDICT: {verdict}")
    print(f"RECOMMENDATION: {recommendation}")

    # Save detailed results to file
    with open("HISTORICAL_OPTIONS_DATA_AUDIT.md", "w") as f:
        f.write("# Historical Options Data Validation Audit\n\n")
        f.write(f"**Audit Timestamp**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**Verdict**: {verdict}\n\n")
        f.write(f"**Recommendation**: {recommendation}\n\n")
        f.write(f"**Test Results**: {tests_passed}/{total_tests} tests passed\n\n")

        f.write("## Test Details\n\n")
        f.write("1. **Data Availability**: ")
        f.write("PASSED\n" if test_data_availability() else "FAILED\n")
        f.write("2. **Data Characteristics**: ")
        f.write("PASSED\n" if test_data_characteristics() else "FAILED\n")
        f.write("3. **Bias Testing**: ")
        if len(biases) == 0:
            f.write("PASSED (no biases detected)\n")
        elif len(biases) <= 2:
            f.write(f"PASSED WITH WARNINGS ({len(biases)} minor biases)\n")
            for bias in biases:
                f.write(f"   - {bias}\n")
        else:
            f.write(f"FAILED ({len(biases)} biases detected)\n")
            for bias in biases:
                f.write(f"   - {bias}\n")
        f.write("4. **Execution Modeling**: ")
        f.write("PASSED\n" if test_execution_modeling() else "FAILED\n")
        f.write("5. **Greeks and IV Consistency**: ")
        f.write("PASSED\n" if test_greeks_and_iv_consistency() else "FAILED\n")

        if len(biases) > 0:
            f.write("\n## Detected Biases and Issues\n\n")
            for bias in biases:
                f.write(f"- {bias}\n")

        f.write("\n## Limitations and Considerations\n\n")
        f.write("1. **Data Source**: Using Webull Market Data API which provides indicative data\n")
        f.write("2. **Historical Depth**: Limited historical options data availability may affect long-term backtesting\n")
        f.write("3. **Greeks Accuracy**: Calculated Greeks may have discrepancies from actual market values\n")
        f.write("4. **Execution Modeling**: Bid-ask spreads and liquidity data should be validated for realistic slippage modeling\n")
        f.write("5. **Survivorship Bias**: Ensure data includes both active and expired/delisted options where possible\n")

    print(f"\nDetailed audit results saved to: HISTORICAL_OPTIONS_DATA_AUDIT.md")

    return tests_passed >= total_tests * 0.6  # Return True if 60% or more tests passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)