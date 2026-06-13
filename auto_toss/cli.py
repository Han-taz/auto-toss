import argparse
import json
import sys
import time
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
from auto_toss.paper import PaperBroker, PaperTradingError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="auto-toss")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prices = subparsers.add_parser("prices", help="Fetch current prices for symbols")
    prices.add_argument("symbols", nargs="+")

    watch_prices = subparsers.add_parser(
        "watch-prices",
        help="Fetch current prices repeatedly until interrupted",
    )
    watch_prices.add_argument("symbols", nargs="+")
    watch_prices.add_argument("--interval", type=_non_negative_float, default=5.0)
    watch_prices.add_argument("--iterations", type=_positive_int)

    stocks = subparsers.add_parser("stocks", help="Fetch stock metadata for symbols")
    stocks.add_argument("symbols", nargs="+")

    subparsers.add_parser("accounts", help="Fetch Toss Securities accounts")

    holdings = subparsers.add_parser("holdings", help="Fetch account holdings")
    holdings.add_argument("--account", required=True)
    holdings.add_argument("--symbol")

    paper_init = subparsers.add_parser(
        "paper-init",
        help="Initialize local paper trading state",
    )
    _add_paper_db_argument(paper_init)
    paper_init.add_argument("--reset", action="store_true")
    paper_init.add_argument("--krw-cash", default="10000000")
    paper_init.add_argument("--usd-cash", default="10000")

    paper_order = subparsers.add_parser(
        "paper-order",
        help="Execute a simulated local paper order",
    )
    _add_paper_db_argument(paper_order)
    paper_order.add_argument("--symbol", required=True)
    paper_order.add_argument("--side", required=True, choices=["BUY", "SELL"])
    paper_order.add_argument("--currency", required=True, choices=["KRW", "USD"])
    paper_order.add_argument("--quantity", required=True)
    paper_order.add_argument("--fill-price", required=True)
    paper_order.add_argument("--client-order-id")

    paper_portfolio = subparsers.add_parser(
        "paper-portfolio",
        help="Show local paper trading portfolio",
    )
    _add_paper_db_argument(paper_portfolio)
    paper_portfolio.add_argument("--mark-price", action="append", default=[])

    paper_ledger = subparsers.add_parser(
        "paper-ledger",
        help="List local paper trading fills",
    )
    _add_paper_db_argument(paper_ledger)
    paper_ledger.add_argument("--limit", type=_positive_int, default=50)

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
    paper_broker_factory: Callable[[str | None], PaperBroker] | None = None,
    sleep: Callable[[float], None] | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    sleep = sleep or time.sleep
    paper_broker_factory = paper_broker_factory or _build_paper_broker
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "preview-order":
            _print_json(build_order_payload(_order_request_from_args(args)), stdout)
            return 0

        if args.command == "paper-init":
            broker = paper_broker_factory(args.db_path)
            _print_json(
                broker.initialize(
                    reset=args.reset,
                    krw_cash=args.krw_cash,
                    usd_cash=args.usd_cash,
                ),
                stdout,
            )
            return 0

        if args.command == "paper-order":
            broker = paper_broker_factory(args.db_path)
            _print_json(
                broker.execute_order(
                    symbol=args.symbol,
                    side=args.side,
                    currency=args.currency,
                    quantity=args.quantity,
                    fill_price=args.fill_price,
                    client_order_id=args.client_order_id,
                ),
                stdout,
            )
            return 0

        if args.command == "paper-portfolio":
            broker = paper_broker_factory(args.db_path)
            _print_json(broker.portfolio(mark_prices=_parse_mark_prices(args.mark_price)), stdout)
            return 0

        if args.command == "paper-ledger":
            broker = paper_broker_factory(args.db_path)
            _print_json(broker.ledger(limit=args.limit), stdout)
            return 0

        config = config_factory()
        client = client_factory(config)

        if args.command == "prices":
            _print_json(client.get_prices(args.symbols), stdout)
        elif args.command == "watch-prices":
            _stream_price_snapshots(
                client=client,
                symbols=args.symbols,
                stdout=stdout,
                sleep=sleep,
                interval=args.interval,
                iterations=args.iterations,
            )
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
    except KeyboardInterrupt:
        return 130
    except (
        ConfigError,
        LiveTradingNotEnabled,
        OrderValidationError,
        PaperTradingError,
        TossApiError,
    ) as exc:
        print(str(exc), file=stderr)
        return 2

    return 0


def _add_paper_db_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db-path", default=None)


def _build_paper_broker(db_path: str | None = None) -> PaperBroker:
    return PaperBroker() if db_path is None else PaperBroker(db_path)


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


def _stream_price_snapshots(
    *,
    client: TossClient,
    symbols: list[str],
    stdout: TextIO,
    sleep: Callable[[float], None],
    interval: float,
    iterations: int | None,
) -> None:
    sequence = 1
    while iterations is None or sequence <= iterations:
        print(
            json.dumps(
                {
                    "sequence": sequence,
                    "prices": client.get_prices(symbols),
                },
                ensure_ascii=False,
            ),
            file=stdout,
            flush=True,
        )

        if iterations is not None and sequence >= iterations:
            break

        sleep(interval)
        sequence += 1


def _non_negative_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--interval must be a number") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("--interval must be non-negative")
    return parsed


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--iterations must be an integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("--iterations must be positive")
    return parsed


def _parse_mark_prices(values: list[str]) -> dict[str, str]:
    mark_prices = {}
    for value in values:
        if "=" not in value:
            raise PaperTradingError("--mark-price must use SYMBOL=PRICE format.")
        symbol, price = value.split("=", 1)
        if not symbol or not price:
            raise PaperTradingError("--mark-price must use SYMBOL=PRICE format.")
        mark_prices[symbol] = price
    return mark_prices
