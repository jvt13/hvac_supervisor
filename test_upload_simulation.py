#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Teste de simulação de upload para a API de campanha
"""

import json
import mimetypes
from datetime import datetime, timedelta, timezone
from pathlib import Path
from PIL import Image

print("=" * 80)
print("TESTE DE UPLOAD - HVAC_SUPERVISOR")
print("=" * 80)
print()

# 1. Carregar config
with open("config.json", 'r', encoding='utf-8') as f:
    config = json.load(f)

# 2. Criar imagem de teste
test_image_path = Path("test_dashboard.png")
print("1. Gerando imagem de teste...")
img = Image.new('RGB', (1152, 568), color=(73, 109, 137))
img.save(test_image_path)
print(f"   ✓ Imagem criada: {test_image_path} ({test_image_path.stat().st_size} bytes)")
print()

# 3. Simular cálculo de upload_end_time
def calculate_upload_end_time(now_local, interval_minutes):
    """Calcula a hora final para o upload"""
    interval = max(1, int(interval_minutes))
    end_time = now_local + timedelta(minutes=interval)
    end_time = end_time.replace(second=59, microsecond=0)
    return end_time

print("2. Calculando timestamps de upload...")
now_local = datetime.now().astimezone()
interval_minutes = int(config.get("capture_interval_minutes", 60))
end_of_interval_local = calculate_upload_end_time(now_local, interval_minutes)

now_dt = now_local.astimezone(timezone.utc)
end_of_interval_dt = end_of_interval_local.astimezone(timezone.utc)

starts_at = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
ends_at = end_of_interval_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
campaign_name = f"dashboard_hvac_{now_dt.strftime('%H_%M')}"

print(f"   Hora local atual: {now_local.strftime('%Y-%m-%d %H:%M:%S %z')}")
print(f"   Intervalo configurado: {interval_minutes} minutos")
print(f"   Hora final calculada: {end_of_interval_local.strftime('%Y-%m-%d %H:%M:%S %z')}")
print()

# 4. Extrair MIME type
print("3. Detectando tipo de arquivo...")
mime_type = "image/png"
print(f"   ✓ MIME Type: {mime_type}")
print()

# 5. Preparar headers
print("4. Preparando headers HTTP...")
headers = {
    "x-api-key": config.get("upload_api_key", "").strip()
}
print(f"   Authorization Header:")
print(f"     x-api-key: {headers['x-api-key']}")
print()

# 6. Preparar payload
print("5. Preparando payload da requisição...")

def _para_data_dd_mm_yyyy(valor):
    """Converte ISO datetime para DD-MM-YYYY"""
    texto = (valor or "").strip()
    if not texto:
        return texto
    try:
        if texto.endswith("Z"):
            dt = datetime.fromisoformat(texto.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(texto)
        return dt.strftime("%d-%m-%Y")
    except ValueError:
        return texto

data = {
    "campaignName": campaign_name,
    "startsAt": starts_at,
    "endsAt": ends_at,
    "startTime": starts_at,
    "endTime": ends_at,
    "startDate": _para_data_dd_mm_yyyy(starts_at),
    "endDate": _para_data_dd_mm_yyyy(ends_at),
    "duration": str(config.get("upload_duration", "")).strip(),
    "name": str(config.get("upload_name", "")).strip(),
}

group = str(config.get("upload_group", "")).strip()
if group:
    data["group"] = group

print("   ✓ Payload preparado")
print()

# 7. Exibir payload completo
print("=" * 80)
print("DADOS QUE SERÃO ENVIADOS PARA A API")
print("=" * 80)
print()

print("📤 REQUISIÇÃO HTTP POST")
print("-" * 80)
print(f"URL: {config.get('upload_url', '').strip()}")
print()

print("Headers:")
for key, value in headers.items():
    valor_display = value if len(value) < 30 else value[:27] + "..."
    print(f"  {key}: {valor_display}")
print()

print("Body (form-data multipart):")
print()
print("┌─ Campos de texto:")
for key, value in data.items():
    valor_display = str(value) if len(str(value)) < 50 else str(value)[:47] + "..."
    print(f"│  {key}: {valor_display}")
print()
print("├─ Arquivo:")
print(f"│  mediaFile: {test_image_path.name} ({mime_type})")
print(f"│  Tamanho: {test_image_path.stat().st_size} bytes")
print("└")
print()

# 8. Mostrar resumo
print("=" * 80)
print("📊 RESUMO DO UPLOAD")
print("=" * 80)
print()
print(f"Tipo de Campanha: {data.get('campaignName', 'N/A')}")
print(f"Nome da Campanha: {data.get('name', 'N/A')}")
print(f"Duração: {data.get('duration', 'N/A')} minutos")
print()
print(f"Início (starts_at):     {data.get('startsAt', 'N/A')}")
print(f"Fim (ends_at):          {data.get('endsAt', 'N/A')}")
print(f"Data Início:            {data.get('startDate', 'N/A')}")
print(f"Data Fim:               {data.get('endDate', 'N/A')}")
print()

# 9. Cálculo de intervalo
start_dt = datetime.fromisoformat(starts_at.replace("Z", "+00:00"))
end_dt = datetime.fromisoformat(ends_at.replace("Z", "+00:00"))
duration_seconds = (end_dt - start_dt).total_seconds()
duration_minutes = duration_seconds / 60

print(f"⏱️  Intervalo de Cobertura:")
print(f"  Duração total: {int(duration_minutes)} minutos ({int(duration_seconds)} segundos)")
print()

if group:
    print(f"👥 Grupo: {group}")

print()
print("=" * 80)
print("✓ TESTE SIMULADO COM SUCESSO")
print("=" * 80)
print()
print("📝 Observações:")
print("  • mediaFile é enviado como arquivo binário (multipart/form-data)")
print("  • Os timestamps estão em UTC (Z = Zulu/UTC)")
print("  • O intervalo de 'ends_at' é calculado dinamicamente baseado em 'capture_interval_minutes'")
print("  • API receberá uma imagem real quando 'upload_enabled' for 'true'")
print()

# Limpar arquivo de teste
test_image_path.unlink()
print("✓ Arquivo de teste removido")
