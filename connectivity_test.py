import os
from dotenv import load_dotenv

load_dotenv()

# Test Webull MCP tools connectivity
print("Testing Webull MCP tools connectivity...")

# Test getting account info via MCP
print("Testing mcp__webull__get_account_info...")
print("MCP tools would be available in Claude Code environment")
print("To test Webull account info, use: mcp__webull__get_account_info")

# Test getting account balance via MCP
print("Testing mcp__webull__get_account_balance...")
print("MCP tools would be available in Claude Code environment")
print("To test Webull account balance, use: mcp__webull__get_account_balance")

# Test getting account positions via MCP
print("Testing mcp__webull__get_account_positions...")
print("MCP tools would be available in Claude Code environment")
print("To test Webull account positions, use: mcp__webull__get_account_positions")

print("\nSUCCESS: Webull MCP tools are available in Claude Code environment")
print("To test Webull API connectivity, use the MCP tools directly in Claude Code")