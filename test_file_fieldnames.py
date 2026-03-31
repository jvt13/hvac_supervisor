#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Debug: Testa diferentes nomes para o campo do arquivo"""

import json
import os
from datetime import datetime
import requests
from PIL import Image

CONFIG_FILE = "config.json"
LATEST_DASHBOARD_FILE = "latest_dashboard.png"

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)

try:
    img = Image.new("RGB", (100, 100), color=(30, 30, 30))
    img.save(LATEST_DASHBOARD_FILE)
    
    config = load_config()
    
    print("\n" + "="*70)
    print("Testando diferentes nomes para o campo do arquivo")
    print("="*70 + "\n")
    
    field_names = ["file", "image", "photo", "capture", "dashboard", "media", "document"]
    
    for field_name in field_names:
        log(f"Testando field_name='{field_name}'")
        try:
            with open(LATEST_DASHBOARD_FILE, "rb") as fh:
                files = {field_name: fh}
                response = requests.post(
                    config["upload_url"],
                    files=files,
                    headers={"x-api-key": config.get("upload_api_key", "")},
                    timeout=3
                )
            
            if response.status_code in [200, 201, 204]:
                log(f"   ✓ SUCESSO! Status: {response.status_code}")
                print(f"\n✅ ENCONTRADO: Use field_name = '{field_name}'")
                break
            else:
                error_msg = response.text[:50] if response.text else "sem mensagem"
                log(f"   Status: {response.status_code} - {error_msg}")
        except requests.Timeout:
            log(f"   Timeout")
        except Exception as e:
            log(f"   Erro: {str(e)[:50]}")
            
except Exception as e:
    print(f"Erro geral: {e}")
