import json
import os
import re
import subprocess
import sys
import threading
import time
import mimetypes
import hashlib
import hmac
import html
import secrets
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import psutil
import pyautogui
import pytesseract
import requests
from PIL import Image, UnidentifiedImageError

CONFIG_FILE = "config.json"
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "supervisor.log")
OUTPUT_DIR = "saida_imagens"
CONFIG_OUTPUT_DIR = os.path.join(OUTPUT_DIR, "config")
LATEST_DASHBOARD_FILE = os.path.join(OUTPUT_DIR, "dashboard.png")
CONFIG_DASHBOARD_FILE = os.path.join(CONFIG_OUTPUT_DIR, "dashboard_area.png")
CONFIG_CLOCK_FILE = os.path.join(CONFIG_OUTPUT_DIR, "clock_area.png")
CONFIG_IDENTITY_FILE = os.path.join(CONFIG_OUTPUT_DIR, "dashboard_identity.png")
CONFIG_IDENTITY_TEXT_FILE = os.path.join(CONFIG_OUTPUT_DIR, "dashboard_identity.txt")
DEFAULT_CONFIG_USERNAME = "admin"
DEFAULT_CONFIG_PASSWORD = "HVAC_SUPERVISOR_2026!"
SESSION_COOKIE_NAME = "hvac_session"
SESSION_TTL_SECONDS = 8 * 60 * 60
REGION_MIN_SIZE = {
    "dashboard": (50, 50),
    "clock": (20, 10),
    "identity": (20, 10),
}

DEFAULT_CONFIG = {
    "dashboard_url": "http://192.168.10.15:3000/player",
    "chrome_path": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "tesseract_path": r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    "monitor_interval_sec": 30,
    "freeze_threshold_sec": 20,
    "max_ocr_failures": 3,
    "ocr_timeout_sec": 10,
    "restart_browser_on_freeze": True,
    "dashboard_x": 250,
    "dashboard_y": 120,
    "dashboard_width": 1450,
    "dashboard_height": 780,
    "clock_x": 1200,
    "clock_y": 900,
    "clock_width": 300,
    "clock_height": 80,
    "identity_x": 120,
    "identity_y": 120,
    "identity_width": 220,
    "identity_height": 60,
    "identity_match_confidence": 0.8,
    "identity_text_match_enabled": True,
    "config_host": "127.0.0.1",
    "config_port": 8787,
    "automation_enabled": False,
    "last_position_setup_date": "",
    "last_dashboard_capture_at": "",
    "capture_interval_minutes": 60,
    "upload_enabled": False,
    "upload_url": "http://localhost:3000/media/api/campaigns/upload",
    "upload_api_key": "chv1N9bKq7rXz3uH",
    "upload_timeout_seconds": 30,
    "upload_campaign_name": "dashboard_hvac",
    "upload_duration": "10",
    "upload_name": "dashboard",
    "upload_group": "",
    "auth_username": DEFAULT_CONFIG_USERNAME,
    "auth_password_hash": "",
    "auth_password_salt": "",
}

CONFIG_LOCK = threading.Lock()
ASSISTANT_REQUEST = threading.Event()
ASSISTANT_RUNNING = threading.Event()
CAPTURE_DASHBOARD_REQUEST = threading.Event()
CAPTURE_CLOCK_REQUEST = threading.Event()
CAPTURE_IDENTITY_REQUEST = threading.Event()
SNAPSHOT_CLOCK_REQUEST = threading.Event()
LAST_GOOD_CONFIG = dict(DEFAULT_CONFIG)
ACTIVE_SESSIONS = {}


def runtime_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def is_process_running(process_name):
    for proc in psutil.process_iter(["name"]):
        if (proc.info.get("name") or "").lower() == process_name.lower():
            return True
    return False


