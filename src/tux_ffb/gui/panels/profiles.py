"""Saved configurations."""
from __future__ import annotations
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from ...core.profiles import Profile, list_profiles, profile_dir


class ProfilesPanel(Adw.PreferencesPage):
    __gtype_name__ = "TuxFfbProfilesPanel"

    def __init__(self, window):
        super().__init__()
        self.window = window

        g = Adw.PreferencesGroup(title="Save")
        self.entry = Adw.EntryRow(title="Name")
        save = Gtk.Button(label="Save current")
        save.set_valign(Gtk.Align.CENTER)
        save.add_css_class("suggested-action")
        save.connect("clicked", self._save)
        self.entry.add_suffix(save)
        g.add(self.entry)
        self.add(g)

        self.group = Adw.PreferencesGroup(title="Profiles", description=str(profile_dir()))
        self.add(self.group)
        self._rows: list[Adw.ActionRow] = []
        self.refresh()

    def _save(self, _b):
        name = self.entry.get_text().strip()
        if not name or not self.window.device:
            return
        try:
            p = Profile.capture(self.window.device, name)
            p.save()
        except Exception as exc:
            self.window._notify(f"save failed: {exc}")
            return
        self.entry.set_text("")
        self.window._notify(f"saved {len(p.values)} settings")
        self.refresh()

    def refresh(self, *_):
        for row in self._rows:
            self.group.remove(row)
        self._rows.clear()
        profiles = list_profiles()
        if not profiles:
            row = Adw.ActionRow(title="No profiles yet",
                                subtitle="Save the current configuration to create one")
            row.set_sensitive(False)
            self.group.add(row); self._rows.append(row)
            return
        for p in profiles:
            row = Adw.ActionRow(title=p.name, subtitle=p.notes or f"{len(p.values)} settings")
            apply = Gtk.Button(label="Apply")
            apply.set_valign(Gtk.Align.CENTER)
            apply.connect("clicked", self._apply, p)
            delete = Gtk.Button(icon_name="user-trash-symbolic")
            delete.set_valign(Gtk.Align.CENTER)
            delete.add_css_class("flat")
            delete.connect("clicked", self._delete, p)
            row.add_suffix(apply); row.add_suffix(delete)
            self.group.add(row); self._rows.append(row)

    def _delete(self, _b, profile):
        try:
            profile.path.unlink()
        except Exception as exc:
            self.window._notify(str(exc))
        self.refresh()

    def _apply(self, _b, profile):
        """Always show what will change before changing it."""
        device = self.window.device
        if not device:
            return
        try:
            changes = profile.diff(device)
        except Exception as exc:
            self.window._notify(f"could not read device: {exc}")
            return
        if not changes:
            self.window._notify("already matches")
            return
        lines = "\n".join(f"{n}[{i}]   {have} → {want}" for n, i, have, want in changes[:14])
        if len(changes) > 14:
            lines += f"\n… and {len(changes) - 14} more"
        dlg = Adw.AlertDialog(heading=f"Apply {profile.name}?",
                              body=f"{len(changes)} settings will change.\n\n{lines}")
        dlg.add_response("cancel", "Cancel")
        dlg.add_response("apply", "Apply")
        dlg.set_response_appearance("apply", Adw.ResponseAppearance.SUGGESTED)
        dlg.connect("response", self._confirmed, profile)
        dlg.present(self.window)

    def _confirmed(self, _dlg, response, profile):
        if response != "apply":
            return
        failures = profile.apply(self.window.device)
        self.window.reload()
        self.window._notify(f"{profile.name} applied" if not failures
                            else f"{len(failures)} setting(s) failed to apply")
