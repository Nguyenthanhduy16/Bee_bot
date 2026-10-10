#!/usr/bin/env python3
"""Configure dedicated Bee Bot profiles without changing the personal Hermes profile.

OAuth is resolved by Hermes from the root account; credentials are never copied.
"""

import argparse
from pathlib import Path
import shutil
import subprocess

import yaml


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hermes-home", type=Path, default=Path.home() / ".hermes")
    parser.add_argument("--state-dir", type=Path, default=None)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    state = (args.state_dir or root / ".bee-bot").resolve()
    source = yaml.safe_load((args.hermes_home / "config.yaml").read_text()) or {}
    model = source.get("model", {})
    if not isinstance(model, dict) or not model.get("provider") or not model.get("default"):
        raise SystemExit("Configure a Hermes model/provider before setting up Bee Bot profiles.")
    # Only model selection travels. Native tools, memory, credentials and channels do not.
    model_selection = {key: model[key] for key in ("provider", "default", "streaming") if key in model}
    skill_source = root / "examples" / "skills" / "bee-bot" / "SKILL.md"
    for actor in ("an", "binh", "chi", "dung", "ops"):
        name = f"bee-bot-{actor}"
        profile = args.hermes_home / "profiles" / name
        if not (profile / "config.yaml").exists():
            subprocess.run(["hermes", "profile", "create", name, "--no-alias", "--no-skills"], check=True)
        config = {
            "model": model_selection,
            "agent": {"max_turns": 12},
            "platform_toolsets": {"acp": ["skills", "bee_bot"], "cli": ["skills", "bee_bot"]},
            "mcp_servers": {
                "bee_bot": {
                    "command": str(root / ".venv" / "bin" / "python"),
                    "args": ["-m", "bee_bot.mcp_server"],
                    "timeout": 30,
                    "supports_parallel_tool_calls": False,
                    "env": {"BEE_BOT_ACTOR_ID": actor, "BEE_BOT_DB": str(state / "state.db"),
                            "BEE_BOT_SCHEDULE": str(state / "schedule.json")},
                }
            },
        }
        (profile / "config.yaml").write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False))
        (profile / "config.yaml").chmod(0o600)
        shutil.copyfile(root / "examples" / "SOUL.md", profile / "SOUL.md")
        skill_target = profile / "skills" / "bee-bot" / "SKILL.md"
        skill_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(skill_source, skill_target)
        print(f"Configured {name}: fixed demo actor {actor}, MCP only, no credential copies")


if __name__ == "__main__":
    main()
