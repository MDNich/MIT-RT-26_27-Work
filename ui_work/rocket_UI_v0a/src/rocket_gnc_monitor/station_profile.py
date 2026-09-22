"""Validated startup choices for a station computer, independent of its mission."""

from dataclasses import asdict, dataclass, replace
import json
from pathlib import Path
from tempfile import NamedTemporaryFile


STATIONS = ("base", "away1", "away2", "away3", "away4")
ROLES = ("telemetry", "video")
VEHICLES = ("balius", "iris")
PROFILE_FILENAME = "station-profile.json"


@dataclass(frozen=True)
class StationProfile:
    station: str = "base"
    role: str = "telemetry"
    vehicle: str = "balius"

    def __post_init__(self):
        for name, choices in (("station", STATIONS), ("role", ROLES), ("vehicle", VEHICLES)):
            value = getattr(self, name)
            if not isinstance(value, str) or value not in choices:
                raise ValueError(f"Unknown {name}: {value!r}; choose {', '.join(choices)}")

    @property
    def layout(self):
        return "video" if self.role == "video" else "base" if self.station == "base" else "away"

    @property
    def channels(self):
        return ("digital", "analog", "analog2") if self.vehicle == "iris" else ("digital", "analog")

    @property
    def local_channels(self):
        if self.station == "base":
            return ("digital",) if self.role == "video" else self.channels
        return self.away_channels[self.station]

    @property
    def away_channels(self):
        return {
            station: ("digital", "analog2" if self.vehicle == "iris" and station == "away4" else "analog")
            for station in STATIONS if station != "base"
        }

    @property
    def telemetry_targets(self):
        if self.vehicle == "balius":
            return ("Balius",)
        if self.station == "base":
            return ("Sustainer", "Booster")
        return ("Booster",) if self.station == "away4" else ("Sustainer",)

    @property
    def station_label(self):
        return "Base station" if self.station == "base" else f"Away station {self.station[-1]}"

    @property
    def vehicle_label(self):
        return self.vehicle.title()

    @property
    def channel_labels(self):
        if self.vehicle == "iris":
            return {"digital": "Sustainer Digital", "analog": "Sustainer Analog", "analog2": "Booster Analog"}
        return {"digital": "Digital", "analog": "Analog"}

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict) or set(value) - {"station", "role", "vehicle"}:
            raise ValueError("A station profile must contain station, role and vehicle choices")
        return cls(**value)

    @classmethod
    def load(cls, data_dir):
        return load_profile(data_dir)

    def save(self, data_dir):
        save_profile(self, data_dir)


def profile_for_layout(layout, profile=None):
    """Translate the original three workspace flags without changing the vehicle."""
    profile = profile or StationProfile()
    values = {"base": ("base", "telemetry"), "away": ("away1", "telemetry"), "video": ("away1", "video")}
    if layout not in values:
        raise ValueError(f"Unknown station layout: {layout!r}")
    station, role = values[layout]
    return replace(profile, station=station, role=role)


def load_profile(data_dir):
    """Remember valid defaults; a missing or damaged preference never blocks setup."""
    directory = Path(data_dir)
    try:
        return StationProfile.from_dict(json.loads((directory / PROFILE_FILENAME).read_text(encoding="utf-8")))
    except FileNotFoundError:
        # Migrate the earlier workspace preference on the first wizard launch.
        try:
            old = json.loads((directory / "station-layout.json").read_text(encoding="utf-8"))
            return profile_for_layout(old["station"])
        except (OSError, ValueError, TypeError, KeyError):
            return StationProfile()
    except (OSError, ValueError, TypeError):
        return StationProfile()


def save_profile(profile, data_dir):
    if not isinstance(profile, StationProfile):
        raise TypeError("Expected a StationProfile")
    directory = Path(data_dir)
    directory.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory, prefix=".station-profile-", delete=False) as output:
            temporary = Path(output.name)
            output.write(json.dumps(profile.to_dict(), indent=2) + "\n")
        temporary.replace(directory / PROFILE_FILENAME)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
