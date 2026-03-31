#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste: Diferentes tamanhos de imagem para encontrar o mínimo
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
print("TEST: Diferentes tamanhos de imagem")
print("="*70)

payload = {
    "campaignName": "test_hvac",
    "startsAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "endsAt": (datetime.now(timezone.utc) + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "duration": "1",
    "name": "dashboard"
}

# Test different sizes
sizes = [
    (100, 100, "100x100"),
    (320, 240, "320x240"),
    (640, 480, "640x480"),
    (800, 600, "800x600"),
    (1024, 768, "1024x768"),
    (1074, 567, "1074x567 (dashboard real)"),
]

for width, height, desc in sizes:
    fname = f"test_{width}x{height}.jpg"
    log(f"\nTestando {desc} ({width}x{height})")
    
    # Create image
    img = Image.new("RGB", (width, height), color=(100, 100, 100))
    # Add variation so it's not totally uniform
    for x in range(0, width, 10):
        for y in range(0, height, 10):
            img.putpixel((x, y), (200, 100, 50))
    img.save(fname, "JPEG")
    
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
        
        file_size = os.path.getsize(fname) / 1024
        log(f"   Tamanho: {file_size:.1f}KB")
        
        if response.status_code in [200, 201, 202, 204]:
            log(f"   ✅ SUCESSO! Status: {response.status_code}")
            print(f"\n🎉 ENCONTRADO!")
            print(f"   Tamanho correto: {desc}")
            print(f"   Arquivo: {file_size:.1f}KB")
            break
        else:
            log(f"   Status: {response.status_code} - {response.text[:60]}")
    except Exception as e:
        log(f"   Erro: {str(e)[:50]}")
    finally:
        if os.path.exists(fname):
            os.remove(fname)
