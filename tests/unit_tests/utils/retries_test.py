# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""Tests for superset.utils.retries.retry_call."""

from collections.abc import Generator
from typing import Any
from unittest.mock import Mock

import pytest

from superset.utils.retries import retry_call


class CustomError(Exception):
    pass


class OtherError(Exception):
    pass


def make_func(**kwargs: Any) -> Mock:
    """A mock callable that ``functools.wraps`` (used by backoff) accepts."""
    func = Mock(**kwargs)
    func.__name__ = "target"
    return func


def test_retry_call_returns_first_attempt() -> None:
    func = make_func(return_value="ok")

    result = retry_call(func, max_tries=3, interval=0)

    assert result == "ok"
    assert func.call_count == 1


def test_retry_call_retries_until_success() -> None:
    func = make_func(side_effect=[CustomError(), CustomError(), "ok"])

    result = retry_call(func, max_tries=3, interval=0, exception=CustomError)

    assert result == "ok"
    assert func.call_count == 3


def test_retry_call_gives_up_and_reraises() -> None:
    error = CustomError("boom")
    func = make_func(side_effect=error)

    with pytest.raises(CustomError) as excinfo:
        retry_call(func, max_tries=3, interval=0, exception=CustomError)

    assert excinfo.value is error
    assert func.call_count == 3


def test_retry_call_does_not_retry_other_exceptions() -> None:
    func = make_func(side_effect=OtherError("nope"))

    with pytest.raises(OtherError):
        retry_call(func, max_tries=3, interval=0, exception=CustomError)

    assert func.call_count == 1


def test_retry_call_forwards_args_and_kwargs() -> None:
    func = make_func(side_effect=[CustomError(), "ok"])

    result = retry_call(
        func,
        max_tries=2,
        interval=0,
        exception=CustomError,
        fargs=[1, 2],
        fkwargs={"three": 3},
    )

    assert result == "ok"
    assert func.call_count == 2
    for actual_call in func.call_args_list:
        assert actual_call.args == (1, 2)
        assert actual_call.kwargs == {"three": 3}


def test_retry_call_honours_custom_strategy() -> None:
    waits: list[Any] = []

    def strategy(*args: Any, **kwargs: Any) -> Generator[int, None, None]:
        waits.append((args, kwargs))
        while True:
            yield 0

    func = make_func(side_effect=[CustomError(), "ok"])

    result = retry_call(
        func,
        max_tries=2,
        exception=CustomError,
        strategy=strategy,
    )

    assert result == "ok"
    assert func.call_count == 2
    assert len(waits) == 1
