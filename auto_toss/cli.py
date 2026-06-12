import argparse
import json
import sys
from typing import Callable, TextIO

from auto_toss.client import TossClient
from auto_toss.config import Config, ConfigError
from auto_toss.errors import TossApiError
from auto_toss.orders import (
    LiveTradingNotEnabled,
    OrderRequest,
    OrderValidationError,
    assert_live_order_allowed,
    build_order_payload,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="auto-toss")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prices = subparsers.add_parser("prices", help="Fetch current prices for symbols")
    prices.add_argument("symbols", nargs="+")

    stocks = subparsers.add_parser("stocks", help="Fetch stock metadata for symbols")
    stocks.add_argument("symbols", nargs="+")

    subparsers.add_parser("accounts", help="Fetch Toss Securities accounts")

    holdings = subparsers.add_parser("holdings", help="Fetch account holdings")
    holdings.add_argument("--account", required=True)
    holdings.add_argument("--symbol")

    preview_order = subparsers.add_parser(
        "preview-order",
        help="Build an order payload without submitting",
    )
    _add_order_arguments(preview_order)

    place_order = subparsers.add_parser(
        "place-order",
        help="Submit an order when live trading is enabled",
    )
    place_order.add_argument("--live", action="store_true")
    place_order.add_argument("--account", required=True)
    _add_order_arguments(place_order)

    return parser


def main(
    argv: list[str] | None = None,
    *,
    config_factory: Callable[[], Config] = Config.from_env,
    client_factory: Callable[[Config], TossClient] = TossClient,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "preview-order":
            _print_json(build_order_payload(_order_request_from_args(args)), stdout)
            return 0

        config = config_factory()
        client = client_factory(config)

        if args.command == "prices":
            _print_json(client.get_prices(args.symbols), stdout)
        elif args.command == "stocks":
            _print_json(client.get_stocks(args.symbols), stdout)
        elif args.command == "accounts":
            _print_json(client.get_accounts(), stdout)
        elif args.command == "holdings":
            _print_json(
                client.get_holdings(account_seq=args.account, symbol=args.symbol),
                stdout,
            )
        elif args.command == "place-order":
            assert_live_order_allowed(
                config_live_enabled=config.live_trading_enabled,
                cli_live=args.live,
            )
            payload = build_order_payload(_order_request_from_args(args))
            _print_json(client.create_order(account_seq=args.account, payload=payload), stdout)
        else:
            parser.error(f"unknown command: {args.command}")
    except (ConfigError, LiveTradingNotEnabled, OrderValidationError, TossApiError) as exc:
        print(str(exc), file=stderr)
        return 2

    return 0


def _add_order_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--side", required=True, choices=["BUY", "SELL"])
    parser.add_argument("--order-type", required=True, choices=["LIMIT", "MARKET"])
    parser.add_argument("--quantity")
    parser.add_argument("--price")
    parser.add_argument("--order-amount")
    parser.add_argument("--time-in-force")
    parser.add_argument("--client-order-id")
    parser.add_argument("--confirm-high-value-order", action="store_true")


def _order_request_from_args(args: argparse.Namespace) -> OrderRequest:
    return OrderRequest(
        symbol=args.symbol,
        side=args.side,
        order_type=args.order_type,
        quantity=args.quantity,
        price=args.price,
        order_amount=args.order_amount,
        time_in_force=args.time_in_force,
        client_order_id=args.client_order_id,
        confirm_high_value_order=args.confirm_high_value_order,
    )


def _print_json(value: object, stdout: TextIO) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2), file=stdout)