def watchdog_executable_path():
    base = runtime_dir()
    candidates = [
        os.path.join(base, "HVAC_WATCHDOG.exe"),
        os.path.join(os.path.dirname(base), "HVAC_WATCHDOG", "HVAC_WATCHDOG.exe"),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return None


def ensure_watchdog_running():
    process_name = "HVAC_WATCHDOG.exe"
    if is_process_running(process_name):
        return

    exe_path = watchdog_executable_path()
    if not exe_path:
        return

    try:
        subprocess.Popen([exe_path], cwd=os.path.dirname(exe_path))
        log(f"Watchdog iniciado automaticamente: {exe_path}")
    except Exception as exc:
        log(f"Falha ao iniciar watchdog automaticamente: {exc}")


def log(message):
    os.makedirs(LOG_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as fh:
        fh.write(f"{timestamp} | {message}\n")
    print(f"{timestamp} | {message}")


def hash_password(password, salt_hex=None):
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200000)
    return salt.hex(), digest.hex()


def verify_password(password, salt_hex, expected_hash):
    if not password or not salt_hex or not expected_hash:
        return False
    _, computed_hash = hash_password(password, salt_hex)
    return hmac.compare_digest(computed_hash, expected_hash)


def ensure_auth_config(config, persist=False):
    changed = False
    if not str(config.get("auth_username", "")).strip():
        config["auth_username"] = DEFAULT_CONFIG_USERNAME
        changed = True
    if not config.get("auth_password_hash") or not config.get("auth_password_salt"):
        salt_hex, password_hash = hash_password(DEFAULT_CONFIG_PASSWORD)
        config["auth_password_salt"] = salt_hex
        config["auth_password_hash"] = password_hash
        changed = True
        log(
            "Credenciais do painel inicializadas. "
            f"Usuario padrao: {config['auth_username']} | Senha padrao: {DEFAULT_CONFIG_PASSWORD}"
        )
    if changed and persist:
        save_config(config)
    return config


def sanitize_region(x, y, width, height):
    return int(x), int(y), max(0, int(width)), max(0, int(height))


def region_min_size(prefix):
    return REGION_MIN_SIZE.get(prefix, (1, 1))


def normalize_loaded_region(config, fallback_config, prefix):
    min_width, min_height = region_min_size(prefix)
    width_key = f"{prefix}_width"
    height_key = f"{prefix}_height"
    if int(config.get(width_key, 0)) >= min_width and int(config.get(height_key, 0)) >= min_height:
        return config

    fallback_width = int(fallback_config.get(width_key, DEFAULT_CONFIG[width_key]))
    fallback_height = int(fallback_config.get(height_key, DEFAULT_CONFIG[height_key]))
    log(
        f"Configuracao invalida detectada para {prefix}: "
        f"{config.get(width_key)}x{config.get(height_key)}. "
        f"Restaurando dimensoes para {fallback_width}x{fallback_height}."
    )
    config[width_key] = fallback_width
    config[height_key] = fallback_height
    return config


def validate_region_values(prefix, x, y, width, height, fallback_config, source):
    x, y, width, height = sanitize_region(x, y, width, height)
    min_width, min_height = region_min_size(prefix)
    if width < min_width or height < min_height:
        fallback = get_region(fallback_config, prefix)
        log(
            f"Regiao invalida ignorada para {prefix} via {source}: "
            f"{width}x{height}. Minimo esperado: {min_width}x{min_height}. "
            f"Mantendo ultima regiao valida: {fallback}."
        )
        return fallback
    return x, y, width, height


def update_region_in_payload(payload, fallback_config, prefix, x, y, width, height, source):
    valid_x, valid_y, valid_w, valid_h = validate_region_values(
        prefix, x, y, width, height, fallback_config, source
    )
    payload[f"{prefix}_x"] = valid_x
    payload[f"{prefix}_y"] = valid_y
    payload[f"{prefix}_width"] = valid_w
    payload[f"{prefix}_height"] = valid_h
    return payload


def escape_value(value):
    return html.escape(str(value or ""), quote=True)


def cleanup_expired_sessions():
    now = time.time()
    expired_tokens = [token for token, expires_at in ACTIVE_SESSIONS.items() if expires_at <= now]
    for token in expired_tokens:
        ACTIVE_SESSIONS.pop(token, None)


def create_session():
    cleanup_expired_sessions()
    token = secrets.token_urlsafe(32)
    ACTIVE_SESSIONS[token] = time.time() + SESSION_TTL_SECONDS
    return token


def parse_cookie_header(cookie_header):
    values = {}
    for chunk in (cookie_header or "").split(";"):
        if "=" not in chunk:
            continue
        key, value = chunk.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def is_session_authenticated(handler):
    cleanup_expired_sessions()
    cookies = parse_cookie_header(handler.headers.get("Cookie", ""))
    token = cookies.get(SESSION_COOKIE_NAME, "")
    expires_at = ACTIVE_SESSIONS.get(token)
    if not expires_at:
        return False
    if expires_at <= time.time():
        ACTIVE_SESSIONS.pop(token, None)
        return False
    ACTIVE_SESSIONS[token] = time.time() + SESSION_TTL_SECONDS
    return True


def clear_session(handler):
    cookies = parse_cookie_header(handler.headers.get("Cookie", ""))
    token = cookies.get(SESSION_COOKIE_NAME, "")
    if token:
        ACTIVE_SESSIONS.pop(token, None)


def render_login_page(error_message=""):
    error_html = f"<div class='error'>{escape_value(error_message)}</div>" if error_message else ""
    return f"""<!doctype html>
<html lang='pt-BR'>
<head>
<meta charset='utf-8'>
<title>Login HVAC Supervisor</title>
<style>
body {{ font-family: Segoe UI, sans-serif; margin:0; min-height:100vh; display:grid; place-items:center; background:#1a1a1a; color:#e5e5e5; }}
.card {{ width:min(420px, calc(100vw - 32px)); background:#2d2d2d; border-radius:14px; padding:24px; box-shadow:0 10px 30px rgba(0, 0, 0, .4); border:1px solid #404040; }}
h1 {{ margin:0 0 8px; font-size:24px; color:#f0f0f0; }}
p {{ margin:0 0 16px; color:#a0a0a0; }}
form {{ display:grid; gap:12px; }}
label {{ display:grid; gap:6px; font-size:14px; color:#e5e5e5; }}
input {{ padding:10px 12px; border:1px solid #505050; border-radius:8px; background:#3a3a3a; color:#e5e5e5; }}
input:focus {{ outline:none; border-color:#0f766e; background:#4a4a4a; }}
button {{ border:0; border-radius:8px; padding:11px 14px; background:#0f766e; color:#f0f0f0; cursor:pointer; transition:background 0.2s; }}
button:hover {{ background:#1a9a8f; }}
.error {{ margin-bottom:12px; padding:10px 12px; border-radius:8px; background:#3a1a1a; color:#ff9999; border:1px solid #7a3a3a; }}
.note {{ margin-top:14px; font-size:12px; color:#808080; }}
</style>
</head>
<body>
<div class='card'>
<h1>HVAC_SUPERVISOR</h1>
<p>Acesso protegido ao painel de configuracao.</p>
{error_html}
<form method='post' action='/login'>
<label>Usuario<input name='username' type='text' autocomplete='username' required></label>
<label>Senha<input name='password' type='password' autocomplete='current-password' required></label>
<button type='submit'>Entrar</button>
</form>
<div class='note'>A senha nao fica salva em texto puro. O sistema armazena apenas hash com salt.</div>
</div>
</body>
</html>"""


def load_config():
    data = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8-sig") as fh:
            data = json.load(fh)

    merged = dict(DEFAULT_CONFIG)
    merged.update(data)
    merged = ensure_auth_config(merged, persist=False)
    return merged


def safe_load_config():
    global LAST_GOOD_CONFIG
    try:
        config = load_config()
        config = normalize_loaded_region(config, LAST_GOOD_CONFIG, "dashboard")
        config = normalize_loaded_region(config, LAST_GOOD_CONFIG, "clock")
        config = normalize_loaded_region(config, LAST_GOOD_CONFIG, "identity")
        LAST_GOOD_CONFIG = dict(config)
        return config
    except Exception as exc:
        log(f"Erro ao carregar configuracao. Usando ultima configuracao valida. Detalhe: {exc}")
        return dict(LAST_GOOD_CONFIG)


def ensure_output_dirs():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(CONFIG_OUTPUT_DIR, exist_ok=True)


def save_config(config):
    ensure_auth_config(config, persist=False)
    with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
        json.dump(config, fh, indent=4, ensure_ascii=False)


def update_config(values):
    with CONFIG_LOCK:
        config = load_config()
        config.update(values)
        save_config(config)
    return config


def get_region(config, prefix):
    return (
        int(config[f"{prefix}_x"]),
        int(config[f"{prefix}_y"]),
        int(config[f"{prefix}_width"]),
        int(config[f"{prefix}_height"]),
    )


def capture_region(region):
    return pyautogui.screenshot(region=region)


def save_region_snapshot(region, output_path, label):
    ensure_output_dirs()
    image = capture_region(region)
    image.save(output_path)
    log(f"Imagem de referencia salva para {label}: {output_path}")
    return output_path


def normalize_identity_text(text):
    normalized = " ".join(text.split()).strip().lower()
    normalized = re.sub(r"[^a-z0-9:/._ -]", "", normalized)
    return normalized


def read_region_text(config, prefix):
    pytesseract.pytesseract.tesseract_cmd = config["tesseract_path"]
    image = capture_region(get_region(config, prefix))
    raw_text = pytesseract.image_to_string(
        image,
        timeout=max(1, int(config.get("ocr_timeout_sec", 10))),
    )
    return raw_text


def save_configuration_snapshots(config, include_dashboard=True, include_clock=True, include_identity=True):
    if include_dashboard:
        save_region_snapshot(get_region(config, "dashboard"), CONFIG_DASHBOARD_FILE, "dashboard")
    if include_clock:
        save_region_snapshot(get_region(config, "clock"), CONFIG_CLOCK_FILE, "data/hora")
    if include_identity:
        save_region_snapshot(get_region(config, "identity"), CONFIG_IDENTITY_FILE, "identificacao do dashboard")
        identity_text = normalize_identity_text(read_region_text(config, "identity"))
        with open(CONFIG_IDENTITY_TEXT_FILE, "w", encoding="utf-8") as fh:
            fh.write(identity_text)
        log(f"Texto de referencia da identificacao salvo: {identity_text or '(vazio)'}")


def ask_point(label, wait_seconds=5):
    print(f"\nPosicione o mouse em: {label}")
    print(f"Aguardando {wait_seconds} segundos para capturar a posicao...")
    deadline = time.monotonic() + wait_seconds

    while True:
        remaining = max(0, int(round(deadline - time.monotonic())))
        print(f"Capturando em {remaining}...", end="\r", flush=True)
        if time.monotonic() >= deadline:
            break
        time.sleep(0.2)

    point = pyautogui.position()
    print(" " * 60, end="\r")
    print(f"Capturado apos {wait_seconds}s: ({point.x}, {point.y})")
    return point.x, point.y


def run_position_assistant(reason):
    if ASSISTANT_RUNNING.is_set():
        return

    ASSISTANT_RUNNING.set()
    try:
        log(f"Assistente de posicoes iniciado ({reason}).")
        x1, y1 = ask_point("INICIO do dashboard (canto superior esquerdo)")
        x2, y2 = ask_point("FIM do dashboard (canto inferior direito)")
        cx1, cy1 = ask_point("INICIO da hora/data (canto superior esquerdo)")
        cx2, cy2 = ask_point("FIM da hora/data (canto inferior direito)")
        ix1, iy1 = ask_point("INICIO da identificacao do dashboard (canto superior esquerdo)")
        ix2, iy2 = ask_point("FIM da identificacao do dashboard (canto inferior direito)")

        dashboard_x = min(x1, x2)
        dashboard_y = min(y1, y2)
        dashboard_w = abs(x2 - x1)
        dashboard_h = abs(y2 - y1)

        clock_x = min(cx1, cx2)
        clock_y = min(cy1, cy2)
        clock_w = abs(cx2 - cx1)
        clock_h = abs(cy2 - cy1)

        identity_x = min(ix1, ix2)
        identity_y = min(iy1, iy2)
        identity_w = abs(ix2 - ix1)
        identity_h = abs(iy2 - iy1)

        with CONFIG_LOCK:
            current_config = safe_load_config()

        dashboard_x, dashboard_y, dashboard_w, dashboard_h = validate_region_values(
            "dashboard", dashboard_x, dashboard_y, dashboard_w, dashboard_h, current_config, reason
        )
        clock_x, clock_y, clock_w, clock_h = validate_region_values(
            "clock", clock_x, clock_y, clock_w, clock_h, current_config, reason
        )
        identity_x, identity_y, identity_w, identity_h = validate_region_values(
            "identity", identity_x, identity_y, identity_w, identity_h, current_config, reason
        )

        today = datetime.now().strftime("%Y-%m-%d")
        config = update_config(
            {
                "dashboard_x": dashboard_x,
                "dashboard_y": dashboard_y,
                "dashboard_width": dashboard_w,
                "dashboard_height": dashboard_h,
                "clock_x": clock_x,
                "clock_y": clock_y,
                "clock_width": clock_w,
                "clock_height": clock_h,
                "identity_x": identity_x,
                "identity_y": identity_y,
                "identity_width": identity_w,
                "identity_height": identity_h,
                "last_position_setup_date": today,
            }
        )
        save_configuration_snapshots(config)
        log_clock_text("Posicao de Data/Hora atualizada")
        log("Assistente finalizado e configuracao atualizada.")
    except Exception as exc:
        log(f"Erro no assistente de posicoes: {exc}")
    finally:
        ASSISTANT_RUNNING.clear()


def run_region_capture(target, reason):
    if ASSISTANT_RUNNING.is_set():
        return

    ASSISTANT_RUNNING.set()
    try:
        if target == "dashboard":
            label = "Dashboard"
            p1 = ask_point("INICIO do dashboard (canto superior esquerdo)")
            p2 = ask_point("FIM do dashboard (canto inferior direito)")
            x = min(p1[0], p2[0])
            y = min(p1[1], p2[1])
            w = abs(p2[0] - p1[0])
            h = abs(p2[1] - p1[1])
            with CONFIG_LOCK:
                current_config = safe_load_config()
            x, y, w, h = validate_region_values("dashboard", x, y, w, h, current_config, reason)
            update_payload = {
                "dashboard_x": x,
                "dashboard_y": y,
                "dashboard_width": w,
                "dashboard_height": h,
                "last_position_setup_date": datetime.now().strftime("%Y-%m-%d"),
            }
        elif target == "clock":
            label = "Data/Hora"
            p1 = ask_point("INICIO da hora/data (canto superior esquerdo)")
            p2 = ask_point("FIM da hora/data (canto inferior direito)")
            x = min(p1[0], p2[0])
            y = min(p1[1], p2[1])
            w = abs(p2[0] - p1[0])
            h = abs(p2[1] - p1[1])
            with CONFIG_LOCK:
                current_config = safe_load_config()
            x, y, w, h = validate_region_values("clock", x, y, w, h, current_config, reason)
            update_payload = {
                "clock_x": x,
                "clock_y": y,
                "clock_width": w,
                "clock_height": h,
                "last_position_setup_date": datetime.now().strftime("%Y-%m-%d"),
            }
        else:
            label = "Identificacao do Dashboard"
            p1 = ask_point("INICIO da identificacao do dashboard (canto superior esquerdo)")
            p2 = ask_point("FIM da identificacao do dashboard (canto inferior direito)")
            x = min(p1[0], p2[0])
            y = min(p1[1], p2[1])
            w = abs(p2[0] - p1[0])
            h = abs(p2[1] - p1[1])
            with CONFIG_LOCK:
                current_config = safe_load_config()
            x, y, w, h = validate_region_values("identity", x, y, w, h, current_config, reason)
            update_payload = {
                "identity_x": x,
                "identity_y": y,
                "identity_width": w,
                "identity_height": h,
                "last_position_setup_date": datetime.now().strftime("%Y-%m-%d"),
            }

        log(f"Captura de posicao iniciada para {label} ({reason}).")
        config = update_config(update_payload)
        if target == "clock":
            save_configuration_snapshots(config, include_dashboard=False, include_clock=True, include_identity=False)
            log_clock_text("Posicao de Data/Hora atualizada")
        elif target == "dashboard":
            save_configuration_snapshots(config, include_dashboard=True, include_clock=False, include_identity=False)
        else:
            save_configuration_snapshots(config, include_dashboard=False, include_clock=False, include_identity=True)
        log(f"Captura de posicao finalizada para {label}.")
    except Exception as exc:
        log(f"Erro na captura de posicao ({target}): {exc}")
    finally:
        ASSISTANT_RUNNING.clear()


def extract_datetime(text):
    compact = " ".join(text.split())

    full_match = re.search(r"(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2}:\d{2})", compact)
    if full_match:
        raw = f"{full_match.group(1)} {full_match.group(2)}"
        try:
            return datetime.strptime(raw, "%d/%m/%Y %H:%M:%S")
        except ValueError:
            pass

    time_match = re.search(r"(\d{2}:\d{2}:\d{2})", compact)
    if time_match:
        today = datetime.now().strftime("%d/%m/%Y")
        raw = f"{today} {time_match.group(1)}"
        try:
            return datetime.strptime(raw, "%d/%m/%Y %H:%M:%S")
        except ValueError:
            pass

    return None


def normalize_clock_text(text):
    compact = " ".join(text.split())

    full_match = re.search(r"(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2}:\d{2})", compact)
    if full_match:
        return f"{full_match.group(1)} {full_match.group(2)}"

    time_match = re.search(r"(\d{2}:\d{2}:\d{2})", compact)
    if time_match:
        return time_match.group(1)

    digits_only = re.sub(r"\D", "", compact)
    if len(digits_only) >= 6:
        hhmmss = digits_only[-6:]
        hh = hhmmss[0:2]
        mm = hhmmss[2:4]
        ss = hhmmss[4:6]
        if 0 <= int(hh) <= 23 and 0 <= int(mm) <= 59 and 0 <= int(ss) <= 59:
            return f"{hh}:{mm}:{ss}"

    return compact


def read_dashboard_clock(config):
    text = read_region_text(config, "clock")
    dt = extract_datetime(text)
    normalized_text = normalize_clock_text(text)
    return dt, normalized_text


def log_clock_text(context):
    try:
        with CONFIG_LOCK:
            config = load_config()
        dashboard_dt, raw_text = read_dashboard_clock(config)
        hora = dashboard_dt.strftime("%d/%m/%Y %H:%M:%S") if dashboard_dt else "invalida"
        log(f"{context} | OCR Data/Hora: {raw_text or '(vazio)'} | Hora lida: {hora}")
    except Exception as exc:
        log(f"{context} | Erro ao ler OCR da Data/Hora: {exc}")


def is_chrome_running():
    for proc in psutil.process_iter(["name"]):
        name = (proc.info.get("name") or "").lower()
        if name == "chrome.exe":
            return True
    return False


def open_dashboard(config):
    chrome = config["chrome_path"]
    url = config["dashboard_url"]
    subprocess.Popen([chrome, "--new-window", url])
    log(f"Dashboard aberto: {url}")


def restart_browser(config):
    subprocess.run(
        ["taskkill", "/f", "/im", "chrome.exe"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    time.sleep(2)
    open_dashboard(config)


def _para_data_dd_mm_yyyy(valor):
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


def calculate_upload_end_time(now_local, interval_minutes):
    """
    Calcula a hora final para o upload somando o intervalo à hora atual.
    
    Exemplos:
    - Se agora é 23:30 e intervalo é 15 min → retorna 23:45:59
    - Se agora é 23:32 e intervalo é 15 min → retorna 23:47:59
    - Se agora é 23:30 e intervalo é 30 min → retorna 00:00:59 (próximo dia)
    - Se agora é 10:30 e intervalo é 60 min → retorna 11:30:59
    """
    interval = max(1, int(interval_minutes))
    
    # Soma o intervalo em minutos à hora atual
    end_time = now_local + timedelta(minutes=interval)
    
    # Define segundo e microsegundo como 59
    end_time = end_time.replace(second=59, microsecond=0)
    
    return end_time


def _detectar_mime_imagem(caminho_imagem):
    try:
        with Image.open(caminho_imagem) as img:
            formato = (img.format or "").upper()
    except UnidentifiedImageError as exc:
        raise RuntimeError(f"Arquivo nao e uma imagem valida: {caminho_imagem}") from exc

    mapa = {
        "PNG": "image/png",
        "JPEG": "image/jpeg",
        "JPG": "image/jpeg",
        "WEBP": "image/webp",
        "BMP": "image/bmp",
        "GIF": "image/gif",
        "TIFF": "image/tiff",
    }
    mime = mapa.get(formato)
    if mime:
        return mime

    mime_guess, _ = mimetypes.guess_type(caminho_imagem.name)
    if mime_guess and mime_guess.startswith("image/"):
        return mime_guess

    raise RuntimeError(
        f"Nao foi possivel identificar MIME de imagem para: {caminho_imagem} (formato={formato})"
    )


def enviar_midia_dashboard(caminho_imagem, config):
    caminho = Path(caminho_imagem)
    if not caminho.exists():
        raise FileNotFoundError(f"Imagem nao encontrada para upload: {caminho}")

    required_fields = [
        "upload_url",
        "upload_api_key",
        "upload_duration",
        "upload_name",
    ]
    missing = [field for field in required_fields if not str(config.get(field, "")).strip()]
    if missing:
        raise RuntimeError(f"Campos obrigatorios do upload nao configurados: {', '.join(missing)}")

    mime_type = _detectar_mime_imagem(caminho)
    now_local = datetime.now().astimezone()
    interval_minutes = int(config.get("capture_interval_minutes", 60))
    end_of_interval_local = calculate_upload_end_time(now_local, interval_minutes)
    now_dt = now_local.astimezone(timezone.utc)
    end_of_interval_dt = end_of_interval_local.astimezone(timezone.utc)
    starts_at = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    ends_at = end_of_interval_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    campaign_name = f"dashboard_hvac_{now_dt.strftime('%H_%M')}"

    headers = {"x-api-key": str(config.get("upload_api_key", "")).strip()}
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

    with caminho.open("rb") as arquivo:
        files = {"mediaFile": (caminho.name, arquivo, mime_type)}
        resposta = requests.post(
            str(config.get("upload_url", "")).strip(),
            files=files,
            data=data,
            headers=headers,
            timeout=max(1, int(config.get("upload_timeout_seconds", 30))),
        )

    try:
        payload = resposta.json()
    except ValueError:
        payload = {"raw": resposta.text}

    if not resposta.ok:
        raise RuntimeError(f"Upload falhou ({resposta.status_code}): {payload}")

    return {"status_code": resposta.status_code, "payload": payload}


def capture_dashboard(config):
    ensure_output_dirs()
    region = get_region(config, "dashboard")
    image = capture_region(region)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    image.save(LATEST_DASHBOARD_FILE)
    update_config({"last_dashboard_capture_at": now_str})
    interval_minutes = int(config.get("capture_interval_minutes", 60))
    log(f"Captura salva com intervalo de {interval_minutes} min: {LATEST_DASHBOARD_FILE}")
    if config.get("upload_enabled", False):
        try:
            resultado = enviar_midia_dashboard(LATEST_DASHBOARD_FILE, config)
            log(f"Upload da imagem do dashboard concluido: status={resultado['status_code']}")
        except Exception as exc:
            log(f"Erro no upload da imagem do dashboard: {exc}")


def parse_capture_timestamp(value):
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def current_capture_window_key(interval_minutes, now=None):
    now = now or datetime.now()
    interval = max(1, int(interval_minutes))
    total_minutes = now.hour * 60 + now.minute
    window_index = total_minutes // interval
    date_key = now.strftime("%Y-%m-%d")
    return f"{date_key}_{window_index}"


def capture_window_key_from_timestamp(interval_minutes, value):
    timestamp = parse_capture_timestamp(value)
    if not timestamp:
        return ""
    return current_capture_window_key(interval_minutes, timestamp)


def should_capture_dashboard_this_cycle(config, now=None):
    now = now or datetime.now()
    interval = max(1, int(config.get("capture_interval_minutes", 60)))
    current_key = current_capture_window_key(interval, now)
    last_capture_key = capture_window_key_from_timestamp(interval, config.get("last_dashboard_capture_at", ""))
    if not last_capture_key:
        log(f"Nenhuma captura valida registrada para a janela atual ({current_key}). Captura sera executada.")
        return True
    if last_capture_key != current_key:
        log(
            f"Ultima captura registrada pertence a outra janela ({last_capture_key}). "
            f"Janela atual: {current_key}. Captura sera executada."
        )
        return True
    return False


def capture_clock_snapshot(config):
    ensure_output_dirs()
    print("\nPreparando snapshot da area Data/Hora...")
    for remaining in range(5, 0, -1):
        print(f"Capturando print em {remaining}...", end="\r", flush=True)
        time.sleep(1)
    print(" " * 50, end="\r")

    region = get_region(config, "clock")
    path = os.path.join(CONFIG_OUTPUT_DIR, "clock_preview.png")
    image = capture_region(region)
    image.save(path)
    log(f"Snapshot da data/hora salvo: {path}")
    return path


def verify_dashboard_identity(config):
    image_reference_exists = os.path.exists(CONFIG_IDENTITY_FILE)
    text_reference_exists = os.path.exists(CONFIG_IDENTITY_TEXT_FILE)

    if not image_reference_exists and not text_reference_exists:
        log("Referencias de identificacao do dashboard nao encontradas. Verificacao ignorada.")
        return True

    try:
        if image_reference_exists:
            match = pyautogui.locateOnScreen(
                CONFIG_IDENTITY_FILE,
                confidence=float(config.get("identity_match_confidence", 0.8)),
                grayscale=True,
                region=get_region(config, "dashboard"),
            )
            if match is not None:
                log("Identificacao do dashboard confirmada por comparacao de imagem.")
                return True

        if text_reference_exists and config.get("identity_text_match_enabled", True):
            with open(CONFIG_IDENTITY_TEXT_FILE, "r", encoding="utf-8") as fh:
                expected_text = normalize_identity_text(fh.read())
            current_text = normalize_identity_text(read_region_text(config, "identity"))
            if expected_text and current_text and expected_text in current_text:
                log(f"Identificacao do dashboard confirmada por OCR. Texto atual: {current_text}")
                return True
            log(
                "Falha na identificacao por OCR. "
                f"Esperado: {expected_text or '(vazio)'} | Atual: {current_text or '(vazio)'}"
            )

        return False
    except Exception as exc:
        log(f"Erro na verificacao da imagem de identificacao do dashboard: {exc}")
        return False


def recover_dashboard(config, reason, force=False):
    log(f"Recuperacao do dashboard acionada. Motivo: {reason}")
    if not force and not config.get("restart_browser_on_freeze", True):
        log("Recuperacao automatica desabilitada na configuracao. Acao nao executada.")
        return
    try:
        restart_browser(config)
    except Exception as exc:
        log(f"Falha na rotina de recuperacao do dashboard: {exc}")


def parse_bool(value):
    return str(value).lower() in ("1", "true", "on", "yes")


def parse_int(form, key, fallback):
    try:
        return int(form.get(key, [fallback])[0])
    except (TypeError, ValueError):
        return fallback


def parse_float(form, key, fallback):
    try:
        return float(form.get(key, [fallback])[0])
    except (TypeError, ValueError):
        return fallback


def render_config_page(config):
    checked = "checked" if config.get("restart_browser_on_freeze") else ""
    automation_checked = "checked" if config.get("automation_enabled") else ""
    identity_text_checked = "checked" if config.get("identity_text_match_enabled") else ""
    upload_checked = "checked" if config.get("upload_enabled") else ""
    auth_username = escape_value(config.get("auth_username", DEFAULT_CONFIG_USERNAME))

    return f"""<!doctype html>
<html lang='pt-BR'>
<head>
<meta charset='utf-8'>
<title>HVAC Supervisor Config</title>
<style>
body {{ font-family: Segoe UI, sans-serif; margin: 24px; background:#1a1a1a; color:#e5e5e5; }}
h1 {{ margin: 0 0 6px; color:#f0f0f0; }}
h2 {{ margin: 0 0 10px; font-size:18px; color:#e5e5e5; }}
p {{ margin: 0; color:#b0b0b0; }}
.shell {{ max-width: 1220px; margin: 0 auto; }}
.card {{ background:#2d2d2d; padding:18px; border-radius:12px; box-shadow:0 1px 8px rgba(0,0,0,.4); border:1px solid #404040; }}
.topbar {{ display:grid; grid-template-columns: minmax(0, 2fr) minmax(300px, 360px); gap:16px; align-items:start; }}
.form-card {{ min-width:0; }}
.side-card {{ background:#3a3a3a; border:1px solid #505050; border-radius:10px; padding:14px; }}
.side-card h2 {{ margin:0 0 10px; font-size:16px; color:#e5e5e5; }}
.status-list {{ display:grid; gap:8px; margin-bottom:14px; }}
.status-item {{ background:#2d2d2d; border:1px solid #404040; border-radius:8px; padding:10px; }}
.status-label {{ display:block; font-size:12px; color:#a0a0a0; margin-bottom:4px; }}
.status-value {{ font-size:13px; font-weight:600; color:#f0f0f0; word-break:break-word; }}
.grid {{ display:grid; grid-template-columns: repeat(2, minmax(220px, 1fr)); gap:10px; margin-top:12px; }}
label {{ display:flex; flex-direction:column; font-size:13px; gap:4px; color:#e5e5e5; }}
input[type='text'], input[type='number'], input[type='password'] {{ padding:8px; border:1px solid #505050; border-radius:6px; background:#3a3a3a; color:#e5e5e5; }}
input[type='text']:focus, input[type='number']:focus, input[type='password']:focus {{ outline:none; border-color:#0f766e; background:#4a4a4a; }}
.toggle {{ margin-top:12px; display:block; }}
.toggle input[type='checkbox'] {{ cursor:pointer; }}
.actions {{ display:grid; gap:8px; }}
button {{ border:0; padding:10px 14px; border-radius:8px; cursor:pointer; background:#0f766e; color:#f0f0f0; text-align:left; transition:background 0.2s; }}
button:hover {{ background:#1a9a8f; }}
button.secondary {{ background:#2563eb; }}
button.secondary:hover {{ background:#3b7dd7; }}
.helper {{ margin-top:12px; color:#808080; font-size:12px; line-height:1.5; }}
@media (max-width: 980px) {{
  .topbar {{ grid-template-columns: 1fr; }}
}}
@media (max-width: 700px) {{
  .grid {{ grid-template-columns: 1fr; }}
}}
</style>
</head>
<body>
<div class='shell'>
<div class='card'>
<h1>HVAC_SUPERVISOR</h1>
<p><small>Configuração local em {escape_value(config["config_host"])}:{config["config_port"]}</small></p>
<div class='topbar'>
<div class='form-card'>
<form id='save-config-form' method='post' action='/save'>
<label class='toggle'>
<input name='automation_enabled' type='checkbox' {automation_checked}> Automação ativa
</label>
<div class='grid'>
<label>URL Dashboard<input name='dashboard_url' type='text' value='{escape_value(config["dashboard_url"])}'></label>
<label>Caminho Chrome<input name='chrome_path' type='text' value='{escape_value(config["chrome_path"])}'></label>
<label>Caminho Tesseract<input name='tesseract_path' type='text' value='{escape_value(config["tesseract_path"])}'></label>
<label>Intervalo Monitor (seg)<input name='monitor_interval_sec' type='number' value='{config["monitor_interval_sec"]}'></label>
<label>Tolerancia de atraso da atualizacao (segundos)<input name='freeze_threshold_sec' type='number' value='{config["freeze_threshold_sec"]}'></label>
<label>Falhas OCR consecutivas<input name='max_ocr_failures' type='number' value='{config["max_ocr_failures"]}'></label>
<label>Dashboard X<input name='dashboard_x' type='number' value='{config["dashboard_x"]}'></label>
<label>Dashboard Y<input name='dashboard_y' type='number' value='{config["dashboard_y"]}'></label>
<label>Dashboard Largura<input name='dashboard_width' type='number' min='50' value='{config["dashboard_width"]}'></label>
<label>Dashboard Altura<input name='dashboard_height' type='number' min='50' value='{config["dashboard_height"]}'></label>
<label>Hora X<input name='clock_x' type='number' value='{config["clock_x"]}'></label>
<label>Hora Y<input name='clock_y' type='number' value='{config["clock_y"]}'></label>
<label>Hora Largura<input name='clock_width' type='number' min='20' value='{config["clock_width"]}'></label>
<label>Hora Altura<input name='clock_height' type='number' min='10' value='{config["clock_height"]}'></label>
<label>Identificacao X<input name='identity_x' type='number' value='{config["identity_x"]}'></label>
<label>Identificacao Y<input name='identity_y' type='number' value='{config["identity_y"]}'></label>
<label>Identificacao Largura<input name='identity_width' type='number' min='20' value='{config["identity_width"]}'></label>
<label>Identificacao Altura<input name='identity_height' type='number' min='10' value='{config["identity_height"]}'></label>
<label>last_position_setup_date<input name='last_position_setup_date' type='text' value='{escape_value(config["last_position_setup_date"])}'></label>
<label>Ultima captura dashboard<input name='last_dashboard_capture_at' type='text' value='{escape_value(config["last_dashboard_capture_at"])}'></label>
<label>Confianca identificacao<input name='identity_match_confidence' type='number' step='0.1' value='{config["identity_match_confidence"]}'></label>
<label>Intervalo captura (minutos)<input name='capture_interval_minutes' type='number' min='1' value='{config.get("capture_interval_minutes", 60)}'></label>
<label>Rota Upload API<input name='upload_url' type='text' value='{escape_value(config["upload_url"])}'></label>
<label>API Key Upload<input name='upload_api_key' type='password' value='{escape_value(config["upload_api_key"])}'></label>
<label>Duration<input name='upload_duration' type='text' value='{escape_value(config["upload_duration"])}'></label>
<label>Name<input name='upload_name' type='text' value='{escape_value(config["upload_name"])}'></label>
<label>Group<input name='upload_group' type='text' value='{escape_value(config["upload_group"])}'></label>
<label>Timeout Upload (seg)<input name='upload_timeout_seconds' type='number' value='{config["upload_timeout_seconds"]}'></label>
<label>Usuario do painel<input name='auth_username' type='text' value='{auth_username}'></label>
<label>Nova senha do painel<input name='auth_new_password' type='password' value='' placeholder='Preencha apenas para trocar'></label>
</div>
<label class='toggle'>
<input name='restart_browser_on_freeze' type='checkbox' {checked}> Reiniciar navegador automaticamente em caso de travamento
</label>
<label class='toggle'>
<input name='identity_text_match_enabled' type='checkbox' {identity_text_checked}> Usar OCR como apoio na identificacao do dashboard
</label>
<label class='toggle'>
<input name='upload_enabled' type='checkbox' {upload_checked}> Enviar imagem do dashboard para API apos captura horaria
</label>
<div class='helper'>O intervalo do monitor controla a frequencia das verificacoes quando a automacao estiver ativa. Senhas do painel sao armazenadas com hash e salt.</div>
</form>
 </div>
<div class='side-card'>
<h2>Acoes e Status</h2>
<div class='status-list'>
<div class='status-item'>
<span class='status-label'>Automacao</span>
<span class='status-value'>{"Ativa" if config.get("automation_enabled") else "Em espera"}</span>
</div>
<div class='status-item'>
<span class='status-label'>Ultima captura dashboard</span>
<span class='status-value'>{config['last_dashboard_capture_at'] or 'Nenhuma captura realizada'}</span>
</div>
<div class='status-item'>
<span class='status-label'>Ultima configuracao de posicao</span>
<span class='status-value'>{escape_value(config['last_position_setup_date'] or 'Nao configurado')}</span>
</div>
<div class='status-item'>
<span class='status-label'>Usuario do painel</span>
<span class='status-value'>{auth_username}</span>
</div>
</div>
<div class='actions'>
<button type='submit' form='save-config-form'>Salvar configuração</button>
</div>
<div class='actions' style='margin-top:10px;'>
<form method='post' action='/capture-dashboard'>
<div class='actions'>
<button class='secondary' type='submit'>Capturar Dashboard (console)</button>
</div>
</form>
<form method='post' action='/capture-clock'>
<div class='actions'>
<button class='secondary' type='submit'>Capturar Data/Hora (console)</button>
</div>
</form>
<form method='post' action='/capture-identity'>
<div class='actions'>
<button class='secondary' type='submit'>Capturar Identificacao (console)</button>
</div>
</form>
<form method='post' action='/capture-assistant'>
<div class='actions'>
<button class='secondary' type='submit'>Captura Completa (console)</button>
</div>
</form>
<form method='post' action='/snapshot-clock'>
<div class='actions'>
<button class='secondary' type='submit'>Salvar print Data/Hora</button>
</div>
</form>
<form method='post' action='/logout'>
<div class='actions'>
<button class='secondary' type='submit'>Sair do painel</button>
</div>
</form>
</div>
<div class='helper'>Cada captura pede posição 1 e posição 2 no console, com espera de 5 segundos entre os pontos.</div>
</div>
</div>
</div>
</div>
</body>
</html>"""


class ConfigHandler(BaseHTTPRequestHandler):
    def redirect(self, location, extra_headers=None):
        self.send_response(303)
        self.send_header("Location", location)
        if extra_headers:
            for key, value in extra_headers:
                self.send_header(key, value)
        self.end_headers()

    def render_html(self, html_content, status_code=200, extra_headers=None):
        payload = html_content.encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        if extra_headers:
            for key, value in extra_headers:
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(payload)

    def require_auth(self):
        if is_session_authenticated(self):
            return True
        self.redirect("/login")
        return False

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/login":
            self.render_html(render_login_page())
            return

        if parsed.path != "/":
            self.send_response(404)
            self.end_headers()
            return

        if not self.require_auth():
            return

        with CONFIG_LOCK:
            config = safe_load_config()

        self.render_html(render_config_page(config))

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/login":
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            form = parse_qs(body)
            username = form.get("username", [""])[0].strip()
            password = form.get("password", [""])[0]

            with CONFIG_LOCK:
                current = safe_load_config()

            if username == current.get("auth_username", "") and verify_password(
                password,
                current.get("auth_password_salt", ""),
                current.get("auth_password_hash", ""),
            ):
                token = create_session()
                self.redirect(
                    "/",
                    extra_headers=[
                        (
                            "Set-Cookie",
                            f"{SESSION_COOKIE_NAME}={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={SESSION_TTL_SECONDS}",
                        )
                    ],
                )
                log("Login realizado no painel de configuracao.")
                return

            self.render_html(render_login_page("Usuario ou senha invalidos."), status_code=401)
            log("Tentativa de login invalida no painel de configuracao.")
            return

        if parsed.path == "/logout":
            clear_session(self)
            self.redirect(
                "/login",
                extra_headers=[
                    (
                        "Set-Cookie",
                        f"{SESSION_COOKIE_NAME}=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0",
                    )
                ],
            )
            return

        if not self.require_auth():
            return

        if parsed.path == "/save":
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            form = parse_qs(body)

            with CONFIG_LOCK:
                current = safe_load_config()

            updated = {
                "dashboard_url": form.get("dashboard_url", [current["dashboard_url"]])[0],
                "chrome_path": form.get("chrome_path", [current["chrome_path"]])[0],
                "tesseract_path": form.get("tesseract_path", [current["tesseract_path"]])[0],
                "monitor_interval_sec": parse_int(form, "monitor_interval_sec", current["monitor_interval_sec"]),
                "freeze_threshold_sec": parse_int(form, "freeze_threshold_sec", current["freeze_threshold_sec"]),
                "max_ocr_failures": parse_int(form, "max_ocr_failures", current["max_ocr_failures"]),
                "capture_interval_minutes": parse_int(form, "capture_interval_minutes", current.get("capture_interval_minutes", 60)),
                "dashboard_x": parse_int(form, "dashboard_x", current["dashboard_x"]),
                "dashboard_y": parse_int(form, "dashboard_y", current["dashboard_y"]),
                "dashboard_width": parse_int(form, "dashboard_width", current["dashboard_width"]),
                "dashboard_height": parse_int(form, "dashboard_height", current["dashboard_height"]),
                "clock_x": parse_int(form, "clock_x", current["clock_x"]),
                "clock_y": parse_int(form, "clock_y", current["clock_y"]),
                "clock_width": parse_int(form, "clock_width", current["clock_width"]),
                "clock_height": parse_int(form, "clock_height", current["clock_height"]),
                "identity_x": parse_int(form, "identity_x", current["identity_x"]),
                "identity_y": parse_int(form, "identity_y", current["identity_y"]),
                "identity_width": parse_int(form, "identity_width", current["identity_width"]),
                "identity_height": parse_int(form, "identity_height", current["identity_height"]),
                "restart_browser_on_freeze": parse_bool(form.get("restart_browser_on_freeze", ["off"])[0]),
                "automation_enabled": parse_bool(form.get("automation_enabled", ["off"])[0]),
                "identity_text_match_enabled": parse_bool(form.get("identity_text_match_enabled", ["off"])[0]),
                "upload_enabled": parse_bool(form.get("upload_enabled", ["off"])[0]),
                "last_position_setup_date": form.get("last_position_setup_date", [current["last_position_setup_date"]])[0].strip(),
                "last_dashboard_capture_at": form.get("last_dashboard_capture_at", [current["last_dashboard_capture_at"]])[0].strip(),
                "identity_match_confidence": parse_float(form, "identity_match_confidence", current["identity_match_confidence"]),
                "upload_url": form.get("upload_url", [current["upload_url"]])[0].strip(),
                "upload_api_key": form.get("upload_api_key", [current["upload_api_key"]])[0].strip(),
                "upload_duration": form.get("upload_duration", [current["upload_duration"]])[0].strip(),
                "upload_name": form.get("upload_name", [current["upload_name"]])[0].strip(),
                "upload_group": form.get("upload_group", [current["upload_group"]])[0].strip(),
                "upload_timeout_seconds": parse_int(form, "upload_timeout_seconds", current["upload_timeout_seconds"]),
                "auth_username": form.get("auth_username", [current["auth_username"]])[0].strip() or current["auth_username"],
            }

            update_region_in_payload(
                updated,
                current,
                "dashboard",
                updated["dashboard_x"],
                updated["dashboard_y"],
                updated["dashboard_width"],
                updated["dashboard_height"],
                "pagina web",
            )
            update_region_in_payload(
                updated,
                current,
                "clock",
                updated["clock_x"],
                updated["clock_y"],
                updated["clock_width"],
                updated["clock_height"],
                "pagina web",
            )
            update_region_in_payload(
                updated,
                current,
                "identity",
                updated["identity_x"],
                updated["identity_y"],
                updated["identity_width"],
                updated["identity_height"],
                "pagina web",
            )

            new_password = form.get("auth_new_password", [""])[0].strip()
            if new_password:
                salt_hex, password_hash = hash_password(new_password)
                updated["auth_password_salt"] = salt_hex
                updated["auth_password_hash"] = password_hash
                log("Senha do painel atualizada via pagina web.")

            update_config(updated)
            log("Configuracao atualizada via pagina web.")

            self.redirect("/")
            return

        if parsed.path == "/capture-assistant":
            ASSISTANT_REQUEST.set()
            log("Assistente de posicoes solicitado via web.")
            self.redirect("/")
            return

        if parsed.path == "/capture-dashboard":
            CAPTURE_DASHBOARD_REQUEST.set()
            log("Captura de posicao do dashboard solicitada via web.")
            self.redirect("/")
            return

        if parsed.path == "/capture-clock":
            CAPTURE_CLOCK_REQUEST.set()
            log("Captura de posicao da data/hora solicitada via web.")
            self.redirect("/")
            return

        if parsed.path == "/capture-identity":
            CAPTURE_IDENTITY_REQUEST.set()
            log("Captura de posicao da identificacao do dashboard solicitada via web.")
            self.redirect("/")
            return

        if parsed.path == "/snapshot-clock":
            SNAPSHOT_CLOCK_REQUEST.set()
            log("Snapshot da data/hora solicitado via web.")
            self.redirect("/")
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, *_):
        return


def start_web_config_server():
    with CONFIG_LOCK:
        config = safe_load_config()

    host = config["config_host"]
    port = int(config["config_port"])

    server = ThreadingHTTPServer((host, port), ConfigHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    log(f"Pagina de configuracao em http://{host}:{port}")
    return server


def monitor_loop():
    ocr_failures = 0
    waiting_logged = False
    automation_was_enabled = False

    while True:
        config = dict(DEFAULT_CONFIG)
        try:
            with CONFIG_LOCK:
                config = safe_load_config()

            if ASSISTANT_REQUEST.is_set() and not ASSISTANT_RUNNING.is_set():
                ASSISTANT_REQUEST.clear()
                run_position_assistant("solicitacao manual")
                with CONFIG_LOCK:
                    config = safe_load_config()

            if CAPTURE_DASHBOARD_REQUEST.is_set() and not ASSISTANT_RUNNING.is_set():
                CAPTURE_DASHBOARD_REQUEST.clear()
                run_region_capture("dashboard", "solicitacao manual")
                with CONFIG_LOCK:
                    config = safe_load_config()

            if CAPTURE_CLOCK_REQUEST.is_set() and not ASSISTANT_RUNNING.is_set():
                CAPTURE_CLOCK_REQUEST.clear()
                run_region_capture("clock", "solicitacao manual")
                with CONFIG_LOCK:
                    config = safe_load_config()

            if CAPTURE_IDENTITY_REQUEST.is_set() and not ASSISTANT_RUNNING.is_set():
                CAPTURE_IDENTITY_REQUEST.clear()
                run_region_capture("identity", "solicitacao manual")
                with CONFIG_LOCK:
                    config = safe_load_config()

            if SNAPSHOT_CLOCK_REQUEST.is_set() and not ASSISTANT_RUNNING.is_set():
                SNAPSHOT_CLOCK_REQUEST.clear()
                try:
                    capture_clock_snapshot(config)
                except Exception as exc:
                    log(f"Erro ao salvar snapshot da data/hora: {exc}")

            if not config.get("automation_enabled", False):
                if not waiting_logged:
                    log(f"Automacao em espera. Ative na pagina http://{config['config_host']}:{config['config_port']}")
                    waiting_logged = True
                automation_was_enabled = False
            else:
                cycle_started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                log(f"Inicio do ciclo de monitoramento: {cycle_started_at}")

                waiting_logged = False
                if not automation_was_enabled:
                    automation_was_enabled = True
                    log("Automacao ativada. Controle de captura horaria sincronizado com o relogio do sistema.")

                ensure_watchdog_running()

                today = datetime.now().strftime("%Y-%m-%d")
                if config.get("last_position_setup_date") != today and not ASSISTANT_RUNNING.is_set():
                    run_position_assistant("primeira execucao do dia")
                    with CONFIG_LOCK:
                        config = safe_load_config()

                if not is_chrome_running():
                    try:
                        open_dashboard(config)
                        time.sleep(8)
                    except Exception as exc:
                        log(f"Falha ao abrir dashboard: {exc}")

                if not verify_dashboard_identity(config):
                    recover_dashboard(config, "dashboard correto nao identificado na tela", force=True)

                if should_capture_dashboard_this_cycle(config):
                    try:
                        capture_dashboard(config)
                    except Exception as exc:
                        log(f"Erro na captura horaria: {exc}")

                dashboard_dt, raw_text = read_dashboard_clock(config)
                hora_ciclo = dashboard_dt.strftime("%d/%m/%Y %H:%M:%S") if dashboard_dt else "invalida"
                log(f"Leitura OCR Data/Hora (ciclo): {raw_text or '(vazio)'} | Hora lida: {hora_ciclo}")

                if dashboard_dt is None:
                    ocr_failures += 1
                    log(f"OCR sem data/hora valida ({ocr_failures}/{config['max_ocr_failures']}): {raw_text}")
                    if ocr_failures >= int(config["max_ocr_failures"]):
                        recover_dashboard(config, "OCR da data/hora invalido acima do limite")
                        ocr_failures = 0
                else:
                    ocr_failures = 0
                    now_dt = datetime.now()
                    delay_seconds = (now_dt - dashboard_dt).total_seconds()
                    if delay_seconds < 0:
                        delay_seconds = 0
                    tolerance_seconds = max(20, int(config.get("freeze_threshold_sec", 20)))
                    if delay_seconds <= tolerance_seconds:
                        log(f"Atualizacao do dashboard dentro da tolerancia. Atraso atual: {int(delay_seconds)}s")
                    else:
                        log(
                            f"Sistema pode estar travado. Hora do dashboard fora da tolerancia. "
                            f"Atraso: {int(delay_seconds)}s | Tolerancia: {tolerance_seconds}s | Hora lida: {hora_ciclo}"
                        )
                        recover_dashboard(config, "atraso na atualizacao da hora do dashboard")

                log("Fim do ciclo de monitoramento.")
        except Exception as exc:
            log(f"Erro no monitoramento: {exc}")

        try:
            sleep_seconds = max(1, int(config.get("monitor_interval_sec", DEFAULT_CONFIG["monitor_interval_sec"])))
        except Exception:
            sleep_seconds = DEFAULT_CONFIG["monitor_interval_sec"]
        time.sleep(sleep_seconds)


def main():
    with CONFIG_LOCK:
        config = safe_load_config()
        config["automation_enabled"] = False
        save_config(config)

    try:
        start_web_config_server()
    except Exception as exc:
        log(f"Falha ao iniciar pagina de configuracao: {exc}")

    log("Supervisor iniciado.")
    monitor_loop()


if __name__ == "__main__":
    main()

