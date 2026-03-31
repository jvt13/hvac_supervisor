#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste: Diferente formatos de imagem
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

config = load_config()

print("\n" + "="*70)
print("TEST: Diferentes formatos de imagem")
print("="*70)

# Test different formats
formats = ["PNG", "JPEG", "BMP"]
test_files = {}

for fmt in formats:
    fname = f"test_image.{fmt.lower()}"
    img = Image.new("RGB", (100, 100), color=(100, 100, 100))
    if fmt == "JPEG":
        img.save(fname, "JPEG")
    elif fmt == "PNG":
        img.save(fname, "PNG")
    elif fmt == "BMP":
        img.save(fname, "BMP")
    test_files[fmt] = fname

now_utc = datetime.now(timezone.utc)
end_utc = (now_utc + timedelta(minutes=1)).replace(tzinfo=timezone.utc)

payload = {
    "campaignName": "test_hvac",
    "startsAt": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "endsAt": end_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "duration": "1",
    "name": "dashboard"
}

for fmt, fname in test_files.items():
    log(f"\n{fmt} - Testando {fname}")
    log(f"   Payload: {payload}")
    
    try:
        with open(fname, "rb") as fh:
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
            print(f"\n🎉 ENCONTRADO! Formato correto: {fmt}")
            break
        else:
            log(f"   Status: {response.status_code}")
            if response.text:
                log(f"   Erro: {response.text[:80]}")
    except Exception as e:
        log(f"   Erro: {str(e)[:60]}")
    finally:
        if os.path.exists(fname):
            os.remove(fname)
