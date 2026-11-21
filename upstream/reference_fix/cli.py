"""Command-line entry point for farolito."""

import argparse
import sys
import tomllib


def load_config(path: str) -> dict:
    with open(path, "rb") as fh:
        return tomllib.load(fh)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="farolito")
    parser.add_argument("--config", default="farolito.toml")
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
    except FileNotFoundError:
        print(f"farolito: config file not found: {args.config}", file=sys.stderr)
        return 2
    name = config.get("name", "world")
    print(f"Hello, {name}! The lamp is on.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
