"""Choose the launch-day computer assignment before opening any instruments."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QButtonGroup, QLabel, QRadioButton, QVBoxLayout, QWizard, QWizardPage

from .station_profile import StationProfile
from .widgets import STYLE


SETUP_STYLE = """
QWizard { background: #0b111a; }
QWizardPage { background: #0b111a; }
QRadioButton#setupChoice { background: #121d2a; border: 1px solid #2a3b4f;
    border-radius: 8px; padding: 13px 16px; spacing: 14px; font-size: 14px; }
QRadioButton#setupChoice:hover { border-color: #79d4c8; background: #1a293a; }
QRadioButton#setupChoice:checked { border-color: #79d4c8; background: #183a40; }
QRadioButton#setupChoice::indicator { width: 16px; height: 16px; border-radius: 8px;
    border: 1px solid #617287; background: #0b111a; }
QRadioButton#setupChoice::indicator:checked { background: #79d4c8; border-color: #79d4c8; }
QLabel#setupSummary { background: #121d2a; border: 1px solid #2a3b4f;
    border-radius: 8px; padding: 16px; color: #b9d3dd; }
"""


class StartupWizard(QWizard):
    def __init__(self, profile=None, parent=None):
        super().__init__(parent)
        profile = profile or StationProfile()
        self.setWindowTitle("Station setup · Rocket GNC Monitor")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage)
        self.setOption(QWizard.WizardOption.NoCancelButton, False)
        self.setOption(QWizard.WizardOption.NoCancelButtonOnLastPage, False)
        self.setButtonText(QWizard.WizardButton.NextButton, "Continue")
        self.setButtonText(QWizard.WizardButton.BackButton, "Back")
        self.setButtonText(QWizard.WizardButton.FinishButton, "Open station")
        self.button(QWizard.WizardButton.FinishButton).setObjectName("primary")
        self.resize(790, 660)
        self.setMinimumSize(680, 610)
        self.setStyleSheet(STYLE + SETUP_STYLE)
        self.choices = {}
        self.groups = {}
        self.add_choices(
            "station", "01 / STATION", "Where is this computer?",
            "Assign this computer to the base station or one of the four away stations.",
            [("base", "Base station", "Launch site · main ground station")]
            + [(f"away{i}", f"Away station {i}", "Remote ground station") for i in range(1, 5)],
            profile.station,
        )
        self.add_choices(
            "role", "02 / ROLE", "What will this computer display?",
            "Keep each station focused on its assigned task.",
            [
                ("telemetry", "Telemetry", "Rocket telemetry and antenna pointing"),
                ("video", "Video", "Camera reception, recording and playback in one dedicated window"),
            ],
            profile.role,
        )
        vehicle_page = self.add_choices(
            "vehicle", "03 / VEHICLE", "Which rocket is flying?",
            "Video and telemetry receivers are assigned for the station you selected.",
            [
                ("balius", "Balius", "Two video channels · Digital and Analog"),
                ("iris", "Iris", "Sustainer Digital + Sustainer Analog + Booster Analog"),
            ],
            profile.vehicle,
        )
        self.summary = QLabel()
        self.summary.setObjectName("setupSummary")
        self.summary.setTextFormat(Qt.TextFormat.PlainText)
        self.summary.setWordWrap(True)
        vehicle_page.layout().insertWidget(vehicle_page.layout().count() - 1, self.summary)
        self.currentIdChanged.connect(self.update_summary)
        for group in self.groups.values():
            group.buttonToggled.connect(lambda *_: self.update_summary())
        self.update_summary()

    def add_choices(self, key, step, title, description, choices, selected):
        page = QWizardPage()
        page.setTitle(title)
        page.setSubTitle(description)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 16, 20, 14)
        layout.setSpacing(10)
        eyebrow = QLabel(step)
        eyebrow.setObjectName("eyebrow")
        layout.addWidget(eyebrow)
        group = self.groups[key] = QButtonGroup(page)
        self.choices[key] = {}
        for value, name, detail in choices:
            control = QRadioButton(f"{name}\n{detail}")
            control.setObjectName("setupChoice")
            control.setAccessibleName(name)
            control.setCursor(Qt.CursorShape.PointingHandCursor)
            control.setChecked(value == selected)
            group.addButton(control)
            self.choices[key][value] = control
            layout.addWidget(control)
        layout.addStretch()
        self.addPage(page)
        return page

    @property
    def profile(self):
        return StationProfile(**{
            key: next(value for value, control in choices.items() if control.isChecked())
            for key, choices in self.choices.items()
        })

    def update_summary(self, *_):
        if not hasattr(self, "summary"):
            return
        profile = self.profile
        text = f"{profile.station_label} · {profile.role.title()} · {profile.vehicle_label}"
        if profile.role == "video":
            channels = ", ".join(profile.channel_labels[channel] for channel in profile.local_channels)
            text += f"\nLocal USB inputs: {channels}."
            if profile.station == "base":
                text += " Away-station feeds: connection pending."
        else:
            text += ("\nTwo displays · separate downlink and uplink boards."
                     if profile.station == "base" else
                     "\nOne display · downlink board and antenna control.")
            targets = ", ".join(target.title() for target in profile.telemetry_targets)
            text += f"\nTelemetry assignment: {targets}."
        text += "\nThese choices will be remembered for the next launch."
        self.summary.setText(text)
