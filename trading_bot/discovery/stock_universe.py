"""Stock universe management for autonomous options trading system."""

import yaml
from typing import List, Set
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class StockUniverse:
    """Manages the configurable stock universe for the autonomous trading system."""

    def __init__(self, config_path: str = "config/universe.yaml"):
        """Initialize stock universe from configuration file.

        Args:
            config_path: Path to universe configuration YAML file
        """
        self.config_path = Path(config_path)
        self.universe: Set[str] = set()
        self._load_universe()

    def _load_universe(self) -> None:
        """Load stock universe from YAML configuration file."""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    config = yaml.safe_load(f)

                # Handle different config formats
                if isinstance(config, dict) and 'universe' in config:
                    symbols = config['universe']
                elif isinstance(config, list):
                    symbols = config
                else:
                    symbols = []

                # Validate and store symbols
                self.universe = {symbol.upper().strip() for symbol in symbols
                              if isinstance(symbol, str) and symbol.strip()}
                logger.info(f"Loaded {len(self.universe)} stocks from universe: {sorted(self.universe)}")
            else:
                # Default universe if no config file exists
                self.universe = {
                    'AAPL', 'MSFT', 'NVDA', 'AMZN', 'META', 'GOOGL', 'TSLA',
                    'JPM', 'V', 'WMT', 'PG', 'UNH', 'HD', 'MA', 'DIS'
                }
                logger.warning(f"Universe config not found at {self.config_path}, using default universe with {len(self.universe)} stocks")

        except Exception as e:
            logger.error(f"Error loading universe config: {e}")
            # Fallback to minimal universe
            self.universe = {'AAPL', 'MSFT', 'GOOGL'}
            logger.info(f"Using fallback universe: {sorted(self.universe)}")

    def get_universe(self) -> List[str]:
        """Get the current stock universe as a sorted list.

        Returns:
            Sorted list of stock symbols in the universe
        """
        return sorted(list(self.universe))

    def add_stock(self, symbol: str) -> None:
        """Add a stock to the universe.

        Args:
            symbol: Stock symbol to add
        """
        if isinstance(symbol, str):
            self.universe.add(symbol.upper().strip())
            logger.info(f"Added {symbol.upper()} to universe")

    def remove_stock(self, symbol: str) -> None:
        """Remove a stock from the universe.

        Args:
            symbol: Stock symbol to remove
        """
        if isinstance(symbol, str):
            symbol_upper = symbol.upper().strip()
            if symbol_upper in self.universe:
                self.universe.remove(symbol_upper)
                logger.info(f"Removed {symbol_upper} from universe")

    def update_universe(self, symbols: List[str]) -> None:
        """Update the entire universe with a new list of symbols.

        Args:
            symbols: List of stock symbols to set as the new universe
        """
        if isinstance(symbols, list):
            self.universe = {symbol.upper().strip() for symbol in symbols
                           if isinstance(symbol, str) and symbol.strip()}
            logger.info(f"Updated universe to {len(self.universe)} stocks: {sorted(self.universe)}")

    def save_universe(self, config_path: str = None) -> None:
        """Save the current universe to a YAML configuration file.

        Args:
            config_path: Path to save universe config (uses self.config_path if None)
        """
        save_path = Path(config_path) if config_path else self.config_path
        save_path.parent.mkdir(parents=True, exist_ok=True)

        config = {'universe': sorted(list(self.universe))}
        with open(save_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)

        logger.info(f"Saved universe with {len(self.universe)} stocks to {save_path}")


def create_default_universe_config(config_path: str = "config/universe.yaml") -> None:
    """Create a default universe configuration file.

    Args:
        config_path: Path where to create the default config file
    """
    universe = StockUniverse(config_path)
    universe.save_universe(config_path)
    logger.info(f"Created default universe config at {config_path}")


if __name__ == "__main__":
    # Create default config if run directly
    create_default_universe_config()
    print("Default universe configuration created at config/universe.yaml")