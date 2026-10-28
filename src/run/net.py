"""src/run/net.py — per-run host port allocation.

Every run takes its own host ports from the configured range, so two runs
do not fight over 8080. The probe is bind-then-close and therefore reserves
nothing: the window it leaves open is not sub-millisecond but as long as
everything between allocation and the container publishing the port — a
`compose up --build` can be minutes, and a sibling run can take the port in
between.

That is acceptable because a finished run reaps its own tree (`compose@1`'s
`reap`), so leftovers do not accumulate, and because `stack.up()` fails
loudly instead of sharing a port.
"""

from __future__ import annotations

import socket

import config


def _free_on(family: int, host: str, port: int) -> bool:
    """Can this address be bound? Docker publishes IPv4 and IPv6 alike."""
    with socket.socket(family, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
        except OSError:
            return False
        return True


def _free(port: int) -> bool:
    if not _free_on(socket.AF_INET, "0.0.0.0", port):
        return False
    if not socket.has_ipv6:
        return True
    try:
        return _free_on(socket.AF_INET6, "::", port)
    except OSError:  # IPv6 disabled in this kernel
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
