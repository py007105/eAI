from unittest.mock import Mock

import pytest

from eternalai.drivers.base import NotSupported, UNSUPPORTED
from eternalai.drivers.docker import DockerDriver


def test_docker_driver_preserves_executor_calls_and_audit():
    executor = Mock()
    executor.audit = []
    driver = DockerDriver(executor)
    assert driver.run("restart_service", "frontend", "operator", ["e1"], "test") is executor.run.return_value
    executor.run.assert_called_once_with("restart_service", "frontend", "operator", ["e1"], "test")
    driver.log_verification("i1", "restart_service", "frontend", "recovered", 1.0)
    executor.log_verification.assert_called_once_with("i1", "restart_service", "frontend", "recovered", 1.0)
    assert driver.audit is executor.audit
    assert driver.replicas("frontend") == 1


def test_unsupported_docker_operations_are_audited():
    executor = Mock()
    executor.audit = []
    driver = DockerDriver(executor)
    for operation in ("scale_to", "delete_pod", *UNSUPPORTED):
        with pytest.raises(NotSupported):
            if operation == "scale_to":
                driver.scale_to("frontend", 2)
            else:
                getattr(driver, operation)("frontend")
    assert executor._log.call_count == 2 + len(UNSUPPORTED)
