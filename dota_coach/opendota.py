import httpx

BASE = "https://api.opendota.com/api"


class OpenDotaError(Exception):
    """Message is safe to show to Discord users."""


class OpenDota:
    def __init__(self, api_key=None):
        self._params = {"api_key": api_key} if api_key else {}
        self._http = httpx.AsyncClient(base_url=BASE, timeout=20)
        self._heroes = None
        self._items = None

    async def _req(self, method, path, **params):
        try:
            r = await self._http.request(method, path, params={**self._params, **params})
        except httpx.HTTPError:
            raise OpenDotaError("OpenDota unreachable, try again shortly.")
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

    async def hero_names(self):
        """{hero_id: npc name}; plus localized lookup via hero_localized()."""
        if self._heroes is None:
            self._heroes = await self._req("GET", "/heroes")
        return {h["id"]: h["name"] for h in self._heroes}

    async def hero_id_by_name(self, text):
        await self.hero_names()
        text = text.lower().strip()
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
