#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste: Usar imagem PNG real criada pelos testes
"""

import json
import os
from datetime import datetime, timezone, timedelta
import requests

CONFIG_FILE = "config.json"
IMAGE_FILE = "test_images/test_dashboard_cycle_1.png"

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)

config = load_config()

print("\n" + "="*70)
print("TEST: Usando imagem PNG real")
print("="*70)

if not os.path.exists(IMAGE_FILE):
    log(f"Erro: {IMAGE_FILE} não encontrado")
else:
    file_size = os.path.getsize(IMAGE_FILE) / 1024
    log(f"✓ Arquivo: {IMAGE_FILE}")
    log(f"  Tamanho: {file_size:.1f}KB")
    
    now_utc = datetime.now(timezone.utc)
    end_utc = (now_utc + timedelta(minutes=1)).replace(tzinfo=timezone.utc)
    
    payload = {
        "campaignName": "dashboard_hvac",
        "startsAt": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "endsAt": end_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duration": "1",
        "name": "dashboard"
    }
    
    log(f"\nPayload: {json.dumps(payload, indent=2)}")
    
    try:
        log(f"\n📤 Enviando para {config['upload_url']}")
        with open(IMAGE_FILE, "rb") as fh:
            files = {"file": fh}
            response = requests.post(
                config["upload_url"],
                data=payload,
                files=files,
                headers={"x-api-key": config.get("upload_api_key", "")},
                timeout=10
            )
        
        log(f"Status: {response.status_code}")
        log(f"Resposta: {response.text[:200]}")
        
        if response.status_code in [200, 201, 202, 204]:
            log(f"\n✅ SUCESSO!")
        else:
            log(f"\n❌ Falha")
    except Exception as e:
        log(f"\n❌ Erro: {e}")
