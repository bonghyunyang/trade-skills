"""SKILL.md 의 frontmatter 가 실제 YAML 파서로 읽히는지 검사한다.

이게 없어서 한 번 크게 당했다. v0.2.0 의 description 안에 `(예: "화장품 ...")`
가 들어갔는데, YAML 평문 스칼라에서 콜론+공백은 매핑 구분자라 frontmatter 전체가
파싱에 실패했다. 런타임은 예외를 던지지 않는다 — **메타데이터를 통째로 비운 채**
스킬을 로드한다. 즉 description 이 사라지고, description 이 사라지면 스킬은
트리거되지 않는다. 본문은 멀쩡하고 테스트도 전부 초록이고 리포트도 잘 나오는데
사용자에게는 스킬이 존재하지 않는 상태가 된다.

정규식으로 `^description:\\s*(.+)$` 만 확인하는 검사는 이걸 못 잡는다. 오히려
"description 771자, 통과"라고 안심시킨다. 그래서 파서로 읽는다.
"""

from __future__ import annotations

import re
import unittest

from context import SKILL

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
# YAML 평문 스칼라를 깨뜨리는 것들. 인용 부호로 감싸지 않은 값에 이게 들어가면
# 파서가 그 줄을 다른 뜻으로 읽는다.
PLAIN_BREAKERS = (": ", " #")
QUOTED_OR_BLOCK = ('"', "'", "|", ">", "[", "{", "&", "*")


def frontmatter() -> str:
    text = SKILL.joinpath("SKILL.md").read_text(encoding="utf-8")
    m = FRONTMATTER.match(text)
    assert m, "SKILL.md 첫 줄부터 --- frontmatter 가 시작돼야 합니다"
    return m.group(1)


class TestFrontmatter(unittest.TestCase):
    def test_parses_with_a_real_yaml_parser(self):
        """PyYAML 이 있으면 진짜로 파싱해 본다. 없으면 아래 평문 검사가 받는다."""
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML 미설치 — test_plain_scalars_are_not_broken 이 대신 잡습니다")
        data = yaml.safe_load(frontmatter())
        self.assertIsInstance(data, dict)
        self.assertEqual(data.get("name"), SKILL.name)
        self.assertGreaterEqual(len(data.get("description", "")), 120)

    def test_plain_scalars_are_not_broken(self):
        """의존성 없이 같은 사고를 잡는다. CI 에 PyYAML 이 없어도 이건 돈다."""
        for lineno, line in enumerate(frontmatter().splitlines(), 1):
            m = re.match(r"^(\s*)([A-Za-z_][\w-]*):\s*(\S.*)$", line)
            if not m:
                continue
            value = m.group(3)
            if value.startswith(QUOTED_OR_BLOCK):
                continue
            for bad in PLAIN_BREAKERS:
                self.assertNotIn(
                    bad, value,
                    f"frontmatter {lineno}번째 줄 '{m.group(2)}' 값에 {bad!r} 가 있습니다. "
                    f"YAML 평문 스칼라가 여기서 끊겨 frontmatter 전체가 빈 메타데이터로 "
                    f"로드됩니다. 표현을 바꾸거나 값을 따옴표로 감싸세요.")

    def test_description_still_carries_the_trigger_words(self):
        """트리거는 description 이 전부다. 축약하다 핵심 단어가 빠지면 스킬이 안 뜬다."""
        front = frontmatter()
        for word in ("HS코드", "수출", "시장", "발굴", "무역통계"):
            self.assertIn(word, front)


if __name__ == "__main__":
    unittest.main()
