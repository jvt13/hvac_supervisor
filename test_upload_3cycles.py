#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de teste: 3 ciclos de upload respeitando intervalo de 1 minuto
Simula execução normal do supervisor com uploads periódicos
"""

import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
import requests
from PIL import Image, ImageDraw, ImageFont

# Paths
CONFIG_FILE = "config.json"
TEST_IMAGE_DIR = "test_images"
LATEST_DASHBOARD_FILE = "latest_dashboard.png"

def log(msg):
    """Print timestamp log"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")

def load_config():
    """Load configuration"""
    with open(CONFIG_FILE, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)

def create_test_image(cycle_num):
    """Create a test dashboard image"""
    os.makedirs(TEST_IMAGE_DIR, exist_ok=True)
    
    img = Image.new("RGB", (1074, 567), color=(30, 30, 30))
    draw = ImageDraw.Draw(img)
    
    # Draw text
    text = f"HVAC Dashboard Teste - Ciclo {cycle_num}\n{datetime.now().strftime('%H:%M:%S')}"
    try:
        draw.text((50, 50), text, fill=(255, 255, 255))
    except:
        # If font loading fails, just continue
        pass
    
    filepath = os.path.join(TEST_IMAGE_DIR, f"test_dashboard_cycle_{cycle_num}.png")
    img.save(filepath)
    
    # Also save as latest_dashboard for upload
    img.save(LATEST_DASHBOARD_FILE)
    log(f"✓ Imagem de teste criada: {filepath}")
    return filepath

def calculate_upload_end_time(now_local, interval_minutes):
    """Calculate upload end time"""
    interval = max(1, int(interval_minutes))
    end_time = now_local + timedelta(minutes=interval)
    end_time = end_time.replace(second=59, microsecond=0)
    return end_time

def upload_to_api(config, cycle_num):
    """Upload image to API"""
    if not os.path.exists(LATEST_DASHBOARD_FILE):
        log(f"✗ Erro: arquivo {LATEST_DASHBOARD_FILE} não encontrado")
        return False
    
    now_utc = datetime.now(timezone.utc)
    interval_minutes = int(config.get("capture_interval_minutes", 60))
    ends_at_utc = now_utc + timedelta(minutes=interval_minutes)
    ends_at_utc = ends_at_utc.replace(second=59, microsecond=0)
    
    # Format timestamps in UTC
    starts_at = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    ends_at_iso = ends_at_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Calculate duration in minutes
    duration_min = int((ends_at_utc - now_utc).total_seconds() / 60)
    
    # Prepare upload data
    upload_data = {
        "campaignName": config.get("upload_campaign_name", "dashboard_hvac"),
        "startsAt": starts_at,
        "endsAt": ends_at_iso,
        "duration": str(duration_min),
        "name": config.get("upload_name", "dashboard"),
    }
    
    # Add optional fields
    group = config.get("upload_group", "")
    if group:
        upload_data["group"] = group
    
    headers = {
        "x-api-key": config.get("upload_api_key", "")
    }
    
    try:
        log(f"📤 Ciclo {cycle_num}: Enviando para {config['upload_url']}")
        log(f"   - Payload: campaignName={upload_data['campaignName']}, starts={starts_at}, ends={ends_at_iso}")
        log(f"   - Duration: {duration_min} minutos")
        
        with open(LATEST_DASHBOARD_FILE, "rb") as fh:
            files = {"file": ("dashboard.png", fh, "image/png")}
            timeout = int(config.get("upload_timeout_seconds", 30))
            response = requests.post(
                config["upload_url"],
                data=upload_data,
                files=files,
                headers=headers,
                timeout=timeout
            )
        
        if response.status_code in [200, 201, 204]:
            log(f"✓ Ciclo {cycle_num}: Upload bem-sucedido! Status: {response.status_code}")
            if response.text:
                log(f"   Response: {response.text[:100]}")
            return True
        else:
            log(f"✗ Ciclo {cycle_num}: Falha no upload. Status: {response.status_code}")
            log(f"   Response: {response.text[:200]}")
            return False
    
    except requests.ConnectionError:
        log(f"✗ Ciclo {cycle_num}: Erro de conexão. Verifique se a API está em {config['upload_url']}")
        return False
    except requests.Timeout:
        log(f"✗ Ciclo {cycle_num}: Timeout na conexão (>{timeout}s)")
        return False
    except Exception as e:
        log(f"✗ Ciclo {cycle_num}: Erro no upload: {e}")
        return False

def main():
    """Main test loop"""
    print("\n" + "="*70)
    print("TEST MODE: 3 Ciclos de Upload com intervalo de 1 minuto")
    print("="*70 + "\n")
    
    config = load_config()
    
    log(f"Config carregada:")
    log(f"  - Intervalo captura: {config.get('capture_interval_minutes')} minutos")
    log(f"  - Upload habilitado: {config.get('upload_enabled')}")
    log(f"  - URL API: {config.get('upload_url')}")
    log(f"  - Timeout: {config.get('upload_timeout_seconds')} segundos\n")
    
    results = []
    
    for cycle in range(1, 4):
        log(f"\n{'='*70}")
        log(f"CICLO {cycle} DE 3")
        log(f"{'='*70}")
        
        # Create test image
        create_test_image(cycle)
        
        # Upload to API
        success = upload_to_api(config, cycle)
        results.append(success)
        
        # Wait 1 minute between cycles (except after last)
        if cycle < 3:
            log(f"⏳ Aguardando 1 minuto antes do próximo ciclo...")
            for remaining in range(60, 0, -1):
                if remaining % 10 == 0 or remaining <= 5:
                    print(f"   {remaining}s restantes...", end="\r")
                time.sleep(1)
            print(" " * 30, end="\r")
    
    # Summary
    print(f"\n{'='*70}")
    print("RESUMO DOS TESTES")
    print(f"{'='*70}\n")
    
    for i, success in enumerate(results, 1):
        status = "✓ SUCESSO" if success else "✗ FALHA"
        log(f"Ciclo {i}: {status}")
    
    total_success = sum(results)
    log(f"\nTotal: {total_success}/{len(results)} ciclos bem-sucedidos")
    
    if total_success == len(results):
        log("✓ Todos os testes passaram! Upload está funcionando corretamente.")
        return 0
    else:
        log("✗ Alguns testes falharam. Verifique a configuração da API.")
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Teste interrompido pelo usuário")
        sys.exit(1)
