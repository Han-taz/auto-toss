from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
import sqlite3
import uuid


class PaperTradingError(RuntimeError):
    pass


@dataclass(frozen=True)
class PaperBroker:
    db_path: str | Path = ".auto_toss/paper_trading.sqlite3"

    def initialize(
        self,
        *,
        reset: bool = False,
        krw_cash: str = "10000000",
        usd_cash: str = "10000",
    ) -> dict[str, object]:
        path = Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if reset and path.exists():
            path.unlink()

        with self._connect() as connection:
            _create_schema(connection)
            connection.execute(
                "INSERT OR IGNORE INTO accounts(id, name) VALUES (1, 'default')"
            )
            for currency, amount in (("KRW", krw_cash), ("USD", usd_cash)):
                _require_currency(currency)
                _require_non_negative_decimal(amount, "cash")
                connection.execute(
                    """
                    INSERT INTO cash_balances(account_id, currency, amount)
                    VALUES (1, ?, ?)
                    ON CONFLICT(account_id, currency)
                    DO UPDATE SET amount = excluded.amount
                    """,
                    (currency, _decimal_text(amount)),
                )
        return self.portfolio()

    def execute_order(
        self,
        *,
        symbol: str,
        side: str,
        currency: str,
        quantity: str,
        fill_price: str,
        client_order_id: str | None = None,
    ) -> dict[str, object]:
        side = side.upper()
        currency = currency.upper()
        _require_side(side)
        _require_currency(currency)
        qty = _require_positive_decimal(quantity, "quantity")
        price = _require_positive_decimal(fill_price, "fill_price")
        amount = qty * price

        with self._connect() as connection:
            _create_schema(connection)
            cash = _get_cash(connection, currency)
            position = _get_position(connection, symbol, currency)

            if side == "BUY":
                if cash < amount:
                    raise PaperTradingError(f"Insufficient {currency} cash.")
                new_quantity = position["quantity"] + qty
                total_cost = position["quantity"] * position["average_cost"] + amount
                average_cost = total_cost / new_quantity
                _set_cash(connection, currency, cash - amount)
                _set_position(connection, symbol, currency, new_quantity, average_cost)
                realized_pnl = Decimal("0")
            else:
                if position["quantity"] < qty:
                    raise PaperTradingError(f"Insufficient {symbol} position.")
                realized_pnl = (price - position["average_cost"]) * qty
                new_quantity = position["quantity"] - qty
                _set_cash(connection, currency, cash + amount)
                if new_quantity == 0:
                    _delete_position(connection, symbol, currency)
                else:
                    _set_position(connection, symbol, currency, new_quantity, position["average_cost"])

            fill_id = uuid.uuid4().hex
            connection.execute(
                """
                INSERT INTO fills(
                    fill_id, client_order_id, symbol, side, currency,
                    quantity, fill_price, amount, realized_pnl
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fill_id,
                    client_order_id,
                    symbol,
                    side,
                    currency,
                    _format_decimal(qty),
                    _format_decimal(price),
                    _format_decimal(amount),
                    _format_decimal(realized_pnl),
                ),
            )

        return {
            "fillId": fill_id,
            "clientOrderId": client_order_id,
            "symbol": symbol,
            "side": side,
            "currency": currency,
            "quantity": _format_decimal(qty),
            "fillPrice": _format_decimal(price),
            "amount": _format_decimal(amount),
            "realizedPnl": _format_decimal(realized_pnl),
        }

    def portfolio(self, *, mark_prices: dict[str, str] | None = None) -> dict[str, object]:
        mark_prices = mark_prices or {}
        with self._connect() as connection:
            _create_schema(connection)
            cash = {
                row["currency"]: _format_decimal(Decimal(row["amount"]))
                for row in connection.execute(
                    "SELECT currency, amount FROM cash_balances WHERE account_id = 1 ORDER BY currency"
                )
            }
            cash.setdefault("KRW", "0")
            cash.setdefault("USD", "0")

            positions = []
            for row in connection.execute(
                """
                SELECT symbol, currency, quantity, average_cost
                FROM positions
                WHERE account_id = 1
                ORDER BY symbol, currency
                """
            ):
                quantity = Decimal(row["quantity"])
                average_cost = Decimal(row["average_cost"])
                mark_price = mark_prices.get(row["symbol"])
                if mark_price is None:
                    market_value = None
                    unrealized_pnl = None
                else:
                    mark = _require_positive_decimal(mark_price, f"mark price for {row['symbol']}")
                    market_value = _format_decimal(quantity * mark)
                    unrealized_pnl = _format_decimal((mark - average_cost) * quantity)

                positions.append(
                    {
                        "symbol": row["symbol"],
                        "currency": row["currency"],
                        "quantity": _format_decimal(quantity),
                        "averageCost": _format_decimal(average_cost),
                        "marketValue": market_value,
                        "unrealizedPnl": unrealized_pnl,
                    }
                )

            realized = {"KRW": Decimal("0"), "USD": Decimal("0")}
            for row in connection.execute(
                "SELECT currency, realized_pnl FROM fills WHERE account_id = 1"
            ):
                realized[row["currency"]] += Decimal(row["realized_pnl"])

        return {
            "cash": cash,
            "positions": positions,
            "realizedPnl": {
                "KRW": _format_decimal(realized["KRW"]),
                "USD": _format_decimal(realized["USD"]),
            },
        }

    def ledger(self, *, limit: int = 50) -> list[dict[str, object]]:
        with self._connect() as connection:
            _create_schema(connection)
            rows = connection.execute(
                """
                SELECT fill_id, client_order_id, symbol, side, currency,
                       quantity, fill_price, amount, realized_pnl, created_at
                FROM fills
                WHERE account_id = 1
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            {
                "fillId": row["fill_id"],
                "clientOrderId": row["client_order_id"],
                "symbol": row["symbol"],
                "side": row["side"],
                "currency": row["currency"],
                "quantity": row["quantity"],
                "fillPrice": row["fill_price"],
                "amount": row["amount"],
                "realizedPnl": row["realized_pnl"],
                "createdAt": row["created_at"],
            }
            for row in rows
        ]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(Path(self.db_path))
        connection.row_factory = sqlite3.Row
        return connection


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS cash_balances (
            account_id INTEGER NOT NULL,
            currency TEXT NOT NULL,
            amount TEXT NOT NULL,
            PRIMARY KEY (account_id, currency)
        );

        CREATE TABLE IF NOT EXISTS positions (
            account_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            currency TEXT NOT NULL,
            quantity TEXT NOT NULL,
            average_cost TEXT NOT NULL,
            PRIMARY KEY (account_id, symbol, currency)
        );

        CREATE TABLE IF NOT EXISTS fills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL DEFAULT 1,
            fill_id TEXT NOT NULL,
            client_order_id TEXT,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            currency TEXT NOT NULL,
            quantity TEXT NOT NULL,
            fill_price TEXT NOT NULL,
            amount TEXT NOT NULL,
            realized_pnl TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )


