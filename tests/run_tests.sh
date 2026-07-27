#!/usr/bin/env bash
# 전체 테스트 실행. 기본은 오프라인(픽스처)이라 네트워크 없이 1초 안에 끝난다.
#
#   ./tests/run_tests.sh          오프라인 스위트
#   ./tests/run_tests.sh --live   + 실제 Comtrade 계약 테스트 (느림, 네트워크 필요)
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d fixtures/cache ] || [ -z "$(ls -A fixtures/cache 2>/dev/null)" ]; then
  echo "픽스처가 없습니다. 먼저 실행하세요:"
  echo "  python3 tests/record_fixtures.py"
  exit 1
fi

echo "=== 오프라인 스위트 ==="
python3 -m unittest discover -p 'test_*.py' -v 2>&1 | tail -n 15

if [ "${1:-}" = "--live" ]; then
  echo
  echo "=== 라이브 계약 테스트 (Comtrade 실호출) ==="
  TRADE_STATS_LIVE=1 python3 -m unittest test_live -v 2>&1 | tail -n 20
fi
