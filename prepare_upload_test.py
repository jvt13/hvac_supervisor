#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para preparar ambiente para teste de upload com intervalo de 1 minuto
"""

import json
from datetime import datetime, timedelta

print("=" * 80)
print("PREPARAÇÃO PARA TESTE DE UPLOAD - 1 MINUTO")
print("=" * 80)
print()

# Carregar config
with open("config.json", 'r', encoding='utf-8') as f:
    config = json.load(f)

print("Situação ANTES:")
print(f"  capture_interval_minutes: {config.get('capture_interval_minutes')}")
print(f"  upload_enabled: {config.get('upload_enabled')}")
print(f"  last_dashboard_capture_at: {config.get('last_dashboard_capture_at')}")
print()

# Fazer ajustes
print("Aplicando ajustes...")
print()

# 1. Reset do timestamp para forçar captura imediata
old_timestamp = config.get('last_dashboard_capture_at', '')
# Voltar 2 minutos para garantir que crossed a window
now = datetime.now()
reset_time = (now - timedelta(minutes=3)).strftime("%Y-%m-%d %H:%M:%S")
config['last_dashboard_capture_at'] = reset_time
print(f"  ✓ Reset timestamp de captura:")
print(f"    De: {old_timestamp}")
print(f"    Para: {reset_time}")
print(f"    (Força captura na próxima janela)")
print()

# 2. Ativar upload
config['upload_enabled'] = True
print(f"  ✓ Ativado upload_enabled: true")
print()

# 3. Confirmar intervalo
interval = config.get('capture_interval_minutes', 60)
print(f"  ✓ Intervalo configurado: {interval} minuto(s)")
print()

# Salvar config
with open("config.json", 'w', encoding='utf-8') as f:
    json.dump(config, f, indent=4, ensure_ascii=False)

print("=" * 80)
print("✓ CONFIG.JSON ATUALIZADO")
print("=" * 80)
print()

print("Situação DEPOIS:")
print(f"  capture_interval_minutes: {config.get('capture_interval_minutes')}")
print(f"  upload_enabled: {config.get('upload_enabled')}")
print(f"  last_dashboard_capture_at: {config.get('last_dashboard_capture_at')}")
print()

print("=" * 80)
print("📋 PRÓXIMAS PASSOS:")
print("=" * 80)
print()
print("1. A aplicação vai ler o novo config.json")
print("2. Na próxima verificação de captura:")
print("   - Vai detectar que passou a janela de 1 minuto")
print("   - Vai fazer uma CAPTURA")
print("   - Como upload_enabled=true, vai FAZER UPLOAD")
print()
print("3. Nos logs, você verá:")
print("   ✓ 'Captura salva com intervalo de 1 min'")
print("   ✓ 'Upload da imagem do dashboard concluido'")
print()
print("💡 Se upload falhar na API, verá:")
print("   ✗ 'Erro no upload da imagem do dashboard: [motivo]'")
print()
print("⏱️  Vai repetir a cada 1 minuto enquanto automação estiver ativa")
print()
