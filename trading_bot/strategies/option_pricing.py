"""Option pricing module with Black-Scholes model and Greeks calculations."""

import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional
import logging
from scipy import stats
import math
from datetime import datetime

logger = logging.getLogger(__name__)


class OptionPricingModel:
    """Black-Scholes option pricing model with Greeks calculations."""

    def __init__(self, risk_free_rate: float = 0.05):
        """Initialize the option pricing model.

        Args:
            risk_free_rate: Risk-free interest rate (default 5%)
        """
        self.risk_free_rate = risk_free_rate
        logger.info(f"Option pricing model initialized with risk-free rate: {risk_free_rate}")

    def black_scholes_price(
        self,
        S: float,  # Current stock price
        K: float,  # Strike price
        T: float,  # Time to expiration (in years)
        r: float,  # Risk-free rate
        sigma: float,  # Volatility
        option_type: str = 'call'  # 'call' or 'put'
    ) -> float:
        """Calculate Black-Scholes option price.

        Args:
            S: Current underlying price
            K: Strike price
            T: Time to expiration in years
            r: Risk-free interest rate
            sigma: Volatility of underlying
            option_type: 'call' or 'put'

        Returns:
            Option price
        """
        if T <= 0:
            # Option has expired
            if option_type.lower() == 'call':
                return max(S - K, 0)
            else:  # put
                return max(K - S, 0)

        # Calculate d1 and d2
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)

        if option_type.lower() == 'call':
            price = S * stats.norm.cdf(d1) - K * np.exp(-r * T) * stats.norm.cdf(d2)
        else:  # put
            price = K * np.exp(-r * T) * stats.norm.cdf(-d2) - S * stats.norm.cdf(-d1)

        return max(price, 0)  # Price cannot be negative

    def calculate_greeks(
        self,
        S: float,  # Current stock price
        K: float,  # Strike price
        T: float,  # Time to expiration (in years)
        r: float,  # Risk-free rate
        sigma: float,  # Volatility
        option_type: str = 'call'  # 'call' or 'put'
    ) -> Dict[str, float]:
        """Calculate option Greeks using Black-Scholes model.

        Args:
            S: Current underlying price
            K: Strike price
            T: Time to expiration in years
            r: Risk-free interest rate
            sigma: Volatility of underlying
            option_type: 'call' or 'put'

        Returns:
            Dictionary containing delta, gamma, theta, vega, rho
        """
        if T <= 0:
            # Option has expired
            if option_type.lower() == 'call':
                delta = 1.0 if S > K else 0.0
            else:  # put
                delta = -1.0 if S < K else 0.0

            return {
                'delta': delta,
                'gamma': 0.0,
                'theta': 0.0,
                'vega': 0.0,
                'rho': 0.0
            }

        # Calculate d1 and d2
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)

        # Common terms
        N_d1 = stats.norm.cdf(d1)
        N_d2 = stats.norm.cdf(d2)
        n_d1 = stats.norm.pdf(d1)  # Standard normal PDF

        if option_type.lower() == 'call':
            delta = N_d1
            theta = (-S * n_d1 * sigma / (2 * np.sqrt(T))
                   - r * K * np.exp(-r * T) * N_d2) / 365  # Per day
            rho = K * T * np.exp(-r * T) * N_d2 / 100  # Per 1% rate change
        else:  # put
            delta = N_d1 - 1
            theta = (-S * n_d1 * sigma / (2 * np.sqrt(T))
                   + r * K * np.exp(-r * T) * stats.norm.cdf(-d2)) / 365  # Per day
            rho = -K * T * np.exp(-r * T) * stats.norm.cdf(-d2) / 100  # Per 1% rate change

        gamma = n_d1 / (S * sigma * np.sqrt(T))
        vega = S * np.sqrt(T) * n_d1 / 100  # Per 1% volatility change

        return {
            'delta': delta,
            'gamma': gamma,
            'theta': theta,
            'vega': vega,
            'rho': rho
        }

    def implied_volatility(
        self,
        market_price: float,  # Observed market price
        S: float,  # Current stock price
        K: float,  # Strike price
        T: float,  # Time to expiration (in years)
        r: float,  # Risk-free rate
        option_type: str = 'call',  # 'call' or 'put'
        tolerance: float = 1e-5,
        max_iterations: int = 100
    ) -> float:
        """Calculate implied volatility using Newton-Raphson method.

        Args:
            market_price: Observed market price of the option
            S: Current underlying price
            K: Strike price
            T: Time to expiration in years
            r: Risk-free interest rate
            option_type: 'call' or 'put'
            tolerance: Convergence tolerance
            max_iterations: Maximum iterations for Newton-Raphson

        Returns:
            Implied volatility (as decimal, e.g., 0.25 for 25%)
        """
        # Check for arbitrage violations
        if option_type.lower() == 'call':
            lower_bound = max(S - K * np.exp(-r * T), 0)
        else:  # put
            lower_bound = max(K * np.exp(-r * T) - S, 0)

        if market_price < lower_bound - 1e-10:  # Allow small tolerance
            logger.warning(f"Market price {market_price} below lower bound {lower_bound} for {option_type}")
            return 0.0

        # Initial volatility guess
        sigma = 0.3  # 30% initial guess

        for i in range(max_iterations):
            # Calculate price and vega at current sigma
            price = self.black_scholes_price(S, K, T, r, sigma, option_type)
            greeks = self.calculate_greeks(S, K, T, r, sigma, option_type)
            vega = greeks['vega'] * 100  # Convert to actual vega (not per 1%)

            # Avoid division by zero
            if abs(vega) < 1e-10:
                break

            # Newton-Raphson update
            price_diff = price - market_price
            if abs(price_diff) < tolerance:
                return sigma

            sigma = sigma - price_diff / vega

            # Ensure volatility stays positive
            sigma = max(sigma, 0.001)  # Minimum 0.1% volatility

            # Check for convergence
            if i > 0 and abs(sigma - sigma_prev) < tolerance:
                break

            sigma_prev = sigma

        # If we didn't converge, return the last value
        logger.warning(f"Implied volatility calculation did not converge after {max_iterations} iterations")
        return sigma

    def calculate_option_metrics(
        self,
        S: float,  # Current stock price
        K: float,  # Strike price
        T: float,  # Time to expiration (in years)
        r: float,  # Risk-free rate
        sigma: float,  # Volatility
        option_type: str = 'call'  # 'call' or 'put'
    ) -> Dict[str, float]:
        """Calculate comprehensive option metrics including price and Greeks.

        Args:
            S: Current underlying price
            K: Strike price
            T: Time to expiration in years
            r: Risk-free interest rate
            sigma: Volatility of underlying
            option_type: 'call' or 'put'

        Returns:
            Dictionary with price, delta, gamma, theta, vega, rho
        """
        price = self.black_scholes_price(S, K, T, r, sigma, option_type)
        greeks = self.calculate_greeks(S, K, T, r, sigma, option_type)

        return {
            'price': price,
            'delta': greeks['delta'],
            'gamma': greeks['gamma'],
            'theta': greeks['theta'],
            'vega': greeks['vega'],
            'rho': greeks['rho']
        }


