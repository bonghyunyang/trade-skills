#!/usr/bin/env bash
# 배포 산출물을 만든다.
#
#   ./package.sh
#
# 만들어지는 것:
#   dist/trade-stats-lookup.zip   Cowork / claude.ai 업로드용 (Settings > Skills)
#
# Claude Code 마켓플레이스 설치는 zip이 필요 없다 — 레포를 그대로 쓴다.
set -euo pipefail

cd "$(dirname "$0")"

# shellcheck source=tests/python.sh
. ./tests/python.sh

SKILL_DIR="plugins/trade-stats/skills/trade-stats-lookup"
DIST="dist"
ZIP="$DIST/trade-stats-lookup.zip"

echo "== 사전 검증 =="

if [ ! -f "$SKILL_DIR/SKILL.md" ]; then
  echo "SKILL.md를 찾을 수 없습니다: $SKILL_DIR" >&2
  exit 1
fi

# 배포본이 깨진 채 나가는 것보다, 여기서 멈추는 편이 낫다.
# Fixtures are gitignored (they hold UN Comtrade's data, not ours), so a fresh
# clone has none. Skipping the suite would let a release ship unverified, which
# is the one thing this gate exists to prevent — so this is fatal, not a warning.
if [ ! -d tests/fixtures/cache ] || [ -z "$(ls -A tests/fixtures/cache 2>/dev/null)" ]; then
  echo "픽스처가 없어 테스트를 실행할 수 없습니다. 먼저 실행하세요:" >&2
  echo "  $PY tests/record_fixtures.py" >&2
  exit 1
fi

./tests/run_tests.sh > /tmp/trade-pkg-tests.log 2>&1 || {
  echo "테스트 실패. 배포를 중단합니다. 로그: /tmp/trade-pkg-tests.log" >&2
  tail -20 /tmp/trade-pkg-tests.log >&2
  exit 1
}
echo "  테스트 통과"

# shellcheck disable=SC2086
$PY - <<'PYCHECK'
import json, re, sys
from pathlib import Path

skill = Path("plugins/trade-stats/skills/trade-stats-lookup")
text = (skill / "SKILL.md").read_text(encoding="utf-8")

m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
if not m:
    sys.exit("SKILL.md에 YAML frontmatter가 없습니다")
front = m.group(1)

name = re.search(r"^name:\s*(\S+)", front, re.M)
desc = re.search(r"^description:\s*(.+)$", front, re.M)
if not name:
    sys.exit("frontmatter에 name이 없습니다")
if not desc:
    sys.exit("frontmatter에 description이 없습니다")
if name.group(1) != skill.name:
    sys.exit(f"name({name.group(1)})과 폴더명({skill.name})이 다릅니다")

# description은 트리거의 전부다. 짧으면 스킬이 뜨지 않는다.
if len(desc.group(1)) < 120:
    sys.exit(f"description이 너무 짧습니다({len(desc.group(1))}자). 트리거 키워드를 더 넣으세요.")

body = text[m.end():]
lines = body.count("\n")
if lines > 500:
    sys.exit(f"SKILL.md 본문이 {lines}줄입니다. 500줄 이하로 줄이고 references/로 분리하세요.")

for ref in ("areas.json", "hs.json", "hs_ko.json", "country_aliases_ko.json",
            "country_names_ko.json", "kr-top-partners.json"):
    if not (skill / "references" / ref).exists():
        sys.exit(f"참조 데이터 누락: {ref}")

for script in ("comtrade.py", "fetch_comtrade.py", "analyze.py", "customs.py"):
    if not (skill / "scripts" / script).exists():
        sys.exit(f"스크립트 누락: {script}")

print(f"  SKILL.md 본문 {lines}줄, description {len(desc.group(1))}자")
print("  참조 데이터·스크립트 확인")
PYCHECK

echo "== 패키징 =="
rm -rf "$DIST"
mkdir -p "$DIST"

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
mkdir -p "$STAGE/trade-stats-lookup"

tar -cf - -C "$SKILL_DIR" \
    --exclude='__pycache__' --exclude='*.pyc' --exclude='.omc' --exclude='.gitignore' \
    . | tar -xf - -C "$STAGE/trade-stats-lookup"

# The zip travels on its own — someone uploads it to Cowork and the repo is
# nowhere in sight. Attribution has to ride along with the bundled data.
cp LICENSE NOTICE "$STAGE/trade-stats-lookup/"

# 윈도우에는 zip/unzip 이 없다. 파이썬 표준 라이브러리로 같은 zip 을 만든다 —
# 배포본을 만들려고 별도 도구를 깔게 만들 이유가 없다.
if command -v zip >/dev/null 2>&1; then
  (cd "$STAGE" && zip -qr "trade-stats-lookup.zip" "trade-stats-lookup")
else
  # shellcheck disable=SC2086
  (cd "$STAGE" && $PY -m zipfile -c "trade-stats-lookup.zip" "trade-stats-lookup")
fi
mv "$STAGE/trade-stats-lookup.zip" "$ZIP"

echo
echo "생성: $ZIP ($(du -h "$ZIP" | cut -f1))"
# shellcheck disable=SC2086
$PY - "$ZIP" <<'PYLIST'
import sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as z:
    for name in sorted(z.namelist()):
        if not name.endswith("/"):
            print("  " + name)
PYLIST
echo
echo "업로드: claude.ai 또는 Cowork → Settings → Capabilities → Skills → Upload"
