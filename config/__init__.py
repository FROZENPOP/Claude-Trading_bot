"""Configuration package."""

import os
import yaml
from pathlib import Path


def load_config(config_path: str = None) -> dict:
    """Load configuration from YAML file.

    Args:
        config_path: Path to config file (defaults to config/config.yaml)

    Returns:
        Configuration dictionary
    """
    if config_path is None:
        config_path = Path(__file__).parent / "config.yaml"

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Resolve environment variables
    return _resolve_env_vars(config)


def _resolve_env_vars(obj):
    """Recursively resolve ${VAR_NAME} environment variables."""
    if isinstance(obj, dict):
        return {k: _resolve_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_resolve_env_vars(item) for item in obj]
    elif isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
        var_name = obj[2:-1]
        return os.environ.get(var_name, "")
    else:
        return obj
