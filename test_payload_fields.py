#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste: Quais campos são necessários no payload
"""

import json
import os
from datetime import datetime, timezone, timedelta
import requests
from PIL import Image

CONFIG_FILE = "config.json"

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)

# Create a proper image
img = Image.new("RGB", (1074, 567), color=(100, 100, 100))
img.save("dashboard_test.jpg", "JPEG")

config = load_config()

print("\n" + "="*70)
print("TEST: Campos necessários no payload")
print("="*70)

test_payloads = [
    ("Sem campos", {}),
    ("Só name", {"name": "dashboard"}),
    ("Só campaignName", {"campaignName": "test"}),
    ("name + campaignName", {"name": "dashboard", "campaignName": "test"}),
    ("Com startsAt", {"startsAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}),
    ("Com endsAt", {"endsAt": (datetime.now(timezone.utc) + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")}),
]

for desc, payload in test_payloads:
    log(f"\n{desc}")
    log(f"   Payload: {payload}")
    
    try:
        with open("dashboard_test.jpg", "rb") as fh:
            files = {"file": fh}
            response = requests.post(
                config["upload_url"],
                data=payload,
                files=files,
                headers={"x-api-key": config.get("upload_api_key", "")},
                timeout=5
            )
        
        if response.status_code in [200, 201, 202, 204]:
            log(f"   ✅ SUCESSO! Status: {response.status_code}")
            print(f"\n🎉 ENCONTRADO!")
            print(f"   Payload correto: {payload}")
            break
        else:
            log(f"   Status: {response.status_code} - {response.text[:60]}")
    except Exception as e:
        log(f"   Erro: {str(e)[:50]}")

os.remove("dashboard_test.jpg")
