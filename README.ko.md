# trade-skills

해외영업 담당자가 **리드 발굴 전 단계인 "어느 시장을 뚫을지"** 를 결정할 수 있게 해주는 Claude 스킬 묶음.

터미널을 열 필요 없다. Claude에게 한국어로 물어보면 된다.

>  "화장품 어느 나라부터 뚫어야 해?"
>  "이차전지 상위 교역국 비교해줘"
>  "3907 베트남 시장 어때?"

HS코드를 몰라도 된다. 품목명을 한국어로 말하면 코드를 찾아 확인해준다.

## 지금 들어 있는 것

| 스킬 | 하는 일 | 인증키 |
|---|---|---|
| `trade-stats-lookup` | HS코드별·국가별 수출입 통계, 경쟁국 점유율, 시장 매력도 순위 | **불필요** |

## 설치

### Claude Code — 마켓플레이스

```
/plugin marketplace add bonghyunyang/trade-skills
/plugin install trade-stats@trade-skills
```

### Claude Code — 로컬

```bash
cp -r plugins/trade-stats/skills/trade-stats-lookup ~/.claude/skills/
```

### Cowork / claude.ai

```bash
./package.sh
```
생성된 `dist/trade-stats-lookup.zip`을 Settings → Capabilities → Skills 에서 업로드한다.

## 필요한 것

- `python3` **3.11 이상** — 표준 라이브러리만 쓴다. `pip install` 없다. (3.11·3.12·3.13 검증)
  - macOS 기본 파이썬은 3.9(EOL)라 로컬에서 직접 돌리려면 `brew install python@3.11` 필요.
    Cowork/claude.ai로 쓰면 해당 없음.
- 인터넷 연결
- **API 키 발급 없음.** UN Comtrade 공개 엔드포인트를 쓴다.

## 무엇이 나오나

HS코드 하나를 주면 기본적으로 **한국 전체 교역 상위 10개국**을 스캔한다(약 80초).

- 국가별 한국 수출액·중량 3년 시계열
- 단가 추이 — 프리미엄화 중인지 저가경쟁 중인지
- 상대국 총수입 규모와 **공급국 점유율** (한국이 몇 위인지)
- 시장 매력도 점수 = 규모 40% + 성장률 35% + 점유율 여유 25%
- 월별 수집 시 계절성과 최근 12개월 YoY
- CSV 3종 + 한국어 마크다운 리포트

CSV는 UTF-8 BOM이라 엑셀에서 바로 열린다.

### HS코드 찾기

한국어 품목명을 그대로 넣으면 된다. 챕터 96개 전체와 주요 품목 123개가 색인돼 있다.

```
"화장품"    → 3304 (기초·색조화장품)
"이차전지"   → 8507 (축전지)
"자동차부품" → 8708
"라면"      → 1902
```

### 예시 출력

```
| # | 국가 | 매력도 | 한국 수출액 | CAGR  | 현지 총수입 | 한국 점유율 | 한국 순위 |
|---|------|--------|-------------|-------|-------------|-------------|-----------|
| 1 | 중국 | 82.9   | $10.4억     | -3.5% | $70.8억     | 16.0%       | 1         |
| 2 | 대만 | 75.3   | $1.1억      | +11.5%| $11.4억     | 7.1%        | 5         |
| 3 | 미국 | 74.9   | $7.4억      | -4.2% | $42.6억     | 20.0%       | 1         |
```

## 알고 써야 할 한계

- **기업 단위 데이터는 없다.** 한국은 관세법상 신고정보가 비밀유지 대상이라 기업명 × 품목 × 금액이
  공개되지 않는다. "어느 회사가 수출하는지"는 답할 수 없다. 바이어 실명은 B/L 공개국(미국·인도 등)의
  유료 데이터가 필요하다.
- **HS 6단위까지.** 10단위(HSK)는 관세청 오픈API가 필요하다.
- 한국 수출액은 FOB, 상대국 수입액은 CIF 기준이라 같은 거래도 금액이 다르다.
- 최신 데이터는 보고 지연으로 2~6개월 비어 있을 수 있다.

자세한 내용은 `plugins/trade-stats/skills/trade-stats-lookup/references/data-notes.md`.

## 직접 CLI로 쓰기

