#!/usr/bin/env bash
# 트리거 테스트 한 문장을 실제 Claude Code 세션에 던지고 흔적을 남긴다.
#
#   ./tests/run_trigger.sh 10 "화장품 미국 시장 어때?"
#
# 프롬프트에는 사용자 발화만 넣는다. 스킬 존재를 암시하는 문구가 한 조각이라도
# 들어가면 그 판정은 트리거 테스트가 아니라 사용법 테스트가 된다.
#
# 케이스마다 캐시를 따로 물리고, 매 실행 전에 그 캐시를 비운다. 캐시가 데워져
# 있으면 네트워크를 안 타서 흔적이 안 남고, 흔적이 없으면 '안 돌았다'로 오판하게 된다.
set -uo pipefail

cd "$(dirname "$0")/.."
. ./tests/python.sh

CASE="$1"
UTTERANCE="$2"
OUT="${TRIGGER_OUT:-$HOME/.cache/trigger-runs}"
mkdir -p "$OUT"

export TRADE_STATS_CACHE_DIR="$OUT/cache-$CASE"
# 같은 케이스를 다시 돌리면 지난 실행의 캐시가 그대로 남아 네트워크를 안 탄다.
# 그러면 흔적이 안 남아 '스킬이 안 돌았다'로 오판하게 되므로 매번 비우고 시작한다.
case "$TRADE_STATS_CACHE_DIR" in
  */cache-?*) rm -rf "$TRADE_STATS_CACHE_DIR" ;;
  *) echo "캐시 경로가 이상합니다: $TRADE_STATS_CACHE_DIR" >&2; exit 1 ;;
esac
mkdir -p "$TRADE_STATS_CACHE_DIR"

START=$(date +%s)
claude -p "$UTTERANCE" --allowedTools Bash Read Write Glob Grep --output-format text \
  > "$OUT/answer-$CASE.md" 2>&1
RC=$?
ELAPSED=$(( $(date +%s) - START ))

{
  echo "== #$CASE  \"$UTTERANCE\"  (${ELAPSED}s, rc=$RC)"
  # shellcheck disable=SC2086
  $PY tests/trigger_evidence.py --since-minutes "$(( ELAPSED / 60 + 2 ))" | sed -n '3,14p'
} | tee "$OUT/evidence-$CASE.txt"
