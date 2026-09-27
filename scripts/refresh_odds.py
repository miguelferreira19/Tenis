"""One bounded odds refresh for manual or scheduled local execution."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from tennis_quant.db import init_db
from tennis_quant.live_odds import ingest_current_odds


def main():
    parser = argparse.ArgumentParser(description="Atualizar fixtures/odds ATP e WTA")
    parser.add_argument("--region", choices=("eu", "uk", "us", "au"), default="eu")
    parser.add_argument("--max-sports", type=int, default=12,
                        help="Limite de competições ativas por execução (1–30)")
    args = parser.parse_args()
    init_db()
    print(json.dumps(ingest_current_odds(region=args.region, max_sports=args.max_sports), indent=2))


if __name__ == "__main__":
    main()
