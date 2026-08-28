"""Axis shaping: one curve editor per axis, endpoints included.

Deliberately NOT a curve plus two sliders. The deadzone and input saturation are
the curve's own endpoints, and presenting them separately is what lets a user
drag the ends inward and wonder why a fold survives.
"""
from __future__ import annotations
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from ..widgets.curve import CurveEditor


class AxisGroup(Adw.PreferencesGroup):
    def __init__(self, window, axis: str, label: str):
        super().__init__(title=label)
        self.window, self.axis = window, axis
        self.editor = CurveEditor()
        self.editor.connect("curve-changed", self._commit)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.append(self.editor)
        self.readout = Gtk.Label(xalign=0.0)
        self.readout.add_css_class("dim-label")
        self.readout.add_css_class("caption")
        box.append(self.readout)
        frame = Gtk.Frame(); frame.set_child(box); frame.add_css_class("view")
        self.add(frame)

        # Numeric entry alongside the editor. Typing "2" beats dragging for a
        # value you already know; the editor is for shaping, not for precision.
        self.dz = Adw.SpinRow(
            title="Deadzone",
            subtitle="Travel at centre with no output",
            adjustment=Gtk.Adjustment(lower=0, upper=99, step_increment=1, page_increment=5))
        self.sat = Adw.SpinRow(
            title="Input saturation",
            subtitle="Travel at which output reaches maximum",
            adjustment=Gtk.Adjustment(lower=1, upper=100, step_increment=1, page_increment=5))
        self.dz.connect("notify::value", self._spin_changed, "deadzone")
        self.sat.connect("notify::value", self._spin_changed, "saturation")
        self.add(self.dz)
        self.add(self.sat)

        self.invert = Adw.SwitchRow(title="Invert", subtitle="Reverse direction")
        self.invert.connect("notify::active", self._invert_changed)
        self.add(self.invert)
        self._loading = False

    def _spin_changed(self, row, _p, which):
        if self._loading:
            return
        value = int(row.get_value())
        e = self.editor
        if which == "deadzone":
            e.deadzone = min(value, e.saturation - 1)
        else:
            e.saturation = max(value, e.deadzone + 1)
        e.queue_draw()
        self._describe()
        self.window.write_setting(f"{which}-{self.axis}", value)
        if self.window.link_axes:
            other = "y" if self.axis == "x" else "x"
            self.window.write_setting(f"{which}-{other}", value)
            self.window.mirror_axis(other, which, value)

    def set_endpoint(self, which, value):
        """Applied from the other axis when the X/Y link is on."""
        self._loading = True
        e = self.editor
        if which == "deadzone":
            e.deadzone = min(value, e.saturation - 1); self.dz.set_value(value)
        else:
            e.saturation = max(value, e.deadzone + 1); self.sat.set_value(value)
        e.queue_draw(); self._describe()
        self._loading = False

    def apply_linear(self):
        self.editor.points = [20, 40, 60, 80, 100]
        self.editor.queue_draw()
        for i, v in enumerate(self.editor.points):
            self.window.write_setting(f"curve-points-{self.axis}", v, index=i)
        self._describe()

    def _invert_changed(self, row, _p):
        if not self._loading:
            self.window.write_setting(f"invert-{self.axis}", int(row.get_active()))

    def _commit(self, editor):
        w = self.window
        self._loading = True
        self.dz.set_value(editor.deadzone)
        self.sat.set_value(editor.saturation)
        self._loading = False
        w.write_setting(f"deadzone-{self.axis}", editor.deadzone)
        w.write_setting(f"saturation-{self.axis}", editor.saturation)
        for i, value in enumerate(editor.points):
            w.write_setting(f"curve-points-{self.axis}", value, index=i)
        self._describe()

    def _describe(self):
        e = self.editor
        text = (f"deadzone {e.deadzone}%   ·   input saturation {e.saturation}%   ·   "
                f"points {e.points}")
        if not e.monotonic:
            text += "   ·   curve folds back — output falls as input rises"
        self.readout.set_text(text)

    def refresh(self, values):
        self._loading = True
        pts = [v for v in (values.get(f"curve-points-{self.axis}") or []) if v is not None]
        dz = (values.get(f"deadzone-{self.axis}") or [None])[0]
        sat = (values.get(f"saturation-{self.axis}") or [None])[0]
        if pts and dz is not None and sat is not None:
            self.editor.set_curve(pts, dz, sat)
            self.dz.set_value(dz)
            self.sat.set_value(sat)
        inv = (values.get(f"invert-{self.axis}") or [None])[0]
        if inv is not None:
            self.invert.set_active(bool(inv))
        self.set_sensitive(self.window.device is not None)
        self._describe()
        self._loading = False


class AxesPanel(Adw.PreferencesPage):
    __gtype_name__ = "TuxFfbAxesPanel"

    def __init__(self, window):
        super().__init__()
        self.window = window

        opts = Adw.PreferencesGroup(title="Options")
        self.link = Adw.SwitchRow(
            title="Link X and Y",
            subtitle="Apply endpoint changes to both axes")
        self.link.set_active(True)
        self.link.connect("notify::active",
                          lambda r, _p: setattr(window, "link_axes", r.get_active()))
        opts.add(self.link)

        row = Adw.ActionRow(title="Presets", subtitle="Applies to both axes")
        linear = Gtk.Button(label="Linear")
        linear.set_valign(Gtk.Align.CENTER)
        linear.connect("clicked", self._linear)
        row.add_suffix(linear)
        stock = Gtk.Button(label="MOZA defaults")
        stock.set_valign(Gtk.Align.CENTER)
        stock.connect("clicked", self._stock)
        row.add_suffix(stock)
        opts.add(row)
        self.add(opts)

        self.groups = [AxisGroup(window, "x", "Roll  ·  X axis"),
                       AxisGroup(window, "y", "Pitch  ·  Y axis")]
        for g in self.groups:
            self.add(g)

    def _linear(self, _b):
        for g in self.groups:
            g.apply_linear()

    def _stock(self, _b):
        """MOZA's shipped defaults, captured from a base with no profile loaded."""
        for g in self.groups:
            g.apply_linear()
            g.set_endpoint("deadzone", 2)
            g.set_endpoint("saturation", 100)
            self.window.write_setting(f"deadzone-{g.axis}", 2)
            self.window.write_setting(f"saturation-{g.axis}", 100)

    def group(self, axis):
        return next(g for g in self.groups if g.axis == axis)

    def refresh(self, values):
        for g in self.groups:
            g.refresh(values)

    def set_live(self, x: float, y: float):
        self.groups[0].editor.set_live(abs(x - 0.5) * 2)
        self.groups[1].editor.set_live(abs(y - 0.5) * 2)
