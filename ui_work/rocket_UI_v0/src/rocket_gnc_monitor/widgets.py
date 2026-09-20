"""Native, software-rendered instruments; no browser or OpenGL dependency."""

from __future__ import annotations
import math
import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF, QRegion
from PySide6.QtWidgets import QWidget

COLORS = dict(
    bg="#0b111a",
    panel="#121d2a",
    raised="#1a293a",
    line="#2a3b4f",
    text="#e8eff7",
    muted="#98abc0",
    accent="#79d4c8",
    gold="#e5b76d",
    violet="#ba9aef",
    red="#ef9294",
)
DARK_COLORS = dict(COLORS)
LIGHT_COLORS = dict(
    bg="#edf2f5",
    panel="#ffffff",
    raised="#e1eaf0",
    line="#b9c9d4",
    text="#152b3c",
    muted="#486174",
    accent="#157d70",
    gold="#986019",
    violet="#7650a5",
    red="#b43840",
)

STYLE = """
QWidget { background: #0b111a; color: #e8eff7; font-family: 'Arial'; font-size: 13px; }
QMainWindow { background: #0b111a; }
QFrame#card, QGroupBox { background: #121d2a; border: 1px solid #2a3b4f; border-radius: 9px; }
QFrame#card QLabel, QFrame#card QWidget#transparent { background: transparent; }
QLabel#eyebrow { color: #79d4c8; font-size: 11px; letter-spacing: 2px; }
QLabel#heading { font-size: 25px; font-weight: 600; }
QLabel#muted { color: #98abc0; }
QLabel#metric { font-size: 28px; font-weight: 500; }
QLabel#section { font-size: 16px; font-weight: 600; }
QPushButton { background: #1a293a; border: 1px solid #34485e; border-radius: 5px; padding: 7px 12px; }
QPushButton:hover { background: #23374b; border-color: #79d4c8; }
QPushButton:pressed { background: #34485e; }
QPushButton:disabled { color: #617287; border-color: #263344; }
QPushButton#primary { background: #79d4c8; color: #091715; border-color: #79d4c8; font-weight: 600; }
QPushButton#primary:disabled { background: #1a293a; color: #617287; border-color: #263344; }
QPushButton#danger { color: #ef9294; }
QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox, QDateTimeEdit { background: #172333; border: 1px solid #34485e; border-radius: 5px; padding: 6px; selection-background-color: #2f716e; }
QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled { color: #617287; border-color: #263344; }
QComboBox QAbstractItemView { background: #172333; selection-background-color: #2f716e; }
QListWidget#navigation { background: #0e1722; border: none; padding: 8px; outline: none; }
QListWidget#navigation::item { padding: 13px 9px; margin-bottom: 5px; border-radius: 6px; }
QListWidget#navigation::item:selected { background: #213c42; color: #9ceddf; }
QListWidget#navigation::item:hover { background: #1a293a; }
QTableWidget, QPlainTextEdit, QListWidget { background: #121d2a; border: 1px solid #2a3b4f; gridline-color: #243348; selection-background-color: #264b55; }
QHeaderView::section { background: #1a293a; color: #aabfd2; padding: 7px; border: none; }
QTableWidget::item { padding: 5px; }
QSlider::groove:horizontal { height: 5px; background: #34485e; border-radius: 2px; }
QSlider::handle:horizontal { background: #79d4c8; width: 14px; margin: -5px 0; border-radius: 7px; }
QCheckBox { spacing: 7px; }
QScrollArea { border: none; }
QScrollBar:vertical { background: #0b111a; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #34485e; min-height: 30px; border-radius: 5px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QToolTip { background: #203447; color: #e8eff7; border: 1px solid #52657a; padding: 7px; }
QStatusBar { background: #121d2a; color: #98abc0; }
QSplitter::handle { background: #0b111a; }
"""


