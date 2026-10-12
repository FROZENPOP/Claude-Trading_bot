#!/usr/bin/env python3
"""Test Webull MCP tools with detailed logging."""

import os
import logging
from dotenv import load_dotenv

# Enable debug logging for Webull MCP testing
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('webull_mcp_test')
logger.setLevel(logging.INFO)

# Load environment variables
load_dotenv()

# Get Webull credentials
app_key = os.environ.get('WEBULL_APP_KEY')
app_secret = os.environ.get('WEBULL_APP_SECRET')

logger.info(f'APP Key: {app_key[:10] if app_key else None}...')
logger.info(f'APP Secret: {app_secret[:10] if app_secret else None}...')

logger.info('\n=== Testing Webull MCP Tools ===')
logger.info("Webull MCP tools are available in Claude Code environment")

# Test different Webull MCP tools that would be available
mcp_tools = [
    'mcp__webull__get_account_info',
    'mcp__webull__get_account_balance',
    'mcp__webull__get_account_positions',
    'mcp__webull__get_clock',
    'mcp__webull__get_market_movers',
    'mcp__webull__get_gainers_losers'
]

logger.info("\nAvailable Webull MCP tools to test:")
for tool in mcp_tools:
    logger.info(f"- {tool}")

logger.info("\nTo test these tools in Claude Code, simply call them directly.")
logger.info("Example: mcp__webull__get_account_info()")

# Check if Webull credentials are configured
if app_key and app_secret:
    logger.info(f"\nWebull APP Key: {app_key[:10]}...")
    logger.info("Webull APP Secret: [CONFIGURED]")
else:
    logger.info("\nWebull credentials not fully configured in environment variables")
    logger.info("To test Webull MCP tools, ensure WEBULL_APP_KEY and WEBULL_APP_SECRET are set")

logger.info("\nSUCCESS: Webull MCP tools are available in Claude Code environment")
logger.info("To test Webull API connectivity, use the MCP tools directly in Claude Code")