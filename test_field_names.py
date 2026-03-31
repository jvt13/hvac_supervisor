#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste: Diferentes nomes de campo para arquivo
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

# Create image
img = Image.new("RGB", (100, 100), color=(100, 100, 100))
img.save("test.jpg", "JPEG")

config = load_config()

print("\n" + "="*70)
print("TEST: Diferentes nomes de campo para arquivo")
print("="*70)

payload = {
    "campaignName": "test_hvac",
    "startsAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "endsAt": (datetime.now(timezone.utc) + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "duration": "1",
    "name": "dashboard"
}

field_names = ["file", "image", "photo", "arquivo", "captura", "midia", "upload", "data", "content"]

for field_name in field_names:
    log(f"\nTestando field_name='{field_name}'")
    
    try:
        with open("test.jpg", "rb") as fh:
            files = {field_name: fh}
            response = requests.post(
                config["upload_url"],
                data=payload,
                files=files,
                headers={"x-api-key": config.get("upload_api_key", "")},
                timeout=5
            )
        
        if response.status_code in [200, 201, 202, 204]:
            log(f"   ✅ SUCESSO! Status: {response.status_code}")
            print(f"\n🎉 ENCONTRADO! Campo correto: '{field_name}'")
            print(f"   Resposta: {response.text[:100]}")
            break
        else:
            log(f"   Status: {response.status_code} - {response.text[:60]}")
    except Exception as e:
        log(f"   Erro: {str(e)[:50]}")

os.remove("test.jpg")