class AttitudeView(QWidget):
    def __init__(self):
        super().__init__()
        self.angles = None
        self.setMinimumSize(190, 170)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(8, 8, -8, -8)
        painter.setBrush(QColor(COLORS["panel"]))
        painter.setPen(QColor(COLORS["line"]))
        painter.drawRoundedRect(rect, 8, 8)
        center = rect.center()
        radius = min(rect.width(), rect.height()) * 0.38
        painter.translate(center)
        if self.angles:
            painter.rotate(-self.angles[0])
        painter.setBrush(QColor("#284963"))
        painter.drawEllipse(QPointF(), radius, radius)
        painter.setClipRegion(
            QRegion(int(-radius), int(-radius), int(radius * 2), int(radius * 2), QRegion.RegionType.Ellipse)
        )
        offset = min(radius, max(-radius, (self.angles[1] if self.angles else 0) * radius / 45))
        painter.fillRect(QRectF(-radius, offset, radius * 2, radius * 2), QColor("#614d3d"))
        painter.setPen(QPen(QColor("#dceaf5"), 1.5))
        painter.drawLine(QPointF(-radius, offset), QPointF(radius, offset))
        for step in [-30, -20, -10, 10, 20, 30]:
            y = offset + step * radius / 45
            painter.drawLine(QPointF(-18, y), QPointF(18, y))
        painter.setClipping(False)
        painter.resetTransform()
        painter.setPen(QPen(QColor(COLORS["accent"]), 3))
        painter.drawLine(QPointF(center.x() - 48, center.y()), QPointF(center.x() - 12, center.y()))
        painter.drawLine(QPointF(center.x() + 12, center.y()), QPointF(center.x() + 48, center.y()))
        painter.drawEllipse(center, 4, 4)
        if self.angles is None:
            painter.setPen(QColor(COLORS["text"]))
            painter.drawText(
                rect, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter, "ATTITUDE UNAVAILABLE"
            )


