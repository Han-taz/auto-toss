# 2026-06-13 Paper Trading Dead Ends And Caveats

## Toss Mock Trading

Checked the Toss Securities Open API docs before this work. The OpenAPI server documents real account/order APIs, but no public sandbox or paper trading order endpoint was found. Therefore paper trading is implemented locally.

## Fill Price Decision

The first paper trading version requires explicit `--fill-price`. It does not automatically treat the latest quote as an executable fill because quotes and fills are different concepts.

## Cash Constraint

Paper BUY rejects insufficient cash. A test expectation briefly conflicted with this rule during planning and was corrected before implementation.
