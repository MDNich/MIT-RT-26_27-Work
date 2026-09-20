"""Offline WGS84 launch-site entry using MGRS and Google Open Location Codes."""

from dataclasses import dataclass
import re
import mgrs
from openlocationcode import openlocationcode as olc
from .domain import finite


@dataclass(frozen=True)
class Location:
    latitude: float
    longitude: float
    code: str = ""
    note: str = "WGS84 latitude / longitude"


def coordinates(latitude, longitude):
    if not finite(latitude) or not -90 <= latitude <= 90:
        raise ValueError("Latitude must be between −90 and 90 degrees.")
    if not finite(longitude) or not -180 <= longitude <= 180:
        raise ValueError("Longitude must be between −180 and 180 degrees.")
    return Location(float(latitude), float(longitude))


def decode_mgrs(text):
    code = re.sub(r"\s+", "", text).upper()
    match = re.fullmatch(r"(?:\d{1,2}[C-HJ-NP-X]|[ABYZ])[A-HJ-NP-Z]{2}(\d{0,10})", code)
    if not match or len(match[1]) % 2:
        raise ValueError("Enter an MGRS grid reference with equally many easting and northing digits.")
    try:
        lat, lon = mgrs.MGRS().toLatLon(code)
    except mgrs.core.MGRSError as exc:
        raise ValueError("Invalid MGRS zone, grid square, or coordinates.") from exc
    coordinates(lat, lon)
    resolution = 10 ** (5 - len(match[1]) // 2)
    return Location(lat, lon, code, f"MGRS grid reference point · {resolution:,} m grid resolution")


def encode_mgrs(latitude, longitude):
    coordinates(latitude, longitude)
    return mgrs.MGRS().toMGRS(latitude, longitude, MGRSPrecision=5)


def decode_plus_code(text, reference=None):
    code = text.strip().upper()
    if olc.isShort(code):
        if reference is None:
            raise ValueError(
                "A short Plus Code needs a nearby reference latitude and longitude, or use its full code."
            )
        origin = coordinates(*reference)
        code = olc.recoverNearest(code, origin.latitude, origin.longitude)
    if not olc.isFull(code):
        raise ValueError("Enter a full Plus Code, such as 87JC9W64+4C. Short codes need a nearby reference.")
    area = olc.decode(code)
    return Location(area.latitudeCenter, area.longitudeCenter, code, "Plus Code area center · WGS84")


def encode_plus_code(latitude, longitude):
    coordinates(latitude, longitude)
    return olc.encode(latitude, longitude, codeLength=11)
