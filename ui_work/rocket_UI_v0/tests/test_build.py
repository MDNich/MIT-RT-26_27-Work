import importlib.util
from pathlib import Path
import pytest


def test_windows_arm_host_with_x64_python_selects_x64_runtime(monkeypatch):
    path = Path(__file__).resolve().parents[1] / "scripts/build.py"
    spec = importlib.util.spec_from_file_location("rocket_build", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.platform, "system", lambda: "Windows")
    monkeypatch.setattr(module.platform, "machine", lambda: "ARM64")
    monkeypatch.setattr(module.sysconfig, "get_platform", lambda: "win-amd64")
    assert module.process_architecture() == "x64"
    monkeypatch.setattr(module.sysconfig, "get_platform", lambda: "win-arm64")
    with pytest.raises(SystemExit, match="x86 Python"):
        module.process_architecture()
