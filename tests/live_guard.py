#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    live_guard.py
# Description: Keeps the test suite off the live system. conftest.py calls
#              install() before plugin.py is imported, which does two things:
#              1. puts an EMPTY stand-in IndigoSecrets module into sys.modules,
#                 so the real file on this Mac (broker address, user name and
#                 password) is never read, and every MQTT_* import in plugin.py
#                 falls back to its blank default;
#              2. refuses every real socket connect for the whole session
#                 (socket.socket.connect / connect_ex, socket.create_connection)
#                 and records the attempt, so a connect made on a background
#                 thread - where paho's loop_start makes it - still fails the run.
#              Before this, test_log_level_applied_at_start called startup(),
#              which read the real broker settings and opened a paho session to
#              the live Mosquitto broker with real credentials.
# Author:      CliveS & Claude Opus 5.5
# Date:        05-10-2026
# Version:     1.0

from __future__ import annotations

import socket
import sys
import types

# Every refused attempt, as (where, address). Tests that provoke one on purpose
# must remove their own entries; anything left over fails the test and the run.
ATTEMPTS: list[tuple[str, object]] = []

_REAL = {
    "connect":           socket.socket.connect,
    "connect_ex":        socket.socket.connect_ex,
    "create_connection": socket.create_connection,
}


class LiveNetworkBlocked(RuntimeError):
    """Raised when a test tries to open a real network connection.

    Deliberately NOT an OSError: paho and most client code catch OSError and
    retry quietly, which would hide the attempt."""


def _refuse(where, address):
    ATTEMPTS.append((where, address))
    raise LiveNetworkBlocked(
        f"a test tried to open a real network connection ({where} to {address!r}); "
        "the suite must never reach the live system - use a fake instead"
    )


def _connect(self, address):
    _refuse("socket.connect", address)


def _connect_ex(self, address):
    _refuse("socket.connect_ex", address)


def _create_connection(address, *args, **kwargs):
    _refuse("socket.create_connection", address)


def install_secrets_stand_in():
    """Put an empty IndigoSecrets into sys.modules. `from IndigoSecrets import X`
    then raises ImportError, so plugin.py takes its blank fallback for every key
    and the real file is never opened."""
    stand_in = types.ModuleType("IndigoSecrets")
    stand_in.__file__ = None
    stand_in.__doc__ = "Empty stand-in installed by tests/live_guard.py"
    sys.modules["IndigoSecrets"] = stand_in
    return stand_in


def install_network_block():
    socket.socket.connect    = _connect
    socket.socket.connect_ex = _connect_ex
    socket.create_connection = _create_connection


def install():
    install_secrets_stand_in()
    install_network_block()


def is_installed():
    return socket.socket.connect is _connect and socket.create_connection is _create_connection
