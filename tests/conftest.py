import os
import socket

import pytest

DEVICE = "sys/tg_test/1"


def tango_available():
    host = os.environ.get("TANGO_HOST")
    if not host or ":" not in host:
        return False
    name, port = host.rsplit(":", 1)
    try:
        with socket.create_connection((name, int(port)), timeout=1):
            return True
    except OSError:
        return False


def pytest_collection_modifyitems(config, items):
    if tango_available():
        return
    skip = pytest.mark.skip(reason="no Tango database at TANGO_HOST")
    for item in items:
        if "tango" in item.keywords:
            item.add_marker(skip)
