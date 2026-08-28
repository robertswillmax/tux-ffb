"""Response-curve editor.

An axis is ONE object: a curve whose left and right nodes move horizontally and
whose points move vertically. That is not a stylistic choice — it is what the
hardware does (docs/03-device-model.md):

  left node x   = deadzone           right node x  = input saturation
  point y       = output value       (the curve's last y is the output range)

Cockpit presents these as a curve plus two unrelated sliders, which is why a user
can drag the endpoints inward and be surprised that a non-monotonic curve stays
non-monotonic. Here they are visibly the same object, and the editor says so when
the curve folds back on itself.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GObject, Gtk  # noqa: E402

HANDLE = 7.0


class CurveEditor(Gtk.DrawingArea):
    __gtype_name__ = "TuxFfbCurveEditor"

    __gsignals__ = {
        # emitted on release, never during drag: EEPROM has a write budget and
        # the link is 115200 baud
        "curve-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self):
        super().__init__()
        self.points: list[int] = [20, 40, 60, 80, 100]   # output values, slots 2..6
        self.deadzone = 2
        self.saturation = 100
        self.live: float | None = None                    # 0..1 input position
        self._drag: tuple[str, int] | None = None
        self._dirty = False

        self.set_content_height(260)
        self.set_hexpand(True)
        self.set_draw_func(self._draw)

        drag = Gtk.GestureDrag()
        drag.connect("drag-begin", self._begin)
        drag.connect("drag-update", self._update)
        drag.connect("drag-end", self._end)
        self.add_controller(drag)

    # -- geometry ----------------------------------------------------------
    def _plot(self):
        w, h = self.get_width(), self.get_height()
        m = 26.0
        return m, m, max(w - 2 * m, 1.0), max(h - 2 * m, 1.0)

    def _values(self) -> list[int]:
        """All six node output values.

        The curve has SIX nodes, not five. The first is pinned at output 0 and
        sits at the deadzone position — it is slot 1, which reads 0 on the
        device. `self.points` holds only the five editable ones (slots 2..6).
        Drawing without the zero node produces a cliff at the deadzone edge
        instead of a flat run followed by a steeper ramp.
        """
        return [0] + self.points

    def _node_xy(self, i: int) -> tuple[float, float]:
        """Node i (0..5) in widget coordinates. Nodes are evenly spaced across
        the span between the two movable endpoints, so shrinking that span makes
        the ramp steeper — the remaining travel still has to reach 100%."""
        px, py, pw, ph = self._plot()
        vals = self._values()
        frac = i / (len(vals) - 1)
        x_in = self.deadzone + (self.saturation - self.deadzone) * frac
        return px + pw * x_in / 100.0, py + ph * (1.0 - vals[i] / 100.0)

    # -- interaction -------------------------------------------------------
    def _hit(self, x: float, y: float) -> tuple[str, int] | None:
        for i in range(len(self._values())):
            nx, ny = self._node_xy(i)
            if abs(x - nx) <= HANDLE * 2 and abs(y - ny) <= HANDLE * 2:
                return ("node", i)
        return None

    def _begin(self, gesture, sx, sy):
        self._drag = self._hit(sx, sy)
        self._start = (sx, sy)

    def _update(self, gesture, dx, dy):
        if not self._drag:
            return
        kind, i = self._drag
        px, py, pw, ph = self._plot()
        x, y = self._start[0] + dx, self._start[1] + dy
        last = len(self._values()) - 1
        # node 0 is the pinned zero point: it moves horizontally (the deadzone)
        # and never vertically. Its output is 0 by definition.
        if i > 0:
            self.points[i - 1] = max(0, min(100, round((1.0 - (y - py) / ph) * 100)))
        # only the endpoints move horizontally — matches the hardware, where
        # interior x positions are fixed
        if i == 0:
            self.deadzone = max(0, min(self.saturation - 1, round((x - px) / pw * 100)))
        elif i == last:
            self.saturation = max(self.deadzone + 1, min(100, round((x - px) / pw * 100)))
        self._dirty = True
        self.queue_draw()

    def _end(self, gesture, dx, dy):
        self._drag = None
        if self._dirty:
            self._dirty = False
            self.emit("curve-changed")

    # -- state -------------------------------------------------------------
    def set_curve(self, points, deadzone, saturation):
        self.points = list(points)
        self.deadzone, self.saturation = deadzone, saturation
        self.queue_draw()

    def set_live(self, fraction: float | None):
        self.live = fraction
        self.queue_draw()

    @property
    def monotonic(self) -> bool:
        return all(b >= a for a, b in zip(self.points, self.points[1:]))

    # -- drawing -----------------------------------------------------------
    def _draw(self, area, cr, width, height):
        # A DrawingArea is handed an uninitialised surface. Without painting a
        # background first, stale content shows through as speckle.
        bg = self.get_style_context().lookup_color("view_bg_color")
        if bg[0]:
            Gdk.cairo_set_source_rgba(cr, bg[1])
            cr.paint()
        px, py, pw, ph = self._plot()
        style = self.get_style_context()
        fg = style.get_color()
        dim = Gdk.RGBA(); dim.red, dim.green, dim.blue, dim.alpha = fg.red, fg.green, fg.blue, 0.16

        cr.set_line_width(1.0)
        Gdk.cairo_set_source_rgba(cr, dim)
        for i in range(5):
            gx = px + pw * i / 4.0
            gy = py + ph * i / 4.0
            cr.move_to(gx, py); cr.line_to(gx, py + ph)
            cr.move_to(px, gy); cr.line_to(px + pw, gy)
        cr.stroke()

        # dead and saturated regions, shaded so they read as part of the curve
        shade = Gdk.RGBA(); shade.red, shade.green, shade.blue, shade.alpha = fg.red, fg.green, fg.blue, 0.07
        Gdk.cairo_set_source_rgba(cr, shade)
        cr.rectangle(px, py, pw * self.deadzone / 100.0, ph)
        cr.rectangle(px + pw * self.saturation / 100.0, py,
                     pw * (100 - self.saturation) / 100.0, ph)
        cr.fill()

        # live input position
        if self.live is not None:
            live = Gdk.RGBA(); live.red, live.green, live.blue, live.alpha = 0.20, 0.65, 0.95, 0.85
            Gdk.cairo_set_source_rgba(cr, live)
            lx = px + pw * max(0.0, min(1.0, self.live))
            cr.set_line_width(2.0)
            cr.move_to(lx, py); cr.line_to(lx, py + ph); cr.stroke()

        # the curve: flat through the deadzone, rising, then flat when saturated
        accent = Gdk.RGBA()
        accent.red, accent.green, accent.blue, accent.alpha = (
            (0.95, 0.45, 0.30, 1.0) if not self.monotonic else (0.25, 0.72, 0.45, 1.0))
        Gdk.cairo_set_source_rgba(cr, accent)
        cr.set_line_width(2.5)
        # flat at zero through the dead band, then the ramp, then flat at the
        # last output value once saturated
        cr.move_to(px, py + ph)
        for i in range(len(self._values())):
            cr.line_to(*self._node_xy(i))
        cr.line_to(px + pw, py + ph * (1.0 - self.points[-1] / 100.0))
        cr.stroke()

        last = len(self._values()) - 1
        for i in range(len(self._values())):
            nx, ny = self._node_xy(i)
            endpoint = i in (0, last)
            cr.arc(nx, ny, HANDLE if endpoint else HANDLE - 1.5, 0, 6.2832)
            cr.fill() if endpoint else cr.stroke()
