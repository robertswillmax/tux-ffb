"""tux-ffb GUI entry point."""
from __future__ import annotations
import sys
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")
from gi.repository import Adw  # noqa: E402

from .window import MainWindow


class Application(Adw.Application):
    def __init__(self):
        super().__init__(application_id="io.github.tux_ffb.TuxFfb")

    def do_activate(self):
        win = self.props.active_window or MainWindow(self)
        win.present()


def main(argv=None) -> int:
    return Application().run(argv if argv is not None else sys.argv)


if __name__ == "__main__":
    sys.exit(main())
