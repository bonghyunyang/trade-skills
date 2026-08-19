#!/usr/bin/env bash
# 트리거 테스트 한 문장을 실제 Claude Code 세션에 던지고 흔적을 남긴다.
#
#   ./tests/run_trigger.sh 10 "화장품 미국 시장 어때?"
#
# 프롬프트에는 사용자 발화만 넣는다. 스킬 존재를 암시하는 문구가 한 조각이라도
# 들어가면 그 판정은 트리거 테스트가 아니라 사용법 테스트가 된다.
#
# 케이스마다 캐시를 따로 물린다. 캐시가 데워져 있으면 네트워크를 안 타서
# 흔적이 안 남고, 흔적이 없으면 '안 돌았다'로 오판하게 된다.
set -uo pipefail

cd "$(dirname "$0")/.."
. ./tests/python.sh

CASE="$1"
UTTERANCE="$2"
OUT="${TRIGGER_OUT:-$HOME/.cache/trigger-runs}"
mkdir -p "$OUT"

export TRADE_STATS_CACHE_DIR="$OUT/cache-$CASE"
mkdir -p "$TRADE_STATS_CACHE_DIR"

START=$(date +%s)
claude -p "$UTTERANCE" --allowedTools Bash Read Write Glob Grep --output-format text \
  > "$OUT/answer-$CASE.md" 2>&1
RC=$?
ELAPSED=$(( $(date +%s) - START ))

{
  echo "== #$CASE  \"$UTTERANCE\"  (${ELAPSED}s, rc=$RC)"
  # shellcheck disable=SC2086
  $PY tests/trigger_evidence.py --since-minutes "$(( ELAPSED / 60 + 2 ))" | sed -n '3,9p'
} | tee "$OUT/evidence-$CASE.txt"
