import os
import sys
from datetime import datetime, date
import json

def get_underlying_price(symbol):
    """Get underlying price using Webull MCP tools."""
    try:
        # Get latest quote for stock
        quote_result = mcp__webull__get_stock_latest_quote(symbols=symbol)
        if quote_result and 'data' in quote_result and len(quote_result['data']) > 0:
            return quote_result['data'][0].get('price')
        else:
            raise ValueError(f"No quote data returned for {symbol}")
    except Exception as e:
        raise ValueError(f"Failed to get underlying price for {symbol}: {e}")

def get_option_chain(symbol):
    """Get option chain using Webull MCP tools."""
    try:
        # Get option contracts for the underlying symbol
        # We need to get contracts first, then get quotes for each
        contracts_result = mcp__webull__get_option_contracts(
            underlying_symbols=symbol,
            status="active"
        )

        if not contracts_result or 'data' not in contracts_result:
            raise ValueError(f"No option contracts returned for {symbol}")

        contracts_data = contracts_result['data']

        # Extract symbols from contracts
        option_symbols = [contract.get('symbol') for contract in contracts_data if contract.get('symbol')]

        if not option_symbols:
            raise ValueError(f"No valid option symbols found for {symbol}")

        # Get quotes for all option symbols
        # Webull MCP has a limit of 20 symbols for option snapshot, so we need to batch
        all_quotes = []
        batch_size = 20

        for i in range(0, len(option_symbols), batch_size):
            batch_symbols = option_symbols[i:i+batch_size]
            try:
                quote_result = mcp__webull__get_option_snapshot(
                    symbols=','.join(batch_symbols)
                )
                if quote_result and 'data' in quote_result:
                    all_quotes.extend(quote_result['data'])
            except Exception as e:
                print(f"Warning: Failed to get quotes for batch {batch_symbols}: {e}", file=sys.stderr)
                continue

        # Convert to list of dicts matching the expected format
        data = []
        for quote in all_quotes:
            # Extract information from Webull option snapshot
            option_symbol = quote.get('symbol', '')
            if not option_symbol:
                continue

            # Parse option symbol to extract components
            # Format: underlying + YYMMDD + C/P + strike*1000
            # Example: MSFT261016C00190000
            underlying = symbol  # We know the underlying

            # Find where the underlying ends in the option symbol
            if not option_symbol.startswith(underlying):
                # Try to extract underlying from symbol (this is approximate)
                # In practice, we'd rely on the contract data from get_option_contracts
                underlying_extracted = ''.join([c for c in option_symbol if not c.isdigit() and c not in ['C', 'P']])
                if underlying_extracted:
                    underlying = underlying_extracted.rstrip('-')  # Remove trailing dash if present
                else:
                    underlying = symbol  # Fallback

            # Extract date part (6 chars after underlying)
            date_start = len(underlying)
            if date_start + 6 > len(option_symbol):
                # Try to find date part differently
                # Look for pattern: 6 digits followed by C or P
                import re
                date_match = re.search(r'(\d{6})([CP])', option_symbol)
                if date_match:
                    date_part = date_match.group(1)
                    option_type_char = date_match.group(2)
                    strike_start = date_match.end()
                else:
                    # Skip if we can't parse
                    continue
            else:
                date_part = option_symbol[date_start:date_start+6]
                option_type_char = option_symbol[date_start+6] if date_start+6 < len(option_symbol) else ''
                strike_start = date_start + 7

            if len(date_part) != 6 or option_type_char not in ['C', 'P']:
                # Try alternative parsing
                continue

            try:
                exp_year = f"20{date_part[0:2]}"
                exp_month = date_part[2:4]
                exp_day = date_part[4:6]
                expiration = f"{exp_year}-{exp_month}-{exp_day}"

                option_type = 'call' if option_type_char == 'C' else 'put'

                # Extract strike price (remaining digits divided by 1000)
                strike_str = option_symbol[strike_start:] if strike_start < len(option_symbol) else '0'
                strike_price = float(strike_str) / 1000 if strike_str.isdigit() else 0.0

                data.append({
                    'option_symbol': option_symbol,
                    'underlying_symbol': underlying,
                    'expiration_date': expiration,
                    'option_type': option_type,
                    'strike_price': strike_price,
                    'bid_price': quote.get('bid_price'),
                    'ask_price': quote.get('ask_price'),
                    'last_price': quote.get('last_price'),
                    'bid_size': quote.get('bid_size'),
                    'ask_size': quote.get('ask_size'),
                    'volume': quote.get('volume'),
                    'open_interest': quote.get('open_interest'),
                    'implied_volatility': quote.get('implied_volatility'),
                    'delta': quote.get('delta'),
                    'gamma': quote.get('gamma'),
                    'theta': quote.get('theta'),
                    'vega': quote.get('vega'),
                    'timestamp': quote.get('timestamp')
                })
            except (ValueError, IndexError):
                # Skip if parsing fails
                continue

        return data

    except Exception as e:
        raise ValueError(f"Failed to get option chain for {symbol}: {e}")

