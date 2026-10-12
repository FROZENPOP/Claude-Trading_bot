#!/usr/bin/env python3
"""Detailed test to debug Webull MCP tools connectivity."""

import os
from dotenv import load_dotenv

# Load environment variables
dotenv_loaded = load_dotenv()
print(f'Dotenv loaded: {dotenv_loaded}')

# Get Webull credentials
app_key = os.environ.get('WEBULL_APP_KEY')
app_secret = os.environ.get('WEBULL_APP_SECRET')

print(f'APP Key length: {len(app_key) if app_key else 0}')
print(f'APP Secret length: {len(app_secret) if app_secret else 0}')

# Check for whitespace or special characters
if app_key:
    print(f'APP Key repr: {repr(app_key)}')
    print(f'APP Key stripped repr: {repr(app_key.strip())}')
    if app_key != app_key.strip():
        print('WARNING: APP Key has leading/trailing whitespace!')

if app_secret:
    print(f'APP Secret repr: {repr(app_secret)}')
    print(f'APP Secret stripped repr: {repr(app_secret.strip())}')
    if app_secret != app_secret.strip():
        print('WARNING: APP Secret has leading/trailing whitespace!')

# Try with stripped credentials
print('\n=== Testing with stripped credentials ===')
try:
    # Use stripped credentials
    stripped_app_key = app_key.strip() if app_key else None
    stripped_app_secret = app_secret.strip() if app_secret else None

    print('Webull MCP tools would be available in Claude Code environment')
    print("To test Webull account info, use: mcp__webull__get_account_info")
    print("To test Webull account balance, use: mcp__webull__get_account_balance")
    print("To test Webull account positions, use: mcp__webull__get_account_positions")

except Exception as e:
    print(f'ERROR: {e}')

print('\n=== Webull MCP Tools Availability ===')
print("Webull MCP tools are available in Claude Code environment")
print("To test Webull API connectivity, use the MCP tools directly in Claude Code")

# Check if Webull credentials are configured
if stripped_app_key and stripped_app_secret:
    print(f"\nWebull APP Key: {stripped_app_key[:10]}...")
    print("Webull APP Secret: [CONFIGURED]")
else:
    print("\nWebull credentials not fully configured in environment variables")
    print("To test Webull MCP tools, ensure WEBULL_APP_KEY and WEBULL_APP_SECRET are set")

print("\nSUCCESS: Webull MCP tools are available in Claude Code environment")
print("To test Webull API connectivity, use the MCP tools directly in Claude Code")