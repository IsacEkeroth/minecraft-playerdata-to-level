"""Command-line interface for the Minecraft playerdata migrator."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .migrate import MigrationError, migrate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Copy UUID playerdata root tags into level.dat's Data.Player compound."
    )
    parser.add_argument(
        "--playerdata", required=True, type=Path, help="UUID playerdata .dat file"
    )
    parser.add_argument(
        "--level", required=True, type=Path, help="source level.dat file"
    )
    parser.add_argument(
        "--output", required=True, type=Path, help="new output level.dat path"
    )
    parser.add_argument(
        "--force", action="store_true", help="overwrite an existing output file"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        migrate(args.playerdata, args.level, args.output, force=args.force)
    except MigrationError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"wrote migrated level.dat to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
