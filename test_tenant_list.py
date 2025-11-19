import requests
import json

BASE_URL = "http://localhost:8000"

# 1. Super admin login
print("=== Super Admin Login ===")
login_response = requests.post(
    f"{BASE_URL}/auth/token",
    data={
        "username": "super",
        "password": "super123"
    },
    headers={"Content-Type": "application/x-www-form-urlencoded"}
)

if login_response.status_code == 200:
    token_data = login_response.json()
    access_token = token_data.get("access_token")
    print("OK: Login basarili! Token alindi.")
else:
    print(f"HATA: Login basarisiz: {login_response.status_code}")
    print(login_response.text)
    exit(1)

# 2. Tenant listesi cek
print("\n=== Tenant Listesi ===")
headers = {"Authorization": f"Bearer {access_token}"}
tenants_response = requests.get(f"{BASE_URL}/superadmin/tenants", headers=headers)

if tenants_response.status_code == 200:
    tenants = tenants_response.json()
    print(f"OK: {len(tenants)} tenant bulundu:")
    for tenant in tenants:
        print(f"  - ID: {tenant.get('id')}, Ad: {tenant.get('ad')}, Aktif: {tenant.get('aktif')}")
else:
    print(f"HATA: Tenant listesi alinamadi: {tenants_response.status_code}")
    print(tenants_response.text)
