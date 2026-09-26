"""A model stand-in for headless runs that must never call one (Bond's final fix wave, T1).

Every model call site catches a failure and falls back to the rules, so an `http` that only raises
proves nothing: a call would pass unseen. NoModel counts every call as well, and a test asserts at
the end that the count is zero.
"""

from __future__ import annotations


class NoModel:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append(url)
        raise AssertionError("no model is called in a headless run")


def no_model(test) -> NoModel:
    """A NoModel whose count `test` (a unittest.TestCase) checks when it ends: a model called in a headless
    run fails the test, even when the rules covered for it."""
    stub = NoModel()
    test.addCleanup(lambda: test.assertEqual(stub.calls, [], "a model was called in a headless run"))
    return stub
