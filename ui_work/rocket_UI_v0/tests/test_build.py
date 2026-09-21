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


@pytest.fixture
def builder(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[1] / "scripts/build.py"
    spec = importlib.util.spec_from_file_location("rocket_build", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "VENDOR", tmp_path / "vendor")
    (tmp_path / "simulation_bridge/src").mkdir(parents=True)
    (tmp_path / "simulation_bridge/src/RocketBridge.java").write_text("test bridge")
    return module


def jar_fixture(path):
    import zipfile

    with zipfile.ZipFile(path, "w") as archive:
        for name in (
            "info/openrocket/core/document/OpenRocketDocument.class",
            "info/openrocket/core/startup/Application.class",
            "com/google/inject/Guice.class",
        ):
            archive.writestr(name, b"test")


def release_fixture(builder, monkeypatch, digest=None, tag="v6.2"):
    import io
    import json

    source = builder.ROOT / "release.jar"
    jar_fixture(source)
    checksum = digest or "sha256:" + builder.sha(source)
    metadata = dict(
        tag_name=tag,
        draft=False,
        prerelease=False,
        assets=[
            dict(
                name=f"OpenRocket-MIT-{tag}.jar",
                size=source.stat().st_size,
                digest=checksum,
                browser_download_url=f"https://github.com/{builder.RELEASE_REPOSITORY}/releases/download/{tag}/OpenRocket-MIT-{tag}.jar",
            )
        ],
    )
    requests = []

    def urlopen(request, **kwargs):
        requests.append(request.full_url)
        return io.BytesIO(json.dumps(metadata).encode())

    monkeypatch.setattr(builder.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(builder, "download", lambda url, path: path.write_bytes(source.read_bytes()))
    return requests, source


def fake_compile(*args):
    if args[0] == "jar":
        Path(args[args.index("--file") + 1]).write_bytes(b"compiled bridge")


def test_download_latest_resolves_named_jar_and_records_checksum(builder, monkeypatch):
    import json

    requests, source = release_fixture(builder, monkeypatch, tag="v7.12")
    monkeypatch.setattr(builder, "run", fake_compile)
    builder.bridge(release="latest")
    assert requests == [f"https://api.github.com/repos/{builder.RELEASE_REPOSITORY}/releases/latest"]
    assert (builder.VENDOR / "openrocket.jar").read_bytes() == source.read_bytes()
    manifest = json.loads((builder.VENDOR / "engine.json").read_text())
    assert manifest["source"]["release_tag"] == "v7.12"
    assert manifest["source"]["checksum_verified"]
    assert manifest["engine_sha256"] == builder.sha(source)


def test_download_pinned_release_and_local_path_with_spaces(builder, monkeypatch):
    import json

    requests, source = release_fixture(builder, monkeypatch)
    monkeypatch.setattr(builder, "run", fake_compile)
    builder.bridge(release="v6.2")
    assert requests[0].endswith("/releases/tags/v6.2")
    local = builder.ROOT / "My OpenRocket.jar"
    local.write_bytes(source.read_bytes())
    builder.bridge(engine=str(local))
    manifest = json.loads((builder.VENDOR / "engine.json").read_text())
    assert manifest["source"] == dict(kind="local_file", path=str(local))
    assert (builder.VENDOR / "openrocket.jar").read_bytes() == local.read_bytes()


@pytest.mark.parametrize("failure", ["checksum", "compile"])
def test_failed_engine_update_preserves_staged_bundle(builder, monkeypatch, failure):
    import subprocess

    builder.VENDOR.mkdir()
    for name in ("openrocket.jar", "rocket-bridge.jar", "engine.json"):
        (builder.VENDOR / name).write_bytes(b"original")
    release_fixture(builder, monkeypatch, digest="sha256:" + "0" * 64 if failure == "checksum" else None)

    def failed_compile(*args):
        raise subprocess.CalledProcessError(1, args)

    monkeypatch.setattr(builder, "run", failed_compile)
    with pytest.raises((SystemExit, subprocess.CalledProcessError)):
        builder.bridge(release="latest")
    for name in ("openrocket.jar", "rocket-bridge.jar", "engine.json"):
        assert (builder.VENDOR / name).read_bytes() == b"original"
    assert list((builder.ROOT / "build").iterdir()) == []


def test_mutually_exclusive_engine_sources_and_missing_release_asset(builder, monkeypatch):
    with pytest.raises(SystemExit, match="not both"):
        builder.bridge(engine="engine.jar", release="latest")
    import io

    monkeypatch.setattr(
        builder.urllib.request, "urlopen", lambda *a, **kw: io.BytesIO(b'{"tag_name":"v6.2","assets":[]}')
    )
    with pytest.raises(SystemExit, match="exactly one OpenRocket-MIT-v6.2.jar"):
        builder.release_asset("latest")


def test_package_forwards_engine_options_before_freezing(builder, monkeypatch):
    calls = []

    def stop_after_bridge(engine, release):
        calls.append((engine, release))
        raise RuntimeError("stop before packaging")

    monkeypatch.setattr(builder, "bridge", stop_after_bridge)
    with pytest.raises(RuntimeError, match="stop before packaging"):
        builder.package("", "", "latest")
    assert calls == [("", "latest")]
