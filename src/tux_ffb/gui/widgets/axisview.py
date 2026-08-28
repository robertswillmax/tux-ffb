"""Live two-axis position, with the configured limits drawn around it."""
from __future__ import annotations
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk  # noqa: E402


class AxisView(Gtk.DrawingArea):
    __gtype_name__ = "TuxFfbAxisView"

    def __init__(self):
        super().__init__()
        self.x = self.y = 0.5
        self.set_content_width(150)
        self.set_content_height(150)
        self.set_draw_func(self._draw)

    def set_position(self, x: float, y: float):
        self.x, self.y = x, y
        self.queue_draw()

    def _draw(self, area, cr, width, height):
        bg = self.get_style_context().lookup_color("view_bg_color")
        if bg[0]:
            Gdk.cairo_set_source_rgba(cr, bg[1])
            cr.paint()
        fg = self.get_style_context().get_color()
        m = 8.0
        size = min(width, height) - 2 * m
        ox, oy = (width - size) / 2, (height - size) / 2
        faint = Gdk.RGBA(); faint.red, faint.green, faint.blue, faint.alpha = fg.red, fg.green, fg.blue, 0.18
        Gdk.cairo_set_source_rgba(cr, faint)
        cr.set_line_width(1.0)
        cr.rectangle(ox, oy, size, size)
        cr.move_to(ox + size / 2, oy); cr.line_to(ox + size / 2, oy + size)
        cr.move_to(ox, oy + size / 2); cr.line_to(ox + size, oy + size / 2)
        cr.stroke()
        dot = Gdk.RGBA(); dot.red, dot.green, dot.blue, dot.alpha = 0.20, 0.65, 0.95, 1.0
        Gdk.cairo_set_source_rgba(cr, dot)
        # ABS_Y increases aft, and cairo's y grows downward — so the raw
        # fraction already maps forward to the top. Inverting it here was wrong.
        cr.arc(ox + size * self.x, oy + size * self.y, 5.0, 0, 6.2832)
        cr.fill()
