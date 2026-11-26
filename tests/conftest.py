import os
import socket

import pytest

DEVICE = "sys/tg_test/1"
LASERLAB_DEVICE = "laserlab/laser/1"


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


def laserlab_available():
    """The laser lab simulator (examples/laserlab/simulator.py) is running."""
    if not tango_available():
        return False
    import tango

    try:
        tango.DeviceProxy(LASERLAB_DEVICE).ping()
        return True
    except tango.DevFailed:
        return False


def pytest_collection_modifyitems(config, items):
    skips = {}
    if not tango_available():
        skips["tango"] = skips["laserlab"] = pytest.mark.skip(reason="no Tango database at TANGO_HOST")
    elif any("laserlab" in item.keywords for item in items) and not laserlab_available():
        skips["laserlab"] = pytest.mark.skip(reason="laser lab simulator not running (examples/laserlab/simulator.py)")
    for item in items:
        for keyword, skip in skips.items():
            if keyword in item.keywords:
                item.add_marker(skip)
