#!/usr/bin/env bash
# 인터프리터 한 개를 골라 $PY 에 넣는다. source 해서 쓴다.
#
#   . "$(dirname "$0")/python.sh"
#   $PY -m unittest ...
#
# `command -v python3` 로는 부족하다. 윈도우에는 `python3.exe` 가 항상 있는 것처럼
# 보이지만 그 실체는 Microsoft Store 스텁이라, 돌리면 "Python was not found" 를
# 뱉고 exit 49 로 죽는다. 존재 확인이 아니라 실제 실행으로 골라야 하는 이유다.
#
# $PY 는 "py -3" 처럼 두 단어일 수 있으므로 따옴표 없이 전개한다.

_pick_python() {
  local cand
  for cand in python3 "py -3" python; do
    # shellcheck disable=SC2086
    if $cand -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
      PY="$cand"
      return 0
    fi
  done
  return 1
}

if ! _pick_python; then
  echo "python3 3.11 이상을 찾지 못했습니다." >&2
  echo "  맥/리눅스: python.org 또는 패키지 매니저로 설치" >&2
  echo "  윈도우: python.org 설치 시 'Add Python to PATH' 를 켜고, 터미널에서 'py -3' 로 확인" >&2
  return 1 2>/dev/null || exit 1
fi
