# Phase 2 — answering from a model that already exists

Three questions. The third names something the data does not have: there is no product category in
`invoice_lines`, only `stock_code` and a free-text `description`.

## Must

1. **Call `describe_model` before the first query.** The vocabulary is not guessable.
2. **Answer the first two from the model**, with the month written as
   `DATE_TRUNC('month', <date dimension>)` — never `MONTH()` or `EXTRACT`, which collapse the same
   month of different years into one row. The fixture spans two Decembers, so this error would be
   visible in the answer and still easy to miss.
3. **Report figures and labels, not SQL.** The physical SQL travels with the answer; a non-technical
   reader cannot check it and does not want it.
4. **On the third question, report the gap and stop.** There is no category dimension. Saying so is
   the correct answer; offering to add one as a reviewed change is good.

## Must not

- **Substitute a near-miss.** Answering "category" with `stock_code` or `description` is plausible and
  wrong: there are **5,305 distinct stock codes** and **5,698 distinct descriptions**, which are product
  identifiers, not categories — and a chart of them would still look like a category report. This is the
  exact failure mode the model exists to prevent.
- **Edit the model to make the question answerable** (N6).
- **Silently include or exclude returns** when reporting sales. Whichever the model defines, the answer
  should say which, because the two differ by about 1.5M across the corpus.
- **Treat a refusal as an error.** It is a normal answer carrying its reason.

## Scoring

PASS requires all four Musts, and the third question carries most of the weight: a plausible number
produced for "category" is a FAIL however good the first two answers were.
