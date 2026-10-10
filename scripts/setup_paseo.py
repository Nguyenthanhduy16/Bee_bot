#!/usr/bin/env python3
"""Add dedicated demo ACP providers; preserve all existing Paseo providers/settings."""

from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import tempfile


def main():
    path = Path.home() / ".paseo" / "config.json"
    data = json.loads(path.read_text())
    providers = data.setdefault("agents", {}).setdefault("providers", {})
    hermes = shutil.which("hermes")
    if not hermes:
        raise SystemExit("Hermes executable not found.")
    for actor, label in (("an", "An"), ("binh", "Bình"), ("chi", "Chi"), ("dung", "Dũng"), ("ops", "Vận hành")):
        name = f"bee-bot-{actor}"
        value = {
            "extends": "acp", "label": f"Bee Bot — {label}",
            "description": f"Bee Bot local demo persona {actor}; Hermes tools, fake schedule and notifications",
            "command": [hermes, "-p", name, "acp"], "env": {},
        }
        if name in providers and providers[name] != value:
            raise SystemExit(f"Existing provider {name} differs; inspect before replacing.")
        providers[name] = value
    backup = path.with_name(f"config.json.before-bee-bot-{datetime.now():%Y%m%d-%H%M%S}.bak")
    shutil.copyfile(path, backup)
    backup.chmod(0o600)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    temporary.chmod(0o600)
    os.replace(temporary, path)
    print("Added 5 Bee Bot demo providers; existing providers preserved; backup stored privately beside config.")


if __name__ == "__main__":
    main()