class MountView(QWidget):
    """The photo-informed model shares real attachment transforms across camera views."""

    def __init__(self):
        super().__init__()
        self.azimuth, self.elevation = 32.0, 12.0
        self.camera = "Perspective"
        self.camera_yaw, self.camera_pitch = 72.0, 20.0
        self.zoom = 1.0
        self.drag_position = None
        self.setMinimumSize(350, 360)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip(
            "Drag to orbit the camera. Scroll to zoom. Double-click to reset the view. Viewing does not move the antenna."
        )
        self.setAccessibleName("Interactive antenna mount preview; drag to orbit; no measured pose")

    def set_camera(self, name):
        self.camera_yaw, self.camera_pitch = {
            "Perspective": (72.0, 20.0),
            "Front": (0.0, 0.0),
            "Side": (90.0, 0.0),
            "Top": (0.0, 90.0),
        }[name]
        self.camera, self.zoom = name, 1.0
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()

    def mouseMoveEvent(self, event):
        if self.drag_position is not None:
            delta = event.position() - self.drag_position
            self.drag_position = event.position()
            self.camera_yaw = (self.camera_yaw - delta.x() * 0.45) % 360
            self.camera_pitch = (self.camera_pitch + delta.y() * 0.45) % 360
            self.camera = "Orbit"
            self.update()
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.set_camera("Perspective")
            event.accept()

    def wheelEvent(self, event):
        self.zoom = min(2.5, max(0.65, self.zoom * 1.12 ** (event.angleDelta().y() / 120)))
        self.update()
        event.accept()

    def set_pose(self, azimuth, elevation):
        if (self.azimuth, self.elevation) != (azimuth, elevation):
            self.azimuth, self.elevation = azimuth, elevation
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(COLORS["panel"]))
        az, el = math.radians(self.azimuth), math.radians(self.elevation)
        rotation = np.array([[math.cos(az), 0, math.sin(az)], [0, 1, 0], [-math.sin(az), 0, math.cos(az)]])
        tilt = np.array([[1, 0, 0], [0, math.cos(el), math.sin(el)], [0, -math.sin(el), math.cos(el)]])

        def identity(v):
            return np.asarray(v, dtype=float)

        def turn(v):
            return rotation @ np.asarray(v)

        def carrier(v):
            return rotation @ tilt @ np.asarray(v) + np.array([0, 3.28, 0])

        def avenger(v):
            return carrier(np.asarray(v) + [-1.03, 0, 0.16])

        center = np.array([0, 2.1, 0.63])
        yaw, pitch = math.radians(self.camera_yaw), math.radians(self.camera_pitch)
        eye = center + 12 * np.array(
            [math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)]
        )
        unit = lambda a: a / max(np.linalg.norm(a), 1e-10)
        forward = unit(center - eye)
        # Analytic camera basis stays defined at top/bottom views and through a full orbit.
        right = np.array([math.cos(yaw), 0, -math.sin(yaw)])
        up = np.cross(right, forward)
        faces = []
        palette = {
            "timber": "#b6ab80",
            "edge": "#87794f",
            "frame": "#84988f",
            "metal": "#b7c5ca",
            "grid": "#d1dce0",
            "dark": "#303c4b",
            "cap": "#202a35",
            "gold": "#b19c62",
        }

        def face(vertices, material):
            vertices = np.asarray(vertices)
            normal = unit(np.cross(vertices[1] - vertices[0], vertices[2] - vertices[0]))
            shade = 0.56 + 0.44 * abs(np.dot(normal, unit(np.array([-2, 5, 4]))))
            color = QColor(palette[material])
            color.setRedF(color.redF() * shade)
            color.setGreenF(color.greenF() * shade)
            color.setBlueF(color.blueF() * shade)
            faces.append((float(np.dot(vertices.mean(axis=0) - eye, forward)), vertices, color))

        def box(c, s, material, transform=identity):
            vertices = [
                transform(np.asarray(c) + np.asarray(v) * np.asarray(s) / 2)
                for v in [
                    (-1, -1, -1),
                    (1, -1, -1),
                    (1, 1, -1),
                    (-1, 1, -1),
                    (-1, -1, 1),
                    (1, -1, 1),
                    (1, 1, 1),
                    (-1, 1, 1),
                ]
            ]
            for ids in [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (3, 2, 6, 7), (0, 3, 7, 4), (1, 5, 6, 2)]:
                face([vertices[i] for i in ids], material)

        def rod(a, b, radius, material, transform=identity, segments=5):
            a, b = np.asarray(a), np.asarray(b)
            direction = unit(b - a)
            v = unit(np.cross(direction, [1, 0, 0] if abs(direction[1]) > 0.9 else [0, 1, 0]))
            vv = np.cross(direction, v)
            ends = [
                [
                    transform(
                        point
                        + radius
                        * (
                            math.cos(i * 2 * math.pi / segments) * v
                            + math.sin(i * 2 * math.pi / segments) * vv
                        )
                    )
                    for i in range(segments)
                ]
                for point in [a, b]
            ]
            face(ends[0], material)
            face(ends[1][::-1], material)
            for i in range(segments):
                j = (i + 1) % segments
                face([ends[0][i], ends[0][j], ends[1][j], ends[1][i]], material)

        for x in (-1, 1):
            for z in (-1, 1):
                foot = [1.22 * x, 0.34, 1.08 * z]
                rod([foot[0], 0, foot[2]], foot, 0.035, "cap")
                box(foot, [0.30, 0.095, 0.24], "timber")
                rod(foot, [0.43 * x, 2.34, 0.35 * z], 0.12, "timber", segments=4)
        box([0, 2.35, 0], [1.45, 0.085, 1.20], "edge")
        rod([0, 2.40, 0], [0, 2.47, 0], 0.40, "cap", segments=18)
        box([0, 2.49, 0], [0.96, 0.065, 0.91], "frame", turn)
        for x in (-0.40, 0.40):
            box([x, 2.96, 0], [0.04, 0.88, 0.55], "frame", turn)
        rod([-0.49, 3.28, 0], [0.49, 3.28, 0], 0.105, "metal", turn, 10)
        # Shared beam and antenna axes pass through the support bearings (y=0, z=0).
        box([0, 0, 0], [2.65, 0.10, 0.10], "metal", carrier)
        for x in (-0.40, 0.40):
            rod([x - 0.025, 3.28, 0], [x + 0.025, 3.28, 0], 0.16, "cap", turn, 16)
            rod([x - 0.035, 3.28, 0], [x + 0.035, 3.28, 0], 0.10, "metal", turn, 12)
            rod([x, 0, 0], [x, 0, 0.36], 0.035, "metal", carrier)
        grid = lambda x, y: [x - 0.03, y, 0.27 + 0.18 * (x / 0.59) ** 2 + 0.12 * (y / 0.56) ** 2]
        for x in np.linspace(-0.59, 0.59, 19):
            for y in np.linspace(-0.56, 0.56, 6)[:-1]:
                rod(grid(x, y), grid(x, y + 1.12 / 5), 0.009, "grid", carrier, 3)
        for y in (-0.56, 0, 0.56):
            for x in np.linspace(-0.59, 0.59, 9)[:-1]:
                rod(grid(x, y), grid(x + 1.18 / 8, y), 0.012, "grid", carrier, 3)
        rod([-0.03, -0.40, 0.28], [-0.03, 0.02, 1.04], 0.03, "dark", carrier)
        box([1.03, 0, 0], [0.18, 0.14, 0.24], "dark", carrier)
        rod([1.03, 0, -0.35], [1.03, 0, 3.55], 0.025, "metal", carrier, 4)
        for k in range(21):
            z, half = -0.12 + k * 0.17, 0.34 - k * 0.003
            rod([1.03 - half, 0, z], [1.03 + half, 0, z], 0.01, "metal", carrier, 3)
            rod([1.03, -half * 0.74, z], [1.03, half * 0.74, z], 0.009, "metal", carrier, 3)
        rings = [
            [
                avenger([radius * math.cos(i * math.pi / 3), radius * math.sin(i * math.pi / 3), z])
                for i in range(6)
            ]
            for z, radius in [(-0.12, 0.285), (-0.075, 0.285), (0.96, 0.185), (1.42, 0.13)]
        ]
        face(rings[0], "cap")
        face(rings[-1], "cap")
        for a, b in zip(rings, rings[1:]):
            for i in range(6):
                j = (i + 1) % 6
                face([a[i], a[j], b[j], b[i]], "dark")
        box([-1.03, 0, 0.03], [0.18, 0.14, 0.24], "metal", carrier)
        rod([0, 0.15, -0.125], [0, 0.15, -0.285], 0.035, "gold", avenger)
        all_points = np.vstack(
            [vertices for _, vertices, _ in faces]
            + [np.array([[x, 0, z] for x in [-2.5, 2.5] for z in [-2.5, 2.5]])]
        )
        flat = np.column_stack(((all_points - center) @ right, (all_points - center) @ up))
        low, high = flat.min(axis=0), flat.max(axis=0)
        scale = self.zoom * min(
            (self.width() - 40) / (high[0] - low[0]), (self.height() - 70) / (high[1] - low[1])
        )
        middle = (low + high) / 2

        def project(v):
            v = np.asarray(v) - center
            return QPointF(
                self.width() / 2 + (v @ right - middle[0]) * scale,
                self.height() / 2 - (v @ up - middle[1]) * scale,
            )

        p.setPen(QPen(QColor(COLORS["line"]), 0.6))
        for t in np.arange(-2.5, 2.6, 0.5):
            p.drawLine(project([t, 0, -2.5]), project([t, 0, 2.5]))
            p.drawLine(project([-2.5, 0, t]), project([2.5, 0, t]))
        for _, vertices, color in sorted(faces, key=lambda f: -f[0]):
            p.setPen(QPen(color, 0.4))
            p.setBrush(color)
            p.drawPolygon(QPolygonF([project(v) for v in vertices]))
        p.setPen(QPen(QColor(COLORS["accent"]), 1.4, Qt.PenStyle.DashLine))
        p.drawLine(project(carrier([0, 0, 1.03])), project(carrier([0, 0, 2.68])))
        p.setPen(QColor(COLORS["muted"]))
        p.setFont(QFont("Arial", 10))
        for name, x, z in [("N", 0, 2.27), ("E", 2.27, 0), ("S", 0, -2.27), ("W", -2.27, 0)]:
            point = project([x, 0, z])
            p.drawText(point, name)
        p.drawText(
            QRectF(8, self.height() - 24, self.width() - 16, 20),
            Qt.AlignmentFlag.AlignCenter,
            "DRAG TO ORBIT · SCROLL TO ZOOM · DOUBLE-CLICK TO RESET",
        )