def _get_cash(connection: sqlite3.Connection, currency: str) -> Decimal:
    row = connection.execute(
        "SELECT amount FROM cash_balances WHERE account_id = 1 AND currency = ?",
        (currency,),
    ).fetchone()
    if row is None:
        return Decimal("0")
    return Decimal(row["amount"])


def _set_cash(connection: sqlite3.Connection, currency: str, amount: Decimal) -> None:
    connection.execute(
        """
        INSERT INTO cash_balances(account_id, currency, amount)
        VALUES (1, ?, ?)
        ON CONFLICT(account_id, currency)
        DO UPDATE SET amount = excluded.amount
        """,
        (currency, _format_decimal(amount)),
    )


def _get_position(connection: sqlite3.Connection, symbol: str, currency: str) -> dict[str, Decimal]:
    row = connection.execute(
        """
        SELECT quantity, average_cost
        FROM positions
        WHERE account_id = 1 AND symbol = ? AND currency = ?
        """,
        (symbol, currency),
    ).fetchone()
    if row is None:
        return {"quantity": Decimal("0"), "average_cost": Decimal("0")}
    return {
        "quantity": Decimal(row["quantity"]),
        "average_cost": Decimal(row["average_cost"]),
    }


def _set_position(
    connection: sqlite3.Connection,
    symbol: str,
    currency: str,
    quantity: Decimal,
    average_cost: Decimal,
) -> None:
    connection.execute(
        """
        INSERT INTO positions(account_id, symbol, currency, quantity, average_cost)
        VALUES (1, ?, ?, ?, ?)
        ON CONFLICT(account_id, symbol, currency)
        DO UPDATE SET quantity = excluded.quantity, average_cost = excluded.average_cost
        """,
        (symbol, currency, _format_decimal(quantity), _format_decimal(average_cost)),
    )


def _delete_position(connection: sqlite3.Connection, symbol: str, currency: str) -> None:
    connection.execute(
        "DELETE FROM positions WHERE account_id = 1 AND symbol = ? AND currency = ?",
        (symbol, currency),
    )


def _require_side(side: str) -> None:
    if side not in {"BUY", "SELL"}:
        raise PaperTradingError("side must be BUY or SELL.")


def _require_currency(currency: str) -> None:
    if currency not in {"KRW", "USD"}:
        raise PaperTradingError("currency must be KRW or USD.")


def _require_positive_decimal(value: str, field: str) -> Decimal:
    decimal = _parse_decimal(value, field)
    if decimal <= 0:
        raise PaperTradingError(f"{field} must be positive.")
    return decimal


def _require_non_negative_decimal(value: str, field: str) -> Decimal:
    decimal = _parse_decimal(value, field)
    if decimal < 0:
        raise PaperTradingError(f"{field} must be non-negative.")
    return decimal


def _parse_decimal(value: str, field: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise PaperTradingError(f"{field} must be a decimal string.") from exc


def _decimal_text(value: str) -> str:
    return _format_decimal(Decimal(value))


def _format_decimal(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return str(normalized.quantize(Decimal("1")))
    return format(normalized, "f")