def main():
    underlying_symbol = 'MSFT'
    try:
        underlying_price = get_underlying_price(underlying_symbol)
        print(f"Underlying price for {underlying_symbol}: {underlying_price}", file=sys.stderr)
    except Exception as e:
        print(f"Failed to get underlying price: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        option_chain = get_option_chain(underlying_symbol)
        print(f"Retrieved {len(option_chain)} option contracts", file=sys.stderr)
    except Exception as e:
        print(f"Failed to get option chain: {e}", file=sys.stderr)
        sys.exit(1)

    # Filter to calls only for simplicity
    calls = [c for c in option_chain if c['option_type'] == 'call']
    # Group by expiration date
    exp_to_calls = {}
    for c in calls:
        exp = c['expiration_date']
        exp_to_calls.setdefault(exp, []).append(c)

    # Sort expirations
    sorted_exps = sorted(exp_to_calls.keys())
    # We'll consider the nearest two expirations
    selected_exps = sorted_exps[:2] if len(sorted_exps) >= 2 else sorted_exps

    opportunities = []
    today = date.today()

    for exp in selected_exps:
        exp_calls = exp_to_calls[exp]
        # Sort by strike
        exp_calls.sort(key=lambda x: x['strike_price'])
        # We'll consider spreads where long strike < short strike
        # Limit to strikes near the money? We'll consider all pairs but limit to avoid combinatorial explosion.
        # For each long call, we'll consider short calls that are at most 5 strikes away?
        # Instead, we'll just consider consecutive strikes for simplicity.
        for i in range(len(exp_calls)-1):
            long = exp_calls[i]
            short = exp_calls[i+1]
            # Ensure we have bid and ask
            if long['ask_price'] is None or short['bid_price'] is None:
                continue
            long_strike = long['strike_price']
            short_strike = short['strike_price']
            net_debit = long['ask_price'] - short['bid_price']
            if net_debit <= 0:
                # Arbitrage or invalid, skip
                continue
            width = short_strike - long_strike
            max_profit = width - net_debit
            max_loss = net_debit
            if max_profit <= 0:
                continue
            # Probability of profit placeholder
            prob = 0.5
            # Expected return on risk (max_loss)
            expected_return = (max_profit * prob - max_loss * (1 - prob)) / max_loss
            # Days to expiry
            try:
                exp_date = datetime.strptime(exp, '%Y-%m-%d').date()
                days_to_expiry = (exp_date - today).days
            except:
                days_to_expiry = 0

            opp = {
                'symbol': underlying_symbol,
                'strategy_type': 'bull_call_spread',
                'long_strike': long_strike,
                'short_strike': short_strike,
                'expiration_date': f"{exp}T00:00:00Z",  # RFC3339
                'days_to_expiry': days_to_expiry,
                'net_debit': round(net_debit, 2),
                'max_profit': round(max_profit, 2),
                'max_loss': round(max_loss, 2),
                'expected_return': round(expected_return, 4),
                'probability_of_profit': prob,
                'underlying_price': round(underlying_price, 2)
            }
            opportunities.append(opp)

    # Sort by expected_return descending
    opportunities.sort(key=lambda x: x['expected_return'], reverse=True)
    # Keep top 5
    opportunities = opportunities[:5]

    # Output as JSON for StructuredOutput
    result = {
        'symbol': underlying_symbol,
        'opportunities': opportunities
    }
    print(json.dumps(result))

if __name__ == '__main__':
    main()