"""Three interchangeable launch-location entry forms with offline conversion."""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QComboBox,
    QStackedWidget,
    QDoubleSpinBox,
    QLineEdit,
    QLabel,
)
from openlocationcode import openlocationcode as olc
from .location import Location, coordinates, decode_mgrs, decode_plus_code, encode_mgrs, encode_plus_code


class LaunchLocation(QWidget):
    def __init__(self, mission, parent=None):
        super().__init__(parent)
        self._location = coordinates(mission.latitude, mission.longitude)
        self._editing = False
        self._filling = True
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.format = QComboBox()
        for title, key in [("Latitude / longitude", "latlon"), ("MGRS", "mgrs"), ("Plus Code", "pluscode")]:
            self.format.addItem(title, key)
        self.format.setAccessibleName("Launch location coordinate format")
        root.addWidget(self.format)
        self.pages = QStackedWidget()
        root.addWidget(self.pages)
        page = QWidget()
        form = QFormLayout(page)
        self.latitude = self.number(-90, 90, "Launch latitude in degrees")
        self.longitude = self.number(-180, 180, "Launch longitude in degrees")
        form.addRow("Latitude (°)", self.latitude)
        form.addRow("Longitude (°)", self.longitude)
        self.pages.addWidget(page)
        page = QWidget()
        form = QFormLayout(page)
        self.mgrs = QLineEdit()
        self.mgrs.setPlaceholderText("e.g. 19T CG 27554 91778")
        self.mgrs.setAccessibleName("Launch MGRS coordinate")
        self.mgrs.setMaxLength(80)
        form.addRow("MGRS", self.mgrs)
        self.pages.addWidget(page)
        page = QWidget()
        form = QFormLayout(page)
        self.plus_code = QLineEdit()
        self.plus_code.setPlaceholderText("e.g. 87JC9W64+4C")
        self.plus_code.setAccessibleName("Launch Plus Code")
        self.plus_code.setMaxLength(80)
        form.addRow("Plus Code", self.plus_code)
        self.reference = QWidget()
        ref_form = QFormLayout(self.reference)
        ref_form.setContentsMargins(0, 0, 0, 0)
        self.reference_lat = QLineEdit(str(mission.latitude) if mission.site_configured else "")
        self.reference_lon = QLineEdit(str(mission.longitude) if mission.site_configured else "")
        self.reference_lat.setPlaceholderText("Nearby latitude, decimal degrees")
        self.reference_lon.setPlaceholderText("Nearby longitude, decimal degrees")
        ref_form.addRow("Nearby latitude (°)", self.reference_lat)
        ref_form.addRow("Nearby longitude (°)", self.reference_lon)
        form.addRow(self.reference)
        help_text = QLabel("Full codes work directly. A short code needs a nearby reference location.")
        help_text.setWordWrap(True)
        form.addRow(help_text)
        self.pages.addWidget(page)
        self.preview = QLabel()
        self.preview.setWordWrap(True)
        self.preview.setAccessibleName("Resolved launch latitude and longitude")
        root.addWidget(self.preview)
        for field in (self.latitude, self.longitude):
            field.valueChanged.connect(self.edited)
        for field in (self.mgrs, self.plus_code, self.reference_lat, self.reference_lon):
            field.textChanged.connect(self.edited)
        self.format.currentIndexChanged.connect(self.change_format)
        self.format.setCurrentIndex(max(0, self.format.findData(mission.launch_location_format)))
        self.change_format()
        if mission.launch_location_code and self.format.currentData() != "latlon":
            # Canonical saved latitude/longitude is authoritative; code is entry provenance.
            field = self.mgrs if self.format.currentData() == "mgrs" else self.plus_code
            self._filling = True
            field.setText(mission.launch_location_code)
            self._location = Location(mission.latitude, mission.longitude, mission.launch_location_code)
            self._filling = False
        self.update_preview()

    def number(self, low, high, name):
        field = QDoubleSpinBox()
        field.setDecimals(7)
        field.setRange(low, high)
        field.setAccessibleName(name)
        return field

    def change_format(self):
        self._filling = True
        self.pages.setCurrentIndex(self.format.currentIndex())
        lat, lon = self._location.latitude, self._location.longitude
        self.latitude.setValue(lat)
        self.longitude.setValue(lon)
        kind = self.format.currentData()
        code = (
            encode_mgrs(lat, lon)
            if kind == "mgrs"
            else encode_plus_code(lat, lon)
            if kind == "pluscode"
            else ""
        )
        if kind == "mgrs":
            self.mgrs.setText(code)
        elif kind == "pluscode":
            self.plus_code.setText(code)
        self._location = Location(lat, lon, code)
        self._editing = False
        self._filling = False
        self.update_preview()

    def edited(self):
        if not self._filling:
            self._editing = True
            self.update_preview()

    def value(self):
        if not self._editing:
            return self._location
        kind = self.format.currentData()
        if kind == "latlon":
            return coordinates(self.latitude.value(), self.longitude.value())
        if kind == "mgrs":
            return decode_mgrs(self.mgrs.text())
        reference = None
        if olc.isShort(self.plus_code.text().strip().upper()):
            try:
                reference = (float(self.reference_lat.text()), float(self.reference_lon.text()))
            except ValueError as exc:
                raise ValueError(
                    "Enter a nearby reference latitude and longitude for this short Plus Code."
                ) from exc
        return decode_plus_code(self.plus_code.text(), reference)

    def update_preview(self):
        self.reference.setVisible(olc.isShort(self.plus_code.text().strip().upper()))
        try:
            value = self.value()
        except ValueError as exc:
            self.preview.setText(str(exc))
            return
        self._location = value
        self.preview.setText(f"Launch site: {value.latitude:.7f}°, {value.longitude:.7f}°\n{value.note}")
