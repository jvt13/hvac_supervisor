#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste: Debug detalhado de headers e multipart
"""

import json
import os
from datetime import datetime, timezone, timedelta
import requests
from requests.models import Request, PreparedRequest
from requests import Session

CONFIG_FILE = "config.json"
IMAGE_FILE = "test_images/test_dashboard_cycle_1.png"

def log(msg):
    print(msg)

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)

config = load_config()

print("\n" + "="*70)
print("DEBUG: Análise de headers e multipart")
print("="*70)

payload = {
    "campaignName": "dashboard_hvac",
    "startsAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "endsAt": (datetime.now(timezone.utc) + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "duration": "1",
    "name": "dashboard"
}

log(f"\nPayload: {payload}")
log(f"File: {IMAGE_FILE}")
log(f"URL: {config['upload_url']}")

# Build request to see headers
with open(IMAGE_FILE, "rb") as fh:
    files = {"file": fh}
    s = Session()
    req = Request(
        "POST",
        config["upload_url"],
        data=payload,
        files=files,
        headers={"x-api-key": config.get("upload_api_key", "")}
    )
    prepared = s.prepare_request(req)
    
    log(f"\n[HEADERS ENVIADOS]")
    for k, v in prepared.headers.items():
        log(f"  {k}: {v[:100]}")
    
    log(f"\n[BODY - PRIMEIROS 500 BYTES]")
    if isinstance(prepared.body, bytes):
        body_preview = prepared.body[:500]
        try:
            log(f"  {body_preview.decode('utf-8', errors='replace')}")
        except:
            log(f"  [Binary data - {len(prepared.body)} bytes]")
    else:
        log(f"  {str(prepared.body)[:500]}")

# Now send actual request
log(f"\n[ENVIANDO REQUEST]")
try:
    with open(IMAGE_FILE, "rb") as fh:
        files = {"file": fh}
        response = requests.post(
            config["upload_url"],
            data=payload,
            files=files,
            headers={"x-api-key": config.get("upload_api_key", "")},
            timeout=10
        )
    
    log(f"\n[RESPONSE]")
    log(f"  Status: {response.status_code}")
    log(f"  Headers: {dict(response.headers)}")
    log(f"  Body: {response.text}")
except Exception as e:
    log(f"\n[ERRO]: {e}")
