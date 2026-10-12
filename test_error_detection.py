#!/usr/bin/env python3
"""Test the error detection logic in Phase 7 script."""

# Simulate what the error messages would look like
test_messages = [
    "Error checking market status: alpaca.common.exceptions.APIError: {\"message\": \"unauthorized.\"}",
    "Error checking account: alpaca.common.exceptions.APIError: {\"message\": \"unauthorized.\"}",
    "Market closed: Next open: 2026-10-07T09:30:00-04:00",
    "Account active. Buying power: $199945.21",
    "401 Authorization Required: { \"message\": \"unauthorized.\" }",
    "Some other error"
]

print("Testing error detection logic:")
print("=" * 50)

for msg in test_messages:
    is_auth_error = ("401 Authorization Required" in msg or "unauthorized" in msg.lower())
    print(f"Message: {msg}")
    print(f"Is auth error: {is_auth_error}")
    print("-" * 30)