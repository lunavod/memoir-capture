import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--headless", action="store_true", default=False,
        help="Skip tests that require a display (WGC capture)",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "capture: test requires a live display for WGC capture"
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--headless"):
        skip = pytest.mark.skip(reason="requires display (use without --headless)")
        for item in items:
            if "capture" in item.keywords:
                item.add_marker(skip)
