from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from tennis_quant.ingest import bootstrap
from tennis_quant.model import train_and_evaluate


def main():
    parser = argparse.ArgumentParser(description="Importar e avaliar Tennis Quant v0.1")
    parser.add_argument("--start", type=int, default=2015)
    parser.add_argument("--end", type=int)
    parser.add_argument("--skip-download", action="store_true")
    args = parser.parse_args()
    if not args.skip_download:
        files = bootstrap(args.start, args.end)
        print(f"Imported {len(files)} raw files / {sum(x['accepted'] for x in files)} rows")
    report = train_and_evaluate()
    print(json.dumps({"selected": report["selected_by_validation"],
        "splits": report["splits"], "test_oos": report[report["selected_by_validation"]]["test_oos"],
        "betting_backtest": report["betting_backtest"]}, indent=2))


if __name__ == "__main__":
    main()

