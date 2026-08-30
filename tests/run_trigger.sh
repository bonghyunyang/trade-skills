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

# 저장소 안에서 돌리면 세션이 스킬 소스를 직접 읽고 '개발자 모드'로 답한다. 실제로
# 23번 답변이 "지금 이 저장소의 trade-stats-lookup 기준입니다" 로 시작했다 — 실제
# 사용자는 그런 cwd 에 있지 않으므로 그건 사용자가 받을 답변이 아니다. 그래서 claude 는
# 빈 폴더에서 띄운다. 플러그인은 user 스코프라 저장소 밖에서도 그대로 로드된다.
REPO="$(pwd)"
RUNDIR="$OUT/cwd-$CASE"
rm -rf "$RUNDIR"
mkdir -p "$RUNDIR"

START=$(date +%s)
CLAUDE_ARGS="--allowedTools Bash Read Write Glob Grep --output-format text"
# shellcheck disable=SC2086
# stdin 을 안 닫으면 claude 가 3초 기다린 뒤 "no stdin data received" 경고를 찍고,
# 그 경고가 answer 파일 첫 줄에 섞여 판정 자료를 더럽힌다.
( cd "$RUNDIR" && claude -p "$UTTERANCE" $CLAUDE_ARGS < /dev/null ) > "$OUT/answer-$CASE.md" 2>&1
RC=$?
cd "$REPO"
ELAPSED=$(( $(date +%s) - START ))

{
  echo "== #$CASE  \"$UTTERANCE\"  (${ELAPSED}s, rc=$RC)"
  # shellcheck disable=SC2086
  $PY tests/trigger_evidence.py --since-minutes "$(( ELAPSED / 60 + 2 ))" | sed -n '3,14p'
} | tee "$OUT/evidence-$CASE.txt"