def calculate_time_to_expiration(
    expiration_date: str,
    current_date: Optional[str] = None,
    trading_hours_adjustment: bool = True
) -> float:
    """Calculate time to expiration in years.

    Args:
        expiration_date: Expiration date in YYYY-MM-DD format
        current_date: Current date in YYYY-MM-DD format (None for today)
        trading_hours_adjustment: Whether to adjust for trading hours

    Returns:
        Time to expiration in years
    """
    if current_date is None:
        current_date = datetime.now().strftime('%Y-%m-%d')

    current = datetime.strptime(current_date, '%Y-%m-%d')
    expiration = datetime.strptime(expiration_date, '%Y-%m-%d')

    # Calculate calendar days
    days_to_exp = (expiration - current).days

    if days_to_exp < 0:
        return 0.0

    # Convert to years
    # Using 365 days per year for simplicity
    # More sophisticated models might use 252 trading days or actual/365
    years_to_exp = days_to_exp / 365.0

    # Optional: Adjust for trading hours (assuming 9:30 AM to 4:00 PM ET)
    # This is a simplification - in reality, options decay based on calendar time
    # but trading only occurs during market hours
    if trading_hours_adjustment and days_to_exp > 0:
        # Assume 6.5 trading hours per day out of 24
        # This adjustment is approximate and may not be needed for most applications
        # For simplicity, we are keeping calendar time (no adjustment applied)
        pass

    return max(years_to_exp, 0.0)


