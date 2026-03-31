import os
import subprocess
import sys
import time

import psutil

PROCESS_NAME = "HVAC_SUPERVISOR.exe"
CHECK_INTERVAL_SEC = 5
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "watchdog.log")


def base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def log(message):
    os.makedirs(os.path.join(base_dir(), LOG_DIR), exist_ok=True)
    log_path = os.path.join(base_dir(), LOG_FILE)
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(f"{timestamp} | {message}\n")
    print(f"{timestamp} | {message}")


def target_path():
    direct_path = os.path.join(base_dir(), PROCESS_NAME)
    nested_path = os.path.join(base_dir(), "HVAC_SUPERVISOR", PROCESS_NAME)
    if os.path.exists(direct_path):
        return direct_path
    return nested_path


def is_running(process_name):
    for proc in psutil.process_iter(["name"]):
        if (proc.info.get("name") or "").lower() == process_name.lower():
            return True
    return False


def start_target():
    exe_path = target_path()
    if not os.path.exists(exe_path):
        log(f"Arquivo nao encontrado: {exe_path}")
        return
    subprocess.Popen([exe_path], cwd=os.path.dirname(exe_path))
    log(f"Supervisor iniciado pelo watchdog: {exe_path}")


def main():
    log("Watchdog iniciado.")
    while True:
        try:
            if not is_running(PROCESS_NAME):
                log("Supervisor nao encontrado em execucao. Iniciando novamente.")
                start_target()
        except Exception as exc:
            log(f"Erro no loop do watchdog: {exc}")
        time.sleep(CHECK_INTERVAL_SEC)


if __name__ == "__main__":
    main()
