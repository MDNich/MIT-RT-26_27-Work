import sys
from types import SimpleNamespace

from PySide6.QtWidgets import QWizard

from rocket_gnc_monitor.station_profile import StationProfile
from rocket_gnc_monitor.startup_wizard import StartupWizard


def test_wizard_preserves_defaults_and_presents_three_required_pages(qtbot):
    profile = StationProfile("away4", "video", "iris")
    wizard = StartupWizard(profile)
    qtbot.addWidget(wizard)
    wizard.show()
    assert wizard.profile == profile
    assert len(wizard.pageIds()) == 3
    assert len(wizard.choices["station"]) == 5
    assert wizard.currentId() == 0
    assert wizard.button(QWizard.WizardButton.CancelButton).isVisible()
    wizard.next()
    assert wizard.currentId() == 1
    wizard.next()
    assert wizard.currentId() == 2
    assert wizard.button(QWizard.WizardButton.FinishButton).text() == "Open station"
    assert wizard.button(QWizard.WizardButton.CancelButton).isVisible()
    assert "Away station 4 · Video · Iris" in wizard.summary.text()
    assert "Local USB inputs: Sustainer Digital, Booster Analog." in wizard.summary.text()
    assert "Sustainer Analog" not in wizard.summary.text()


def test_wizard_selection_and_back_navigation_keep_station_identity(qtbot):
    wizard = StartupWizard()
    qtbot.addWidget(wizard)
    wizard.show()
    wizard.choices["station"]["away2"].setChecked(True)
    wizard.next()
    wizard.choices["role"]["video"].setChecked(True)
    wizard.next()
    wizard.choices["vehicle"]["iris"].setChecked(True)
    assert wizard.profile == StationProfile("away2", "video", "iris")
    wizard.back()
    wizard.back()
    assert wizard.choices["station"]["away2"].isChecked()
    wizard.choices["station"]["base"].setChecked(True)
    assert "Local USB inputs: Sustainer Digital." in wizard.summary.text()
    assert "connection pending" in wizard.summary.text()
    assert "Booster Analog" not in wizard.summary.text()


def test_iris_summary_distinguishes_sustainer_and_booster_telemetry(qtbot):
    wizard = StartupWizard(StationProfile("away1", "telemetry", "iris"))
    qtbot.addWidget(wizard)
    assert "Telemetry assignment: Sustainer." in wizard.summary.text()
    wizard.choices["station"]["away4"].setChecked(True)
    assert "Telemetry assignment: Booster." in wizard.summary.text()
    wizard.choices["station"]["base"].setChecked(True)
    assert "Telemetry assignment: Sustainer, Booster." in wizard.summary.text()
    wizard.choices["station"]["away3"].setChecked(True)
    wizard.choices["role"]["video"].setChecked(True)
    assert "Local USB inputs: Sustainer Digital, Sustainer Analog." in wizard.summary.text()


def test_cancel_startup_does_not_create_controller_or_save_profile(qapp, tmp_path, monkeypatch):
    from PySide6 import QtWidgets
    from rocket_gnc_monitor import __main__ as entry
    from rocket_gnc_monitor.controller import Controller

    def forbidden(*args, **kwargs):
        raise AssertionError("Cancelling setup must not construct a controller")

    monkeypatch.setattr(Controller, "__init__", forbidden)
    monkeypatch.setattr(StartupWizard, "exec", lambda self: self.DialogCode.Rejected)
    monkeypatch.setattr(sys, "argv", ["rocket-gnc-monitor", "--data-dir", str(tmp_path)])
    with monkeypatch.context() as patch:
        patch.setattr(QtWidgets, "QApplication", lambda *_: qapp)
        assert entry.main() == 0
    assert not (tmp_path / "station-profile.json").exists()


def test_accepted_startup_saves_choices_before_opening_station(qapp, tmp_path, monkeypatch):
    from PySide6 import QtWidgets
    from rocket_gnc_monitor import __main__ as entry, station_workspace

    selected = StationProfile("away2", "video", "iris")
    opened = []

    def choose(wizard):
        for key, value in selected.to_dict().items():
            wizard.choices[key][value].setChecked(True)
        return wizard.DialogCode.Accepted

    class Window:
        def __init__(self, data, *, profile, auto_place):
            assert StationProfile.load(data) == selected
            opened.append(profile)
            self.controller = SimpleNamespace(video_streams=dict.fromkeys(profile.local_channels))

        def show(self):
            pass

    monkeypatch.setattr(station_workspace, "StationWindow", Window)
    monkeypatch.setattr(StartupWizard, "exec", choose)
    monkeypatch.setattr(sys, "argv", ["rocket-gnc-monitor", "--data-dir", str(tmp_path)])
    monkeypatch.setattr(qapp, "exec", lambda: 0)
    with monkeypatch.context() as patch:
        patch.setattr(QtWidgets, "QApplication", lambda *_: qapp)
        assert entry.main() == 0
    assert opened == [selected]
