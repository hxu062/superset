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

import threading
import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from superset.mcp_service.screenshot.webdriver_pool import (
    WebDriverCreationError,
    WebDriverPool,
)

WINDOW_SIZE = (800, 600)


def run_in_thread(app: Flask, func: Any) -> Any:
    """Run func on a worker thread and return its result or re-raise its error"""
    result: dict[str, Any] = {}

    def target() -> None:
        try:
            with app.app_context():
                result["value"] = func()
        except BaseException as ex:  # pylint: disable=broad-except
            result["error"] = ex

    thread = threading.Thread(target=target)
    thread.start()
    thread.join(timeout=30)
    assert not thread.is_alive()
    if "error" in result:
        raise result["error"]
    return result["value"]


@pytest.fixture(name="app")
def app_fixture() -> Any:
    app = Flask(__name__)
    app.config["WEBDRIVER_TYPE"] = "firefox"
    with app.app_context():
        yield app


def test_create_driver_from_worker_thread(
    app: Flask, caplog: pytest.LogCaptureFixture
) -> None:
    """Driver creation must work off the main thread (no signal usage)"""
    pool = WebDriverPool()
    driver = MagicMock()

    with patch(
        "superset.mcp_service.screenshot.webdriver_pool.WebDriverSelenium"
    ) as selenium_cls:
        selenium_cls.return_value.create.return_value = driver
        pooled = run_in_thread(app, lambda: pool._create_driver(WINDOW_SIZE))

    assert pooled.driver is driver
    driver.set_window_size.assert_called_once_with(*WINDOW_SIZE)
    assert pool.get_stats()["created"] == 1
    assert "signal" not in caplog.text


def test_get_driver_from_worker_thread(app: Flask) -> None:
    """The public context manager is usable from a worker thread"""
    pool = WebDriverPool()
    driver = MagicMock()

    def borrow() -> Any:
        with patch(
            "superset.mcp_service.screenshot.webdriver_pool.WebDriverSelenium"
        ) as selenium_cls:
            selenium_cls.return_value.create.return_value = driver
            with pool.get_driver(WINDOW_SIZE) as borrowed:
                return borrowed

    assert run_in_thread(app, borrow) is driver


def test_create_driver_times_out_and_quits_late_driver(app: Flask) -> None:
    """A creation that overruns the timeout raises and the late driver is quit"""
    pool = WebDriverPool(creation_timeout_seconds=1)
    driver = MagicMock()

    def slow_create() -> MagicMock:
        time.sleep(2)
        return driver

    with patch(
        "superset.mcp_service.screenshot.webdriver_pool.WebDriverSelenium"
    ) as selenium_cls:
        selenium_cls.return_value.create.side_effect = slow_create
        with pytest.raises(WebDriverCreationError):
            pool._create_driver(WINDOW_SIZE)

        deadline = time.time() + 10
        while not driver.quit.called and time.time() < deadline:
            time.sleep(0.05)

    driver.quit.assert_called_once()
    assert pool.get_stats()["created"] == 0


def test_create_driver_quits_driver_when_setup_fails(app: Flask) -> None:
    """A driver that fails after creation is quit and the error propagates"""
    pool = WebDriverPool()
    driver = MagicMock()
    driver.set_window_size.side_effect = RuntimeError("boom")

    with patch(
        "superset.mcp_service.screenshot.webdriver_pool.WebDriverSelenium"
    ) as selenium_cls:
        selenium_cls.return_value.create.return_value = driver
        with pytest.raises(RuntimeError, match="boom"):
            pool._create_driver(WINDOW_SIZE)

    driver.quit.assert_called_once()
