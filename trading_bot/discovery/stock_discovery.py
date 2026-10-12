"""Stock discovery module for autonomous options trading system.

Provides multiple sources for stock discovery:
1. Configured universe (static)
2. Most active stocks (Webull MCP)
3. Market movers (Webull MCP)
4. News-based discoveries (Webull MCP)
"""

import logging
import yaml
from typing import List, Set, Dict, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
from .stock_universe import StockUniverse

logger = logging.getLogger(__name__)


class StockDiscovery:
    """Discovers stocks for options trading using multiple sources."""

    def __init__(self,
                 universe_config_path: str = "config/universe.yaml",
                 discovery_config_path: str = "config/discovery.yaml"):
        """Initialize stock discovery.

        Args:
            universe_config_path: Path to stock universe configuration file
            discovery_config_path: Path to discovery configuration file
        """
        self.universe = StockUniverse(universe_config_path)
        self.discovery_config = self._load_discovery_config(discovery_config_path)
        logger.info("Stock discovery initialized")

    def _load_discovery_config(self, config_path: str) -> Dict[str, Any]:
        """Load discovery configuration from YAML file.

        Args:
            config_path: Path to discovery configuration YAML file

        Returns:
            Dictionary containing discovery configuration
        """
        config_path = Path(config_path)
        try:
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                return config.get('discovery', {})
            else:
                logger.warning(f"Discovery config not found at {config_path}, using defaults")
                return self._get_default_discovery_config()
        except Exception as e:
            logger.error(f"Error loading discovery config: {e}")
            return self._get_default_discovery_config()

    def _get_default_discovery_config(self) -> Dict[str, Any]:
        """Get default discovery configuration.

        Returns:
            Default discovery configuration dictionary
        """
        return {
            'use_universe': True,
            'use_most_active': False,
            'use_market_movers': False,
            'use_news': False,
            'max_stocks': 50,
            'most_active': {'limit': 20},
            'market_movers': {'limit': 20},
            'news_based': {
                'lookback_hours': 24,
                'limit': 10
            }
        }

    def get_configured_universe(self) -> List[str]:
        """Get stocks from the configured universe.

        Returns:
            List of stock symbols from configured universe
        """
        return self.universe.get_universe()

    def get_most_active_stocks(self, limit: int = 20) -> List[str]:
        """Get most active stocks by volume using Webull MCP.

        Args:
            limit: Maximum number of stocks to return

        Returns:
            List of stock symbols ordered by activity
        """
        try:
            # Implement actual MCP call
            most_active_result = mcp__webull__get_most_active(limit=limit)
            if most_active_result and 'data' in most_active_result:
                return [stock['symbol'] for stock in most_active_result['data']]
            else:
                logger.warning("Unexpected response format from get_most_active")
                return []
        except Exception as e:
            logger.warning(f"Error getting most active stocks: {e}")
            return []

    def get_market_movers(self, limit: int = 20) -> List[str]:
        """Get market movers (gainers and losers) using Webull MCP.

        Args:
            limit: Maximum number of stocks to return for each category

        Returns:
            List of stock symbols that are significant market movers
        """
        try:
            # Implement actual MCP call
            gainers_result = mcp__webull__get_gainers_losers(limit=limit, direction="DESC")  # DESC for gainers
            losers_result = mcp__webull__get_gainers_losers(limit=limit, direction="ASC")   # ASC for losers

            movers = []

            # Process gainers
            if gainers_result and 'data' in gainers_result:
                movers.extend([stock['symbol'] for stock in gainers_result['data']])

            # Process losers
            if losers_result and 'data' in losers_result:
                movers.extend([stock['symbol'] for stock in losers_result['data']])

            # Remove duplicates while preserving order
            seen = set()
            unique_movers = []
            for symbol in movers:
                if symbol not in seen:
                    seen.add(symbol)
                    unique_movers.append(symbol)

            return unique_movers
        except Exception as e:
            logger.warning(f"Error getting market movers: {e}")
            return []

    def get_news_based_stocks(self, lookback_hours: int = 24, limit: int = 10) -> List[str]:
        """Get stocks based on recent news using Webull MCP.

        Args:
            lookback_hours: How many hours back to look for news
            limit: Maximum number of stocks to return

        Returns:
            List of stock symbols with recent news coverage
        """
        try:
            # Implement actual MCP call
            from datetime import datetime, timedelta

            news_result = mcp__webull__get_news(
                start=(datetime.now() - timedelta(hours=lookback_hours)).isoformat(),
                end=datetime.now().isoformat(),
                limit=limit
            )

            # Extract unique symbols from news articles
            symbols = set()
            if news_result and 'data' in news_result:
                # Handle different possible response formats
                news_data = news_result['data']
                if isinstance(news_data, list):
                    # Direct list of news articles
                    for article in news_data:
                        if isinstance(article, dict) and 'symbols' in article:
                            symbols.update(article['symbols'])
                elif isinstance(news_data, dict) and 'news' in news_data:
                    # Nested under 'news' key
                    for article in news_data['news']:
                        if isinstance(article, dict) and 'symbols' in article:
                            symbols.update(article['symbols'])

            return list(symbols)[:limit]
        except Exception as e:
            logger.warning(f"Error getting news-based stocks: {e}")
            return []

    def discover_stocks(self) -> List[str]:
        """Discover stocks using enabled sources from configuration.

        Returns:
            List of unique stock symbols from all enabled sources
        """
        # Get configuration values
        use_universe = self.discovery_config.get('use_universe', True)
        use_most_active = self.discovery_config.get('use_most_active', False)
        use_market_movers = self.discovery_config.get('use_market_movers', False)
        use_news = self.discovery_config.get('use_news', False)
        max_stocks = self.discovery_config.get('max_stocks', 50)

        # Get source-specific limits
        most_active_limit = self.discovery_config.get('most_active', {}).get('limit', 20)
        market_movers_limit = self.discovery_config.get('market_movers', {}).get('limit', 20)
        news_lookback_hours = self.discovery_config.get('news_based', {}).get('lookback_hours', 24)
        news_limit = self.discovery_config.get('news_based', {}).get('limit', 10)

        discovered_stocks: Set[str] = set()

        # Get stocks from configured universe
        if use_universe:
            universe_stocks = set(self.get_configured_universe())
            discovered_stocks.update(universe_stocks)
            logger.info(f"Added {len(universe_stocks)} stocks from configured universe")

        # Get most active stocks
        if use_most_active:
            active_stocks = set(self.get_most_active_stocks(limit=most_active_limit))
            discovered_stocks.update(active_stocks)
            logger.info(f"Added {len(active_stocks)} stocks from most active discovery")

        # Get market movers
        if use_market_movers:
            mover_stocks = set(self.get_market_movers(limit=market_movers_limit))
            discovered_stocks.update(mover_stocks)
            logger.info(f"Added {len(mover_stocks)} stocks from market movers discovery")

        # Get news-based stocks
        if use_news:
            news_stocks = set(self.get_news_based_stocks(
                lookback_hours=news_lookback_hours,
                limit=news_limit
            ))
            discovered_stocks.update(news_stocks)
            logger.info(f"Added {len(news_stocks)} stocks from news-based discovery")

        # Convert to sorted list and limit
        result = sorted(list(discovered_stocks))[:max_stocks]
        logger.info(f"Discovered {len(result)} unique stocks from {len(discovered_stocks)} total candidates")

        return result

    def get_discovery_sources_status(self) -> Dict[str, bool]:
        """Get the status of each discovery source.

        Returns:
            Dictionary indicating which discovery sources are available/working
        """
        # Test each source to determine availability
        status = {
            'configured_universe': True,  # Always available if universe file exists
            'most_active_stocks': False,
            'market_movers': False,
            'news_based': False
        }

        # Test most active stocks
        try:
            result = mcp__webull__get_most_active(top=1)
            if result and 'data' in result:
                status['most_active_stocks'] = True
        except Exception:
            pass  # Keep as False

        # Test market movers
        try:
            gainers_result = mcp__webull__get_gainers_losers(top=1, direction="DESC")
            losers_result = mcp__webull__get_gainers_losers(top=1, direction="ASC")
            if (gainers_result and 'data' in gainers_result) or (losers_result and 'data' in losers_result):
                status['market_movers'] = True
        except Exception:
            pass  # Keep as False

        # Test news-based stocks
        try:
            from datetime import datetime, timedelta
            news_result = mcp__webull__get_news(
                start=(datetime.now() - timedelta(hours=1)).isoformat(),
                end=datetime.now().isoformat(),
                limit=1
            )
            if news_result and 'data' in news_result:
                status['news_based'] = True
        except Exception:
            pass  # Keep as False

        return status


def discover_stocks_for_trading(
    universe_config: str = "config/universe.yaml",
    discovery_config: str = "config/discovery.yaml"
) -> List[str]:
    """Convenience function to discover stocks for trading.

    Args:
        universe_config: Path to universe configuration file
        discovery_config: Path to discovery configuration file

    Returns:
        List of stock symbols ready for screening
    """
    discovery = StockDiscovery(universe_config, discovery_config)
    return discovery.discover_stocks()


if __name__ == "__main__":
    # Test the discovery system
    print("Testing stock discovery system...")

    # Test universe loading
    universe = StockUniverse()
    print(f"Configured universe ({len(universe.get_universe())} stocks): {universe.get_universe()[:10]}...")

    # Test discovery with universe only
    stocks = discover_stocks_for_trading()
    print(f"Discovered stocks (with config): {stocks}")

    # Test discovery source status
    discovery = StockDiscovery()
    print(f"Discovery sources status: {discovery.get_discovery_sources_status()}")