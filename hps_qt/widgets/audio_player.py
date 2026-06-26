"""
Embedded audio player widget using PySide6 QMediaPlayer.
Plays WAV files inline — no external app needed.
"""
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QSlider, QSizePolicy
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtCore import Qt, QUrl, QTimer


def _fmt(ms: int) -> str:
    s = ms // 1000
    return f"{s // 60}:{s % 60:02d}"


class AudioPlayer(QWidget):
    """
    Compact inline audio player.
    Call load(path) to load a WAV/MP3 file.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._player = QMediaPlayer(self)
        self._audio_out = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_out)
        self._audio_out.setVolume(1.0)

        # ── layout ──────────────────────────────────────────────────────
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        self._file_label = QLabel("No audio loaded")
        self._file_label.setStyleSheet("color:#a0a0a0; font-size:9pt;")
        self._file_label.setWordWrap(True)
        outer.addWidget(self._file_label)

        controls = QHBoxLayout()
        controls.setSpacing(6)

        self._play_btn = QPushButton("▶ Play")
        self._play_btn.setFixedWidth(80)
        self._play_btn.clicked.connect(self._toggle_play)
        self._play_btn.setEnabled(False)

        self._stop_btn = QPushButton("■ Stop")
        self._stop_btn.setFixedWidth(70)
        self._stop_btn.clicked.connect(self._stop)
        self._stop_btn.setEnabled(False)

        self._seek = QSlider(Qt.Horizontal)
        self._seek.setRange(0, 1000)
        self._seek.setValue(0)
        self._seek.sliderMoved.connect(self._on_seek)
        self._seek.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._time_label = QLabel("0:00 / 0:00")
        self._time_label.setFixedWidth(80)
        self._time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._time_label.setStyleSheet("color:#a0a0a0; font-size:9pt;")

        controls.addWidget(self._play_btn)
        controls.addWidget(self._stop_btn)
        controls.addWidget(self._seek)
        controls.addWidget(self._time_label)
        outer.addLayout(controls)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color:#888; font-size:8pt;")
        outer.addWidget(self._status_label)

        # ── signals ─────────────────────────────────────────────────────
        self._player.playbackStateChanged.connect(self._on_state_changed)
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.errorOccurred.connect(self._on_error)

        # Style
        self.setStyleSheet(
            "AudioPlayer { background:#1a1a1a; border:1px solid #444; "
            "border-radius:4px; padding:6px; }"
        )

    # ── public API ──────────────────────────────────────────────────────────

    def load(self, path):
        """Load a file path (str or Path). Accepts WAV, MP3, OGG."""
        path = Path(path)
        self._player.stop()
        if not path.exists():
            self._file_label.setText(f"File not found: {path.name}")
            self._play_btn.setEnabled(False)
            self._stop_btn.setEnabled(False)
            self._status_label.setText("⚠ file missing")
            return
        self._player.setSource(QUrl.fromLocalFile(str(path)))
        self._file_label.setText(f"🎧  {path.name}")
        self._play_btn.setEnabled(True)
        self._stop_btn.setEnabled(True)
        self._status_label.setText("Ready")
        self._seek.setValue(0)
        self._time_label.setText("0:00 / 0:00")

    def clear(self):
        self._player.stop()
        self._player.setSource(QUrl())
        self._file_label.setText("No audio loaded")
        self._play_btn.setEnabled(False)
        self._stop_btn.setEnabled(False)
        self._status_label.setText("")
        self._seek.setValue(0)
        self._time_label.setText("0:00 / 0:00")

    # ── slots ────────────────────────────────────────────────────────────────

    def _toggle_play(self):
        if self._player.playbackState() == QMediaPlayer.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def _stop(self):
        self._player.stop()

    def _on_seek(self, value):
        dur = self._player.duration()
        if dur > 0:
            self._player.setPosition(int(dur * value / 1000))

    def _on_state_changed(self, state):
        if state == QMediaPlayer.PlayingState:
            self._play_btn.setText("⏸ Pause")
            self._status_label.setText("Playing")
        elif state == QMediaPlayer.PausedState:
            self._play_btn.setText("▶ Play")
            self._status_label.setText("Paused")
        else:
            self._play_btn.setText("▶ Play")
            self._status_label.setText("Stopped")

    def _on_position_changed(self, pos):
        dur = self._player.duration()
        if dur > 0:
            self._seek.setValue(int(pos * 1000 / dur))
        self._time_label.setText(f"{_fmt(pos)} / {_fmt(dur)}")

    def _on_duration_changed(self, dur):
        self._time_label.setText(f"0:00 / {_fmt(dur)}")

    def _on_error(self, error, msg):
        self._status_label.setText(f"⚠ {msg}")
        self._play_btn.setEnabled(False)
