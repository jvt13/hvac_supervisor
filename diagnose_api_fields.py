#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para diagnosticar problema de campo no upload
Testa quais campos a API aceita
"""

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
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
    log(f"✓ Imagem criada")

def calculate_upload_end_time(now_local, interval_minutes):
    interval = max(1, int(interval_minutes))
    end_time = now_local + timedelta(minutes=interval)
    end_time = end_time.replace(second=59, microsecond=0)
    return end_time

def test_upload_with_fields(config, field_set):
    """Test upload with specific field set"""
    now_local = datetime.now()
    now_utc = datetime.now(timezone.utc)
    
    interval_minutes = int(config.get("capture_interval_minutes", 60))
    ends_at = calculate_upload_end_time(now_local, interval_minutes)
    ends_at_utc = ends_at.replace(tzinfo=timezone.utc)
    
    start_date = now_local.strftime("%d-%m-%Y")
    end_date = ends_at.strftime("%d-%m-%Y")
    start_time = now_local.strftime("%H:%M:%S")
    end_time = ends_at.strftime("%H:%M:%S")
    starts_at = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    ends_at_iso = ends_at_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    duration_sec = (ends_at - now_local).total_seconds()
    duration_min = int(duration_sec / 60)
    
    upload_data = {}
    
    if "campaignName" in field_set:
        upload_data["campaignName"] = config.get("upload_campaign_name", "dashboard_hvac")
    if "startsAt" in field_set:
        upload_data["startsAt"] = starts_at
    if "endsAt" in field_set:
        upload_data["endsAt"] = ends_at_iso
    if "startTime" in field_set:
        upload_data["startTime"] = start_time
    if "endTime" in field_set:
        upload_data["endTime"] = end_time
    if "startDate" in field_set:
        upload_data["startDate"] = start_date
    if "endDate" in field_set:
        upload_data["endDate"] = end_date
    if "duration" in field_set:
        upload_data["duration"] = str(duration_min)
    if "name" in field_set:
        upload_data["name"] = config.get("upload_name", "dashboard")
    if "group" in field_set:
        upload_data["group"] = config.get("upload_group", "")
    
    headers = {
        "x-api-key": config.get("upload_api_key", "")
    }
    
    log(f"\n📋 Testando com campos: {', '.join(sorted(field_set))}")
    log(f"   Payload: {json.dumps(upload_data, indent=2)}")
    
    try:
        with open(LATEST_DASHBOARD_FILE, "rb") as fh:
            files = {"file": fh}
            response = requests.post(
                config["upload_url"],
                data=upload_data,
                files=files,
                headers=headers,
                timeout=30
            )
        
        if response.status_code in [200, 201, 204]:
            log(f"✓ SUCESSO! Status: {response.status_code}")
            return True
        else:
            log(f"✗ Falha. Status: {response.status_code}")
            log(f"   Resposta: {response.text[:200]}")
            return False
    except Exception as e:
        log(f"✗ Erro: {e}")
        return False

def main():
    print("\n" + "="*70)
    print("DIAGNOSTICO: Teste de campos API")
    print("="*70)
    
    config = load_config()
    create_test_image()
    
    # Test different field combinations
    test_cases = [
        # Minimal set
        {"startsAt", "endsAt", "duration", "name"},
        
        # With campaign name
        {"campaignName", "startsAt", "endsAt", "duration", "name"},
        
        # With times
        {"campaignName", "startsAt", "endsAt", "startTime", "endTime", "duration", "name"},
        
        # With dates
        {"campaignName", "startsAt", "endsAt", "startDate", "endDate", "duration", "name"},
        
        # All fields
        {"campaignName", "startsAt", "endsAt", "startTime", "endTime", "startDate", "endDate", "duration", "name", "group"},
        
        # Without group
        {"campaignName", "startsAt", "endsAt", "startTime", "endTime", "startDate", "endDate", "duration", "name"},
    ]
    
    results = []
    for i, field_set in enumerate(test_cases, 1):
        success = test_upload_with_fields(config, field_set)
        results.append((field_set, success))
        if success:
            log(f"\n🎉 ENCONTRADO! Este conjunto de campos funcionou!")
            break
    
    print("\n" + "="*70)
    print("RESUMO")
    print("="*70)
    for field_set, success in results:
        status = "✓" if success else "✗"
        print(f"{status} {', '.join(sorted(field_set))}")

if __name__ == "__main__":
    main()
