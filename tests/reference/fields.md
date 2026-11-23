# Fields in the Wallet files

Each file is one Wallet's data as Polymarket's public APIs reported it. This note says what each field is. It says nothing about how to use them.

## Top level
- `address`: the Wallet's address.
- `name`: a label for the file.
- `activity_from`, `activity_until`: the time span (Unix seconds) the activity rows are known to cover; `null` means no limit on that side.
- `activity`: the Wallet's own activity rows.
- `positions`: Polymarket's own list of the Wallet's positions.
- `markets`: data for the Markets the Wallet traded.
- `prices`: price history points (not filled in these files).

## `activity` rows
- `type`: `TRADE`, `REDEEM` or `CONVERSION` (other types such as `SPLIT` or `MERGE` can exist in general).
- `side`: `BUY` or `SELL` for a TRADE; `null` otherwise.
- `size`: number of shares in the row.
- `price`: price per share, 0 to 1 (0 where the row has no price).
- `usdc_size`: cash in USDC that changed hands in the row.
- `token_id`: the outcome token; `null` where the row names no single token.
- `condition_id`: the Market's id. On a `CONVERSION` row it holds the id of the negative-risk event instead, the same value as `neg_risk_id` on that event's Markets.
- `timestamp`: Unix seconds.

## `positions` rows
- `condition_id`, `token_id`: the Market and outcome token.
- `status`: `CLOSED` or `OPEN`, the list Polymarket returned it in.
- `shares_bought`: shares bought, as Polymarket's position list reports it.
- `first_entry_at`, `last_event_at`: Unix seconds.

## `markets` rows
- `condition_id`: the Market's id.
- `token_ids`: the Market's outcome tokens; `token_ids[i]` goes with `outcome_prices[i]`.
- `outcome_prices`: each outcome's final price.
- `closed`: whether the Market is closed.
- `closed_time`: when the Market closed (Unix seconds), or `null`.
- `start_time`: when the Market opened (Unix seconds).
- `fees_enabled`, `fee_rate`, `fee_exponent`: the Market's fee schedule as Polymarket lists it (rate and exponent may be `null`).
- `event_id`: the event the Market belongs to.
- `neg_risk_id`: the negative-risk event id, or `null` if the Market is not in one.
- `tags`: Polymarket's labels for the Market.
