"""src/run/net.py — per-run host port allocation.

Two concurrent runs must not fight over 8080. Every run reserves its own
host ports from the configured range. The bind-then-close probe leaves a
sub-millisecond TOCTOU window; `stack.up()` fails loudly if the port is
taken, which is the correct outcome (never silently share a port).
"""

from __future__ import annotations

import socket

import config


def _free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
        return True


def allocate(count: int) -> list[int]:
    found: list[int] = []
    for port in range(config.PORT_RANGE_START, config.PORT_RANGE_END + 1):
        if len(found) == count:
            break
        if _free(port):
            found.append(port)
    if len(found) < count:
        raise RuntimeError(
            f"could not allocate {count} free ports in "
            f"{config.PORT_RANGE_START}-{config.PORT_RANGE_END}"
        )
    return found