def parse_option_symbol(option_symbol: str) -> Dict[str, any]:
    """Parse an option symbol into its components.

    Args:
        option_symbol: Option symbol (e.g., 'AAPL240119C00150000')

    Returns:
        Dictionary with underlying, expiration_date, option_type, strike_price
    """
    # Option symbol format: {UNDERLYING}{YY}{MM}{DD}{C/P}{STRIKE*1000}
    # Example: AAPL240119C00150000

    if len(option_symbol) < 15:
        raise ValueError(f"Invalid option symbol format: {option_symbol}")

    # Find where the underlying symbol ends (first digit)
    underlying_end = 0
    for i, char in enumerate(option_symbol):
        if char.isdigit():
            underlying_end = i
            break

    if underlying_end == 0:
        raise ValueError(f"Could not find underlying symbol in: {option_symbol}")

    underlying = option_symbol[:underlying_end]
    remainder = option_symbol[underlying_end:]

    # Parse date part (YYMMDD)
    if len(remainder) < 6:
        raise ValueError(f"Invalid date portion in option symbol: {option_symbol}")

    date_part = remainder[:6]
    year = f"20{date_part[0:2]}"
    month = date_part[2:4]
    day = date_part[4:6]
    expiration_date = f"{year}-{month}-{day}"

    # Parse option type
    option_type_char = remainder[6] if len(remainder) > 6 else None
    if option_type_char not in ['C', 'P']:
        raise ValueError(f"Invalid option type in symbol: {option_symbol}")
    option_type = 'call' if option_type_char == 'C' else 'put'

    # Parse strike price
    strike_part = remainder[7:] if len(remainder) > 7 else None
    if not strike_part or not strike_part.isdigit():
        raise ValueError(f"Invalid strike price in option symbol: {option_symbol}")

    strike_price = int(strike_part) / 1000.0

    return {
        'underlying': underlying,
        'expiration_date': expiration_date,
        'option_type': option_type,
        'strike_price': strike_price,
        'raw_symbol': option_symbol
    }


# Convenience functions
def black_scholes_call(S, K, T, r, sigma):
    """Calculate Black-Scholes call price."""
    model = OptionPricingModel(r)
    return model.black_scholes_price(S, K, T, r, sigma, 'call')


def black_scholes_put(S, K, T, r, sigma):
    """Calculate Black-Scholes put price."""
    model = OptionPricingModel(r)
    return model.black_scholes_price(S, K, T, r, sigma, 'put')


def calculate_greeks(S, K, T, r, sigma, option_type='call'):
    """Calculate option Greeks."""
    model = OptionPricingModel(r)
    return model.calculate_greeks(S, K, T, r, sigma, option_type)


if __name__ == "__main__":
    # Example usage
    # Parameters
    S = 150.0  # Stock price
    K = 150.0  # Strike price
    T = 0.25   # 3 months to expiration
    r = 0.05   # 5% risk-free rate
    sigma = 0.25  # 25% volatility

    model = OptionPricingModel(r)

    # Calculate call price and Greeks
    call_price = model.black_scholes_price(S, K, T, r, sigma, 'call')
    call_greeks = model.calculate_greeks(S, K, T, r, sigma, 'call')

    logger.info(f"Call Price: ${call_price:.2f}")
    logger.info(f"Call Delta: {call_greeks['delta']:.4f}")
    logger.info(f"Call Gamma: {call_greeks['gamma']:.6f}")
    logger.info(f"Call Theta: {call_greeks['theta']:.4f} per day")
    logger.info(f"Call Vega: {call_greeks['vega']:.4f} per 1% vol change")

    # Calculate put price and Greeks
    put_price = model.black_scholes_price(S, K, T, r, sigma, 'put')
    put_greeks = model.calculate_greeks(S, K, T, r, sigma, 'put')

    logger.info(f"\nPut Price: ${put_price:.2f}")
    logger.info(f"Put Delta: {put_greeks['delta']:.4f}")
    logger.info(f"Put Gamma: {put_greeks['gamma']:.6f}")
    logger.info(f"Put Theta: {put_greeks['theta']:.4f} per day")
    logger.info(f"Put Vega: {put_greeks['vega']:.4f} per 1% vol change")

    # Test implied volatility calculation
    market_price = 5.00
    iv = model.implied_volatility(market_price, S, K, T, r, 'call')
    logger.info(f"\nImplied Volatility for ${market_price} call: {iv:.2%}")

    # Test symbol parsing
    try:
        parsed = parse_option_symbol("AAPL240119C00150000")
        logger.info(f"\nParsed symbol: {parsed}")
    except Exception as e:
        logger.error(f"Error parsing symbol: {e}")