```bash
cd plugins/trade-stats/skills/trade-stats-lookup/scripts

# 상위 10개 교역국 스캔
python3 analyze.py market --hs 3907

# 특정 국가 + 월별 계절성
python3 analyze.py market --hs 3304 --countries 베트남,인도 --monthly 24

# HS코드 찾기 — 한국어 그대로
python3 fetch_comtrade.py hs-search "화장품"
python3 fetch_comtrade.py hs-search "이차전지" --level 4

# 단발 조회
python3 fetch_comtrade.py rank --hs 3907 --year 2025
python3 fetch_comtrade.py mirror --hs 3907 --importer VN --year 2024
```

응답은 `~/.cache/trade-stats-lookup/`에 7일 캐시된다.

## 레포 구조

```
trade-skills/
├─ .claude-plugin/marketplace.json
├─ plugins/trade-stats/
│  ├─ .claude-plugin/plugin.json
│  └─ skills/trade-stats-lookup/
│     ├─ SKILL.md
│     ├─ scripts/
│     │  ├─ comtrade.py           # API 클라이언트 · 캐시 · 백오프 · 코드 해석
│     │  ├─ fetch_comtrade.py     # 단발 조회 CLI
│     │  ├─ analyze.py            # 시장 리포트 생성
│     │  └─ refresh_reference.py  # 참조 스냅샷 갱신
│     └─ references/
│        ├─ hs_ko.json             # 한국어 HS 색인 (챕터 96 + 품목 123)
│        ├─ hs-codes.md           # 한국어 → 영어 검색어 힌트
│        ├─ country-codes.md      # 국가 코드 · Comtrade 표기 함정
│        ├─ data-notes.md         # 출처 · 한계 · 다음 Phase
│        ├─ areas.json            # 지역 312개 (폐지국 플래그 포함)
│        ├─ hs.json               # HS 2/4/6단위 8,262개
│        ├─ country_aliases_ko.json  # 한글/영문 입력 → 코드
│        ├─ country_names_ko.json    # 코드 → 한글 표기
│        └─ kr-top-partners.json     # 한국 교역 상위 20개국 스냅샷
├─ tests/                          # 오프라인 87개 + 라이브 계약 7개
├─ package.sh                      # 배포 검증 + zip 생성
└─ README.ko.md
```

## 개발

```bash
./tests/run_tests.sh          # 오프라인 스위트 (~0.1초, 네트워크 불필요)
./tests/run_tests.sh --live   # + 실제 API 계약 검증 (~35초)
./package.sh                  # 검증 통과 시 dist/trade-stats-lookup.zip 생성
```

자세한 내용은 `tests/README.md`.

트리거 테스트(스킬이 실제로 호출되는지)는 코드로 잡을 수 없어 별도 절차로 돌린다 —
`tests/TRIGGER_TESTS.md`. 최근 실행 결과는 긍정 6/6, 오발동 0.

## 로드맵

| 스킬 | 상태 |
|---|---|
| `trade-stats-lookup` | ✅ v0.1 |
| `trade-market-rank` | 국가 우선순위 스코어링 심화 |
| `trade-buyer-find` | 바이어 발굴 — 유료 B/L 데이터 필요 |
| `trade-outreach-draft` | 현지어 콜드메일 초안 |
| `trade-pipeline-sheet` | 파이프라인 기록 관리 |

관세청 오픈API(HS 10단위·빠른 월별)를 붙이려면 인증키를 서버에만 두는 프록시가 필요하다.
사용자에게 키 발급을 요구하지 않는 것이 이 프로젝트의 설계 원칙이다.

## 라이선스와 데이터 출처

**코드**는 MIT다 (`LICENSE`).

**번들된 참조 데이터는 MIT가 아니다.** 출처와 조건은 `NOTICE`에 정리돼 있다.

- `areas.json`, `hs.json` — UN Comtrade 공개 참조 파일. `refresh_reference.py codes`로 재생성 가능.
- `hs.json`의 품목 설명은 **세계관세기구(WCO)가 저작권을 주장하는 HS 노멘클레이처**다.
  UN Comtrade에서 받았다는 사실이 제3자 재배포 권한을 주지는 않는다. 포크·상용 배포 전에 확인할 것.
- `hs_ko.json` 등 한국어 색인은 이 프로젝트의 작업물이고 MIT다.
- `tests/fixtures/cache/`는 UN Comtrade 원본 응답이라 **레포에 포함하지 않는다.**
  기여자는 `python3 tests/record_fixtures.py`로 로컬 생성한다.

무역통계 출처: United Nations Comtrade (https://comtrade.un.org).
유엔은 이 프로젝트를 보증하지 않는다.
