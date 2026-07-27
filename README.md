# trade-skills

A Claude skill that answers **"which market should we go after first?"** from UN
Comtrade data — no API key, no dependencies, no signup.

> 한국어 문서: **[README.ko.md](README.ko.md)**

```
"Which countries should we target for cosmetics?"
"Compare lithium battery markets across our top trading partners"
"HS 3907 — how does Vietnam look?"
```

Ask in plain language. The skill resolves the HS code, pulls the trade data,
and returns a ranked shortlist with the reasoning shown.

---

## ⚠️ Read this first

These matter more than the tool does. Get them wrong and you get numbers that
are correct and conclusions that are backwards.

- **Share of imports is not market share.** Mirror data covers imports only, so
  domestic producers are invisible. "Korea holds 53% in Vietnam" means 53% of
  *imported* instant noodles — the local manufacturers who actually dominate
  that market are absent from the dataset entirely. The risk is highest in food,
  automotive, steel, and cosmetics. For the same reason, "local total imports"
  is not the size of that country's market.
- **No company-level data exists here.** Korean customs declarations are
  confidential by law, so no source gives you exporter name × product × value.
  Buyer names require paid bill-of-lading data (Panjiva, ImportYeti, Volza) from
  countries that publish B/Ls — the US and India do; Korea, the EU, Japan, and
  China do not.
- **HS 6-digit maximum.** National 8/10-digit subdivisions are not comparable
  across countries and are not in Comtrade.
- **FOB vs CIF.** Korea reports exports FOB, partners report imports CIF. The
  same shipment is worth more on the importer's books. Never compute a share by
  mixing the two.
- **The score is relative, not absolute.** Every axis is min-max normalized
  across the countries in *that* query. Adding or removing an unrelated country
  can flip the ranking, not just the scores. Run it twice with different
  comparison sets and trust the countries that stay put.
- **Unit price is `value ÷ weight`.** Its movement mixes price changes with
  product-mix changes and the two cannot be separated above HS 6-digit. It is
  not a quality signal.

Full detail: [`references/data-notes.md`](plugins/trade-stats/skills/trade-stats-lookup/references/data-notes.md)
(Korean).

---

## Why this exists

Written by someone who did overseas sales, for that job.

**Market research eats half a day per product.** Deciding which country to go
after first means opening KOTRA reports, KITA's K-stat, and ITC Trade Map
separately, typing the HS code into each, and copying numbers into a
spreadsheet. The questions being asked are simple — where are we losing share,
where is there still room — but getting to them is not.

**So the decision ends up being made on instinct.** The country where the last
trade show produced the most business cards. The one an inquiry came from. Ask
for the reasoning and it is "the market is big." Whether the market is actually
growing, who is capturing that growth, and whether any room is left usually goes
unchecked.

**Buyer discovery is the next problem, and the first one has already exhausted
you.** Pick the wrong market and the contact list length does not matter. In
practice the first step gets rushed so the buyer list can start.

This tool does one thing: **make market selection quantitative.** One question,
eighty seconds, no HS code required — and, more importantly, the caveats needed
to read the answer correctly travel with the numbers.

Tools that just produce numbers already exist. The failure mode is numbers that
quietly lead somewhere wrong: import share mistaken for market share, an
entrepôt read as a promising market, a country with no data read as a bad
market. So the warnings above are not buried in documentation — they are printed
inside the report itself.

**Buyer discovery is deliberately out of scope.** Korean company-level trade
data is not legally public, so no free tool can do it, and pretending otherwise
is the worst option. Getting "which country to go looking in" right is the goal
instead.

## What you get

For one HS code, across ten markets by default (~80 seconds):

| Column | Meaning |
|---|---|
| Local total imports | What that country buys from the world |
| **Market CAGR** | How fast **the market** is growing |
| Korea's exports + CAGR | How fast **your** sales into it are growing |
| Korea's share | Share **of imports** — see the caveat below |
| Top supplier | The incumbent, flagged ⚠️ when they hold 60%+ |
| Attractiveness | size 40% + market growth 35% + share headroom 25% |

