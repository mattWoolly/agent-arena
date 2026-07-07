`data/sales.csv` contains order data with columns:
`order_id,date,region,product,units,unit_price`. Revenue for an order is
`units * unit_price`.

Produce two files. Follow every constraint exactly — grading is mechanical.

1. `REPORT.md`, with:
   - Exactly four headings, all H2 (`##`), in this order, spelled exactly:
     `## Overview`, `## Top Products`, `## Regional Performance`,
     `## Recommendations`. No other headings of any level anywhere.
   - At most 250 words in the whole file (headings count).
   - The Overview section must state the total revenue formatted exactly like
     `$12,345.67` (dollar sign, thousands commas, two decimals) and the total
     number of orders.
   - The Recommendations section must contain exactly three bullet points
     (lines starting with `- `), each at most 25 words, grounded in the data.
   - Nowhere in the file use any of these words (case-insensitive):
     leverage, delve, robust, seamless, revolutionize.

2. `summary.json`, a JSON object with exactly these five keys and no others:
   - `"total_revenue"`: number, total revenue rounded to 2 decimals
   - `"orders"`: integer, number of orders
   - `"median_order_value"`: number, median of per-order revenue rounded to
     2 decimals (for an even count, the mean of the two middle values)
   - `"top_product_by_revenue"`: string, product with the highest total revenue
   - `"revenue_by_region"`: object mapping every region present in the data to
     its total revenue rounded to 2 decimals

Compute all numbers from the CSV — do not estimate. Work only inside the
current directory. Do not create git commits.
