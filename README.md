# trade-skills

**"우리 제품, 어느 나라부터 팔러 갈까?"** 를 데이터로 정해주는 Claude 스킬입니다.

해외영업 담당자를 위해 만들었습니다. 터미널을 열 필요도, 프로그램을 설치할 필요도,
회원가입을 할 필요도 없습니다.

**한국어** · [English](#english)

---

## ⚠️ 먼저 읽어주세요

이 세 가지를 모르고 쓰면 **숫자는 맞는데 결론이 반대로** 갈 수 있습니다.

### 1. 여기 나오는 "점유율"은 수입품 중에서의 점유율입니다

시장 점유율이 아닙니다. **현지 공장에서 만들어 파는 물량은 이 통계에 아예 없습니다.**

> "미국 화장품 한국 점유율 24.8%"
> = 미국이 **수입하는** 화장품 중 한국산이 24.8%
> ≠ 미국 화장품 시장의 1/4이 한국산

미국은 현지 화장품 회사가 강한 나라라(P&G, Estée Lauder 등) 실제 시장 점유율은 훨씬 낮습니다.
식품·자동차·철강·화장품처럼 **현지 생산이 강한 품목일수록 이 차이가 큽니다.**
사업계획서나 보고서에 쓰실 때 "수입 기준"이라고 꼭 함께 적어주세요.

같은 이유로 표의 "현지 총수입"도 그 나라의 시장 규모가 아닙니다.

### 2. 바이어 회사 이름은 나오지 않습니다

도구가 부족해서가 아니라 **법 때문입니다.** 한국은 관세법상 수출입 신고정보가 비밀유지 대상이라,
어느 회사가 무엇을 얼마에 수출했는지가 어디에도 공개되지 않습니다. 관세청도 무역협회도 마찬가지입니다.
다른 무료 도구를 찾아 헤매실 필요 없습니다.

이 스킬이 답해주는 건 **"어느 나라에 바이어를 찾으러 갈지"** 입니다. 바이어 발굴의 바로 앞 단계입니다.

### 3. 수출 절차·관세·인증 정보는 이 스킬이 검증한 게 아닙니다

Claude가 아는 일반 지식으로 답할 수는 있지만, 이 도구가 확인해준 내용이 아닙니다.
**특히 관세율은 2025년 이후 계속 바뀌고 있으니 반드시 따로 확인하세요.**

- 미국 HTS: https://hts.usitc.gov
- 관세청 FTA 포털 · 무역협회 · KOTRA 상담

---

## 왜 만들었나

해외영업을 하면서 가장 답답했던 게 세 가지였습니다.

**첫째, 시장조사가 너무 오래 걸립니다.** "어느 나라부터 뚫을지"를 정하려면
KOTRA 보고서, 무역협회 K-stat, ITC Trade Map을 각각 열어 HS코드를 손으로 넣고,
나온 숫자를 엑셀에 옮겨 붙여야 합니다. 품목 하나에 반나절이 갑니다.
그런데 정작 비교하고 싶은 건 "우리가 지금 어디서 점유율을 잃고 있고, 어디가
아직 여지가 있나" 같은 단순한 질문입니다.

**둘째, 그러다 보니 결국 감으로 정합니다.** 전시회에서 명함을 많이 받은 나라,
지난번에 인콰이어리가 왔던 나라, 대표님이 가보고 싶어 하는 나라.
근거를 대라고 하면 "시장이 크니까" 정도입니다. 시장이 실제로 크고 있는지,
그 성장을 누가 가져가고 있는지, 우리 자리가 남아 있는지는 확인하지 않은 채로요.

**셋째, 바이어 발굴은 그다음 문제인데 앞 단계에서 이미 지칩니다.**
시장을 잘못 고르면 컨택 리스트가 아무리 길어도 소용이 없습니다.
그런데 현실은 앞 단계를 대충 넘기고 바이어 리스트부터 만듭니다.

### 그래서 이렇게 만들었습니다

**"어느 시장을 뚫을지"를 감이 아니라 숫자로 정하는 것** 하나에 집중했습니다.
질문 한 줄에 80초면 답이 나오게, HS코드를 몰라도 되게, 그리고 무엇보다
**그 숫자를 어떻게 읽어야 하는지까지** 같이 나오게 만들었습니다.

숫자만 뽑아주는 도구는 이미 있습니다. 문제는 그 숫자가 조용히 틀린 결론으로
이끄는 경우입니다. 수입 점유율을 시장 점유율로 착각하거나, 중계무역 허브를
유망 시장으로 오인하거나, 데이터가 없는 나라를 나쁜 시장으로 읽는 식으로요.
그래서 이 도구는 **경고를 숨기지 않습니다.** 위의 ⚠️ 항목들이 리포트 안에도
그대로 들어갑니다.

**바이어 발굴은 의도적으로 넣지 않았습니다.** 한국은 법적으로 기업 단위 데이터가
공개되지 않아서 무료로는 불가능하고, 되는 척하는 게 가장 나쁘다고 봤습니다.
대신 "어느 나라에 바이어를 찾으러 갈지"까지를 정확히 하는 걸 목표로 했습니다.

---

## 어떻게 쓰나요

Claude에게 **한국어로 그냥 물어보면** 됩니다.

```
"화장품 미국 시장 어때?"
"이차전지 어느 나라부터 뚫어야 해?"
"베트남에 라면 팔면 경쟁 심한가?"
"우리 품목 어디부터 봐야 할까"
```

HS코드를 몰라도 됩니다. **품목명을 한국어로 말하면** 코드 후보를 찾아서
"이 코드로 볼까요?" 하고 확인받은 뒤 진행합니다.

약 80초 뒤에 순위표와 근거, 그리고 엑셀에서 바로 열리는 CSV가 나옵니다.

## 무엇이 나오나요

| 항목 | 뜻 |
|---|---|
| 현지 총수입 | 그 나라가 전 세계에서 수입하는 금액 |
| **시장 CAGR** | **그 시장**이 커지는 속도 |
| 한국 수출액·CAGR | **우리**가 그 나라에 파는 금액과 속도 |
| 한국 점유율 | 수입품 중 한국 비중 (위 ⚠️1 참고) |
| 1위 공급국 | 지금 그 자리를 차지한 나라. 60% 이상이면 ⚠️ 표시 |
| 매력도 | 시장규모 40% + 시장성장 35% + 점유율 여유 25% |

**가장 쓸모 있는 건 "시장 CAGR"과 "한국 수출 CAGR"의 차이입니다.**

- 시장은 크는데 우리 수출이 줄고 있다 → **점유율을 뺏기는 중**
- 시장은 주는데 우리 수출만 늘고 있다 → **중계무역 경유일 가능성** (실제 소비지가 다른 나라)

### 예시

```
| # | 국가  | 매력도 | 현지 총수입 | 시장 CAGR | 한국 수출 | 한국 CAGR | 한국 점유율 | 1위 공급국 |
|---|-------|--------|-------------|-----------|-----------|-----------|-------------|------------|
| 1 | 대만  | 75.3   | $11.4억     | +36.2%    | $1.1억    | +11.5%    | 7.1%        | 중국 31%   |
| 2 | 중국  | 72.0   | $70.8억     |  +1.6%    | $10.4억   |  -3.5%    | 16.0%       | 한국 16%   |
| 3 | 인도  | 62.1   | $27.0억     |  +4.1%    | $3.5억    |  -5.7%    | 14.1%       | 중국 34%   |
```

## 설치

### Claude Code를 쓰신다면

```
/plugin marketplace add bonghyunyang/trade-skills
/plugin install trade-stats@trade-skills
```

### Cowork · claude.ai를 쓰신다면

[Releases](https://github.com/bonghyunyang/trade-skills/releases)에서 `trade-stats-lookup.zip`을 받아
**Settings → Capabilities → Skills** 에서 업로드하세요.

### 필요한 것

- 인터넷 연결
- **API 키 발급 불필요** — UN Comtrade 공개 데이터를 씁니다
- (직접 명령어로 돌릴 때만) `python3` 3.11 이상

---

## 숫자를 읽을 때 더 알아두면 좋은 것

- **매력도 점수는 절대 등급이 아닙니다.** 이번에 함께 조회한 국가들 사이의 상대값이라,
  관계없는 나라 하나를 넣고 빼는 것만으로 순위가 뒤집힐 수 있습니다.
  판단이 갈리면 비교 대상을 바꿔 두세 번 돌려보고, **순위가 유지되는 나라**를 믿으세요.
- **"점유율 여유"가 크다고 빈 시장이 아닙니다.** 한국 점유율이 낮아도 그 자리에 이미
  다른 나라가 앉아 있을 수 있습니다. 그래서 표에 1위 공급국을 같이 보여주고,
  60% 이상 과점이면 ⚠️ 를 붙입니다.
- **순위에서 빠진 나라는 "나쁜 시장"이 아닙니다.** 데이터가 없어 측정을 못 한 겁니다.
- **단가(금액÷중량) 변화는 원인을 알 수 없습니다.** 가격이 오른 건지, 비싼 제품 비중이
  늘어난 건지 구분되지 않습니다. "프리미엄화됐다"고 읽으면 대개 틀립니다.
- **한국 수출액은 FOB, 상대국 수입액은 CIF** 기준이라 같은 거래도 금액이 다릅니다.
- **HS 6자리까지만** 볼 수 있습니다. 10자리(HSK)는 관세청 오픈API가 따로 필요합니다.
- 최신 데이터는 나라마다 2~6개월 늦게 들어옵니다. 스킬이 자동으로 있는 데까지 물러나 조회합니다.

더 자세한 내용: [`data-notes.md`](plugins/trade-stats/skills/trade-stats-lookup/references/data-notes.md)

## 직접 명령어로 쓰기

```bash
cd plugins/trade-stats/skills/trade-stats-lookup/scripts

python3 analyze.py market --hs 3907                      # 상위 10개 교역국
python3 analyze.py market --hs 3304 --countries 베트남,인도 --monthly 24
python3 fetch_comtrade.py hs-search "화장품"             # HS코드 찾기
python3 fetch_comtrade.py rank   --hs 3907 --year 2025
python3 fetch_comtrade.py mirror --hs 3907 --importer VN --year 2024
```

조회 결과는 `~/.cache/trade-stats-lookup/`에 7일간 보관되어, 같은 질문은 즉시 답합니다.

무료 공개 API라 요청 간격을 두고 호출합니다. 사내에서 여러 명이 같은 인터넷을 쓴다면
`TRADE_STATS_MIN_INTERVAL=6` 처럼 간격을 늘려주세요.

## 개발

```bash
python3 tests/record_fixtures.py   # 최초 1회 (픽스처는 레포에 없습니다)
./tests/run_tests.sh               # 오프라인 105개, 네트워크 불필요
./tests/run_tests.sh --live        # + 실제 API 계약 검증
./package.sh                       # 검증 후 배포용 zip 생성
```

트리거 테스트(스킬이 실제로 호출되는지)는 코드로 잡을 수 없어 별도 절차로 돕니다 —
[`tests/TRIGGER_TESTS.md`](tests/TRIGGER_TESTS.md). 자세한 내용은 [`tests/README.md`](tests/README.md).

## 레포 구조

```
trade-skills/
├─ .claude-plugin/marketplace.json
├─ plugins/trade-stats/skills/trade-stats-lookup/
│  ├─ SKILL.md
│  ├─ scripts/      comtrade.py · fetch_comtrade.py · analyze.py · refresh_reference.py
│  └─ references/   한국어 HS 색인, 국가 코드, 데이터 주의사항
├─ tests/           오프라인 105개 + 라이브 계약 7개
├─ package.sh       검증 + zip 생성
└─ README.md
```

## 로드맵

| 스킬 | 상태 |
|---|---|
| `trade-stats-lookup` | ✅ v0.1 |
| `trade-market-rank` | 국가 우선순위 스코어링 심화 |
| `trade-buyer-find` | 바이어 발굴 — 유료 B/L 데이터 필요 |
| `trade-outreach-draft` | 현지어 콜드메일 초안 |
| `trade-pipeline-sheet` | 파이프라인 기록 관리 |

## 라이선스와 데이터 출처

**코드**는 MIT입니다 ([`LICENSE`](LICENSE)).

**함께 들어 있는 참조 데이터는 MIT가 아닙니다.** 출처와 조건은 [`NOTICE`](NOTICE)에 정리했습니다.

- `areas.json`, `hs.json` — UN Comtrade 공개 참조 파일
- `hs.json`의 품목 설명은 **세계관세기구(WCO)가 저작권을 주장하는 HS 노멘클레이처**입니다.
  UN Comtrade에서 받았다는 사실이 제3자 재배포 권한을 주지는 않습니다. 포크하거나 상용으로
  쓰시기 전에 확인하세요.
- 한국어 색인(`hs_ko.json` 등)은 이 프로젝트의 작업물이고 MIT입니다.

무역통계 출처: United Nations Comtrade (https://comtrade.un.org).
유엔은 이 프로젝트를 보증하지 않습니다.

---

<a id="english"></a>

# trade-skills — English

[한국어](#trade-skills) · **English**

A Claude skill that answers **"which market should we go after first?"** from UN
Comtrade data — no API key, no dependencies, no signup.

Built for Korean exporters, so the interface and reports are in Korean.

---

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

`reporter` is fixed to Korea, and the HS-code index is Korean-language. The data
layer itself is reporter-agnostic — supporting other reporting countries is a
tracked limitation, not a design decision.

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
