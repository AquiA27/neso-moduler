"""Test performance improvement for customer assistant."""

import asyncio
import time
import httpx
import json

# Test endpoint
BASE_URL = "http://localhost:8000"
TOKEN = None


async def login():
    """Login to get auth token."""
    global TOKEN
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/auth/token",
            data={
                "username": "ali",
                "password": "1234"
            }
        )
        if response.status_code == 200:
            TOKEN = response.json().get("access_token")
            print(f"[OK] Logged in successfully")
        else:
            print(f"[ERROR] Login failed: {response.status_code}")
            print(response.text)


async def test_recommendation_query():
    """Test a recommendation query (should NOT trigger many embedding calls)."""
    if not TOKEN:
        print("[ERROR] Not logged in")
        return

    test_query = "biraz hastayım ne önerebilirsin"

    print(f"\n[TEST] Query: '{test_query}'")
    print("Expected: Low embedding calls (0-1), fast response")

    async with httpx.AsyncClient(timeout=30.0) as client:
        start_time = time.time()

        response = await client.post(
            f"{BASE_URL}/customer-assistant/chat",
            headers={"Authorization": f"Bearer {TOKEN}"},
            json={"text": test_query}
        )

        elapsed = time.time() - start_time

        if response.status_code == 200:
            data = response.json()
            print(f"[OK] Response received in {elapsed:.2f} seconds")
            print(f"  Type: {data.get('type')}")
            print(f"  Message: {data.get('message')}")
            print(f"  Intent: {data.get('intent')}")
            print(f"  Sentiment: {data.get('sentiment')}")

            if data.get('recommendations'):
                print(f"  Recommendations: {len(data['recommendations'])} products")
                for rec in data['recommendations'][:3]:
                    print(f"    - {rec['product_name']} ({rec['reason']})")
        else:
            print(f"[ERROR] Request failed: {response.status_code}")
            print(response.text)


async def test_order_query():
    """Test a direct order query (should trigger embedding calls but fewer)."""
    if not TOKEN:
        print("[ERROR] Not logged in")
        return

    test_query = "bir kahve istiyorum"

    print(f"\n[TEST] Query: '{test_query}'")
    print("Expected: Some embedding calls for product matching")

    async with httpx.AsyncClient(timeout=30.0) as client:
        start_time = time.time()

        response = await client.post(
            f"{BASE_URL}/customer-assistant/chat",
            headers={"Authorization": f"Bearer {TOKEN}"},
            json={"text": test_query}
        )

        elapsed = time.time() - start_time

        if response.status_code == 200:
            data = response.json()
            print(f"[OK] Response received in {elapsed:.2f} seconds")
            print(f"  Type: {data.get('type')}")
            print(f"  Message: {data.get('message')}")
            print(f"  Intent: {data.get('intent')}")

            if data.get('matched_products'):
                print(f"  Matched products: {len(data['matched_products'])}")
                for match in data['matched_products'][:3]:
                    print(f"    - {match['product_name']} (confidence: {match['confidence']:.2f})")
        else:
            print(f"[ERROR] Request failed: {response.status_code}")
            print(response.text)


async def main():
    """Run tests."""
    print("=" * 60)
    print("PERFORMANCE TEST - Customer Assistant")
    print("=" * 60)

    await login()

    # Test 1: Recommendation query (should be fast now)
    await test_recommendation_query()

    # Test 2: Order query (baseline for comparison)
    await test_order_query()

    print("\n" + "=" * 60)
    print("Check backend logs for embedding API call counts")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
