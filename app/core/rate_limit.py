import sys

from slowapi import Limiter
from slowapi.util import get_remote_address

# limiter is constructed once, at import time, during pytest's collection phase
# -- before any individual test runs -- so PYTEST_CURRENT_TEST (only set while
# a test is executing) isn't available yet. `pytest` itself is already in
# sys.modules by then, so check for that instead. Without this, the ~30 login
# calls across the test suite trip the limit well within the same minute.
limiter = Limiter(key_func=get_remote_address, enabled="pytest" not in sys.modules)
