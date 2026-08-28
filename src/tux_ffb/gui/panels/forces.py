"""Force-feedback settings.

Every control commits on release, not while dragging: EEPROM has a finite write
budget and the config link is 115200 baud. Settings whose effect has not been
observed on hardware are labelled, because storing a value and changing behaviour
are separate claims (docs/07-safety.md).
"""
from __future__ import annotations
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

# (setting, title, subtitle)
MASTERS = [
    ("ffb-intensity",    "Overall intensity", "Multiplier over every effect"),
    ("max-torque-limit", "Maximum torque",    "Ceiling, as a percent"),
    ("spring",           "Spring",            "Centring, scales with displacement"),
    ("damper",           "Damper",            "Resistance, scales with speed"),
    ("friction",         "Friction",          "Constant drag at any speed"),
    ("inertia",          "Inertia",           "Resists changes in motion"),
]
CENTERING = [
    ("centering-strength", "Assist strength", "Force of the assist"),
    ("centering-range",    "Assist range",    "Width of the assisted band; capped at 50"),
]


class ForcesPanel(Adw.PreferencesPage):
    __gtype_name__ = "TuxFfbForcesPanel"

    def __init__(self, window):
        super().__init__()
        self.window = window
        self._rows: dict[str, Adw.SpinRow] = {}
        self._loading = False

        pg = Adw.PreferencesGroup(title="Presets")
        for key, preset in self.window.table.presets.items():
            row = Adw.ActionRow(title=preset.get("title", key),
                                subtitle=preset.get("description", ""))
            btn = Gtk.Button(label="Apply")
            btn.set_valign(Gtk.Align.CENTER)
            btn.connect("clicked", self._apply_preset, key)
            row.add_suffix(btn)
            pg.add(row)
        self.add(pg)

        g = Adw.PreferencesGroup(title="Force feedback")
        for name, title, sub in MASTERS:
            g.add(self._row(name, title, sub))
        self.add(g)

        g2 = Adw.PreferencesGroup(
            title="Adaptive centring",
            description="Drives the stick to true centre, where spring force alone cannot.")
        self.acc_enable = Adw.SwitchRow(title="Enabled")
        self.acc_enable.connect("notify::active", self._acc_toggled)
        g2.add(self.acc_enable)
        self._acc_rows = []
        for name, title, sub in CENTERING:
            row = self._row(name, title, sub)
            self._acc_rows.append(row)
            g2.add(row)
        self.add(g2)

    def _apply_preset(self, _btn, key):
        preset = self.window.table.presets[key]
        for name, values in preset["values"].items():
            for i, v in enumerate(values):
                self.window.write_setting(name, v, index=i)
        self.window._notify(f"applying {preset.get('title', key)}")
        self.window.after_writes(self.window.reload)

    def _acc_toggled(self, row, _p):
        active = row.get_active()
        for r in self._acc_rows:
            r.set_sensitive(active and self.window.device is not None)
        if not self._loading:
            self.window.write_setting("adaptive-centering", int(active))

    def _row(self, name, title, subtitle):
        setting = self.window.table.settings.get(name)
        if setting is not None and not setting.effect_verified:
            subtitle += "  ·  unverified"
        row = Adw.SpinRow(title=title, subtitle=subtitle,
                          adjustment=Gtk.Adjustment(lower=0, upper=100, step_increment=1,
                                                    page_increment=10))
        row.connect("notify::value", self._changed, name)
        self._rows[name] = row
        return row

    def _changed(self, row, _pspec, name):
        if self._loading:
            return
        self.window.write_setting(name, int(row.get_value()))

    def refresh(self, values: dict[str, list]):
        self._loading = True
        connected = self.window.device is not None
        for name, row in self._rows.items():
            vals = values.get(name) or []
            if vals and vals[0] is not None:
                row.set_value(vals[0])
            row.set_sensitive(connected)
        acc = (values.get("adaptive-centering") or [None])[0]
        if acc is not None:
            self.acc_enable.set_active(bool(acc))
        self.acc_enable.set_sensitive(connected)
        # strength and range do nothing while the assist is off; greying them
        # out says so, rather than letting someone tune an inactive control
        for r in self._acc_rows:
            r.set_sensitive(connected and bool(acc))
        self._loading = False
