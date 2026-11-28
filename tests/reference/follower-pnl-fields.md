# Fields in `follower-pnl-set.json`

The file is one hand-made Wallet in the same layout as the Wallet files of the Sample Dataset. This note says what each field is. It says nothing about how to use them.

## Top level
- `address`: the Wallet's address (made up).
- `name`: a label for the file.
- `activity_from`, `activity_until`: the time span (Unix seconds) the activity rows are known to cover; `null` means no limit on that side.
- `activity`: the Wallet's own activity rows.
- `positions`: the list of the Wallet's positions, as Polymarket would list them.
- `markets`: data for the Markets the Wallet traded.
- `prices`: recorded price history points.

## `activity` rows
- `type`: `TRADE` in every row of this file.
- `side`: `BUY` or `SELL`.
- `size`: number of shares in the row.
- `price`: price per share, 0 to 1.
- `usdc_size`: cash in USDC that changed hands in the row.
- `token_id`: the outcome token.
- `condition_id`: the Market's id.
- `timestamp`: Unix seconds.

## `positions` rows
- `condition_id`, `token_id`: the Market and outcome token.
- `status`: `CLOSED` or `OPEN`, the list it is in.
- `shares_bought`: shares bought.
- `first_entry_at`, `last_event_at`: Unix seconds.

## `markets` rows
- `condition_id`: the Market's id.
- `token_ids`: the Market's outcome tokens; `token_ids[i]` goes with `outcome_prices[i]`.
- `outcome_prices`: each outcome's final price.
- `closed`: whether the Market is closed.
- `closed_time`: when the Market closed (Unix seconds).
- `start_time`: when the Market opened (Unix seconds).
- `fees_enabled`, `fee_rate`, `fee_exponent`: the Market's fee schedule.
- `event_id`, `neg_risk_id`, `tags`: not used in this file (`null` or empty).

## `prices` rows
- `token_id`: the outcome token the price is of.
- `t`: the time of the point (Unix seconds). The points are one minute apart.
- `price`: the recorded market price of that token at that time, 0 to 1.
