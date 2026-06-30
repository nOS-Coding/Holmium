#!/usr/bin/env python3
"""Holmium Dual-Boot Detection — scan for existing OS installations."""

import json
import os
import re
import subprocess
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


@dataclass
class DetectedOS:
    name: str
    label: str
    partition: str
    filesystem: str
    bootloader: str = ""
    grub_config: str = ""
    is_installed: bool = True


KNOWN_OSES = {
    "debian": DetectedOS("Debian", "Debian GNU/Linux", "", "ext4", "grub", "/etc/default/grub"),
    "kde-neon": DetectedOS("KDE Neon", "KDE neon", "", "ext4", "grub", "/etc/default/grub"),
    "ubuntu": DetectedOS("Ubuntu", "Ubuntu", "", "ext4", "grub", "/etc/default/grub"),
    "fedora": DetectedOS("Fedora", "Fedora Linux", "", "btrfs", "grub", "/etc/default/grub"),
    "nobara": DetectedOS("Nobara", "Nobara Linux", "", "btrfs", "grub", "/etc/default/grub"),
    "cachyos": DetectedOS("CachyOS", "CachyOS", "", "btrfs", "grub", "/etc/default/grub"),
}


def run(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def detect_partitions():
    """List all partitions with filesystem info."""
    result = run(["lsblk", "-o", "NAME,FSTYPE,LABEL,PARTLABEL,SIZE,TYPE,MOUNTPOINT", "-J"])
    if not result:
        return []
    
    try:
        data = json.loads(result)
        partitions = []
        for dev in data.get("blockdevices", []):
            _flatten_partitions(dev, partitions)
        return partitions
    except (json.JSONDecodeError, KeyError):
        return []


def _flatten_partitions(dev, acc, prefix=""):
    name = prefix + dev.get("name", "")
    if dev.get("type") == "part" and dev.get("fstype"):
        acc.append({
            "name": name,
            "fstype": dev.get("fstype"),
            "label": dev.get("label") or dev.get("partlabel") or "",
            "size": dev.get("size", ""),
            "mountpoint": dev.get("mountpoint", ""),
        })
    for child in dev.get("children", []):
        _flatten_partitions(child, acc, prefix)


def detect_os_on_partition(part_info):
    """Check if a partition has a known OS installed."""
    label = (part_info.get("label") or "").lower()
    fstype = part_info.get("fstype") or ""
    dev_name = part_info.get("name", "")
    
    for os_id, os_info in KNOWN_OSES.items():
        if os_id in label or os_info.label.lower() in label:
            os_info.partition = dev_name
            os_info.filesystem = fstype
            return os_info
    
    # Generic detection: any ext4/btrfs root partition
    if fstype in ("ext4", "btrfs"):
        return DetectedOS(
            name=f"Linux ({fstype})",
            label=part_info.get("label") or "Unknown Linux",
            partition=dev_name,
            filesystem=fstype,
        )
    
    return None


def detect_all():
    """Detect all installed OSes on the system."""
    partitions = detect_partitions()
    detected = []
    
    for part in partitions:
        os_info = detect_os_on_partition(part)
        if os_info and os_info not in detected:
            detected.append(os_info)
    
    # Deduplicate by name
    seen = set()
    unique = []
    for os_info in detected:
        if os_info.name not in seen:
            seen.add(os_info.name)
            unique.append(os_info)
    
    return unique


def generate_grub_entry(os_info: DetectedOS) -> str:
    """Generate a GRUB chain-load entry for the detected OS."""
    if os_info.bootloader == "grub":
        return f"""
### BEGIN HOLMIUM DUAL-BOOT: {os_info.label}
menuentry '{os_info.label} (chain-load)' {{
    insmod part_gpt
    insmod {os_info.filesystem}
    search --no-floppy --fs-uuid --set=root $(blkid -s UUID -o value /dev/{os_info.partition})
    configfile /boot/grub/grub.cfg
}}
### END HOLMIUM DUAL-BOOT: {os_info.label}
"""
    return ""


def write_dual_boot_config(selected_oses: list[DetectedOS], grub_dir="/boot/grub"):
    """Write dual-boot entries to GRUB config."""
    entries = []
    for os_info in selected_oses:
        entry = generate_grub_entry(os_info)
        if entry:
            entries.append(entry)
    
    if not entries:
        return False
    
    custom_path = Path(grub_dir) / "custom.cfg"
    existing = ""
    if custom_path.exists():
        existing = custom_path.read_text()
    
    # Find and replace Holmium dual-boot section
    start_marker = "### BEGIN HOLMIUM DUAL-BOOT"
    end_marker = "### END HOLMIUM DUAL-BOOT"
    
    lines = existing.split("\n")
    new_lines = []
    skip = False
    for line in lines:
        if start_marker in line:
            skip = True
        if not skip:
            new_lines.append(line)
        if end_marker in line:
            skip = False
    
    # Append new entries
    new_lines.append("")
    for entry in entries:
        new_lines.append(entry)
    
    custom_path.parent.mkdir(parents=True, exist_ok=True)
    custom_path.write_text("\n".join(new_lines))
    custom_path.chmod(0o644)
    
    return True


def format_detected_for_display(detected: list[DetectedOS]) -> list[dict]:
    """Format detected OSes for TUI display."""
    return [{"name": os.name, "label": os.label, "partition": os.partition} for os in detected]


if __name__ == "__main__":
    detected = detect_all()
    print(json.dumps(format_detected_for_display(detected), indent=2))
    if detected:
        print(f"\nFound {len(detected)} existing OS(es)")
