
from fastapi.testclient import TestClient
import sys
import os

# Add current dir to path
sys.path.append(os.path.dirname(__file__))

from app.main import app

client = TestClient(app)

print("--- REPRODUCING 500 ERROR ---")

try:
    print("Testing GET /api/v1/setups...")
    response = client.get("/api/v1/setups")
    print(f"Status: {response.status_code}")
    if response.status_code != 200:
        print(f"Error Response: {response.text}")
    else:
        print("Success! Data received.")
except Exception as e:
    print(f"Exception during request: {e}")

try:
    print("\nTesting GET /scheduler/status...")
    response = client.get("/scheduler/status")
    print(f"Status: {response.status_code}")
    if response.status_code != 200:
        print(f"Error Response: {response.text}")
    else:
        print(f"Success! Scheduler status: {response.json()}")
except Exception as e:
    print(f"Exception during request: {e}")
