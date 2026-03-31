#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para resetar senha do painel para a senha padrão
"""

import json
import hashlib
import secrets

CONFIG_FILE = "config.json"
DEFAULT_PASSWORD = "HVAC_SUPERVISOR_2026!"

def hash_password(password, salt_hex=None):
    """Gera hash PBKDF2-SHA256 da senha"""
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200000)
    return salt.hex(), digest.hex()

print("=" * 80)
print("RESET DE SENHA - HVAC_SUPERVISOR")
print("=" * 80)
print()

# Carregar config
with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
    config = json.load(f)

print(f"Usuário anterior: {config.get('auth_username', 'admin')}")
print(f"Hash anterior: {config['auth_password_hash'][:20]}...")
print()

# Gerar novo hash para a senha padrão
salt_hex, password_hash = hash_password(DEFAULT_PASSWORD)

print("Resetando para senha padrão...")
print(f"Nova senha: {DEFAULT_PASSWORD}")
print()

# Atualizar config
config["auth_username"] = "admin"
config["auth_password_salt"] = salt_hex
config["auth_password_hash"] = password_hash

# Salvar
with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
    json.dump(config, f, indent=4, ensure_ascii=False)

print(f"✓ Novo salt: {salt_hex}")
print(f"✓ Novo hash: {password_hash}")
print()
print("=" * 80)
print("✓ Senha resetada com sucesso!")
print("=" * 80)
print()
print("Acesse o painel com:")
print("  Usuário: admin")
print(f"  Senha:   {DEFAULT_PASSWORD}")
print()
