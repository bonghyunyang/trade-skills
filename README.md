<div align="center">

# trade-skills

### Pick your export market with numbers, not instinct.

Name a product. No HS code, no API key, no signup.

[![Claude Code](https://img.shields.io/badge/Claude%20Code-plugin-6f42c1)](https://claude.com/claude-code)
[![Cowork](https://img.shields.io/badge/Cowork%20%C2%B7%20claude.ai-skill-0ea5e9)](https://claude.ai)
[![No API key](https://img.shields.io/badge/API%20key-not%20required-16a34a)](#install)
[![Tests](https://github.com/bonghyunyang/trade-skills/actions/workflows/tests.yml/badge.svg)](https://github.com/bonghyunyang/trade-skills/actions/workflows/tests.yml)
[![License](https://img.shields.io/badge/license-MIT-black)](LICENSE)

</div>

> [!NOTE]
> **This tool speaks Korean.** It is built for exporters selling *from* Korea: it
> answers in Korean, indexes products by Korean name, and its rankings are framed
> around Korean export share. The data underneath is UN Comtrade, so the analysis
> is not Korea-specific — but the conversation is. Read this README in English;
> expect Korean in the chat.

---

> [!WARNING]
> **Thirty seconds before you use this.** Miss these and you get numbers that are
> correct and conclusions that are backwards.
>
> - **"Share" here means share of imports**, not market share — domestic producers are absent from the data.
> - **No buyer company names.** Not a tool limitation; Korean customs declarations are confidential by law.
> - **Export procedures and tariffs are not verified by this tool.** Check tariff rates independently.
>
> Details → [Reading the numbers](#reading-en)

---

<a id="install"></a>

## ⚡ Install

**Claude Code**

```
/plugin marketplace add bonghyunyang/trade-skills
/plugin install trade-stats@trade-skills
```

**Cowork · claude.ai** — download `trade-stats-lookup.zip` from
[Releases](https://github.com/bonghyunyang/trade-skills/releases) and upload it under
**Settings → Capabilities → Skills**.

An internet connection is all you need. No key to request, no `pip install`.

## 💬 Try it

> "Which countries should we target for cosmetics?"

> "Compare lithium battery markets across our top trading partners"

> "HS 3907 — how does Vietnam look?"

> "Where haven't we sold cosmetics yet?"

Built for Korean exporters: `reporter` is fixed to Korea and the reports are in Korean.

## 🧭 Two modes

|  | Command | Coverage | Time |
|---|---|---|---|
| Rank markets you already know | `market` | Named countries, or Korea's top 10 partners | 3–5 min |
| **Find markets you have never sold to** | `discover` | **All 225 Comtrade reporters** | 1-2 min |

The default target list is Korea's top 10 trading partners, which are by definition
countries you already sell to — no new market can come out of that set. `discover`
scans every reporting country instead, then you narrow to two or three and run
`market` on those.

A real run on HS 3304 put **Poland first**: imports grew from $1.49B (2023) to
$2.31B (2025), +24.3% a year, while Korean exports went from $57.5M to $304M — 5.3x.
Poland is not in Korea's top 10, so the default preset could never have surfaced it.

## 📊 What you get

For one HS code, across ten markets by default (3–5 minutes on a cold cache, under a second on a warm one):

| Column | Meaning |
|---|---|
| Local total imports | What that country buys from the world |
| **Market CAGR** | How fast **the market** is growing |
| Korea's exports + CAGR | How fast **your** sales into it are growing |
| Korea's share | Share **of imports** — see the warning above |
| Top supplier | The incumbent, flagged ⚠️ at 60%+ |
| Attractiveness | untapped market 50% + market CAGR 50% |
| Untapped market | local total imports × (1 − Korea's share) — the money still on the table |

Plus per-country supplier tables, three CSVs (UTF-8 BOM, opens straight in Excel),
and a Markdown report.

**The gap between the two CAGRs is usually the most useful number on the page.**

| Pattern | Reading |
|---|---|
| Market ↑ · your exports ↓ | **Losing share** |
| Market ↓ · your exports ↑ | **Likely an entrepôt** — the real destination is elsewhere |
| Market ↑ · your exports ↑↑ | **Gaining share** — push here now |

## 🤔 Why this exists

Written by someone who did overseas sales, for that job.

**Market research eats half a day per product.** Deciding which country to go
after first means opening KOTRA reports, KITA's K-stat, and ITC Trade Map
separately, typing the HS code into each, and copying numbers into a spreadsheet.
The questions being asked are simple — where are we losing share, where is there
still room — but getting to them is not.

**So the decision ends up being made on instinct.** The country where the last
trade show produced the most business cards. Ask for the reasoning and it is
"the market is big." Whether the market is actually growing, who is capturing
that growth, and whether any room is left usually goes unchecked.

**Buyer discovery is the next problem, and the first one has already exhausted
you.** Pick the wrong market and the contact list length does not matter.

Tools that just produce numbers already exist. The failure mode is numbers that
**quietly lead somewhere wrong**: import share mistaken for market share, an
entrepôt read as a promising market, a country with no data read as a bad market.
So the warnings are not buried in documentation — they are printed inside the
report itself.

<a id="reading-en"></a>

## ⚠️ Reading the numbers

- **Share of imports is not market share.** "Korea holds 53% in Vietnam" means 53%
  of *imported* instant noodles — the local manufacturers who actually dominate
  that market are absent from the dataset entirely. Highest risk in food,
  automotive, steel, and cosmetics. For the same reason, "local total imports" is
  not the size of that country's market.
- **The score is absolute, so it travels.** Both axes are fixed scales — untapped
  market $10M–$10B, market CAGR −10%…+20% — so a country scores the same whoever
  else is in the query, and scores from separate runs are comparable. The ceiling
  is the point: without it the score just tracks market size (measured at
  Spearman +0.89) and tells you that big markets are big.
- **Two different reasons to be unranked.** `측정불가` means a required figure is
  missing and the country could not be compared — not that it is a bad market.
  `규모 미달` means the data is there and the market is genuinely small. Lower
  `--min-market` if your business runs on smaller volumes.
- **Untapped is not an empty market.** A low Korean share may mean someone else is
  already sitting there, so the incumbent supplier is shown alongside it.

<details>
<summary><b>More caveats (expand)</b></summary>

- **A country excluded from the ranking is not a bad market** — it could not be measured.
- **Unit price is `value ÷ weight`.** Its movement mixes price changes with
  product-mix changes and the two cannot be separated above HS 6-digit. Not a
  quality signal.
- **FOB vs CIF.** Korea reports exports FOB, partners report imports CIF. Never
  compute a share by mixing the two.
- **A 4-digit heading can hold unlike products.** HS 3907 mixes polycarbonate
  (27% of Korea's exports under it), polyethers (19%), epoxy (18%) and PET (11%) —
  run it as-is and you get that basket's market, not yours. The tool checks the
  6-digit split before querying and **stops to ask when no single subheading holds
  60%**. Concentrated headings pass straight through: 3304 is 90% one subheading,
  6309 has only one.
- **Years can differ across one table.** Korea's export figure is usually a year
  newer than the partner-reported market size beside it. Reports state the basis;
  carry it with you if you lift the table.
- **HS 6-digit maximum.** National 8/10-digit subdivisions are not comparable
  across countries and are not in Comtrade.
- Latest data lags 2–6 months per reporter; the skill steps back automatically.
- When Korea's reported exports and the partner's reported imports diverge by 2x or
  more, the report flags it — a re-export or coverage signal.

Full detail: [`data-notes.md`](plugins/trade-stats/skills/trade-stats-lookup/references/data-notes.md) (Korean)

</details>

## 🔒 Boundaries

**No company-level data.** Korean customs declarations are confidential by law, so
no source gives you exporter name × product × value. Buyer names require paid
bill-of-lading data (Panjiva, ImportYeti, Volza) from countries that publish B/Ls —
the US and India do; Korea, the EU, Japan, and China do not.

**One optional feature needs a key.** Everything above is keyless. Only the HSK
10-digit lookup (`domestic`) uses Korea Customs Service data, which has no public
unauthenticated tier. It is free to register and the skill prints step-by-step
instructions when you actually need it. What it buys you: your exact product line
rather than a 6-digit bucket, a unit price you can read as price rather than
product mix, and figures roughly a year fresher than Comtrade. It does **not**
produce shares or market size — no country publishes 10-digit import statistics,
so that denominator does not exist.

**Export procedures, tariffs, and certification are not verified here.** Claude can
answer from general knowledge, but this tool did not check it. US tariff policy has
been changing since 2025 — verify at [US HTS](https://hts.usitc.gov) and with your
customs authority.

<details>
<summary><b>🛠 CLI · Development (expand)</b></summary>

```bash
cd plugins/trade-stats/skills/trade-stats-lookup/scripts
python3 analyze.py market   --hs 3907    # rank a known shortlist (3-5 min)
python3 analyze.py discover --hs 3304    # scan all 225 reporters (1-2 min)
python3 fetch_comtrade.py hs-search "화장품"   # Korean product name in, HS codes out
```

Requires `python3` 3.11+. Responses cache for 7 days under
`~/.cache/trade-stats-lookup/`. This runs against UN Comtrade's free
unauthenticated tier: requests are paced, `Retry-After` is honored, and the
interval cannot be set below one second. Raise `TRADE_STATS_MIN_INTERVAL` on a
shared office IP; set `TRADE_STATS_CONTACT` so the publisher can reach you.

```bash
python3 tests/record_fixtures.py   # once — fixtures are gitignored
./tests/run_tests.sh               # 151 offline tests, no network
./tests/run_tests.sh --live        # + real API contract tests
./package.sh                       # verify, then build the zip
```

Tests replay recorded API responses through the skill's own cache layer, so there
is no mock layer to drift out of sync, and an un-fixtured request fails loudly
instead of silently going to the network. The live contract suite is the
early-warning system for upstream schema changes — the offline suite replays
recordings and cannot catch those. It runs weekly in CI and opens an issue on
failure.

Skill triggering cannot be covered by unit tests; see
[`tests/TRIGGER_TESTS.md`](tests/TRIGGER_TESTS.md).

</details>

## 🔬 How far this is verified

This tool sells numbers, so here is what was checked and what was not.

**Checked**

- **Against figures the Korean government published.** Korea's 2024 total exports:
  USD 683,764M per Korea Customs Service, USD 683,127,018,292 per this tool — a
  0.09% gap. HS 3304 matches to the digit. This comparison runs weekly in CI and
  opens an issue when it drifts.
- **174 offline tests** replaying recorded responses, plus live contract tests that
  fire when UN Comtrade changes its API shape.
- **A silent inflation bug was caught this way.** Through v0.2.7, a reporter whose
  breakdown rows filled the response cap could report up to 5× its real imports
  (Slovenia HS3304: USD 619M against an actual 124M). v0.3.0 removed the cause;
  partner-sum reconciliation now catches the class.
- **31 trigger sentences** thrown at real sessions to check the skill activates —
  and stays quiet when it should. Twelve of them are verbatim questions real users
  posted in public Q&A, not phrasings the author invented.

**Not checked**

- **No external users yet.** Everything above was verified by the author.
- **Claude Code only.** Cowork and claude.ai select skills differently; triggering
  there is unverified.
- Tariff figures (WITS) are indicative. Verify before you clear customs.

Seeing a number that looks wrong is the most useful thing you can report — there is
[a template for it](https://github.com/bonghyunyang/trade-skills/issues/new?template=wrong-number.yml)
that asks for the HS code, the country, and what you expected instead. If it
reproduces, it becomes a test. Same for
[a question that should have activated the skill and did not](https://github.com/bonghyunyang/trade-skills/issues/new?template=skill-did-not-trigger.yml)
— paste your wording unedited; the rough version is the useful one.

## 🗺 Roadmap

| Feature | Status |
|---|---|
| Market prioritisation (`market`) | ✅ v0.1 |
| Reverse product lookup (`products`) | ✅ v0.1 |
| Tariff comparison (`tariff`) | ✅ v0.1 |
| Worldwide discovery (`discover`) | ✅ v0.2 |
| Absolute attractiveness score | ✅ v0.2 |
| HSK 10-digit via Korea Customs (`domestic`) | ✅ v0.2 (optional key) |
| Mixed 4-digit guard | ✅ v0.3.2 |
| Buyer candidate discovery | Under review (free paths reach trade fairs, not names) |
| Cold-email drafts in the buyer's language | Planned |

## 📄 License

Code is MIT ([`LICENSE`](LICENSE)).

**Bundled reference data is not MIT** ([`NOTICE`](NOTICE)). The commodity
descriptions in `hs.json` are World Customs Organization Harmonized System
nomenclature, obtained via UN Comtrade's public reference endpoint; that does not
by itself convey WCO redistribution rights. Check your position before forking or
shipping commercially.

Trade statistics from [United Nations Comtrade](https://comtrade.un.org).
The United Nations does not endorse this project.

---

<div align="center">

**Market selection by evidence, not instinct.**

</div>
