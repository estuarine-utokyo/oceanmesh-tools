from __future__ import annotations

import sys
import time
from contextlib import contextmanager


@contextmanager
def step(msg: str, enabled: bool = True):
    t0 = time.perf_counter()
    if enabled:
        print(msg, flush=True)
    try:
        yield
    finally:
        if enabled:
            dt = (time.perf_counter() - t0) * 1000.0
            print(f"  done in {dt:.1f} ms", flush=True)

