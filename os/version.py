#!/usr/bin/env python3
"""Holmium OS version management.

Reads /etc/holmium/VERSION (semver string).
Provides read, bump_patch, bump_minor, bump_major functions.
CLI: python version.py [command] [--write]
"""

import argparse
import os
import re
import sys

VERSION_FILE = "/etc/holmium/VERSION"

SEMVER_RE = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?P<pre>-[^+]+)?(\+(?P<build>.+))?$")


def read_version(path=VERSION_FILE):
    """Read semver string from VERSION file. Returns tuple (major, minor, patch)."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Version file not found: {path}")
    with open(path, "r") as f:
        raw = f.read().strip()
    m = SEMVER_RE.match(raw)
    if not m:
        raise ValueError(f"Invalid semver in {path}: {raw!r}")
    return int(m.group("major")), int(m.group("minor")), int(m.group("patch"))


def format_version(major, minor, patch):
    return f"{major}.{minor}.{patch}"


def bump_patch(path=VERSION_FILE, write=True):
    major, minor, patch = read_version(path)
    patch += 1
    version = format_version(major, minor, patch)
    if write:
        _write(path, version)
    return version


def bump_minor(path=VERSION_FILE, write=True):
    major, minor, _ = read_version(path)
    minor += 1
    version = format_version(major, minor, 0)
    if write:
        _write(path, version)
    return version


def bump_major(path=VERSION_FILE, write=True):
    major, _, _ = read_version(path)
    major += 1
    version = format_version(major, 0, 0)
    if write:
        _write(path, version)
    return version


def _write(path, version):
    with open(path, "w") as f:
        f.write(version + "\n")


def main():
    parser = argparse.ArgumentParser(description="Holmium OS version tool")
    parser.add_argument("command", nargs="?", default="read",
                        choices=["read", "bump-patch", "bump-minor", "bump-major"],
                        help="Version operation (default: read)")
    parser.add_argument("--path", default=VERSION_FILE, help="Path to VERSION file")
    parser.add_argument("--no-write", action="store_true", help="Print new version without writing")
    args = parser.parse_args()

    try:
        if args.command == "read":
            major, minor, patch = read_version(args.path)
            print(format_version(major, minor, patch))
        elif args.command == "bump-patch":
            print(bump_patch(args.path, write=not args.no_write))
        elif args.command == "bump-minor":
            print(bump_minor(args.path, write=not args.no_write))
        elif args.command == "bump-major":
            print(bump_major(args.path, write=not args.no_write))
    except (FileNotFoundError, ValueError, PermissionError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
