"""LAN scanner tools using python-nmap."""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import nmap

from tools.registry import register_tool

KNOWN_DEVICES_PATH = Path("/var/holmium/network/known_devices.json")


def _ensure_known_devices() -> Dict[str, Any]:
    KNOWN_DEVICES_PATH.parent.mkdir(parents=True, exist_ok=True)
    if KNOWN_DEVICES_PATH.is_file():
        return json.loads(KNOWN_DEVICES_PATH.read_text())
    return {"devices": []}


def _save_known_devices(data: Dict[str, Any]) -> None:
    KNOWN_DEVICES_PATH.write_text(json.dumps(data, indent=2))


def _get_local_subnet() -> str:
    """Discover local subnet from routing table."""
    import subprocess
    try:
        out = subprocess.check_output(
            ["ip", "-o", "-4", "route", "show", "to", "default"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        parts = out.strip().split()
        for i, p in enumerate(parts):
            if p == "dev" and i + 1 < len(parts):
                iface = parts[i + 1]
                addr_out = subprocess.check_output(
                    ["ip", "-o", "-4", "addr", "show", iface],
                    text=True,
                    stderr=subprocess.DEVNULL,
                )
                for line in addr_out.split("\n"):
                    if "inet " in line:
                        addr = line.strip().split()[3]
                        from ipaddress import ip_network
                        net = ip_network(addr, strict=False)
                        return str(net)
        return "192.168.1.0/24"
    except Exception:
        return "192.168.1.0/24"


@register_tool(
    "lan_scan",
    "Scan the local network for active devices (ping scan).",
)
def lan_scan() -> List[Dict[str, Any]]:
    try:
        nm = nmap.PortScanner()
        subnet = _get_local_subnet()
        nm.scan(hosts=subnet, arguments="-sn --timeout 5")
        results: List[Dict[str, Any]] = []
        for host in nm.all_hosts():
            host_info = nm[host]
            mac = ""
            vendor = ""
            if "addresses" in host_info and "mac" in host_info["addresses"]:
                mac = host_info["addresses"]["mac"]
            if "vendor" in host_info and mac in host_info["vendor"]:
                vendor = host_info["vendor"][mac]

            results.append({
                "ip": host,
                "mac": mac,
                "hostname": host_info.get("hostnames", [{}])[0].get("name", "") if host_info.get("hostnames") else "",
                "vendor": vendor,
                "status": host_info.get("status", {}).get("state", ""),
            })
        return results
    except Exception as e:
        return [{"error": str(e)}]


@register_tool(
    "lan_scan_device",
    "Full port scan on a specific IP address.",
    params_schema={
        "type": "object",
        "properties": {
            "ip": {
                "type": "string",
                "description": "IP address to scan",
            },
        },
        "required": ["ip"],
    },
)
def lan_scan_device(ip: str) -> Dict[str, Any]:
    try:
        nm = nmap.PortScanner()
        nm.scan(hosts=ip, arguments="-sV --timeout 30")
        result: Dict[str, Any] = {"ip": ip, "ports": []}
        if ip in nm.all_hosts():
            host_info = nm[ip]
            if "tcp" in host_info:
                for port, port_info in host_info["tcp"].items():
                    result["ports"].append({
                        "port": port,
                        "state": port_info.get("state", ""),
                        "service": port_info.get("name", ""),
                        "product": port_info.get("product", ""),
                        "version": port_info.get("version", ""),
                    })
            if "osmatch" in host_info and host_info["osmatch"]:
                result["os"] = host_info["osmatch"][0].get("name", "")
        return result
    except Exception as e:
        return {"error": str(e), "ip": ip}


@register_tool(
    "lan_get_known_devices",
    "Get the list of known/registered network devices.",
)
def lan_get_known_devices() -> List[Dict[str, Any]]:
    data = _ensure_known_devices()
    return data.get("devices", [])


@register_tool(
    "lan_register_device",
    "Register a device by MAC address and name in the known devices list.",
    params_schema={
        "type": "object",
        "properties": {
            "mac": {
                "type": "string",
                "description": "MAC address to register",
            },
            "name": {
                "type": "string",
                "description": "Human-readable device name",
            },
        },
        "required": ["mac", "name"],
    },
)
def lan_register_device(mac: str, name: str) -> bool:
    data = _ensure_known_devices()
    for d in data["devices"]:
        if d["mac"].lower() == mac.lower():
            d["name"] = name
            _save_known_devices(data)
            return True
    data["devices"].append({"mac": mac.lower(), "name": name})
    _save_known_devices(data)
    return True


@register_tool(
    "lan_unknown_devices",
    "Scan the network and return devices not in the known registry.",
)
def lan_unknown_devices() -> List[Dict[str, Any]]:
    known = _ensure_known_devices()
    known_macs = {d["mac"].lower() for d in known.get("devices", [])}

    scan_results = lan_scan()
    unknown: List[Dict[str, Any]] = []
    for device in scan_results:
        mac = device.get("mac", "").lower()
        if mac and mac not in known_macs:
            unknown.append(device)
    return unknown
