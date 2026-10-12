#!/usr/bin/env python3
"""Demonstration script showing how the stock discovery system works.

This script demonstrates the stock discovery capabilities that will be
available once the Alpaca MCP integration is complete.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from trading_bot.discovery.stock_discovery import StockDiscovery


def main():
    """Run the stock discovery demonstration."""
    print("=" * 60)
    print("Stock Discovery System Demonstration")
    print("=" * 60)

    # Initialize the discovery system
    discovery = StockDiscovery()

    # Show current configuration
    print("\n1. Current Discovery Configuration:")
    config = discovery.discovery_config
    for key, value in config.items():
        if key not in ['most_active', 'market_movers', 'news_based']:
            print(f"   {key}: {value}")

    print("\n2. Source-Specific Configuration:")
    for source in ['most_active', 'market_movers', 'news_based']:
        if source in config:
            print(f"   {source}: {config[source]}")

    # Show discovery sources status
    print("\n3. Discovery Sources Status:")
    status = discovery.get_discovery_sources_status()
    for source, available in status.items():
        status_str = "[AVAILABLE]" if available else "[NOT AVAILABLE - MCP pending]"
        print(f"   {source}: {status_str}")

    # Perform stock discovery
    print("\n4. Performing Stock Discovery:")
    stocks = discovery.discover_stocks()
    print(f"   Discovered {len(stocks)} stocks:")
    print(f"   {', '.join(stocks)}")

    # Show what would happen if we enabled MCP sources
    print("\n5. Example: What if we enabled MCP sources?")
    print("   (This shows the structure - actual MCP calls would happen here)")

    # Temporarily enable sources for demonstration
    original_config = discovery.discovery_config.copy()
    discovery.discovery_config.update({
        'use_most_active': True,
        'use_market_movers': True,
        'use_news': True
    })

    print("   With MCP sources enabled, discovery would:")
    print("   - Call Alpaca MCP for most active stocks")
    print("   - Call Alpaca MCP for market movers (gainers/losers)")
    print("   - Call Alpaca MCP for news-based discoveries")
    print("   - Merge results with configured universe")
    print("   - Remove duplicates and apply limits")

    # Restore original config
    discovery.discovery_config = original_config

    print("\n" + "=" * 60)
    print("Demonstration Complete")
    print("=" * 60)
    print("\nNext Steps:")
    print("1. Implement actual Alpaca MCP calls in stock_discovery.py")
    print("2. Connect discovery system to stock screening (Phase 3)")
    print("3. Integrate with options opportunity generation (Phase 4)")
    print("4. Build autonomous trading loop (Phase 8)")


if __name__ == "__main__":
    main()