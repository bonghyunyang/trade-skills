# 테스트

```bash
./tests/run_tests.sh          # 오프라인, 네트워크 불필요, ~0.1초
./tests/run_tests.sh --live   # + 실제 Comtrade 계약 테스트 (~35초)
```

## 왜 이렇게 구성했나

이 프로젝트에서 위험한 버그는 **크래시가 아니라 조용한 오답**이다. 리포트는 멀쩡하게 나오는데
숫자가 틀려서 반대 결론으로 이끄는 종류다. 실제로 개발 중에 이런 게 네 개 나왔다.

- 베트남 파트너 중복 행 → 한국 점유율 20.4%로 표시 (실제 40.9%)
- 시장규모 축에 한국 수출액 대체 → 수출 1위 미국이 0.0점으로 꼴찌
- 축 1개짜리 리비아가 축 3개짜리 시장들을 제치고 100점 1위
- 단일 국가 조회 시 무조건 50.0점

전부 사람이 눈으로 봐야 잡히는 것들이라, 테스트로 고정해두지 않으면 재발한다.
`test_scoring.py`의 각 테스트는 위 사고 하나씩에 대응한다.

## 오프라인 방식 — 픽스처

`comtrade.py`가 원본 응답을 URL 해시로 캐싱하므로, `TRADE_STATS_CACHE_DIR`를
`tests/fixtures/cache`로 돌리면 스위트 전체가 네트워크 없이 **실제 응답 데이터**로 돈다.
별도 mock 레이어가 없어서 mock이 현실과 어긋날 일도 없다.

`context.block_network()`가 픽스처에 없는 요청을 테스트 실패로 만든다. 이게 없으면
픽스처가 지워져도 스위트가 조용히 라이브 호출로 넘어가 계속 통과해버린다.

픽스처 갱신:

```bash
python3 tests/record_fixtures.py           # 없는 것만 녹화
python3 tests/record_fixtures.py --force   # 전부 다시
```

## 라이브 계약 테스트

`test_live.py`는 `TRADE_STATS_LIVE=1` 없이는 건너뛴다. 오프라인 스위트가 **잡을 수 없는**
브리프 1순위 리스크 — "API 스펙 변경 → 스크립트 파손" — 를 담당한다. 녹화본을 재생하는
스위트는 정의상 upstream 변경을 감지하지 못한다.

확인하는 것: 인증키 없이 되는가, 파싱하는 필드가 남아 있는가, 전체 상대국이 한 콜에 오는가,
월별이 여전히 1기간 제한인가, 대만 490/158 상태가 그대로인가, 참조 스냅샷이 upstream과 맞는가.

릴리스 전 · 리포트가 이상할 때 · 주기적으로 돌린다.

## 파일

| 파일 | 담당 |
|---|---|
| `context.py` | 픽스처 경로 고정, 네트워크 차단 |
| `test_comtrade.py` | 국가/HS 해석, 응답 정규화, 중복 행 병합 |
| `test_scoring.py` | 매력도 점수 — 과거 사고 4건 회귀 |
| `test_hs_search.py` | 한국어 HS 검색 |
| `test_e2e.py` | `analyze.py market` 전체 실행, 출력 계약 |
| `test_resilience.py` | 국가별 실패 격리, 네트워크 장애, 캐시 손상 |
| `test_live.py` | 실제 API 계약 (opt-in) |
| `record_fixtures.py` | 픽스처 녹화 |
| `build_hs_ko.py` | 한국어 HS 색인 생성 |

## 픽스처가 오래되면

`test_partner_sum_reconciles_with_the_reporters_world_row`가 먼저 깨진다.
인도 응답이 500행 상한에 걸리는 걸 전제하는데, upstream이 바뀌면 그 전제가 무너진다.
이때는 `--force`로 다시 녹화하고 diff를 확인한다 — diff 자체가 스펙 변경의 신호다.
