"""Terminal review, no Discord. Examples:
  python -m dota_coach.cli 8123456789 --player 123456789
  python -m dota_coach.cli 8123456789 --player "Invoker" --no-llm
  python -m dota_coach.cli --last 123456789
  python -m dota_coach.cli --trend 123456789 [--n 10]
"""
import argparse
import asyncio
import json
import os

from dotenv import load_dotenv

from .db import DB
from .opendota import OpenDota, OpenDotaError
from .review import advise, build_draft, build_laneplan, build_trend, fetch_metrics, resolve_player, to_account_id


async def run(args):
    od = OpenDota(os.getenv("OPENDOTA_API_KEY"))
    db = DB()
    try:
        if args.laneplan:
            print(await build_laneplan(od, to_account_id(int(args.account)), args.laneplan, args.enemy or None, cache=db))
            return
        if args.draft:
            split = lambda t: [x.strip() for x in t.split(",") if x.strip()]
            print(await build_draft(od, to_account_id(int(args.account)), split(args.draft), split(args.pool) or None))
            return
        if args.trend:
            print(await build_trend(od, to_account_id(int(args.trend)), args.n, cache=db))
            return
        if args.last:
            account_id = to_account_id(int(args.last))
            match_id, hero_id = await od.recent_match_id(account_id), None
        else:
            match_id = args.match_id
            account_id, hero_id = await resolve_player(od, args.player)
        m, _ = await fetch_metrics(od, match_id, account_id, hero_id)
        print(f"== match {match_id} metrics ==")
        print(json.dumps(m, indent=2))
        if not args.no_llm:
            print("\n== advice ==")
            print(await advise(m))
    except OpenDotaError as e:
        raise SystemExit(str(e))


def main():
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("match_id", nargs="?", type=int)
    ap.add_argument("--player", help="account id or hero name")
    ap.add_argument("--last", metavar="ACCOUNT_ID", help="review this account's latest match")
    ap.add_argument("--trend", metavar="ACCOUNT_ID", help="trend over recent ranked mid matches")
    ap.add_argument("--draft", metavar="ENEMIES", help="comma separated enemy heroes; needs --account")
    ap.add_argument("--pool", default="", help="comma separated candidate heroes for --draft")
    ap.add_argument("--laneplan", metavar="HERO", help="your mid hero; needs --account; optional --enemy")
    ap.add_argument("--enemy", default="", help="enemy mid for --laneplan")
    ap.add_argument("--account", help="account id for --draft")
    ap.add_argument("--n", type=int, default=10, help="matches for --trend (max 20)")
    ap.add_argument("--no-llm", action="store_true", help="print metrics only")
    args = ap.parse_args()
    if (args.draft or args.laneplan) and not args.account:
        ap.error("--draft/--laneplan need --account")
    if not args.draft and not args.laneplan and not args.trend and not args.last and not (args.match_id and args.player):
        ap.error("give MATCH_ID and --player, --last ACCOUNT_ID, or --trend ACCOUNT_ID")
    args.n = max(1, min(args.n, 20))
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
