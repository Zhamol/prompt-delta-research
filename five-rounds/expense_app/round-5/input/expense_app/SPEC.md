# Build an expense tracker from scratch

Create `expense_app/ledger.py`, a Python 3 standard-library-only command-line application.
There is deliberately no starter implementation. Do not change other tasks. No network,
external packages, interactive prompts, or shell commands are needed by the application.

## Interface and behavior

Invoke `python ledger.py --db PATH COMMAND [OPTIONS]`. PATH names a UTF-8 JSON file;
its parent directory already exists. Each successful invocation exits 0 and prints
exactly one JSON value to stdout, followed by a newline. Diagnostics go to stderr.

- `add --amount AMOUNT --category CATEGORY --date YYYY-MM-DD`: persist an expense
  and print its record: `{ "id": 1, "amount_cents": 1234, "category": "food", "date": "2024-02-29" }`.
- `list [--category CATEGORY]`: print the matching records in ascending numeric ID
  order. Without the filter, return all records. No matches returns `[]`.
- `summary`: print `{ "count": N, "total_cents": T, "by_category": { "food": 1234 } }`.
  Empty state is exactly `{ "count": 0, "total_cents": 0, "by_category": {} }`.

Amounts are strings matching `[0-9]+(?:\.[0-9]{1,2})?` with ASCII digits only,
strictly greater than zero and at most 1,000,000.00 inclusive. Leading zeroes are
allowed. No signs, whitespace, exponent notation, NaN, Infinity, rounding, or
more than two decimal places. Use exact integer cents, never floating arithmetic.
Categories are trimmed with Python str.strip(); the resulting string must have
1 to 40 characters inclusive. Preserve case and Unicode. Filter categories follow
the same validation. Dates must be exactly YYYY-MM-DD and valid Gregorian dates
(including leap years), years 0001 through 9999.

IDs start at 1 and increase by one on every successful add. IDs persist across
separate process invocations. Different database paths must be independent.

## Persistence contract

File format is a JSON object with exactly `next_id` and `expenses` keys.
`expenses` is a list of records with exactly the four fields above, IDs 1 through N
in order, and `next_id` is N+1. Integer fields must be integers, not booleans;
amount_cents is in [1, 100000000]. Stored categories must already be trimmed and
valid. Stored dates must be valid as above. An absent file means empty state.
Read-only commands must not create an absent database or change existing bytes.
An add must atomically replace the file after validation, so failed validation
cannot partially modify it. No concurrent writers need to be supported.

Invalid command arguments, malformed JSON, and any schema-invalid existing file
must exit nonzero, print a nonempty diagnostic to stderr, and leave database bytes
unchanged (or leave the file absent). Never silently reset corrupted data. Failed
adds must not consume IDs. Empty files are corrupt, not absent databases.

## Grading criteria

All independent hidden tests must pass: core add/list/filter/summary functionality;
exact cents and repeated-process persistence; invalid inputs and non-mutation;
empty state, leap dates, amount/category boundaries, Unicode, database separation,
and malformed/schema-invalid storage. Tests invoke the CLI as a separate process
and calculate expected results independently. Grader code and reference solutions
are not provided in the agent sandbox. Cosmetic output key order is not graded.