Plus per-country supplier tables, three CSVs (UTF-8 BOM, opens straight in
Excel), and a Markdown report.

The gap between *market CAGR* and *your CAGR* is usually the most useful number
on the page: a growing market where your exports shrink means you are losing
share, and the reverse often means you are looking at an entrepôt rather than a
real destination.

### Example

```
| # | Country   | Score | Imports  | Market CAGR | KR exports | KR CAGR | KR share | Top supplier |
|---|-----------|-------|----------|-------------|------------|---------|----------|--------------|
| 1 | Taiwan    | 75.3  | $1.14B   | +36.2%      | $110M      | +11.5%  | 7.1%     | China 31%    |
| 2 | China     | 72.0  | $7.08B   |  +1.6%      | $1.04B     |  -3.5%  | 16.0%    | Korea 16%    |
| 3 | India     | 62.1  | $2.70B   |  +4.1%      | $350M      |  -5.7%  | 14.1%    | China 34%    |
```

## Install

**Claude Code — marketplace**

```
/plugin marketplace add bonghyunyang/trade-skills
/plugin install trade-stats@trade-skills
```

**Claude Code — local**

```bash
cp -r plugins/trade-stats/skills/trade-stats-lookup ~/.claude/skills/
```

**Cowork / claude.ai**

```bash
./package.sh   # produces dist/trade-stats-lookup.zip
```

Upload the zip under Settings → Capabilities → Skills.

**Requirements:** `python3` **3.11 or newer** (standard library only — no
`pip install`) and an internet connection. Tested on 3.11, 3.12, and 3.13.
macOS ships 3.9, which is end-of-life — `brew install python@3.11` if you are
running this locally rather than through Cowork.

## Scope

Built for Korean exporters: `reporter` is fixed to Korea, and the interface,
HS-code index, and reports are in Korean. The data layer is
reporter-agnostic — supporting other reporting countries is a tracked
limitation, not a design decision.

## CLI

```bash
cd plugins/trade-stats/skills/trade-stats-lookup/scripts

python3 analyze.py market --hs 3907                       # top 10 partners
python3 analyze.py market --hs 3304 --countries VN,IN --monthly 24
python3 fetch_comtrade.py hs-search "화장품"              # Korean product name
python3 fetch_comtrade.py rank   --hs 3907 --year 2025
python3 fetch_comtrade.py mirror --hs 3907 --importer VN --year 2024
```

Responses are cached for 7 days under `~/.cache/trade-stats-lookup/`.

This runs against UN Comtrade's free unauthenticated preview tier. Requests are
paced, `Retry-After` is honored, and the pacing interval cannot be set below one
second. If several people share an office IP, raise
`TRADE_STATS_MIN_INTERVAL`. Set `TRADE_STATS_CONTACT` to an email or repo URL so
the data publisher has a way to reach you. Bulk extraction warrants a
subscription key instead.

## Development

```bash
python3 tests/record_fixtures.py   # required once — fixtures are gitignored
./tests/run_tests.sh               # 100 tests, offline, ~0.15s
./tests/run_tests.sh --live        # + real API contract tests
./package.sh                       # verify, then build the zip
```

Tests replay recorded API responses through the skill's own cache layer, so
there is no mock layer to drift out of sync, and an un-fixtured request fails
loudly instead of silently going to the network. The live contract suite is the
early-warning system for upstream schema changes — the offline suite replays
recordings and cannot catch those.

Skill triggering cannot be covered by unit tests; see
[`tests/TRIGGER_TESTS.md`](tests/TRIGGER_TESTS.md).

## License and data

Code is MIT ([`LICENSE`](LICENSE)).

**Bundled reference data is not MIT** — see [`NOTICE`](NOTICE) for each file's
origin and terms. In particular, the commodity descriptions in `hs.json` are
World Customs Organization Harmonized System nomenclature, obtained via UN
Comtrade's public reference endpoint; that does not by itself convey WCO
redistribution rights. Check your position before forking or shipping
commercially.

Trade statistics from the United Nations Comtrade database
(https://comtrade.un.org). The United Nations does not endorse this project.
