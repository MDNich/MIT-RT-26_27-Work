import dataclasses
import json
from types import SimpleNamespace

import pytest

from rocket_gnc_monitor.__main__ import resolve_profile
from rocket_gnc_monitor.station_profile import StationProfile, load_profile, profile_for_layout


@pytest.mark.parametrize("station", ["base", "away1", "away2", "away3", "away4"])
@pytest.mark.parametrize("role", ["telemetry", "video"])
@pytest.mark.parametrize("vehicle", ["balius", "iris"])
def test_topology_follows_station_role_and_vehicle(station, role, vehicle):
    profile = StationProfile(station, role, vehicle)
    assert profile.layout == ("video" if role == "video" else "base" if station == "base" else "away")
    assert profile.channels == (("digital", "analog", "analog2") if vehicle == "iris" else ("digital", "analog"))
    expected_local = profile.channels if station == "base" else ("digital", "analog2" if vehicle == "iris" and station == "away4" else "analog")
    assert profile.local_channels == (("digital",) if station == "base" and role == "video" else expected_local)
    assert profile.station_label == ("Base station" if station == "base" else f"Away station {station[-1]}")
    assert profile.vehicle_label == vehicle.title()
    assert set(profile.channel_labels) == set(profile.channels)
    assert profile.channel_labels["analog"] == ("Sustainer Analog" if vehicle == "iris" else "Analog")
    assert set(profile.away_channels) == {"away1", "away2", "away3", "away4"}
    if vehicle == "iris":
        assert profile.away_channels["away4"] == ("digital", "analog2")
        assert all(profile.away_channels[site] == ("digital", "analog") for site in ("away1", "away2", "away3"))
        assert profile.telemetry_targets == (("Sustainer", "Booster") if station == "base" else
                                             ("Booster",) if station == "away4" else ("Sustainer",))
    else:
        assert profile.telemetry_targets == ("Balius",)


@pytest.mark.parametrize("field,value", [("station", "away5"), ("role", "pilot"), ("vehicle", "Balius"), ("vehicle", None)])
def test_profile_rejects_invalid_choices(field, value):
    with pytest.raises(ValueError):
        StationProfile(**{field: value})


def test_profile_is_immutable_and_round_trips_without_mission_changes(tmp_path):
    profile = StationProfile("away3", "video", "iris")
    mission = tmp_path / "mission.json"
    mission.write_text('{"name":"Flight A"}')
    profile.save(tmp_path)
    assert StationProfile.load(tmp_path) == profile
    assert json.loads((tmp_path / "station-profile.json").read_text()) == profile.to_dict()
    assert mission.read_text() == '{"name":"Flight A"}'
    assert not list(tmp_path.glob(".station-profile-*"))
    with pytest.raises(dataclasses.FrozenInstanceError):
        profile.station = "base"


@pytest.mark.parametrize("contents", ["broken json", "[]", '{"station":"away9"}', '{"role":false}', '{"extra":1}'])
def test_invalid_saved_profile_returns_safe_defaults(tmp_path, contents):
    (tmp_path / "station-profile.json").write_text(contents)
    assert load_profile(tmp_path) == StationProfile()


@pytest.mark.parametrize("layout,station,role", [("base", "base", "telemetry"), ("away", "away1", "telemetry"), ("video", "away1", "video")])
def test_legacy_layout_migration(tmp_path, layout, station, role):
    (tmp_path / "station-layout.json").write_text(json.dumps({"station": layout}))
    assert load_profile(tmp_path) == StationProfile(station, role)
    assert profile_for_layout(layout, StationProfile(vehicle="iris")) == StationProfile(station, role, "iris")


def test_cli_explicit_profile_fields_override_legacy_layout_and_saved_defaults(tmp_path):
    StationProfile("away4", "video", "iris").save(tmp_path)
    args = SimpleNamespace(station="away", site="base", role="video", vehicle=None)
    assert resolve_profile(args, tmp_path) == StationProfile("base", "video", "iris")
    args = SimpleNamespace(station=None, site=None, role=None, vehicle=None)
    assert resolve_profile(args, tmp_path) == StationProfile("away4", "video", "iris")
