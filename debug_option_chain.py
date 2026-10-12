#!/usr/bin/env python3
"""Debug what strikes are available in the option chain."""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add project to path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from research_options_strategies import OptionsDataPipeline

def debug_option_chain():
    """Debug the option chain data."""
    print("OPTION CHAIN DEBUG")
    print("=" * 30)

    pipeline = OptionsDataPipeline(symbol="AAPL")

    lookback_start = "2026-07-19"
    end_date = "2026-09-07"

    print(f"Loading option chain data for {end_date}")

    option_chain = pipeline.get_option_chain_data(end_date)

    print(f"Total option chain rows: {len(option_chain)}")
    print(f"Columns: {list(option_chain.columns)}")

    if len(option_chain) > 0:
        print(f"\nFirst few rows:")
        print(option_chain.head())

        # Check unique values
        print(f"\nUnique option types: {option_chain['option_type'].unique()}")
        print(f"Unique symbols: {option_chain['symbol'].unique()[:5]}...")  # First 5

        # Check expiration dates
        if 'expiration_date' in option_chain.columns:
            exp_dates = option_chain['expiration_date'].dropna().unique()
            print(f"Unique expiration dates: {sorted(exp_dates)[:10]}...")  # First 10

            # Calculate days to expiration for current date
            current_date = datetime(2026, 9, 7)  # From our test
            option_chain['days_to_exp'] = option_chain['expiration_date'].apply(
                lambda x: (datetime.strptime(x, '%Y-%m-%d') - current_date).days if pd.notna(x) else None
            )

            print(f"\nDays to expiration stats:")
            print(f"  Min: {option_chain['days_to_exp'].min()}")
            print(f"  Max: {option_chain['days_to_exp'].max()}")
            print(f"  Mean: {option_chain['days_to_exp'].mean()}")

            # Check preferred DTEs from strategy
            preferred_dte = [21, 30, 45, 60]
            print(f"\nChecking for preferred DTEs: {preferred_dte}")

            for dte in preferred_dte:
                count = len(option_chain[option_chain['days_to_exp'] == dte])
                print(f"  DTE {dte}: {count} options")

                if count > 0:
                    # Show sample of strikes for this DTE - using correct column names
                    sample = option_chain[option_chain['days_to_exp'] == dte][['strike_price', 'option_type', 'bid_price', 'ask_price']].head()
                    print(f"    Sample: {sample.to_string()}")

        # Check strike prices
        if 'strike_price' in option_chain.columns:
            strikes = option_chain['strike_price'].dropna().unique()
            print(f"\nStrike price stats:")
            print(f"  Min: {strikes.min()}")
            print(f"  Max: {strikes.max()}")
            print(f"  Count: {len(strikes)}")
            print(f"  Sample strikes: {sorted(strikes)[:10]} ... {sorted(strikes)[-10:]}")

            # Check what's around our underlying price
            underlying_price = 136.8853209779345
            atm_strike = round(underlying_price)
            print(f"\nAround underlying price {underlying_price} (ATM strike {atm_strike}):")

            # Find strikes near ATM
            near_atm = option_chain[
                (option_chain['strike_price'] >= atm_strike - 5) &
                (option_chain['strike_price'] <= atm_strike + 5)
            ][['strike_price', 'option_type', 'bid_price', 'ask_price', 'days_to_exp']].dropna()

            print(f"  Found {len(near_atm)} options within 5 points of ATM")
            if len(near_atm) > 0:
                print(f"  Sample:\n{near_atm.head(10).to_string()}")

        # Check bid/ask data availability
        print(f"\nBid/Ask data availability:")
        print(f"  Has bid_price: {option_chain['bid_price'].notna().sum()}/{len(option_chain)}")
        print(f"  Has ask_price: {option_chain['ask_price'].notna().sum()}/{len(option_chain)}")
        print(f"  Has both: {(option_chain['bid_price'].notna() & option_chain['ask_price'].notna()).sum()}/{len(option_chain)}")

        # Check mid prices for a few strikes
        print(f"\nChecking mid price calculation:")
        valid_bidask = option_chain[
            option_chain['bid_price'].notna() & option_chain['ask_price'].notna() &
            (option_chain['bid_price'] > 0) & (option_chain['ask_price'] > 0)
        ].copy()

        if len(valid_bidask) > 0:
            valid_bidask['mid_price'] = (valid_bidask['bid_price'] + valid_bidask['ask_price']) / 2
            print(f"  Valid bid/ask rows: {len(valid_bidask)}")
            print(f"  Mid price stats:")
            print(f"    Min: {valid_bidask['mid_price'].min()}")
            print(f"    Max: {valid_bidask['mid_price'].max()}")
            print(f"    Mean: {valid_bidask['mid_price'].mean()}")

if __name__ == "__main__":
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    debug_option_chain()
    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")