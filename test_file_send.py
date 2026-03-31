#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste: Corrigir o envio do arquivo
"""

import json
import os
from datetime import datetime, timezone, timedelta
import requests

CONFIG_FILE = "config.json"
IMAGE_FILE = "test_images/test_dashboard_cycle_1.png"

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)

config = load_config()

print("\n" + "="*70)
print("TESTE: Upload correto do arquivo")
print("="*70)

if not os.path.exists(IMAGE_FILE):
    print(f"Erro: {IMAGE_FILE} nao encontrado")
else:
    file_size = os.path.getsize(IMAGE_FILE)
    print(f"\nArquivo: {IMAGE_FILE}")
    print(f"Tamanho: {file_size} bytes")

    now_utc = datetime.now(timezone.utc)
    end_utc = (now_utc + timedelta(minutes=1)).replace(tzinfo=timezone.utc)
    
    payload = {
        "campaignName": "dashboard_hvac",
        "startsAt": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "endsAt": end_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duration": "1",
        "name": "dashboard"
    }
    
    # Method 1: Keep file open during request
    print("\n[METODO 1] File open durante request:")
    try:
        with open(IMAGE_FILE, "rb") as file_obj:
            files = {"file": ("dashboard.png", file_obj, "image/png")}
            response = requests.post(
                config["upload_url"],
                data=payload,
                files=files,
                headers={"x-api-key": config.get("upload_api_key", "")},
                timeout=10
            )
        
        print(f"  Status: {response.status_code}")
        print(f"  Resposta: {response.text}")
        
        if response.status_code in [200, 201, 202, 204]:
            print(f"\n[SUCESSO]")
            exit(0)
    except Exception as e:
        print(f"  Erro: {e}")
    
    # Method 2: Read file into memory first
    print("\n[METODO 2] Read file into memory:")
    try:
        with open(IMAGE_FILE, "rb") as f:
            file_content = f.read()
        
        files = {"file": ("dashboard.png", file_content, "image/png")}
        response = requests.post(
            config["upload_url"],
            data=payload,
            files=files,
            headers={"x-api-key": config.get("upload_api_key", "")},
            timeout=10
        )
        
        print(f"  Status: {response.status_code}")
        print(f"  Resposta: {response.text}")
        
        if response.status_code in [200, 201, 202, 204]:
            print(f"\n[SUCESSO]")
            exit(0)
    except Exception as e:
        print(f"  Erro: {e}")
    
    # Method 3: Try with just files parameter
    print("\n[METODO 3] Apenas files parameter:")
    try:
        files = {"file": open(IMAGE_FILE, "rb")}
        response = requests.post(
            config["upload_url"],
            data=payload,
            files=files,
            headers={"x-api-key": config.get("upload_api_key", "")},
            timeout=10
        )
        
        print(f"  Status: {response.status_code}")
        print(f"  Resposta: {response.text}")
        
        if response.status_code in [200, 201, 202, 204]:
            print(f"\n[SUCESSO]")
            exit(0)
    except Exception as e:
        print(f"  Erro: {e}")
        
    print("\n[Nenhum metodo funcionou]")
