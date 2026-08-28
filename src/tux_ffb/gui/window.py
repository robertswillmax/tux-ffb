"""Main window. Owns the device connection and refreshes the panels from it.

The device is the source of truth: every value shown is read back from the base,
never remembered locally. MOZA Cockpit does the opposite — it displays its own
profile state, which is why it can show a curve type the base does not have.
"""
from __future__ import annotations

import queue
import threading

import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

from ..core.commands import Table
from ..core.device import Device, UnsafeWrite
from ..core.discovery import find_port
from ..core.hid import AxisMonitor, ff_effects, find_node
from ..core.transport import Transport
from .panels.axes import AxesPanel
from .panels.forces import ForcesPanel
from .panels.overview import OverviewPanel
from .panels.profiles import ProfilesPanel


class MainWindow(Adw.ApplicationWindow):
    __gtype_name__ = "TuxFfbWindow"

    def __init__(self, app, port: str | None = None):
        super().__init__(application=app, title="tux-ffb", default_width=760, default_height=720)
        self.port = port
        self.table = Table.load()
        self.transport: Transport | None = None
        self.device: Device | None = None
        self._calibrating = False
        self.link_axes = True

        self.overview = OverviewPanel(self)
        self.axes = AxesPanel(self)
        self.forces = ForcesPanel(self)
        self.profiles = ProfilesPanel(self)

        # GtkStack, not AdwViewStack: AdwViewSwitcher always reserves an icon
        # slot and draws a placeholder when a page has none, so it cannot show
        # labels alone. GtkStackSwitcher is text-only by design.
        stack = Gtk.Stack()
        stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        for widget, name, title in ((self.overview, "overview", "Overview"),
                                    (self.axes, "axes", "Axes"),
                                    (self.forces, "forces", "Forces"),
                                    (self.profiles, "profiles", "Profiles")):
            stack.add_titled(widget, name, title)
        self.stack = stack

        header = Adw.HeaderBar()
        header.set_title_widget(Gtk.StackSwitcher(stack=stack))
        refresh = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Re-read from the device")
        refresh.connect("clicked", lambda _b: self.reload())
        header.pack_end(refresh)
        self.toast = Adw.ToastOverlay()
        self.toast.set_child(stack)

        view = Adw.ToolbarView()
        view.add_top_bar(header)
        view.set_content(self.toast)
        self.set_content(view)

        # Serial writes must never run on the GTK thread. A write is a write
        # plus a verifying read with sleeps; a curve drag fires seven of them,
        # which would freeze the UI for several seconds and read as a hang.
        self._writes: queue.Queue = queue.Queue()
        self._inflight = 0
        threading.Thread(target=self._write_worker, daemon=True).start()

        self.monitor = AxisMonitor()
        self.monitor.ensure_running()
        self.connect_device()
        GLib.timeout_add(50, self._tick)
        GLib.timeout_add_seconds(3, self._poll_connection)

    # -- connection --------------------------------------------------------
    def connect_device(self) -> bool:
        try:
            self.transport = Transport(self.port)
            self.port = self.transport.path
            self.device = Device(self.transport, self.table)
        except Exception:
            self.transport, self.device = None, None
        self.reload()
        return self.device is not None

    def _poll_connection(self):
        """The base is powered separately and is often simply off. Absence is a
        normal state, not an error.

        Re-discovers rather than checking a remembered path: the node number
        moves across a passthrough cycle, so a fixed path goes stale.
        """
        self.monitor.ensure_running()
        present = find_port() is not None
        if present and self.device is None:
            self.connect_device()
        elif not present and self.device is not None:
            self.transport = self.device = None
            self.reload()
        return True

    # -- data --------------------------------------------------------------
    def reload(self):
        values, info = {}, {"port": self.port or "—"}
        if self.device:
            try:
                readings = self.device.read_all()
                values = {n: [r.value for r in rs] for n, rs in readings.items()}
                info["calibration"] = self.device.calibration_percent()
            except Exception as exc:
                self._notify(f"read failed: {exc}")
                self.transport = self.device = None
        node = find_node()
        if node:
            bits = ff_effects(node)
            info["ff"] = f"kernel PID effects available ({bits})" if bits else "no force feedback reported"
        self.overview.refresh(values, info)
        self.axes.refresh(values)
        self.forces.refresh(values)

    def write_setting(self, name, value, index=0):
        """Queue a write. Returns immediately; the worker reports failures."""
        if not self.device:
            return
        self._inflight += 1
        self._writes.put((name, value, index))

    def _write_worker(self):
        while True:
            name, value, index = self._writes.get()
            # coalesce: if the same address is queued again, only the last
            # value matters. Dragging a slider should not write every step.
            pending = {(name, index): value}
            try:
                while True:
                    n2, v2, i2 = self._writes.get_nowait()
                    pending[(n2, i2)] = v2
            except queue.Empty:
                pass
            done = len(pending)
            for (n, i), v in pending.items():
                device = self.device
                if device is None:
                    continue
                try:
                    ok, note = device.write(n, v, index=i)
                except UnsafeWrite as exc:
                    GLib.idle_add(self._notify, str(exc))
                    continue
                except Exception as exc:
                    GLib.idle_add(self._notify, f"{n}: write failed — {exc}")
                    continue
                if not ok:
                    GLib.idle_add(self._notify, f"{n}: {note}")
            # coalescing can collapse several queued writes into one, so
            # decrement by what was actually pulled, not by one
            self._inflight = max(0, self._inflight - max(done, 1))

    def after_writes(self, callback, timeout_s: float = 30.0):
        """Run `callback` once the write queue has drained.

        Writes are queued to a worker and each verifies by read-back, so a
        preset of nine settings takes several seconds. Reloading on a fixed
        timer races that and shows stale values.
        """
        deadline = [timeout_s * 5]

        def poll():
            deadline[0] -= 1
            if deadline[0] <= 0:
                return False
            if self._inflight == 0 and self._writes.empty():
                callback()
                return False
            return True
        GLib.timeout_add(200, poll)

    def mirror_axis(self, axis, which, value):
        """Reflect a linked change into the other axis's controls."""
        self.axes.group(axis).set_endpoint(which, value)

    def run_calibration(self):
        if not self.device or self._calibrating:
            return
        self._calibrating = True

        def progress(pct):
            GLib.idle_add(self.overview.set_progress, pct)

        def done():
            self._calibrating = False
            self.overview.set_progress(None)
            self.reload()
            self._notify("calibration complete")

        import threading
        def run():
            try:
                self.device.calibrate_cogging(progress=progress)
            finally:
                GLib.idle_add(done)
        threading.Thread(target=run, daemon=True).start()

    def _tick(self):
        s = self.monitor.state
        x, y = s.fraction("x"), s.fraction("y")
        self.overview.set_position(x, y)
        self.axes.set_live(x, y)
        return True

    def _notify(self, text):
        self.toast.add_toast(Adw.Toast(title=text, timeout=4))
