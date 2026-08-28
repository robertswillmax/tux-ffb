"""Named configuration profiles.

Plain YAML, one file per profile, in the user's config directory — shareable in
a forum post or a Discord thread, which is half the point.

A profile stores only settings whose effect is confirmed and which are writable.
Recording values we cannot write, or whose meaning we have not established, would
make a profile that silently fails to apply.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml


def profile_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")
    return Path(base) / "tux-ffb" / "profiles"


def _slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]+", "-", name.strip()).strip("-")
    return s or "profile"


@dataclass
class Profile:
    name: str
    values: dict[str, list] = field(default_factory=dict)
    notes: str = ""
    path: Path | None = None

    @classmethod
    def capture(cls, device, name: str, notes: str = "") -> "Profile":
        values = {}
        for setting_name, readings in device.read_all().items():
            s = device.table[setting_name]
            if not s.writable or not s.effect_verified:
                continue
            vals = [r.value for r in readings]
            if any(v is None for v in vals):
                continue
            values[setting_name] = vals
        return cls(name=name, values=values, notes=notes)

    @classmethod
    def load(cls, path: Path) -> "Profile":
        doc = yaml.safe_load(path.read_text()) or {}
        return cls(name=doc.get("name", path.stem), values=doc.get("values", {}),
                   notes=doc.get("notes", ""), path=path)

    def save(self, directory: Path | None = None) -> Path:
        directory = directory or profile_dir()
        directory.mkdir(parents=True, exist_ok=True)
        path = self.path or directory / f"{_slug(self.name)}.yaml"
        path.write_text(yaml.safe_dump(
            {"name": self.name, "notes": self.notes, "values": self.values},
            sort_keys=True, default_flow_style=False))
        self.path = path
        return path

    def diff(self, device) -> list[tuple[str, int, object, object]]:
        """(setting, index, current, wanted) for everything this profile changes."""
        out = []
        current = {n: [r.value for r in rs] for n, rs in device.read_all().items()}
        for name, wanted in self.values.items():
            have = current.get(name) or []
            for i, want in enumerate(wanted):
                if i < len(have) and have[i] != want:
                    out.append((name, i, have[i], want))
        return out

    def apply(self, device, only_changed: bool = True) -> list[tuple[str, int, str]]:
        """Write the profile. Returns whatever failed, empty on success."""
        failures = []
        targets = (self.diff(device) if only_changed else
                   [(n, i, None, v) for n, vs in self.values.items() for i, v in enumerate(vs)])
        for name, index, _have, want in targets:
            try:
                ok, note = device.write(name, want, index=index)
            except Exception as exc:
                failures.append((name, index, str(exc)))
                continue
            if not ok:
                failures.append((name, index, note))
        return failures


def list_profiles(directory: Path | None = None) -> list[Profile]:
    directory = directory or profile_dir()
    if not directory.is_dir():
        return []
    out = []
    for path in sorted(directory.glob("*.yaml")):
        try:
            out.append(Profile.load(path))
        except Exception:
            continue
    return out
