from auto_toss.cli import build_parser


def test_parser_has_expected_commands():
    parser = build_parser()
    commands = parser._subparsers._group_actions[0].choices

    assert {
        "prices",
        "stocks",
        "accounts",
        "holdings",
        "preview-order",
        "place-order",
    } <= set(commands)
