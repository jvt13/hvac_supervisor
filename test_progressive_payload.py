#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste progressivo: começa com menos campos e vai adicionando
para descobrir qual é o payload correto que a API espera
"""

import json
import os
from datetime import datetime, timezone, timedelta
import requests
from PIL import Image

CONFIG_FILE = "config.json"
TEST_FILE = "test_simple.png"

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)

# Create test image
img = Image.new("RGB", (50, 50), color=(30, 30, 30))
img.save(TEST_FILE)

config = load_config()

print("\n" + "="*70)
print("TEST: Descobrindo payload correto")
print("="*70)

payloads = [
    {
        "name": "Apenas arquivo",
        "data": {},
        "desc": "Sem campos extras"
    },
    {
        "name": "Com name",
        "data": {"name": "dashboard"},
        "desc": "Field 'name'"
    },
    {
        "name": "Com startsAt e endsAt apenas",
        "data": {
            "startsAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "endsAt": (datetime.now(timezone.utc) + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "desc": "Timestamp fields only"
    },
    {
        "name": "Com campaignName",
        "data": {
            "campaignName": "test",
        },
        "desc": "Campaign name only"
    },
    {
        "name": "campaign + name",
        "data": {
            "campaignName": "test",
            "name": "dashboard",
        },
        "desc": "Campaign e name"
    },
]

for i, test in enumerate(payloads, 1):
    log(f"\n{i}️⃣ {test['name']} ({test['desc']})")
    log(f"   Payload: {test['data']}")
    
    try:
        with open(TEST_FILE, "rb") as fh:
            files = {"file": fh}
            response = requests.post(
                config["upload_url"],
                data=test["data"],
                files=files,
                headers={"x-api-key": config.get("upload_api_key", "")},
                timeout=5
            )
        
        if response.status_code in [200, 201, 202, 204]:
            log(f"   ✅ SUCESSO! Status: {response.status_code}")
            print(f"\n🎉 ENCONTRADO! Este é o payload correto:")
            print(f"   {test['data']}")
            break
        else:
            log(f"   Status: {response.status_code}")
            if response.text:
                log(f"   Resposta: {response.text[:80]}")
    except Exception as e:
        log(f"   Erro: {str(e)[:40]}")

os.remove(TEST_FILE)
