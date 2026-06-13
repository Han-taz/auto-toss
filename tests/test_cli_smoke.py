from auto_toss.cli import build_parser


def test_parser_has_expected_commands():
    parser = build_parser()
    commands = parser._subparsers._group_actions[0].choices

    assert {
        "prices",
        "stocks",
        "accounts",
        "holdings",
        "watch-prices",
        "paper-init",
        "paper-order",
        "paper-portfolio",
        "paper-ledger",
        "preview-order",
        "place-order",
        "run-strategy",
        "orders",
        "order-detail",
        "cancel-order",
        "modify-order",
        "reconcile-orders",
        "audit-runs",
        "audit-run",
        "audit-order-events",
        "audit-reconciliations",
        "audit-summary",
    } <= set(commands)
