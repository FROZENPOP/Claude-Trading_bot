#!/usr/bin/env python3
"""
Test script to check Webull API credentials and permissions.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project to path
sys.path.append(os.path.join(os.path.dirname(__file__)))

def test_basic_connectivity():
    """Test basic API connectivity with the credentials."""
    print("Testing Webull API connectivity...")

    try:
        # Test Webull MCP tools connection by getting account info
        account_info = mcp__webull__get_account_info()

        if account_info:
            print("[PASS] Successfully connected to Webull API")
            print(f"[INFO] Account ID: {account_info.get('account_id', 'NOT AVAILABLE')}")
            print(f"[INFO] Account Status: {account_info.get('account_status', 'NOT AVAILABLE')}")
            buying_power = account_info.get('buying_power', 'NOT AVAILABLE')
            if buying_power != 'NOT AVAILABLE':
                print(f"[INFO] Buying Power: ${float(buying_power):.2f}")
            else:
                print(f"[INFO] Buying Power: {buying_power}")
            return True
        else:
            print("[FAIL] No account info returned from Webull API")
            return False

    except Exception as e:
        print(f"[FAIL] Error connecting to Webull API: {e}")
        return False

def test_options_permissions():
    """Test if we have permission to access options data."""
    print("\nTesting options data permissions...")

    try:
        # Test Webull MCP tools for options data - get option chain for a common symbol
        option_chain = mcp__webull__get_option_contracts(
            underlying_symbols="AAPL",
            limit=1
        )

        if option_chain:
            print(f"[PASS] Successfully retrieved option chain with {len(option_chain) if isinstance(option_chain, list) else 1} contracts")
            return True
        else:
            print("[FAIL] No options data returned")
            return False

    except Exception as e:
        print(f"[FAIL] Error accessing options data: {e}")
        # Check if it's a permission issue vs other error
        error_str = str(e).lower()
        if "403" in error_str or "permission" in error_str or "authorization" in error_str:
            print("   This appears to be a permission issue")
        return False

def test_account_info():
    """Test if we can get account information."""
    print("\nTesting account information access...")

    try:
        # Test Webull MCP tools for account access
        account_info = mcp__webull__get_account_info()

        if account_info:
            print("[PASS] Successfully retrieved account info:")
            print(f"   Account ID: {account_info.get('account_id', 'NOT AVAILABLE')}")
            print(f"   Status: {account_info.get('account_status', 'NOT AVAILABLE')}")
            buying_power = account_info.get('buying_power', 'NOT AVAILABLE')
            if buying_power != 'NOT AVAILABLE':
                print(f"   Buying Power: ${float(buying_power):.2f}")
            else:
                print(f"   Buying Power: {buying_power}")
            return True
        else:
            print("[FAIL] No account data returned from Webull API")
            return False

    except Exception as e:
        print(f"[FAIL] Error getting account info from Webull API: {e}")
        return False

def main():
    """Run all tests."""
    print("WEBULL API CREDENTIALS AND PERMISSIONS TEST")
    print("=" * 50)

    tests_passed = 0
    total_tests = 3

    # Test 1: Basic connectivity
    if test_basic_connectivity():
        tests_passed += 1
        print("\n[PASS] Basic connectivity test PASSED")
    else:
        print("\n[FAIL] Basic connectivity test FAILED")

    # Test 2: Options permissions
    if test_options_permissions():
        tests_passed += 1
        print("\n[PASS] Options permissions test PASSED")
    else:
        print("\n[FAIL] Options permissions test FAILED")

    # Test 3: Account info
    if test_account_info():
        tests_passed += 1
        print("\n[PASS] Account information test PASSED")
    else:
        print("\n[FAIL] Account information test FAILED")

    # Summary
    print("\n" + "=" * 50)
    print(f"RESULTS: {tests_passed}/{total_tests} tests passed")

    if tests_passed == total_tests:
        print("*** All tests passed! Webull API credentials are working correctly.")
    elif tests_passed >= 2:
        print("!!! Most tests passed. There may be specific permission issues with options data.")
    else:
        print("XXX Multiple tests failed. Please check your Webull API credentials and account status.")

    return tests_passed >= 2  # Consider success if at least 2/3 tests pass

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)