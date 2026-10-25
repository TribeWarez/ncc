import os
import time

import pytest

pytest.importorskip("PySide6")

from ncc.single_instance import SingleInstance, instance_name  # noqa: E402


def test_instance_name_is_stable(qapp):
    assert instance_name() == instance_name()
    assert instance_name().startswith("ncc-single-instance-")


def test_second_instance_is_rejected(qapp):
    name = f"ncc-test-{os.getpid()}-{time.monotonic_ns()}"
    first = SingleInstance(name)
    second = SingleInstance(name)
    try:
        assert first.try_acquire() is True
        assert second.try_acquire() is False
    finally:
        first.close()
        second.close()
