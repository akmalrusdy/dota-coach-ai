import asyncio
import time

import httpx

BASE = "https://api.opendota.com/api"
ALIASES = {
    "od": "outworld", "dp": "death prophet", "qop": "queen of pain", "sf": "shadow fiend",
    "ta": "templar assassin", "cm": "crystal maiden", "am": "anti-mage", "np": "nature's prophet",
    "tb": "terrorblade", "ss": "shadow shaman", "wk": "wraith king", "bs": "bloodseeker",
}


class OpenDotaError(Exception):
    """Message is safe to show to Discord users."""


class OpenDota:
    def __init__(self, api_key=None):
        self._params = {"api_key": api_key} if api_key else {}
        self._http = httpx.AsyncClient(base_url=BASE, timeout=20)
        self._heroes = None
        self._items = None
        self._stats = None
        self._last = 0.0

    async def _req(self, method, path, **params):
        for attempt in range(3):
            # ponytail: ~1 req/s keeps bursts under the free per-minute limit; not shared across processes
            await asyncio.sleep(max(0.0, 1.1 - (time.monotonic() - self._last)))
            self._last = time.monotonic()
            try:
                r = await self._http.request(method, path, params={**self._params, **params})
            except httpx.HTTPError:
                raise OpenDotaError("OpenDota unreachable, try again shortly.")
            if r.status_code != 429 and r.status_code < 500 or attempt == 2:
                break
            await asyncio.sleep(65 if r.status_code == 429 else 3)  # 429: per-minute window; 5xx: transient
        if r.status_code == 404:
            raise OpenDotaError("Not found on OpenDota (wrong id, or match data is private).")
        if r.status_code == 429:
            raise OpenDotaError("OpenDota rate limit hit. Wait a minute and retry.")
        if r.status_code >= 400:
            raise OpenDotaError(f"OpenDota error {r.status_code}.")
        return r.json()

    async def match(self, match_id):
        return await self._req("GET", f"/matches/{match_id}")

    async def request_parse(self, match_id):
        await self._req("POST", f"/request/{match_id}")

    async def recent_match_id(self, account_id):
        rows = await self._req("GET", f"/players/{account_id}/matches", limit=1)
        if not rows:
            raise OpenDotaError("No matches found. Enable 'Expose Public Match Data' in Dota settings.")
        return rows[0]["match_id"]

    async def recent_matches(self, account_id, limit=40, **filters):
        return await self._req("GET", f"/players/{account_id}/matches", limit=limit, **filters)

    async def hero_stats(self):
        """{hero_id: heroStats row}: per-rank-bracket picks/wins over the recent window."""
        if self._stats is None:
            self._stats = {h["id"]: h for h in await self._req("GET", "/heroStats")}
        return self._stats

    async def matchups(self, hero_id):
        """{enemy_hero_id: (games, wins)} for hero_id. Thin sample: shrink before use."""
        rows = await self._req("GET", f"/heroes/{hero_id}/matchups")
        return {r["hero_id"]: (r["games_played"], r["wins"]) for r in rows}

    async def player_heroes(self, account_id, **filters):
        """{hero_id: (games, wins)} from the player's own history."""
        rows = await self._req("GET", f"/players/{account_id}/heroes", **filters)
        return {int(r["hero_id"]): (r["games"], r["win"]) for r in rows}

    async def rank_tier(self, account_id):
        return (await self._req("GET", f"/players/{account_id}")).get("rank_tier")

    async def hero_labels(self):
        """{hero_id: display name}"""
        await self.hero_names()
        return {h["id"]: h["localized_name"] for h in self._heroes}

    async def hero_names(self):
        """{hero_id: npc name}; plus localized lookup via hero_localized()."""
        if self._heroes is None:
            self._heroes = await self._req("GET", "/heroes")
        return {h["id"]: h["name"] for h in self._heroes}

    async def hero_id_by_name(self, text):
        await self.hero_names()
        text = ALIASES.get(text.lower().strip(), text.lower().strip())
        for h in self._heroes:
            if text in (h["localized_name"].lower(), h["name"].removeprefix("npc_dota_hero_")):
                return h["id"]
        for h in self._heroes:
            if text in h["localized_name"].lower():
                return h["id"]
        return None

    async def items(self):
        """{item: {"cost", "components"}} from OpenDota constants."""
        if self._items is None:
            data = await self._req("GET", "/constants/items")
            self._items = {
                k: {"cost": v.get("cost") or 0, "components": v.get("components") or []}
                for k, v in data.items()
            }
        return self._items
