import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import Memoir

def test_ping():
    result = Memoir.ping()
    print(result)
    assert result == "Memoir 0.1.0 loaded OK"

def test_version():
    assert Memoir.__version__ == "0.1.0"

if __name__ == "__main__":
    test_ping()
    test_version()
    print("All Phase 1 tests passed.")
