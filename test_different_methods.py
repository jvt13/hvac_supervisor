#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste: Tenta diferentes formas de enviar o arquivo
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
print("TEST: Diferentes formas de envio")
print("="*70)

tests = [
    {
        "name": "POST com binary raw (sem form)",
        "test": lambda: requests.post(
            config["upload_url"],
            data=open(TEST_FILE, "rb"),
            headers={
                "x-api-key": config.get("upload_api_key", ""),
                "Content-Type": "image/png"
            },
            timeout=5
        )
    },
    {
        "name": "POST com form-data vazio + arquivo",
        "test": lambda: requests.post(
            config["upload_url"],
            files={"file": open(TEST_FILE, "rb")},
            headers={"x-api-key": config.get("upload_api_key", "")},
            timeout=5
        )
    },
    {
        "name": "POST com JSON body",
        "test": lambda: requests.post(
            config["upload_url"],
            json={"name": "test", "file": "base64:..."},
            headers={"x-api-key": config.get("upload_api_key", "")},
            timeout=5
        )
    },
    {
        "name": "POST sem arquivo, só header",
        "test": lambda: requests.post(
            config["upload_url"],
            data={"test": "value"},
            headers={"x-api-key": config.get("upload_api_key", "")},
            timeout=5
        )
    },
]

for i, test_info in enumerate(tests, 1):
    log(f"\n{i}️⃣ {test_info['name']}")
    
    try:
        response = test_info["test"]()
        
        if response.status_code in [200, 201, 202, 204]:
            log(f"   ✅ SUCESSO! Status: {response.status_code}")
            print(f"\n🎉 ENCONTRADO!")
            print(f"   Método: {test_info['name']}")
            print(f"   Status: {response.status_code}")
            break
        else:
            log(f"   Status: {response.status_code}")
            if response.text:
                log(f"   Resposta: {response.text[:80]}")
    except Exception as e:
        log(f"   Erro: {str(e)[:60]}")

os.remove(TEST_FILE)
