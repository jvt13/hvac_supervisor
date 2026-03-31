#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Teste da funcionalidade de intervalo de captura dinâmico
"""

from datetime import datetime, timedelta

def calculate_upload_end_time(now_local, interval_minutes):
    """Calcula hora final para upload somando o intervalo à hora atual"""
    interval = max(1, int(interval_minutes))
    
    # Soma o intervalo em minutos à hora atual
    end_time = now_local + timedelta(minutes=interval)
    
    # Define segundo como 59
    end_time = end_time.replace(second=59, microsecond=0)
    
    return end_time

# Casos de teste
test_cases = [
    {"descricao": "23:30 com intervalo 15 min", "hora": "23:30:00", "intervalo": 15, "esperado": "23:45:59"},
    {"descricao": "23:32 com intervalo 15 min", "hora": "23:32:00", "intervalo": 15, "esperado": "23:47:59"},
    {"descricao": "23:30 com intervalo 30 min (próximo dia)", "hora": "23:30:00", "intervalo": 30, "esperado": "00:00:59"},
    {"descricao": "10:30 com intervalo 60 min", "hora": "10:30:00", "intervalo": 60, "esperado": "11:30:59"},
    {"descricao": "12:00 com intervalo 60 min", "hora": "12:00:00", "intervalo": 60, "esperado": "13:00:59"},
    {"descricao": "23:45 com intervalo 30 min", "hora": "23:45:00", "intervalo": 30, "esperado": "00:15:59"},
    {"descricao": "00:30 com intervalo 15 min", "hora": "00:30:00", "intervalo": 15, "esperado": "00:45:59"},
]

print("=" * 80)
print("TESTE: Cálculo de Hora Final de Upload com Intervalo Dinâmico")
print("=" * 80)
print()

success_count = 0
for test in test_cases:
    h, m, s = map(int, test["hora"].split(":"))
    now = datetime.now().replace(hour=h, minute=m, second=s, microsecond=0)
    result = calculate_upload_end_time(now, test["intervalo"])
    
    # Para comparação quando passa para próximo dia
    resultado_str = result.strftime('%H:%M:%S')
    if result.day > now.day:
        resultado_str += " (próximo dia)"
    
    match = resultado_str.replace(" (próximo dia)", "") == test["esperado"].replace(" (próximo dia)", "")
    status = "✓ PASS" if match else "✗ FAIL"
    success_count += 1 if match else 0
    
    print(f"{status} | {test['descricao']}")
    print(f"      Agora:      {test['hora']}")
    print(f"      Intervalo: {test['intervalo']} minuto(s)")
    print(f"      Esperado:  {test['esperado']}")
    print(f"      Obtido:    {resultado_str}")
    print()

print("=" * 80)
print(f"Resultado: {success_count}/{len(test_cases)} testes passaram")
print("=" * 80)

if success_count == len(test_cases):
    print("\n✓ Todos os testes passaram com sucesso!")
    exit(0)
else:
    print(f"\n✗ {len(test_cases) - success_count} teste(s) falharam")
    exit(1)
