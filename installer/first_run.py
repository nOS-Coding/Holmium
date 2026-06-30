#!/usr/bin/env python3
"""Holmium OS First-Run Wizard — runs in the TUI environment on first boot.
Single-purpose appliance: no user accounts, no sudo, no DE.
Configures Holmium itself: name, WiFi, WireGuard, auth token."""

import json
import os
import secrets
import subprocess
import sys

CONFIG_PATH = "/etc/holmium/config.json"
TOKEN_PATH = "/etc/holmium/token"
WG_DIR = "/etc/wireguard"
CLIENTS_DIR = "/etc/wireguard/clients"

HOLMIUM_LOGO = r"""
  ██████████   ██████   ███  ███ ███ ███ ██   ██
 ██          ██    ██  ██ ███ ██  ██  ██ ██   ██
 ██          ██    ██  ██  █   ██  ██  ██ ██   ██
 ██  ███████ ████████  ██      ██  ██  ██ ███████
 ██  ██  ██  ██    ██  ██      ██  ██  ██ ██   ██
 ██  ██  ██  ██    ██  ██      ██  ██  ██ ██   ██
  ██████  ██ ██    ██ ████    ██████ ████ ██   ██
"""


def run(cmd, **kwargs):
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def step_welcome():
    os.system("clear")
    print(f"\033[1;33m{HOLMIUM_LOGO}\033[0m")
    print("  \033[1;36mHOLMIUM OS — Single-Purpose AI Appliance\033[0m\n")
    print("  This wizard configures Holmium for first use.\n")
    print("  Holmium OS is a dedicated appliance. No desktop, no user accounts,")
    print("  no package manager. Holmium is the only interface to the system.\n")
    input("  Press Enter to begin...")


def step_user_name():
    os.system("clear")
    print("\n\033[1;33m  Step 1: Who am I talking to?\033[0m\n")
    name = input("  Enter your name: ").strip()
    while not name:
        name = input("  Name cannot be empty: ").strip()
    return name


def step_wifi():
    os.system("clear")
    print("\n\033[1;33m  Step 2: WiFi Configuration\033[0m\n")
    ssid = input("  WiFi SSID: ").strip()
    password = input("  WiFi Password: ").strip()
    print(f"\n  SSID: {ssid}")
    print(f"  Password: {'*' * len(password)}")
    ok = input("  Correct? (Y/n): ").strip().lower()
    if ok == "n":
        return step_wifi()
    return ssid, password


def step_wireguard_keys():
    os.system("clear")
    print("\n\033[1;33m  Step 3: WireGuard Server Keys\033[0m\n")
    os.makedirs(WG_DIR, exist_ok=True)
    os.makedirs(CLIENTS_DIR, exist_ok=True)

    privkey = run(["wg", "genkey"]).stdout.strip()
    pubkey = run(["bash", "-c", f"echo '{privkey}' | wg pubkey"]).stdout.strip()

    with open(f"{WG_DIR}/server_private.key", "w") as f:
        f.write(privkey + "\n")
    with open(f"{WG_DIR}/server_public.key", "w") as f:
        f.write(pubkey + "\n")
    os.chmod(f"{WG_DIR}/server_private.key", 0o600)

    print(f"  Server Private Key: saved to {WG_DIR}/server_private.key")
    print(f"  \033[1;32mServer Public Key: {pubkey}\033[0m\n")
    print("  (Share the public key with your clients)\n")
    input("  Press Enter to continue...")
    return privkey, pubkey


def step_auth_token():
    os.system("clear")
    print("\n\033[1;33m  Step 4: Auth Token\033[0m\n")
    token = secrets.token_hex(32)
    print(f"  \033[1;32mHolmium Auth Token: {token}\033[0m\n")
    print("  (Save this — needed for CLI and Android app)\n")

    with open(TOKEN_PATH, "w") as f:
        f.write(token + "\n")
    os.chmod(TOKEN_PATH, 0o600)

    input("  Press Enter to continue...")
    return token


def step_summary(name, ssid, pubkey, token):
    os.system("clear")
    print("\n\033[1;33m  Step 5: Summary\033[0m\n")
    print(f"  User name:           {name}")
    print(f"  WiFi SSID:           {ssid}")
    print(f"  WireGuard PubKey:    {pubkey}")
    print(f"  Auth Token:          {token[:16]}...{token[-8:]}\n")
    ok = input("  Write configuration? (Y/n): ").strip().lower()
    return ok != "n"


def write_config(name, ssid, wifi_password, pubkey, token):
    config = {
        "user_name": name,
        "wifi_ssid": ssid,
        "wifi_password": wifi_password,
        "wireguard_public_key": pubkey,
        "holmium_token": token,
        "tts_voice": "am_michael",
        "stt_model": "large-v3",
        "vllm_model": "QuantTrio/Qwen3.6-35B-A3B-AWQ",
        "vllm_socket": "/run/holmium/vllm.sock",
        "backend_socket": "/run/holmium/backend.sock",
        "wireguard_subnet": "10.0.0.0/24",
        "ntfy_topic": f"holmium-{secrets.token_hex(4)}",
        "timezone": "UTC",
        "mode_default": "work",
        "mode_temps": {
            "think": [0.1, 0.85],
            "work": [0.5, 0.9],
            "image": [0.8, 0.95]
        }
    }
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
    os.chmod(CONFIG_PATH, 0o600)


def start_services():
    os.system("clear")
    print("\n\033[1;33m  Starting Services\033[0m\n")
    services = [
        "holmium-wireguard",
        "holmium-vllm",
        "holmium-backend",
        "holmium-tui",
        "holmium-scheduler",
        "netsh-monitor",
    ]
    for svc in services:
        print(f"  Starting {svc}...")
        ret = run(["rc-service", svc, "start"])
        if ret.returncode == 0:
            print(f"  \033[1;32m  ✓ {svc} started\033[0m")
        else:
            print(f"  \033[1;33m  ! {svc}: {ret.stderr.strip() or 'already running'}\033[0m")
    input("\n  Press Enter to continue...")


def disable_first_run():
    os.system("clear")
    print("\n\033[1;33m  Finalizing\033[0m\n")
    flag_path = "/etc/holmium/first_run"
    if os.path.exists(flag_path):
        os.remove(flag_path)
        print("  First-run flag disabled.\n")


def configure_wifi_connection(ssid, password):
    if not ssid:
        return
    try:
        run(["nmcli", "device", "wifi", "connect", ssid, "password", password],
            timeout=30)
    except Exception:
        pass


def main():
    if os.path.exists(CONFIG_PATH):
        print("  Config exists — skipping first-run.")
        sys.exit(0)

    step_welcome()
    name = step_user_name()
    ssid, wifi_password = step_wifi()
    privkey, pubkey = step_wireguard_keys()
    token = step_auth_token()

    if step_summary(name, ssid, pubkey, token):
        write_config(name, ssid, wifi_password, pubkey, token)
        print("  \033[1;32m  ✓ Configuration written\033[0m\n")

        configure_wifi_connection(ssid, wifi_password)

        start_services()
        disable_first_run()

        os.system("clear")
        print(HOLMIUM_LOGO)
        print(f"\n  \033[1;32m✓ Setup complete. Welcome, {name}.\033[0m")
        print("  Holmium is ready. The TUI is your interface to the system.\n")
    else:
        print("\n  Setup cancelled. Re-run first_run.py to restart.\n")


if __name__ == "__main__":
    main()
