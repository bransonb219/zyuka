# Logframe guide

A Linga `logframe.yml` describes what you want to measure. The indicator
engine reads this file, validates it against your data, and produces per-
round values with longitudinal change and traffic-light status.

## File shape

```yaml
goal: "Improved wellbeing of target households"
goal_indicators:
  - code: "G1"
    name: "People reached"
    type: "count_unique"
    numerator: "pid_seed != ''"
    disaggregations: ["sex", "province"]
    targets: { baseline: 150, midline: 300, endline: 500 }
    unit: "people"

outcomes:
  - code: "OC1"
    name: "Household incomes increased"
    indicators:
      - code: "OC1.1"
        name: "Proportion with an income source"
        type: "proportion"
        numerator: "livelihoods/has_income_source == 'yes'"
        denominator: "pid_seed != ''"
        targets: { baseline: 0.4, midline: 0.6, endline: 0.75 }
    outputs:
      - code: "OP1.1"
        name: "Livelihoods training delivered"
        indicators:
          - code: "OP1.1.1"
            name: "People trained"
            type: "count"
            numerator: "training/attended == 'yes'"
            targets: { baseline: 50, midline: 150, endline: 300 }
```

## Indicator types

| Type | Meaning |
|---|---|
| `count` | Number of rows matching the numerator expression |
| `count_unique` | Number of distinct values in the numerator (not boolean) |
| `proportion` | `count(numerator) / count(denominator)` |
| `mean` | Mean of the numeric expression |
| `median` | Median of the numeric expression |
| `sum` | Sum of the numeric expression |
| `ratio` | `sum(numerator) / sum(denominator)` |

## Expressions

Numerator and denominator are evaluated by a **safe parser**. No `eval`,
no `exec`. The allowed syntax is:

- Column references by name: `age`, `livelihoods/has_income_source`.
- Comparison operators: `==`, `!=`, `<`, `<=`, `>`, `>=`.
- Boolean logic: `and`, `or`, `not`.
- Literals: numbers, strings, booleans, `None`.
- Function calls restricted to a safe allowlist:
  - `isna(column)` — true if the value is missing.
  - `between(column, lo, hi)` — inclusive numeric range.
  - `selected(column, 'value')` — matches a `select_multiple` answer.
  - `startswith(column, 'prefix')`.
  - `in_list(column, ['a', 'b'])`.

Anything else (imports, attribute access, lambdas, unknown functions)
is rejected with a plain-language error.

## Disaggregations

Any column can be a disaggregation — most commonly `sex`, `age_band`,
`province`, `district`. The engine groups the data and recomputes the
indicator per group, then writes each disaggregation to its own sheet
in the Excel workbook.

## Targets and traffic-light status

Each indicator can declare `targets:` keyed by round. The longitudinal
output computes `percent_of_target = 100 * value / target` and maps it
to a status:

| percent_of_target | Status |
|---|---|
| ≥ `on_track` (default 80) | `on_track` |
| ≥ `at_risk` (default 50) | `at_risk` |
| otherwise | `off_track` |

Thresholds are configurable under `traffic_light:` in `linga.yml`.

## Validation

`linga compute` validates the logframe against your data before computing
anything. Missing columns raise plain-language errors with a "did you
mean?" suggestion powered by `difflib`.
