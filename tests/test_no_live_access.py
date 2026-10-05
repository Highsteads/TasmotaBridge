#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_no_live_access.py
# Description: Proves the harness keeps the suite off the live system: the real
#              IndigoSecrets.py is never read, the plugin sees blank broker
#              settings, startup() makes no connection, and any real socket
#              connect is refused with a clear error.
# Author:      CliveS & Claude Opus 5.5
# Date:        05-10-2026
# Version:     1.0

from __future__ import annotations

import logging
import socket
import sys

import pytest

import live_guard


def test_indigosecrets_is_the_empty_stand_in(plugin_mod):
    mod = sys.modules.get("IndigoSecrets")
    assert mod is not None and getattr(mod, "__file__", "x") is None, \
        "the real IndigoSecrets.py was imported; conftest must install the stand-in first"
    assert [k for k in vars(mod) if k.startswith("MQTT")] == []


def test_plugin_sees_blank_broker_settings(plugin_mod):
    assert plugin_mod.MQTT_BROKER == ""
    assert plugin_mod.MQTT_USERNAME == ""
    assert plugin_mod.MQTT_PASSWORD == ""
    assert plugin_mod.resolve_broker({})["host"] == ""


def test_network_block_is_installed():
    assert live_guard.is_installed()


@pytest.mark.parametrize("attempt", [
    lambda: socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("127.0.0.1", 9)),
    lambda: socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect_ex(("127.0.0.1", 9)),
    lambda: socket.create_connection(("127.0.0.1", 9), timeout=0.5),
], ids=["connect", "connect_ex", "create_connection"])
def test_a_deliberate_connect_is_refused(attempt):
    before = len(live_guard.ATTEMPTS)
    try:
        with pytest.raises(live_guard.LiveNetworkBlocked, match="real network connection"):
            attempt()
        assert len(live_guard.ATTEMPTS) == before + 1
    finally:
        del live_guard.ATTEMPTS[before:]   # provoked on purpose: not a leak


def test_startup_with_no_broker_makes_no_connection(plugin_mod):
    p = object.__new__(plugin_mod.Plugin)
    p.logger = logging.getLogger("tasmota-test")
    p.pluginPrefs = {}
    p.indigo_log_handler = logging.Handler()
    p.mqtt_client = None
    p._set_broker(plugin_mod.resolve_broker({}))
    p.startup()
    assert p.mqtt_client is None
