# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Python bot that scrapes Beymen.com men's products for configured brands/categories, tracks price history in SQLite, and sends Gmail + Telegram alerts when a discount threshold is crossed **and** the user's size is in stock. Single-user, no framework, no package layout — flat modules imported by name.

All user-facing strings, log messages, comments, and docstrings are in Turkish. Keep new code consistent with that.

## Commands

```bash
pip install -r requirements.txt

python bot.py            # scheduler mode: runs a check immediately, then every check_interval_hours
python bot.py --test     # one-shot scan + send mail
python bot.py --dry-run  # one-shot scan, no mail (no EMAIL_PASSWORD needed)
python bot.py --summary  # send daily summary mail now
python bot.py --report   # regenerate report.html from the DB only, no scraping
```

`--dry-run` and `--report` are the safe modes for development: they skip `load_email_password()` and never hit SMTP. Every other mode exits if `.env` has no `EMAIL_PASSWORD`.

There is no test suite, linter, or formatter configured. Verification is done by running `--dry-run` (exercises scraper → tracker → database → report) and inspecting `beymen_bot.log` / `report.html`.

## Architecture

`bot.py` is the only entry point and the only module that reads `config.yaml`/`.env`. Config is passed down as a plain dict; no module reads it independently.

Pipeline for one check (`bot.run_check`):

1. `scraper.scrape_all(config)` — iterates every brand × category combination plus `wishlist` URLs, returns deduplicated product dicts.
2. `tracker.process_products(products, config)` — upserts each into SQLite, decides which deserve an alert, enriches with trend/stock/reference-price fields.
3. `notifier.send_alert_email` + `notifier.send_telegram_alerts`, then `tracker.mark_all_alerted` (only after a successful send).
4. `report.generate_report()` — rewrites `report.html` from the whole DB, always, even when nothing was scraped.

`database.py` owns all SQL; nothing else opens a connection.

### Scraper

Beymen has no public API. `scraper.py` fetches the search HTML and pulls out the embedded `BEYMEN.productListMain = {...}` object using `_extract_json_object`, which walks braces while tracking string/escape state. Regex was tried and abandoned (see git history) — nested objects break it. `_parse_product_list` tries three markers in order (`BEYMEN.productListMain =`, `window.BEYMEN.productListMain =`, bare `productListMain =`), so a site-side rename usually only needs a fourth fallback here.

Beymen's JSON mixes camelCase and PascalCase keys, and the `products` array sometimes contains bare strings instead of objects. `_extract_products` defends against both — preserve the `p.get("x") or p.get("X")` pattern and the `isinstance(p, dict)` guard when touching it.

**Size filtering happens in the scraper, not the tracker.** A product whose `matching_sizes` is empty is dropped before it ever reaches the database, so the DB only contains products that were once available in the user's sizes.

`stock == 0` means "unknown" (Beymen doesn't always report it), not "sold out" — hence `0 < stock <= threshold` for low-stock checks throughout.

Pacing is deliberate: random 1.0–2.5s between pages, 0.5–1.5s between brand/category combos, and `_fetch_page` backs off exponentially on 429 / network errors. Don't remove these.

### Alert decision (tracker.py)

Order of checks in `process_products`:

- Cooldown (`last_alerted` + `cooldown_hours`) suppresses re-alerts — **unless** `discount_jumped`: the discount rose by at least `discount_jump_threshold` points *and* is at/above `min_discount`. That bypass is the reason `prev_discount` is read from the DB row before the upsert's effect matters.
- Then `discount_rate >= min_discount` (reason `discount`/`discount_jump`), else `notify_new_products and is_new` (reason `new_product`).

`ref_original` is the reference "was" price shown in alerts. `database.upsert_product` deliberately never overwrites `products.original_price` after insert, so `ref_original` is the *first-seen* list price rather than whatever Beymen currently claims. Use `ref_original`, not the scraped `original_price`, in anything user-facing.

### Database

SQLite at `beymen_tracker.db`, two tables: `products` (current state, keyed by Beymen product id as TEXT) and `price_history` (one row appended per product per check). Schema changes are applied as `CREATE TABLE IF NOT EXISTS` in `init_db()` plus bare `ALTER TABLE ... ADD COLUMN` wrapped in `try/except: pass` — that's the migration mechanism for existing DBs; follow it when adding columns.

`available_sizes` is stored as a JSON string, so every read site has to `json.loads` it (see `tracker.get_daily_summary`, `report.generate_report`, `notifier.send_daily_summary`).

### HTML output

`notifier.py` (email) and `report.py` (report.html) both build HTML with `str.format()` on module-level template constants. Consequence: **every literal `{`/`}` in those templates must be doubled** — this is why all the CSS in `report._HTML_TEMPLATE` and the JS functions use `{{ }}`. Email templates are table-based inline-CSS for mail-client compatibility; don't modernize them to flexbox.

Beymen CDN image URLs contain `{width}`/`{height}` placeholders and an `/mnresize/W/H/` path segment. Each consumer substitutes its own dimensions (`scraper` 600×780, `notifier._img_tag` 150×195, `report._img_tag` 400×520).

The Unicode price-trend sparkline (`▁▂▃▄▅▆▇█` over the last 7 history rows) exists twice: `tracker._price_trend` and inline in `report.generate_report`. Changing the algorithm means changing both.

## Config

`config.yaml` is committed with placeholder values (`kullanici@gmail.com`, `BOT_TOKEN_BURAYA`) and is the file users edit directly — there is no `config.yaml.example`, despite the error message in `bot.load_config` referencing one. Telegram is opt-in and silently skipped while `bot_token` is still `BOT_TOKEN_BURAYA`.

`.env` holds only `EMAIL_PASSWORD` (a Gmail App Password). `.env`, `*.db`, and `*.log` are gitignored; `report.html` is not.
