import memoir


def test_ping():
    assert memoir.ping() == "memoir-capture 0.1.1 loaded OK"


def test_version():
    assert memoir.__version__ == "0.1.1"
