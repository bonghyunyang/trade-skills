# HS코드 찾기

`references/hs.json`에 HS 2/4/6 단위 8,262개, `references/hs_ko.json`에 한국어 색인
(챕터 96개 전체 + 주요 품목 118개, 키워드 826개)이 들어 있다.

**한국어를 그대로 넣어라. 번역하지 마라.**

```bash
python3 scripts/fetch_comtrade.py hs-search "화장품"
python3 scripts/fetch_comtrade.py hs-search "이차전지" --level 4
```

결과의 `matched`가 `ko`면 한국어 색인이 잡은 것이고, `ko_keyword`에 실제로 걸린 단어가 담긴다.
한국어로 안 잡힐 때만 아래 번역표를 참고해 영어로 재검색한다.

## 자릿수 고르기

| 단위 | 의미 | 언제 |
|---|---|---|
| 2 | 류(Chapter) | 산업 전체 규모 감 잡을 때 |
| 4 | 호(Heading) | **기본값.** 시장 크기 비교에 적당 |
| 6 | 소호(Subheading) | 제품이 특정될 때. 국제 공통 최소 단위 |
| 8/10 | 국가별 세분 | **Comtrade에 없다.** 관세청 오픈API 필요 |

HS 6단위까지는 전 세계 공통이다. 8단위(EU CN), 10단위(한국 HSK, 미국 HTS)는 나라마다 다르게 쪼개므로
국제 비교 자체가 불가능하다. 사용자가 10단위를 주면 앞 6자리로 자르고 그 사실을 말한다.

## 한국어 → 영어 검색어 (한국어 색인에 없을 때만)

품목명을 그대로 직역하면 잘 안 걸린다. HS 설명은 법률 용어에 가깝다.

| 한국어 | 검색어 후보 |
|---|---|
| 화장품 | `beauty`, `cosmetic`, `skin care`, `perfume` |
| 기초화장품 | `beauty or make-up preparations` |
| 마스크팩 | `beauty` (별도 코드 없음 — 3304.99에 포함) |
| 플라스틱 원료 | `polymers`, `in primary forms` |
| 폴리에스터 수지 | `polyesters`, `polyacetals` |
| 반도체 | `electronic integrated circuits` |
| 디스플레이 패널 | `liquid crystal devices`, `monitors` |
| 자동차 부품 | `parts and accessories of motor vehicles` |
| 배터리 | `electric accumulators`, `lithium-ion` |
| 라면 | `pasta`, `noodles`, `prepared foods` |
| 김 | `seaweeds`, `algae` |
| 의약품 | `medicaments` |
| 의료기기 | `instruments and appliances`, `medical` |
| 철강 | `flat-rolled products`, `iron or non-alloy steel` |
| 공작기계 | `machine-tools` |
| 섬유/원단 | `woven fabrics`, `knitted` |
| 신발 | `footwear` |
| 가전 | `household`, `electro-thermic` |

검색이 비면 더 상위 개념으로 넓혀라. `"skin"` → `"beauty"` → `"cosmetic"` 순으로.

## 한국 주요 수출품 HS 4단위

시장 스캔을 바로 돌릴 때 쓸 수 있는 출발점.

| HS | 품목 |
|---|---|
| 8542 | 집적회로(반도체) |
| 8703 | 승용차 |
| 2710 | 석유제품 |
| 8708 | 자동차 부품 |
| 8507 | 축전지(2차전지) |
| 3907 | 폴리아세탈·폴리에테르·에폭시 수지 |
| 3304 | 기초화장품·색조화장품 |
| 8517 | 전화기·통신기기 |
| 7208 | 열연강판 |
| 8479 | 특수 기계류 |
| 2917 | 폴리카르복실산(테레프탈산 등) |
| 3902 | 폴리프로필렌 |
| 8905 | 선박 |
| 9013 | 액정 디바이스 |
| 1902 | 파스타·라면 |

## 확인 습관

HS코드를 확정하기 전에 사용자에게 후보와 설명을 보여주고 고르게 하라.
잘못된 코드로 돌린 리포트는 숫자가 그럴듯해서 더 위험하다.
