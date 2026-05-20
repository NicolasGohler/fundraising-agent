"""
save_cookies.py — Run this locally to generate a fresh CRYPTORANK_COOKIES secret.

Usage:
    python save_cookies.py

A browser window will open. Log into CryptoRank manually, then close the browser.
The script prints a single line — copy it and run:

    gh secret set CRYPTORANK_COOKIES --body "paste-here" --repo NicolasGohler/fundraising-agent
"""

import json
import base64
from playwright.sync_api import sync_playwright

LOGIN_URL = "https://cryptorank.io/login"
TEST_URL   = "https://cryptorank.io/price/bitcoin/team"  # lightweight team page to verify session

print("=" * 60)
print("  CryptoRank Cookie Saver")
print("=" * 60)
print()
print("A browser will open. Please:")
print("  1. Log into CryptoRank")
print("  2. Close the browser window when done")
print()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    page.goto(LOGIN_URL)

    print("Waiting for you to log in and close the browser...")
    try:
        # Wait until the browser is closed by the user
        page.wait_for_url("**/funding-rounds**", timeout=300_000)
    except Exception:
        pass  # User may close from any page — that's fine

    # Give a moment for any final cookies to be set
    try:
        page.wait_for_timeout(2000)
    except Exception:
        pass

    storage = context.storage_state()
    browser.close()

# Encode as base64 so it's safe to pass as a single-line secret
encoded = base64.b64encode(json.dumps(storage).encode()).decode()

print()
print("=" * 60)
print("  Session saved successfully!")
print("=" * 60)
print()
print("Run this command to update the GitHub secret:")
print()
print(f'gh secret set CRYPTORANK_COOKIES --body "{encoded}" --repo NicolasGohler/fundraising-agent')
print()
print("Cookies typically last 30–60 days.")
print("You'll get a Slack warning when they need refreshing.")
