"""Device overview: what is connected, how it is behaving, and what it needs."""
from __future__ import annotations
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from ..widgets.axisview import AxisView

# The base stores a catalogue id (0-33) but only uses it to pick one of four
# decode modes, and the mode is what governs whether buttons work. We can name
# three catalogue entries out of thirty-four, so offering all of them would be
# false precision. Offer the four modes instead, each by a grip that uses it.
#
#   mode 0: ids 0-15, 20-31   mode 1: id 32   mode 2: ids 16-19   mode 3: id 33
GRIP_MODES = [
    (0, 0, "MH16"),
    (1, 32, "WW-16"),
    (2, 17, "VIRPIL grips"),
    (3, 33, "Generic"),
]
MODE_OF = {**{i: 0 for i in list(range(16)) + list(range(20, 32))},
           **{i: 2 for i in range(16, 20)}, 32: 1, 33: 3}


# id 133. Stored values are telemetry=0, directinput=1, integrated=2 - NOT the
# order Cockpit lists them in. DirectInput is offered first because that is what
# DCS uses and the base does not default to it. Telemetry is listed because the
# base supports it, but tux-ffb provides no telemetry source.
FFB_MODES = [(1, "DirectInput"), (2, "Integrated"), (0, "Telemetry")]


def ffb_mode_index(value: int) -> int:
    for i, (v, _label) in enumerate(FFB_MODES):
        if v == value:
            return i
    return 0


def mode_index(grip_id: int) -> int:
    """Row in GRIP_MODES for a stored catalogue id."""
    mode = MODE_OF.get(grip_id)
    for i, (m, _id, _label) in enumerate(GRIP_MODES):
        if m == mode:
            return i
    return 0


class OverviewPanel(Adw.PreferencesPage):
    __gtype_name__ = "TuxFfbOverviewPanel"

    def __init__(self, window):
        super().__init__()
        self.window = window
        self._loading = False

        g = Adw.PreferencesGroup(title="Device")
        self.row_state = Adw.ActionRow(title="Connection", subtitle="—")
        self.row_grip = Adw.ComboRow(
            title="Grip",
            subtitle="If buttons do not work, try another",
            model=Gtk.StringList.new([label for _m, _i, label in GRIP_MODES]))
        self.row_grip.connect("notify::selected", self._grip_changed)
        self.row_mode = Adw.ComboRow(
            title="Base mode",
            subtitle="Switching modes clears the force-feedback settings",
            model=Gtk.StringList.new(["Force feedback", "Force sensing"]))
        self.row_mode.connect("notify::selected", self._mode_changed)
        self.row_ffbmode = Adw.ComboRow(
            title="Force feedback mode",
            subtitle="DirectInput for DCS; telemetry unsupported here",
            model=Gtk.StringList.new([label for _v, label in FFB_MODES]))
        self.row_ffbmode.connect("notify::selected", self._ffbmode_changed)
        self.row_ff = Adw.ActionRow(title="Force feedback", subtitle="—")
        for r in (self.row_state, self.row_mode, self.row_ffbmode,
                  self.row_grip, self.row_ff):
            g.add(r)
        self.add(g)

        g2 = Adw.PreferencesGroup(title="Position",
                                  description="After the base's curve, deadzone and saturation")
        self.axisview = AxisView()
        self.axisview.set_margin_top(8); self.axisview.set_margin_bottom(8)
        frame = Gtk.Frame(); frame.set_child(self.axisview); frame.add_css_class("view")
        g2.add(frame)
        self.add(g2)

        g3 = Adw.PreferencesGroup(title="Cogging calibration")
        self.row_cal = Adw.ActionRow(title="Status", subtitle="—")
        self.btn_cal = Gtk.Button(label="Run calibration")
        self.btn_cal.add_css_class("suggested-action")
        self.btn_cal.set_valign(Gtk.Align.CENTER)
        self.btn_cal.connect("clicked", self._calibrate)
        self.row_cal.add_suffix(self.btn_cal)
        g3.add(self.row_cal)
        self.progress = Gtk.ProgressBar(show_text=True, visible=False)
        g3.add(self.progress)
        self.add(g3)

    def _ffbmode_changed(self, row, _p):
        if self._loading:
            return
        self.window.write_setting("ffb-mode", FFB_MODES[row.get_selected()][0])

    def _mode_changed(self, row, _p):
        if self._loading:
            return
        self.window.write_setting("base-mode", row.get_selected())

    def _grip_changed(self, row, _p):
        if self._loading:
            return
        # write a catalogue id that selects the chosen decode mode
        self.window.write_setting("grip-type", GRIP_MODES[row.get_selected()][1])

    def _calibrate(self, _btn):
        dlg = Adw.AlertDialog(
            heading="Run cogging calibration?",
            body="Drives the motor for about 53 seconds. Leave the stick untouched.")
        dlg.add_response("cancel", "Cancel")
        dlg.add_response("run", "Run calibration")
        dlg.set_response_appearance("run", Adw.ResponseAppearance.DESTRUCTIVE)
        dlg.connect("response", lambda d, r: r == "run" and self.window.run_calibration())
        dlg.present(self.window)

    def refresh(self, values, info):
        connected = self.window.device is not None
        self.row_state.set_subtitle(
            f"MOZA AB9 on {info.get('port')}" if connected
            else "No base found. Power it on and it will be picked up.")
        grip = (values.get("grip-type") or [None])[0]
        self._loading = True
        fm = (values.get("ffb-mode") or [None])[0]
        if fm is not None:
            self.row_ffbmode.set_selected(ffb_mode_index(fm))
        self.row_ffbmode.set_sensitive(connected)
        mode = (values.get("base-mode") or [None])[0]
        if mode in (0, 1):
            self.row_mode.set_selected(mode)
        self.row_mode.set_sensitive(connected)
        if grip is not None and 0 <= grip < 34:
            self.row_grip.set_selected(mode_index(grip))
        self.row_grip.set_sensitive(connected)
        self._loading = False
        self.row_ff.set_subtitle(info.get("ff") or "—")
        pct = info.get("calibration")
        if pct is None:
            self.row_cal.set_subtitle("unknown")
        elif pct >= 100:
            self.row_cal.set_subtitle("calibrated")
        else:
            self.row_cal.set_subtitle(f"incomplete — reads {pct}%")
        self.btn_cal.set_sensitive(connected)

    def set_position(self, x, y):
        self.axisview.set_position(x, y)

    def set_progress(self, pct: int | None):
        if pct is None:
            self.progress.set_visible(False)
            self.btn_cal.set_sensitive(True)
            return
        self.progress.set_visible(True)
        self.progress.set_fraction(pct / 100.0)
        self.progress.set_text(f"calibrating… {pct}%")
        self.btn_cal.set_sensitive(False)
