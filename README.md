# Major IPO Calendar

A selective, date-only US major-IPO calendar. Default: offer amount >= USD 1 billion or named watchlist, NYSE/Nasdaq, with SPAC/ETF/fund/secondary filters based on supplied classifications and issuer names. No price-time predictions, no trading actions. The watchlist is only a filter; it does not imply those companies have announced IPOs. Nasdaq expected dates can be indicative calendar dates rather than debut dates. A separately verified issuer timetable is supported via `config.json`.

## Deployment

1. Create public repository `rickeylau/major-ipo-calendar`, default branch `main`. Check that the chosen data provider permits your intended use and publication. The initial seed uses public SEC filings. The automatic Nasdaq web endpoint is undocumented and may reject GitHub runners; live availability is not verified. No API token needed for this version.
2. Upload the root files and both workflows in `.github/workflows/` (hidden folder; use Git or create the two files in GitHub's editor). Keep the folder paths unchanged. Do not upload `__pycache__`.
3. Actions > Update Major IPO Calendar > Run workflow. Wait for success; inspect `source_status.json` (`status: ok`) and `major-ipo.ics`.
4. Run Calendar Maintenance once. It validates ICS, checks source status/hash/freshness, and commits a health report. It shares the write concurrency group with updates.
5. Add by URL: `https://raw.githubusercontent.com/rickeylau/major-ipo-calendar/refs/heads/main/major-ipo.ics` (only valid after creating the repo and publishing the file). The seed is already populated; if first live update fails, the seed is kept, but the source is not marked healthy.
6. Update Calendar Health to V4.3 only after the first live update succeeds. Add repo access to the existing fine-grained GitHub token if it is restricted to selected repositories. Keep the existing KM macro.

## Automation

Updates every 3 hours, UTC minute 53. Keep Alive 09:41 UTC on days 1 and 15. The script requires all three monthly responses to have valid tables; source failures fail the workflow and preserve the previous ICS. A successful run with no qualifying IPOs is normal. Only the new IPO calendar permits empty event lists in the health monitor. No private API keys are stored in the repository.

## Manual milestones

Edit `manual_events` in config only when there is an issuer announcement or official filing. Initial Anthropic dates are expected, not confirmed: November 18 pricing, November 19 trading, both ET; no exact time. Amount is the base offer at the midpoint (825 million x $74), excluding overallotment. Source: https://www.sec.gov/Archives/edgar/data/2130357/000162828026073040/anthropicpbc-fwpxeeaprospea.htm . A manual expected event disappears after its date passes or an explicitly withdrawn symbol is found; if automatic dates disagree, review the manual timetable. The program does not automatically discover issuer-confirmed debut dates or actual first-trade times. Nasdaq dates alone are never asserted as confirmed listing dates. The source `https://www.nasdaq.com/market-activity/ipos` notes expected dates are estimates. Large-deal detection is dependent on provider coverage and its reported offer amount (may include overallotment); the name/type exclusions are best-effort, not a legal classification. No automatic IPO index inclusion assumptions.

## Local commands

`python -m unittest -v` (16 tests); `python major_ipo.py --seed` regenerates from manual seed only and explicitly marks source status seed; `python major_ipo.py` fetches live monthly source data. Python 3.10+; standard library only. Do not use seed mode as the production workflow.
