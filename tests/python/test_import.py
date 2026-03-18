import memoir


def test_ping():
    assert memoir.ping() == "memoir-capture 0.1.0 loaded OK"


def test_version():
    assert memoir.__version__ == "0.1.0"
