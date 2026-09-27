from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from tennis_quant.db import init_db
from tennis_quant.odds import import_odds_csv


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Importar snapshots de odds com proveniência")
    parser.add_argument("csv", type=Path)
    parser.add_argument("--source", required=True, help="Nome ou URL da fonte")
    args = parser.parse_args()
    init_db()
    print(json.dumps(import_odds_csv(args.csv, args.source), indent=2))

