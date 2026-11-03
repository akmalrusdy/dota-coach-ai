"""Build the local patch-notes file from Valve's public patch feed.
  python -m dota_coach.patch 7.41f   ->  data/patch_notes.md
"""
import asyncio
import re
import sys
from pathlib import Path

import httpx

FEED = "https://www.dota2.com/datafeed/patchnotes"
OUT = Path(__file__).resolve().parent.parent / "data" / "patch_notes.md"


def _notes(lst):
    clean = (re.sub(r"<[^>]+>", " ", n.get("note", "")).strip() for n in lst or [])
    return [c for c in clean if c]


def render(patch, hero_labels, ability_names):
    """Markdown: '## <Hero>' sections of bullet lines. ability_names: {ability_id: display name}."""
    lines = [f"# Patch {patch['patch_name']}", ""]
    for h in patch.get("heroes", []):
        body = []
        for a in h.get("abilities", []):
            name = ability_names.get(a["ability_id"], f"ability {a['ability_id']}")
            body += [f"- {name}: {n}" for n in _notes(a.get("ability_notes"))]
        for k, v in h.items():
            if k.endswith("_notes") and isinstance(v, list):
                body += [f"- {k[:-6].replace('_', ' ').title()}: {n}" for n in _notes(v)]
        if body:
            lines += [f"## {hero_labels.get(h['hero_id'], h['hero_id'])}", *body, ""]
    items = [f"- {ability_names.get(i['ability_id'], i['ability_id'])}: {n}"
             for i in patch.get("items", []) for n in _notes(i.get("ability_notes"))]
    if items:
        lines += ["## Items", *items, ""]
    return "\n".join(lines)


async def main(version):
    async with httpx.AsyncClient(timeout=30) as c:
        patch = (await c.get(FEED, params={"version": version, "language": "english"})).json()
        if not patch.get("success"):
            raise SystemExit(f"No patch notes for {version}")
        heroes = (await c.get("https://api.opendota.com/api/heroes")).json()
        ids = (await c.get("https://api.opendota.com/api/constants/ability_ids")).json()
        abil = (await c.get("https://api.opendota.com/api/constants/abilities")).json()
    labels = {h["id"]: h["localized_name"] for h in heroes}
    # some keys are merged ids like "3060,1617"
    names = {int(i): abil.get(k, {}).get("dname") or k for ks, k in ids.items() for i in ks.split(",")}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(render(patch, labels, names))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
