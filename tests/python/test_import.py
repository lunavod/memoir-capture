import memoir


def test_ping():
    assert memoir.ping() == "Memoir 0.1.0 loaded OK"


def test_version():
    assert memoir.__version__ == "0.1.0"
