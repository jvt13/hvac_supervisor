#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script avançado de debug - testa um campo por vez
"""

import json
import os
from datetime import datetime, timezone, timedelta
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

def create_test_image():
    img = Image.new("RGB", (1074, 567), color=(30, 30, 30))
    img.save(LATEST_DASHBOARD_FILE)

def calculate_upload_end_time(now_local, interval_minutes):
    interval = max(1, int(interval_minutes))
    end_time = now_local + timedelta(minutes=interval)
    end_time = end_time.replace(second=59, microsecond=0)
    return end_time

def test_only_file(config):
    """Test with file only"""
    log("\n1️⃣ Teste: APENAS ARQUIVO (sem campos)")
    try:
        with open(LATEST_DASHBOARD_FILE, "rb") as fh:
            files = {"file": fh}
            response = requests.post(
                config["upload_url"],
                files=files,
                headers={"x-api-key": config.get("upload_api_key", "")},
                timeout=5
            )
        log(f"   Status: {response.status_code}")
        if response.status_code not in [200, 201, 204]:
            log(f"   Erro: {response.text[:150]}")
            return False
        return True
    except Exception as e:
        log(f"   Erro: {e}")
        return False

def test_single_fields(config):
    """Test with single fields one at a time"""
    now_local = datetime.now()
    now_utc = datetime.now(timezone.utc)
    
    interval_minutes = int(config.get("capture_interval_minutes", 60))
    ends_at = calculate_upload_end_time(now_local, interval_minutes)
    ends_at_utc = ends_at.replace(tzinfo=timezone.utc)
    
    fields_data = {
        "campaignName": config.get("upload_campaign_name", "dashboard_hvac"),
        "startsAt": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "endsAt": ends_at_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "startTime": now_local.strftime("%H:%M:%S"),
        "endTime": ends_at.strftime("%H:%M:%S"),
        "startDate": now_local.strftime("%d-%m-%Y"),
        "endDate": ends_at.strftime("%d-%m-%Y"),
        "duration": "1",
        "name": config.get("upload_name", "dashboard"),
        "group": config.get("upload_group", ""),
    }
    
    for idx, (field_name, field_value) in enumerate(fields_data.items(), 2):
        log(f"\n{idx}️⃣ Teste: APENAS CAMPO '{field_name}' = {field_value[:30] if len(str(field_value)) > 30 else field_value}")
        
        try:
            with open(LATEST_DASHBOARD_FILE, "rb") as fh:
                files = {"file": fh}
                data = {field_name: field_value}
                response = requests.post(
                    config["upload_url"],
                    data=data,
                    files=files,
                    headers={"x-api-key": config.get("upload_api_key", "")},
                    timeout=5
                )
            
            if response.status_code in [200, 201, 204]:
                log(f"   ✓ Status: {response.status_code} - CAMPO OK")
                return field_name
            else:
                log(f"   Status: {response.status_code}")
                log(f"   Erro: {response.text[:100]}")
        except Exception as e:
            log(f"   Erro conexão: {e}")
    
    return None

def main():
    print("\n" + "="*70)
    print("DEBUG AVANÇADO: Testando um campo por vez")
    print("="*70)
    
    config = load_config()
    create_test_image()
    
    # First just file
    if test_only_file(config):
        log("\n✓ Arquivo sozinho funciona!")
    else:
        log("\n✗ Problema com arquivo ou API")
        return
    
    # Then single fields
    log("\n" + "─"*70)
    log("Testando campos individuais...")
    log("─"*70)
    
    working_field = test_single_fields(config)
    
    if working_field:
        log(f"\n🎉 Campo '{working_field}' funcionou isolado!")
    else:
        log("\n❌ Nenhum campo funcionou isolado - problema com API ou chave")

if __name__ == "__main__":
    main()
