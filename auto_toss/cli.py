import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="auto-toss")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("prices", help="Fetch current prices for symbols")
    subparsers.add_parser("stocks", help="Fetch stock metadata for symbols")
    subparsers.add_parser("accounts", help="Fetch Toss Securities accounts")
    subparsers.add_parser("holdings", help="Fetch account holdings")
    subparsers.add_parser("preview-order", help="Build an order payload without submitting")
    subparsers.add_parser("place-order", help="Submit an order when live trading is enabled")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(argv)
    return 0
