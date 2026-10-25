"""Validate documentation fixtures and references; not a server conformance test."""
from pathlib import Path
import base64
import hashlib
import json
import re
import uuid

ROOT = Path(__file__).resolve().parent


def main():
    files = {p.stem: json.loads(p.read_text()) for p in (ROOT / "examples").glob("*.json")}
    assert len(files) == 6, "Missing or unexpected exchange examples"
    info, sub, obs = (files[n] for n in ("info", "subscribe", "observation"))
    request, response, reset = (files[n] for n in ("video-request", "video-response", "reset"))
    for record in (info, sub, obs, reset):
        for key in ("node_id", "boot_id", "mission_id"):
            uuid.UUID(record[key])
    for envelope in (sub, obs, reset):
        assert envelope["v"] == 1
        assert envelope["source_mode"] == "live"
        assert re.fullmatch(r"0|[1-9][0-9]*", envelope["sent_mono_ms"])
        assert len(json.dumps(envelope).encode()) <= 262144
    assert info["node_id"] == obs["node_id"] == reset["node_id"]
    assert info["boot_id"] == obs["boot_id"] == sub["payload"]["resume"]["boot_id"]
    assert sub["payload"]["client_node_id"] == sub["node_id"]
    assert sub["payload"]["client_boot_id"] == sub["boot_id"]
    assert info["mission_id"] == sub["mission_id"] == obs["mission_id"] == request["mission_id"]
    assert int(obs["event_seq"]) == int(sub["payload"]["resume"]["after_event_seq"]) + 1
    payload = obs["payload"]
    raw = base64.b64decode(payload["packet"]["raw_b64"], validate=True)
    assert hashlib.sha256(raw).hexdigest() == payload["packet"]["raw_sha256"]
    assert int(payload["timing"]["received_mono_ms"]) <= int(obs["sent_mono_ms"])
    assert payload["observation_id"].startswith(obs["node_id"] + ":" + obs["boot_id"] + ":")
    assert request["expected_server_boot_id"] == response["server_boot_id"]
    assert request["expected_media_epoch"] == response["media_epoch"]
    assert request["stream_id"] == response["stream_id"] == "gs1.sustainer.digital"
    assert response["lease_ms"] == 30000
    assert response["transport"]["srt_streamid"] == "rt1:" + response["session_id"] + ":" + response["session_token"]
    assert 50000 <= response["transport"]["port"] <= 50063
    assert re.fullmatch(r"[0-9a-f]{32}", response["session_token"])
    assert int(reset["payload"]["old_cursor"]["after_event_seq"]) < int(reset["payload"]["retained_first_event_seq"])
    tex = "\n".join(p.read_text() for p in ROOT.rglob("*.tex") if "build" not in p.parts)
    for name in re.findall(r"\\input\{([^}]+)\}", tex):
        assert (ROOT / (name + ".tex")).is_file(), name
    for name in re.findall(r"\\lstinputlisting\{([^}]+)\}", tex):
        assert (ROOT / name).is_file(), name
    labels = re.findall(r"\\label\{([^}]+)\}", tex)
    assert len(labels) == len(set(labels)), "Duplicate labels"
    for ref in re.findall(r"\\ref\{([^}]+)\}", tex):
        assert ref in labels, ref
    requirements = re.findall(r"\\req\{([^}]+)\}", tex)
    assert len(requirements) == len(set(requirements)), "Duplicate requirement IDs"
    print(json.dumps({"examples": len(files), "requirements": len(requirements),
                      "tikz_figures": len(list((ROOT / "figures").glob("*.tex"))),
                      "result": "passed", "scope": "documentation fixtures only"}))


if __name__ == "__main__":
    main()
