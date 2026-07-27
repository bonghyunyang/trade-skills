<div align="center">

# trade-skills

### 감으로 정하던 수출 시장을, 숫자로 정합니다.

품목명 한 줄이면 됩니다. HS코드도, API 키도, 회원가입도 필요 없습니다.

[![Claude Code](https://img.shields.io/badge/Claude%20Code-plugin-6f42c1)](https://claude.com/claude-code)
[![Cowork](https://img.shields.io/badge/Cowork%20%C2%B7%20claude.ai-skill-0ea5e9)](https://claude.ai)
[![No API key](https://img.shields.io/badge/API%20key-not%20required-16a34a)](#install-ko)
[![Tests](https://github.com/bonghyunyang/trade-skills/actions/workflows/tests.yml/badge.svg)](https://github.com/bonghyunyang/trade-skills/actions/workflows/tests.yml)
[![License](https://img.shields.io/badge/license-MIT-black)](LICENSE)

**한국어** · [English](#english)

</div>

---

> [!WARNING]
> **이 도구를 쓰기 전에 30초만 읽어주세요.** 모르고 쓰면 숫자는 맞는데 결론이 반대로 갑니다.
>
> - **여기 나오는 "점유율"은 수입품 중 비중입니다.** 시장 점유율이 아닙니다 — 현지 공장 물량은 통계에 없습니다.
> - **바이어 회사 이름은 나오지 않습니다.** 도구 문제가 아니라 관세법상 비공개입니다.
> - **수출 절차·관세 정보는 이 도구가 검증한 게 아닙니다.** 특히 관세율은 반드시 따로 확인하세요.
>
> 자세한 설명 → [숫자를 읽는 법](#reading-ko)

---

<a id="install-ko"></a>

## ⚡ 설치

**Claude Code**

```
/plugin marketplace add bonghyunyang/trade-skills
/plugin install trade-stats@trade-skills
```

**Cowork · claude.ai**

[Releases](https://github.com/bonghyunyang/trade-skills/releases)에서 `trade-stats-lookup.zip`을 받아
**Settings → Capabilities → Skills** 에서 업로드하세요.

인터넷 연결만 있으면 됩니다. API 키 발급도, `pip install`도 없습니다.

## 💬 이렇게 물어보세요

> "화장품 미국 시장 어때?"

> "이차전지 어느 나라부터 뚫어야 해?"

> "베트남에 라면 팔면 경쟁 심한가?"

> "우리 품목 어디부터 봐야 할까"

HS코드를 몰라도 됩니다. **품목명을 한국어로 말하면** 코드 후보를 찾아
"이 코드로 볼까요?" 하고 확인받은 뒤 진행합니다. 약 80초 뒤 답이 나옵니다.

## 📊 무엇이 나오나요

```
| # | 국가  | 매력도 | 현지 총수입 | 시장 CAGR | 한국 수출 | 한국 CAGR | 한국 점유율 | 1위 공급국 |
|---|-------|--------|-------------|-----------|-----------|-----------|-------------|------------|
| 1 | 대만  | 75.3   | $11.4억     | +36.2%    | $1.1억    | +11.5%    | 7.1%        | 중국 31%   |
| 2 | 중국  | 72.0   | $70.8억     |  +1.6%    | $10.4억   |  -3.5%    | 16.0%       | 한국 16%   |
| 3 | 인도  | 62.1   | $27.0억     |  +4.1%    | $3.5억    |  -5.7%    | 14.1%       | 중국 34%   |
```

여기에 국가별 공급국 상세표, 엑셀에서 바로 열리는 CSV 3종, 한국어 리포트가 함께 나옵니다.

**가장 쓸모 있는 건 두 CAGR의 차이입니다.**

| 이런 모양이면 | 이런 뜻입니다 |
|---|---|
| 시장 ↑ · 우리 수출 ↓ | **점유율을 뺏기는 중** |
| 시장 ↓ · 우리 수출 ↑ | **중계무역 경유 가능성** (실제 소비지가 다른 나라) |
| 시장 ↑ · 우리 수출 ↑↑ | **점유율을 얻는 중** — 지금 밀어야 할 시장 |

## 🆚 이 도구 없이 vs 함께

| | 기존 방식 | trade-skills |
|---|---|---|
| 시장 하나 비교 | KOTRA · K-stat · Trade Map을 각각 열고 엑셀로 옮김 (반나절) | 질문 한 줄, 80초 |
| HS코드 | 직접 찾아 입력 | "화장품"이라고 말하면 됨 |
| 비교 국가 수 | 하나씩 반복 | 기본 10개국 동시 |
| 성장률 | 우리 수출 실적만 봄 | **시장 성장률과 나란히** 비교 |
| 경쟁 구도 | 따로 조사 | 1위 공급국·과점 여부 자동 표시 |
| 함정 | 알아서 걸러야 함 | **리포트가 먼저 경고** |

## 🤔 왜 만들었나

해외영업을 하면서 답답했던 게 세 가지였습니다.

**시장조사가 너무 오래 걸립니다.** "어느 나라부터 뚫을지" 하나 정하려고
KOTRA 보고서, 무역협회 K-stat, ITC Trade Map을 각각 열어 HS코드를 손으로 넣고
엑셀에 옮겨 붙입니다. 정작 알고 싶은 건 "우리가 어디서 점유율을 잃고 있고,
어디가 아직 여지가 있나" 정도인데요.

**그래서 결국 감으로 정합니다.** 전시회에서 명함 많이 받은 나라, 인콰이어리가 왔던 나라.
근거를 대라면 "시장이 크니까". 시장이 실제로 크고 있는지, 그 성장을 누가 가져가는지,
우리 자리가 남아 있는지는 확인하지 않은 채로요.

**바이어 발굴은 그다음인데 앞 단계에서 이미 지칩니다.** 시장을 잘못 고르면
컨택 리스트가 길어도 소용없는데, 현실은 앞 단계를 대충 넘기고 리스트부터 만듭니다.

그래서 **"어느 시장을 뚫을지"를 숫자로 정하는 것** 하나에 집중했습니다.

숫자만 뽑아주는 도구는 이미 있습니다. 문제는 그 숫자가 **조용히 틀린 결론으로**
이끄는 경우입니다. 수입 점유율을 시장 점유율로 착각하거나, 중계무역 허브를 유망 시장으로
오인하거나, 데이터가 없는 나라를 나쁜 시장으로 읽는 식으로요.
그래서 이 도구는 **경고를 문서에 묻지 않고 리포트 본문에 넣습니다.**

<a id="reading-ko"></a>

## ⚠️ 숫자를 읽는 법

### 1. "점유율"은 수입품 중 비중입니다

> "미국 화장품 한국 점유율 24.8%"
> = 미국이 **수입하는** 화장품 중 한국산이 24.8%
> ≠ 미국 화장품 시장의 1/4이 한국산

현지 공장에서 만들어 파는 물량은 이 통계에 **아예 없습니다.** 미국은 현지 화장품
회사가 강해서(P&G, Estée Lauder 등) 실제 시장 점유율은 훨씬 낮습니다.
식품·자동차·철강·화장품처럼 현지 생산이 강한 품목일수록 차이가 큽니다.

보고서에 쓰실 때 **"수입 기준"이라고 꼭 함께 적어주세요.** 같은 이유로 표의
"현지 총수입"도 그 나라의 시장 규모가 아닙니다.

### 2. 매력도 점수는 절대 등급이 아닙니다

이번에 함께 조회한 국가들 사이의 **상대값**입니다. 관계없는 나라 하나를 넣고 빼는
것만으로 순위가 뒤집힐 수 있습니다. 판단이 갈리면 비교 대상을 바꿔 두세 번 돌려보고
**순위가 유지되는 나라**를 믿으세요.

### 3. "점유율 여유"가 크다고 빈 시장이 아닙니다

한국 점유율이 낮아도 그 자리에 이미 다른 나라가 앉아 있을 수 있습니다.
그래서 표에 1위 공급국을 같이 보여주고, 60% 이상 과점이면 ⚠️ 를 붙입니다.

<details>
<summary><b>그 외 알아두면 좋은 것 (펼치기)</b></summary>

- **순위에서 빠진 나라는 "나쁜 시장"이 아닙니다.** 데이터가 없어 측정을 못 한 겁니다.
- **단가(금액÷중량) 변화는 원인을 알 수 없습니다.** 가격이 오른 건지, 비싼 제품
  비중이 늘어난 건지 구분되지 않습니다. "프리미엄화됐다"고 읽으면 대개 틀립니다.
- **한국 수출액은 FOB, 상대국 수입액은 CIF** 기준이라 같은 거래도 금액이 다릅니다.
  두 소스를 섞어 점유율을 계산하면 안 됩니다.
- **HS 6자리까지만** 볼 수 있습니다. 10자리(HSK)는 관세청 오픈API가 따로 필요합니다.
- 최신 데이터는 나라마다 **2~6개월 늦게** 들어옵니다. 자동으로 있는 데까지 물러나 조회합니다.
- 한국 신고 수출액과 상대국 신고 수입액이 크게 어긋나면(2배 이상) **리포트가 경고합니다.**
  제3국 경유 재수출이나 상대국 통계 커버리지 부족 신호입니다.

전체 내용 → [`data-notes.md`](plugins/trade-stats/skills/trade-stats-lookup/references/data-notes.md)

</details>

## 🔒 하지 않는 것

**바이어 기업명은 제공하지 않습니다.** 도구가 부족해서가 아니라 **법 때문입니다.**
한국은 관세법상 수출입 신고정보가 비밀유지 대상이라, 어느 회사가 무엇을 얼마에
수출했는지가 어디에도 공개되지 않습니다. 관세청도 무역협회도 마찬가지입니다.
다른 무료 도구를 찾아 헤매실 필요 없습니다.

기업 단위 데이터는 **선하증권(B/L)을 공개하는 나라**에서만 나옵니다 — 미국·인도 등.
유료 서비스(Panjiva · ImportYeti · Volza)를 씁니다. 한국·EU·일본·중국은 안 나옵니다.

**수출 절차·관세·인증은 이 도구가 검증하지 않습니다.** Claude가 아는 일반 지식으로
답할 수는 있지만 확인된 내용이 아닙니다. 특히 관세율은 2025년 이후 계속 바뀌고 있으니
[미국 HTS](https://hts.usitc.gov), 관세청 FTA 포털, KOTRA에서 반드시 확인하세요.

<details>
<summary><b>🛠 직접 명령어로 쓰기 · 개발 (펼치기)</b></summary>

### CLI

```bash
cd plugins/trade-stats/skills/trade-stats-lookup/scripts

python3 analyze.py market --hs 3907                      # 상위 10개 교역국
python3 analyze.py market --hs 3304 --countries 베트남,인도 --monthly 24
python3 fetch_comtrade.py hs-search "화장품"             # HS코드 찾기
python3 fetch_comtrade.py rank   --hs 3907 --year 2025
python3 fetch_comtrade.py mirror --hs 3907 --importer VN --year 2024
```

`python3` 3.11 이상이 필요합니다. 조회 결과는 `~/.cache/trade-stats-lookup/`에 7일간
보관되어 같은 질문은 즉시 답합니다.

무료 공개 API라 요청 간격을 두고 호출합니다. 사내에서 여러 명이 같은 인터넷을 쓴다면
`TRADE_STATS_MIN_INTERVAL=6` 처럼 간격을 늘려주세요.

### 테스트

```bash
python3 tests/record_fixtures.py   # 최초 1회 (픽스처는 레포에 없습니다)
./tests/run_tests.sh               # 오프라인 105개, 네트워크 불필요
./tests/run_tests.sh --live        # + 실제 API 계약 검증
./package.sh                       # 검증 후 배포용 zip 생성
```

테스트는 녹화한 실제 API 응답을 스킬 자체 캐시로 재생합니다. mock 레이어가 없어
현실과 어긋날 일이 없고, 픽스처에 없는 요청은 조용히 네트워크로 새지 않고 실패합니다.

라이브 계약 테스트는 upstream 스펙 변경을 감지하는 조기경보입니다 — 오프라인 스위트는
녹화본을 재생하므로 정의상 이걸 잡을 수 없습니다. 매주 월요일 CI가 돌리고,
실패하면 자동으로 이슈를 엽니다.

스킬이 실제로 호출되는지(트리거)는 코드 테스트로 잡을 수 없어 별도 절차로 돕니다 —
[`tests/TRIGGER_TESTS.md`](tests/TRIGGER_TESTS.md) · [`tests/README.md`](tests/README.md)

### 레포 구조

```
trade-skills/
├─ .claude-plugin/marketplace.json
├─ plugins/trade-stats/skills/trade-stats-lookup/
│  ├─ SKILL.md
│  ├─ scripts/      comtrade.py · fetch_comtrade.py · analyze.py · refresh_reference.py
│  └─ references/   한국어 HS 색인, 국가 코드, 데이터 주의사항
├─ tests/           오프라인 105개 + 라이브 계약 7개
└─ package.sh       검증 + zip 생성
```

</details>

## 🗺 로드맵

| 스킬 | 상태 |
|---|---|
| `trade-stats-lookup` | ✅ v0.1 |
| `trade-market-rank` | 국가 우선순위 스코어링 심화 |
| `trade-buyer-find` | 바이어 발굴 — 유료 B/L 데이터 필요 |
| `trade-outreach-draft` | 현지어 콜드메일 초안 |
| `trade-pipeline-sheet` | 파이프라인 기록 관리 |

## 📄 라이선스

**코드**는 MIT입니다 ([`LICENSE`](LICENSE)).

**함께 들어 있는 참조 데이터는 MIT가 아닙니다** ([`NOTICE`](NOTICE)).
특히 `hs.json`의 품목 설명은 **세계관세기구(WCO)가 저작권을 주장하는 HS 노멘클레이처**입니다.
UN Comtrade에서 받았다는 사실이 제3자 재배포 권한을 주지는 않으니, 포크하거나 상용으로
쓰시기 전에 확인하세요. 한국어 색인(`hs_ko.json` 등)은 이 프로젝트의 작업물이고 MIT입니다.

무역통계 출처: [United Nations Comtrade](https://comtrade.un.org).
유엔은 이 프로젝트를 보증하지 않습니다.

---

<div align="center">
<a id="english"></a>

# trade-skills — English

### Pick your export market with numbers, not instinct.

Name a product. No HS code, no API key, no signup.

[한국어](#trade-skills) · **English**

</div>

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

Built for Korean exporters: `reporter` is fixed to Korea and the reports are in Korean.

## 📊 What you get

For one HS code, across ten markets by default (~80 seconds):

| Column | Meaning |
|---|---|
| Local total imports | What that country buys from the world |
| **Market CAGR** | How fast **the market** is growing |
| Korea's exports + CAGR | How fast **your** sales into it are growing |
| Korea's share | Share **of imports** — see the warning above |
| Top supplier | The incumbent, flagged ⚠️ at 60%+ |
| Attractiveness | size 40% + market growth 35% + share headroom 25% |

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
- **The score is relative, not absolute.** Every axis is min-max normalized across
  the countries in *that* query. Adding or removing an unrelated country can flip
  the ranking, not just the scores. Run it twice with different comparison sets and
  trust the countries that stay put.
- **Headroom is not an empty market.** A low Korean share may mean someone else is
  already sitting there, so the incumbent supplier is shown alongside it.

<details>
<summary><b>More caveats (expand)</b></summary>

- **A country excluded from the ranking is not a bad market** — it could not be measured.
- **Unit price is `value ÷ weight`.** Its movement mixes price changes with
  product-mix changes and the two cannot be separated above HS 6-digit. Not a
  quality signal.
- **FOB vs CIF.** Korea reports exports FOB, partners report imports CIF. Never
  compute a share by mixing the two.
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

**Export procedures, tariffs, and certification are not verified here.** Claude can
answer from general knowledge, but this tool did not check it. US tariff policy has
been changing since 2025 — verify at [US HTS](https://hts.usitc.gov) and with your
customs authority.

<details>
<summary><b>🛠 CLI · Development (expand)</b></summary>

```bash
cd plugins/trade-stats/skills/trade-stats-lookup/scripts
python3 analyze.py market --hs 3907
python3 fetch_comtrade.py hs-search "화장품"
```

Requires `python3` 3.11+. Responses cache for 7 days under
`~/.cache/trade-stats-lookup/`. This runs against UN Comtrade's free
unauthenticated tier: requests are paced, `Retry-After` is honored, and the
interval cannot be set below one second. Raise `TRADE_STATS_MIN_INTERVAL` on a
shared office IP; set `TRADE_STATS_CONTACT` so the publisher can reach you.

```bash
python3 tests/record_fixtures.py   # once — fixtures are gitignored
./tests/run_tests.sh               # 105 offline tests, no network
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

**감으로 정하던 시장 선정을, 근거 있는 결정으로.**

</div>
