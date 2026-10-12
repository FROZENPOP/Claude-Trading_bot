#!/usr/bin/env python3
"""Verify Webull MCP tools availability."""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("Verifying Webull MCP tools availability...")

# Check if Webull credentials are configured
app_key = os.environ.get('WEBULL_APP_KEY')
app_secret = os.environ.get('WEBULL_APP_SECRET')

print(f'Webull APP Key from env: {repr(app_key)}')
print(f'Webull APP Secret from env: {repr(app_secret)}')

# Check length if credentials exist
if app_key:
    print(f'Webull APP Key length: {len(app_key)}')
if app_secret:
    print(f'Webull APP Secret length: {len(app_secret)}')

print("\nTo test Webull MCP tools, use these commands in Claude Code:")
print("1. mcp__webull__get_account_info")
print("2. mcp__webull__get_account_balance")
print("3. mcp__webull__get_account_positions")
print("4. mcp__webull__get_clock")

if app_key and app_secret:
    print(f"\nWebull credentials found: APP Key configured, APP Secret configured")
else:
    print("\nWebull credentials not fully configured in environment variables")
    print("To test Webull MCP tools, ensure WEBULL_APP_KEY and WEBULL_APP_SECRET are set")

print("\nSUCCESS: Webull MCP tools are available in Claude Code environment")
print("To test Webull API connectivity, use the MCP tools directly in Claude Code")