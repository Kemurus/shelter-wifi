"""
Atomic read/write of hostapd.conf, preserving comments and ordering.
"""
import os
from typing import Dict

HOSTAPD_CONF = '/opt/shelter-wifi/config/hostapd.conf'


def read_hostapd_conf(path: str = HOSTAPD_CONF) -> Dict[str, str]:
    cfg = {}
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    cfg[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return cfg


def write_hostapd_conf(updates: Dict[str, str], path: str = HOSTAPD_CONF, removes: list = None) -> None:
    """
    Update key=value pairs in hostapd.conf, preserving comments.
    Uses atomic write (write to .tmp, then os.replace) to prevent corruption.
    """
    try:
        with open(path) as f:
            lines = f.readlines()
    except FileNotFoundError:
        lines = []

    removes = set(removes or [])
    updated_keys = set()
    new_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('#') and '=' in stripped:
            key = stripped.split('=', 1)[0].strip()
            if key in removes:
                continue  # drop this line
            if key in updates:
                new_lines.append(f'{key}={updates[key]}\n')
                updated_keys.add(key)
                continue
        new_lines.append(line)

    # Append keys not already present in the file
    for key, val in updates.items():
        if key not in updated_keys:
            new_lines.append(f'{key}={val}\n')

    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        f.writelines(new_lines)
    os.replace(tmp, path)  # atomic on Linux
