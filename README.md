<div align="center">

# trade-skills

### 수출, 어느 나라부터 가야 할까?

감으로 찍던 시장 선정을 근거 있는 결정으로 바꿉니다.
품목 이름만 말하면 됩니다. HS코드도, API 키도, 회원가입도 필요 없습니다.

[![Claude Code](https://img.shields.io/badge/Claude%20Code-plugin-6f42c1)](https://claude.com/claude-code)
[![Cowork](https://img.shields.io/badge/Cowork%20%C2%B7%20claude.ai-skill-0ea5e9)](https://claude.ai)
[![No API key](https://img.shields.io/badge/API%20key-not%20required-16a34a)](#install-ko)
[![Tests](https://github.com/bonghyunyang/trade-skills/actions/workflows/tests.yml/badge.svg)](https://github.com/bonghyunyang/trade-skills/actions/workflows/tests.yml)
[![License](https://img.shields.io/badge/license-MIT-black)](LICENSE)

**한국어** · [English](#english)

</div>

---

> [!WARNING]
> **이 도구를 쓰기 전에 30초만 읽어주세요.** 모르고 쓰면 숫자는 맞는데 결론이 반대로 갑니다.
>
> - **여기 나오는 "점유율"은 수입품 중 비중입니다.** 시장 점유율이 아닙니다. 현지 공장 물량은 통계에 잡히지 않습니다.
> - **바이어 회사 이름은 나오지 않습니다.** 관세법상 비공개입니다.
> - **수출 절차와 관세 정보는 이 도구가 검증한 내용이 아닙니다.** 특히 관세율은 반드시 따로 확인하세요.
>
> 자세한 설명은 [숫자를 읽는 법](#reading-ko)에 있습니다.

---

<a id="install-ko"></a>

## ⚡ 설치

컴퓨터를 잘 다루지 않아도 됩니다. 아래 둘 중 편한 쪽 하나만 하시면 됩니다.

| | 이런 분께 | 걸리는 시간 |
|---|---|---|
| **A. claude.ai에 올리기** | 브라우저만 쓰시는 분. 설치할 게 없습니다 | 2분 |
| **B. Claude Code에 설치** | 회사 노트북에 프로그램을 깔 수 있는 분 | 5분 |

처음이시면 **A**를 권합니다. 파일 하나 올리면 끝입니다.

<details open>
<summary><b>A. claude.ai에서 쓰기 (권장)</b></summary>

**1단계. 파일을 받습니다**

[Releases 페이지](https://github.com/bonghyunyang/trade-skills/releases)를 엽니다.
맨 위에 있는 최신 버전에서 `trade-stats-lookup.zip`을 눌러 받습니다.
압축은 풀지 마세요. zip 파일 그대로 올려야 합니다.

**2단계. claude.ai에 올립니다**

1. [claude.ai](https://claude.ai)에 로그인합니다
2. 왼쪽 아래 본인 이름을 누르고 **Settings**로 들어갑니다
3. **Capabilities** 탭을 엽니다
4. **Skills** 항목에서 **Upload skill**을 누릅니다
5. 방금 받은 `trade-stats-lookup.zip`을 선택합니다

목록에 `trade-stats-lookup`이 보이면 끝입니다.

**3단계. 되는지 확인합니다**

새 대화를 열고 이렇게 쳐 보세요.

> 화장품 미국 시장 어때?

Claude가 "HS코드 후보를 찾았습니다" 하면서 코드를 몇 개 보여주면 정상입니다.

> [!NOTE]
> Skills 메뉴가 안 보이면 요금제 문제입니다. Skills는 Pro 이상에서 제공됩니다.

</details>

<details>
<summary><b>B. Claude Code에서 쓰기</b></summary>

**1단계. Claude Code를 설치합니다**

이미 쓰고 계시면 건너뛰세요. 처음이시면 [claude.com/claude-code](https://claude.com/claude-code)의
안내를 따라 설치합니다.

**2단계. 터미널에서 두 줄을 칩니다**

터미널(맥은 터미널, 윈도우는 PowerShell)에서 `claude`를 실행한 다음 아래를 순서대로 입력합니다.

```
/plugin marketplace add bonghyunyang/trade-skills
```

```
/plugin install trade-stats@trade-skills
```

**3단계. 확인합니다**

```
/plugin
```

목록에 `trade-stats`가 보이면 끝입니다. 그대로 질문하시면 됩니다.

**나중에 업데이트할 때**

```
/plugin marketplace update bonghyunyang/trade-skills
```

</details>

### 준비물

인터넷 연결과 `python3` 3.11 이상, 이 둘뿐입니다.

맥과 리눅스에는 python3이 대부분 이미 깔려 있습니다. 확인은 터미널에서 이렇게 합니다.

```bash
python3 --version
```

`Python 3.11.x` 이상이 나오면 됩니다. 없다고 나오면 [python.org](https://www.python.org/downloads/)에서
받아 설치하시면 됩니다. 윈도우에서 설치할 때 **Add Python to PATH** 체크박스를 꼭 켜 주세요.

**윈도우는 함정이 하나 있습니다.** 파이썬을 제대로 깔았는데도 `python3 --version`이
`Python was not found...`라며 Microsoft Store를 열려고 합니다. 윈도우가 기본으로 심어 둔
가짜 `python3` 때문인데, 이때는 이렇게 확인하세요.

```bash
py -3 --version
```

여기서 버전이 나오면 준비 끝입니다. 스킬에도 이 상황이 적혀 있어서, Claude가 알아서
`py -3`으로 바꿔 실행합니다.

**회원가입도, API 키 발급도 필요 없습니다.** UN Comtrade의 공개 데이터를 쓰기 때문입니다.
(HSK 10단위 정밀 조회 하나만 관세청 인증키가 필요한데, 그건 기본 기능이 아니고
필요해질 때 화면에서 발급 방법을 안내해 드립니다.)

### 잘 안 될 때

| 이런 증상 | 이렇게 하세요 |
|---|---|
| Skills 메뉴가 안 보임 | claude.ai Pro 이상 요금제가 필요합니다 |
| zip을 올렸는데 목록에 없음 | 압축을 풀지 않은 zip 파일 그대로인지 확인하세요 |
| "python3을 찾을 수 없습니다" | 위 준비물 항목대로 python3을 설치하세요 |
| 윈도우에서 "Python was not found"라며 스토어가 열림 | 파이썬은 깔려 있습니다. `py -3 --version`으로 확인하고, 그대로 다시 물어보세요 |
| 질문했는데 스킬이 안 켜짐 | "무역통계로 화장품 미국 시장 조회해줘"처럼 품목과 나라를 같이 말해 보세요 |
| 조회가 3분 넘게 걸림 | 정상입니다. 무료 공개 API라 요청 간격을 둡니다. 두 번째부터는 1초입니다 |
| "429" 또는 "호출 제한" 오류 | 사무실에서 여러 명이 같은 인터넷을 쓰면 생깁니다. 잠시 후 다시 하시면 됩니다 |

## 💬 이렇게 물어보세요

> "화장품 미국 시장 어때?"

> "화장품 어디 새로 뚫을 데 없나?"

> "이차전지 어느 나라부터 뚫어야 해?"

> "베트남에 라면 팔면 경쟁 심한가?"

> "우리 품목 어디부터 봐야 할까"

HS코드는 몰라도 됩니다. **품목 이름을 한국어로 말하면** 코드 후보를 찾아서
"이 코드로 볼까요?" 하고 한 번 확인합니다. 그다음 3~5분쯤 기다리면 답이 나옵니다.
무료 공개 API라 요청 간격을 두고 부르기 때문입니다. 같은 조회를 다시 하면 1초 안에 끝납니다.

## 📊 이런 답이 나옵니다

화장품(HS 3304)으로 실제 돌린 결과입니다.

```
| #  | 국가   | 매력도 | 여유 시장 | 현지 총수입 | 시장 CAGR | 한국 수출 CAGR | 한국 점유율 | 1위 공급국 |
|----|--------|--------|-----------|-------------|-----------|----------------|-------------|------------|
|  1 | 미국   |  70.1  |  $56.2억  |   $74.7억   |   +4.5%   |     +30.8%     |    24.8%    | 한국 25%   |
|  2 | 일본   |  63.3  |  $10.5억  |   $18.4억   |   +7.7%   |     +14.9%     |    42.9%    | 한국 43%   |
|  3 | 베트남 |  62.2  |   $1.8억  |    $3.1억   |  +14.7%   |      -4.2%     |    40.9%    | 한국 41%   |
|  6 | 중국   |  50.5  | $110.9억  |  $130.3억   |   -9.7%   |     -16.6%     |    14.9%    | 프랑스 28% |
|  9 | 홍콩   |  41.4  |  $30.5억  |   $38.9억   |  -18.2%   |     +16.6%     |    21.6%    | 한국 22%   |
| 10 | 인도   |  26.4  |   $3.8억  |    $4.7억   |  -36.5%   |     +39.9%     |    18.7%    | 중국 22%   |
```

여기에 나라별 경쟁사 표와 한국어 리포트가 같이 나옵니다. 엑셀용 CSV도 요청하면 만들어 드립니다.

**여유 시장이 이 표의 핵심입니다.** `현지 총수입 × (1 - 한국 점유율)`, 그러니까 아직 우리
몫이 아닌 수입액입니다. 실무 언어로 옮기면 지금 테이블에 남아 있는 돈입니다.
"베트남 매력도 62.2점"은 회의에서 아무도 받아주지 않습니다.
"베트남은 아직 안 먹은 수입이 1.8억 달러 남았고 시장이 연 14.7%씩 큽니다"는 그대로 품의서에 들어갑니다.

---

## 🎯 이걸 쓰면 뭐가 달라지나

### 주력 시장이 무너지는 걸 먼저 봅니다

위 표에서 베트남을 보세요. 점유율 40.9%입니다. 우리 주력 시장이죠.

그런데 시장은 연 14.7% 크는데 한국 수출은 연 4.2% 줄고 있습니다. **격차 19%p.**
지금 누군가에게 자리를 내주는 중입니다. 우리 수출 실적만 보면 절대 안 보입니다.
"베트남 잘 나가는데요"로 끝나거든요.

위 표의 홍콩은 반대 모양입니다. 시장이 연 18.2% 줄어드는데 한국 수출은 연 16.6% 늘었습니다.
홍콩에서 다 소비된다고 보기 어렵습니다. 중계무역으로 다른 나라에 넘어간다는 신호입니다.

시장 성장률과 우리 성장률을 한 화면에 나란히 놓는 곳은 KOTRA에도 K-stat에도 Trade Map에도 없습니다.
따로 받아서 엑셀에서 붙여야 나오는 숫자입니다.

| 이런 모양이면 | 이런 뜻입니다 |
|---|---|
| 시장 ↑, 우리 수출 ↓ | 점유율을 뺏기는 중입니다 |
| 시장 ↓, 우리 수출 ↑ | 중계무역 경유일 수 있습니다 (실제 소비지가 다른 나라) |
| 시장 ↑, 우리 수출 ↑↑ | 뺏어오는 중입니다. 지금 밀어야 할 곳입니다 |

### 아무도 안 보던 나라를 찾아냅니다

> "화장품 어디 새로 뚫을 데 없나?"

이렇게 물으면 UN Comtrade에 신고하는 **225개국 전부**를 훑습니다.
한국이 거의 안 파는 나라까지 같이 나옵니다.

```
| # | 국가       | 매력도 | 여유 시장 | 시장 CAGR | 한국 점유율 | 태그            |
|---|------------|--------|-----------|-----------|-------------|-----------------|
| 1 | 폴란드     |  88.4  | $20.0억   |  +24.3%   |    13.2%    | 고성장          |
| 2 | 키프로스   |  79.6  |  $6.0억   |  +25.1%   |     0.9%    | 미개척, 고성장  |
| 3 | 슬로바키아 |  76.8  |  $4.0억   |  +22.1%   |     5.4%    | 고성장          |
```

1위로 나온 폴란드를 보겠습니다. 화장품 수입이 2023년 14.9억 달러에서 2025년 23.1억 달러로
늘었습니다. 연 24.3%입니다. 같은 기간 한국 수출은 5,746만 달러에서 3.04억 달러로 **5.3배**가 됐습니다.

폴란드는 한국 교역 상위 10개국에 없습니다. 그래서 기존 도구의 기본값으로는 아예 안 나옵니다.
이미 파는 나라 안에서 순위를 매기는 것과, 아직 안 파는 나라를 발견하는 것은 다른 일입니다.

### 점수를 다른 조회와 비교할 수 있습니다

매력도는 **절대 기준**입니다. 여유 시장 1천만~100억 달러, 시장 성장률 -10%~+20%를
각각 0~100으로 편 값입니다.

그래서 어느 나라를 같이 조회하든 같은 나라는 같은 점수가 나옵니다.
미국은 10개국을 함께 봐도 70.1, 5개국만 봐도 70.1입니다.
다른 날 다른 품목으로 뽑은 점수와도 비교됩니다.

사내 우선순위표를 만들 수 있다는 뜻입니다. "A라인 폴란드 88점, B라인 멕시코 70점"처럼요.

### 숫자를 틀리게 읽는 걸 리포트가 막습니다

숫자만 뽑아주는 도구는 이미 많습니다. 진짜 사고는 그 숫자를 잘못 읽을 때 납니다.

키프로스가 발굴 목록 2위로 올라왔습니다. 한국 점유율 0.9%, 여유 시장 6.0억 달러.
비어 있는 시장처럼 보입니다. 그런데 자세히 들여다보면 **1위 공급국 그리스가 53%**를 쥐고 있습니다.
빈 시장이 아니라 진입장벽이 높은 시장입니다. 리포트가 이걸 ⚠️로 먼저 알려줍니다.

이런 장치를 여러 개 넣었습니다.

- 점유율은 수입품 중 비중이지 시장 점유율이 아닙니다. 현지 공장 물량은 통계에 없습니다
- 한 나라가 60% 넘게 쥔 과점 시장에는 경고를 붙입니다
- 한국 신고 수출과 상대국 신고 수입이 2배 넘게 어긋나면 알려줍니다 (제3국 경유 신호입니다)
- 순위에서 빠진 나라를 `측정불가`와 `규모 미달`로 나눕니다. 뜻이 정반대라서요
- 단가가 올랐다고 "프리미엄화됐다"고 쓰지 않습니다. 품목 구성이 바뀐 것일 수 있거든요

### 반나절 걸리던 일이 몇 분입니다

| | 지금까지 | trade-skills |
|---|---|---|
| 시장 하나 보려면 | KOTRA, K-stat, Trade Map을 각각 열고 엑셀로 옮기기 (반나절) | 질문 한 줄, 3~5분 |
| HS코드 | 직접 찾아서 입력 | "화장품"이라고 말하면 끝 |
| 나라 여러 개 | 하나씩 다시 반복 | 기본 10개국 한 번에 |
| 안 가본 나라 발굴 | 사실상 불가능 | 전 세계 225개국 스캔 |
| 성장률 | 우리 수출 실적만 보임 | 시장 성장률까지 나란히 |
| 경쟁 구도 | 따로 찾아봐야 함 | 1위 공급국과 과점 여부 자동 표시 |
| 해석 함정 | 알아서 조심해야 함 | 리포트가 먼저 알려줌 |

같은 조회를 다시 하면 1초 안에 끝납니다. 결과를 일주일간 들고 있거든요.

---

## 🙋 이럴 때 쓰시면 됩니다

- 출장이나 전시회 예산을 어디에 쓸지 정할 때
- 사장님이 "왜 하필 거기냐"고 물을 때 (표를 그대로 인용하시면 됩니다)
- 내년 사업계획에서 목표 시장을 고를 때
- 주력 시장이 흔들리는 것 같은데 확신이 안 설 때
- 신규 아이템이나 신규 국가를 뚫으라는 지시를 받았을 때
- 국가는 정해졌는데 뭘 팔지 모를 때 (품목을 거꾸로 찾아 드립니다)

시장조사 예산이 따로 없어서 구글링으로 때우시던 자리를 대신합니다.

## 📖 실무 예제

실제로 돌린 결과를 그대로 옮겼습니다. 화장품 수출을 준비하는 중소기업 담당자라고 가정하겠습니다.

---

### 예제 1. 내년 목표 시장 정하기

**상황**: 내년 사업계획에 목표 시장 3개를 써야 합니다. 근거도 같이 내야 합니다.

> **나**: 화장품 수출하는데 어느 나라부터 봐야 할까?

Claude가 먼저 품목 코드를 확인합니다.

> **Claude**: 화장품으로 검색하니 코드 후보가 나왔습니다.
> - **3304** 미용, 메이크업, 기초화장용 제품류
> - 3303 향수와 화장수
> - 3305 두발용 제품류
>
> 기초화장품과 색조를 같이 보시려면 3304가 맞습니다. 이걸로 진행할까요?

> **나**: 응 3304로

3~5분 뒤에 표가 나옵니다.

```
| # | 국가   | 매력도 | 여유 시장 | 시장 CAGR | 한국 수출 CAGR | 한국 점유율 |
|---|--------|--------|-----------|-----------|----------------|-------------|
| 1 | 미국   |  70.1  |  $56.2억  |   +4.5%   |     +30.8%     |    24.8%    |
| 2 | 일본   |  63.3  |  $10.5억  |   +7.7%   |     +14.9%     |    42.9%    |
| 3 | 베트남 |  62.2  |   $1.8억  |  +14.7%   |      -4.2%     |    40.9%    |
| 4 | 말레이시아 | 56.7 | $5.3억  |   +6.7%   |     +15.3%     |    14.5%    |
| 5 | 호주   |  53.6  |  $10.6억  |   +1.9%   |     +51.2%     |    14.5%    |
```

**여기서 읽어야 할 것**

미국은 여유 시장이 56.2억 달러입니다. 2위 중국의 절반이지만 시장이 커지는 쪽이라
순위가 높습니다. 한국이 이미 1위 공급국(25%)인데도
아직 그만큼 남아 있습니다. 시장도 우리 수출도 같이 크는 중입니다(+4.5%, +30.8%).

말레이시아는 점유율이 14.5%로 낮은데 우리 수출이 연 15.3%씩 늘고 있습니다.
자리를 넓혀가는 중입니다. 규모는 작지만 진입 여지가 큽니다.

**보고서에 이렇게 씁니다**

> 1순위 미국. 수입 기준 여유 시장 56.2억 달러, 시장 연 4.5% 성장, 한국 점유율 24.8%로 1위 공급국.
> 2순위 말레이시아. 여유 시장 5.3억 달러, 시장 연 6.7% 성장, 한국 점유율 14.5%로 확대 여지.
> (출처: UN Comtrade, 상대국 신고 수입 기준)

점유율을 쓰실 때 **"수입 기준"**을 꼭 같이 적어 주세요. 현지 공장 물량은 이 통계에 없습니다.

---

### 예제 2. 아무도 안 보던 시장 찾기

**상황**: 위 목록은 다 아는 나라들입니다. 경쟁사가 아직 안 간 곳을 찾고 싶습니다.

> **나**: 화장품 어디 새로 뚫을 데 없나? 안 가본 나라로

> **Claude**: 전 세계 225개국을 훑겠습니다. 6~10분 걸립니다. 진행할까요?

> **나**: ㅇㅇ

```
| # | 국가       | 매력도 | 여유 시장 | 시장 CAGR | 한국 점유율 | 태그            |
|---|------------|--------|-----------|-----------|-------------|-----------------|
| 1 | 폴란드     |  88.4  | $20.0억   |  +24.3%   |    13.2%    | 고성장          |
| 2 | 키프로스   |  79.6  |  $6.0억   |  +25.1%   |     0.9%    | 미개척, 고성장  |
| 3 | 슬로바키아 |  76.8  |  $4.0억   |  +22.1%   |     5.4%    | 고성장          |
| 4 | 크로아티아 |  76.4  |  $3.8억   |  +26.0%   |     1.5%    | 초기진입, 고성장 |
```

> **나**: 폴란드 자세히 알려줘

> **Claude**: 폴란드 화장품 수입이 2023년 14.9억 달러에서 2025년 23.1억 달러로 늘었습니다.
> 연 24.3%입니다. 같은 기간 한국 수출은 5,746만 달러에서 3.04억 달러로 5.3배가 됐습니다.
> 한국 점유율은 13.2%이고 아직 20억 달러가 남아 있습니다.

**여기서 조심할 것**

키프로스는 점유율 0.9%라 비어 보이지만, 좁혀서 다시 보면 **1위 공급국 그리스가 53%**를
쥐고 있습니다. 빈 시장이 아니라 이미 주인이 있는 시장입니다. 리포트가 ⚠️로 표시해 줍니다.

`집계주의` 태그가 붙은 나라는 통계 신고 형식 때문에 총액이 정확하지 않을 수 있습니다.
후보로 살리실 거면 그 나라만 따로 다시 조회하시면 정확한 숫자가 나옵니다.

---

### 예제 3. 주력 시장이 흔들리는지 확인하기

**상황**: 베트남이 우리 주력입니다. 점유율 40.9%면 잘하고 있는 것 같은데 매출이 안 늘어납니다.

> **나**: 베트남 화장품 우리가 뺏기고 있는 거야?

> **Claude**: 베트남 화장품 수입 시장은 연 14.7% 커지는데 한국 수출은 연 4.2% 줄었습니다.
> **격차 18.9%p입니다.** 점유율 40.9%로 여전히 1위 공급국이지만, 시장이 커지는 만큼
> 따라가지 못하고 있습니다. 그 자리를 다른 나라가 채우는 중입니다.

이게 이 도구의 핵심입니다. **우리 수출 실적만 보면 절대 안 보입니다.**
"베트남 4억 달러, 점유율 41%, 1위"로 끝나거든요. 옆에 시장 성장률을 놓아야 보입니다.

반대 사례도 있습니다. 홍콩은 시장이 연 18.2% 줄어드는데 한국 수출은 연 16.6% 늘었습니다.
홍콩에서 다 소비된다고 보기 어렵습니다. 중계무역으로 다른 나라에 넘어간다는 신호입니다.
**홍콩 실적을 홍콩 시장 성과로 보고하면 안 됩니다.**

---

### 예제 4. 나라는 정했는데 뭘 팔지 모를 때

**상황**: 싱가포르 지사가 생겼습니다. 무엇을 밀지 정해야 합니다.

> **나**: 싱가포르에 뭘 팔면 좋을까? 우리는 직원 20명짜리 회사야

> **Claude**: 한국이 싱가포르에 이미 팔고 있는 품목 전체를 훑었습니다.
> 금액 상위는 반도체(85), 석유(27), 선박(89), 기계(84)인데 대기업 영역이라 표에서 뺐습니다.
> 소비재와 경량 품목만 추리면 이렇습니다.
>
> | 품목 | 최신 수출액 | 2년 성장 |
> |---|---|---|
> | HS33 화장품, 향료 | $1.43억 | +14.4% |
> | HS34 비누, 세제 | $0.37억 | **+29.4%** |
> | HS21 조제식료품 | $0.42억 | +3.7% |
> | HS08 과일, 견과 | $0.27억 | +11.0% |
>
> 비누와 세제(HS34)가 연 29.4%로 가장 빠릅니다. 다만 이 숫자는 **한국 전체 실적**이라
> 수요가 검증됐다는 뜻이지, 그 물량을 신규 진입자가 가져올 수 있다는 뜻은 아닙니다.

> **나**: HS34로 좁혀서 경쟁 구도 봐줘

여기서부터는 예제 1의 흐름으로 이어집니다.

---

### 예제 5. 우리 제품만 정확히 보고 싶을 때

**상황**: HS 6단위로는 우리가 안 만드는 제품까지 섞여 나옵니다.

> **나**: 3304에 색조도 기초도 다 들어가는데, 우리는 기초만 만들어. 기초만 볼 수 있어?

> **Claude**: HSK 10단위로 내려가면 됩니다. 다만 이 조회는 관세청 인증키가 필요합니다.
> 무료이고 5분이면 발급받으실 수 있습니다. 발급 방법을 안내해 드릴까요?
> 지금 당장은 HS 6단위 기준으로 답을 드릴 수 있습니다.

키를 발급받고 다시 물으면 이렇게 나옵니다.

```
▪ 베트남  최근 12개월 $4.33억
  3304999000 기타                $208,044,045  YoY +22.3%  단가 $39.5/kg
  3304991000 기초화장용 제품류    $161,662,091  YoY  -5.6%  단가 $22.4/kg
     └ 단가 -18.4%. HSK 10단위라 품목 구성이 거의 고정입니다. 가격 변화로 읽으셔도 됩니다.
  3304992000 메이크업용 제품류     $18,774,537  YoY +17.8%  단가 $49.4/kg
```

HS 6단위에서는 단가가 내려가도 "가격이 내린 것인지 싼 제품이 많이 팔린 것인지 알 수 없다"가
정답이었습니다. 10단위에서는 구성이 고정이라 **가격이 내렸다고 말할 수 있습니다.**
`기타`처럼 여러 제품이 묶인 코드는 10단위여도 그렇게 못 읽습니다. 리포트가 구분해 줍니다.

관세청 데이터는 한국 신고 기준이라 UN Comtrade보다 1년 이상 최신입니다.
다만 **점유율 계산에는 쓰지 않습니다.** 상대국이 10단위 수입 통계를 공개하지 않아서
분모가 존재하지 않기 때문입니다. 점유율은 예제 1의 표만 쓰시면 됩니다.

---

## 🤔 왜 만들었나

해외영업을 하면서 이게 제일 답답했습니다.

**"어느 나라부터 뚫을지" 하나 정하는 데 시간이 너무 많이 들었습니다.** 구글링으로 시작해서
무료든 유료든 보고서를 뒤지고 정리하다 보면 반나절이 사라집니다.

그렇게 해놓고도 근거를 대라고 하면 "경쟁사가 저기서 잘하고 있으니까", "누가 시장 크다고 하던데"
같은 카더라뿐이었습니다. 결국 출장 가서 직접 보고 나서야 맞춰가는 식이었습니다.
그 과정이 참 싫었습니다.

그래서 **"어느 시장부터 갈지"를 숫자로 정하는 것** 하나에만 집중했습니다.

숫자를 뽑아주는 도구는 이미 많습니다. 진짜 문제는 그 숫자가 **조용히 엉뚱한 결론으로**
데려가는 경우입니다. 수입 점유율을 시장 점유율로 착각하거나, 중계무역 허브를 유망 시장으로 보거나,
데이터가 없는 나라를 나쁜 시장으로 읽는 식입니다.
그래서 이 도구는 **주의사항을 문서 구석에 묻어두지 않고 리포트 안에 그대로 넣습니다.**

<a id="reading-ko"></a>

## ⚠️ 숫자를 읽는 법

### 1. "점유율"은 수입품 중 비중입니다

> "미국 화장품 한국 점유율 24.8%"
> = 미국이 **수입하는** 화장품 중 한국산이 24.8%
> ≠ 미국 화장품 시장의 1/4이 한국산

현지 공장에서 만들어 파는 물량은 이 통계에 **아예 잡히지 않습니다.** 미국은 현지 화장품
회사가 워낙 강해서(P&G, Estée Lauder 같은) 실제 시장 점유율은 훨씬 낮습니다.
식품, 자동차, 철강, 화장품처럼 현지에서 많이 만드는 품목일수록 이 차이가 커집니다.

보고서에 쓰실 땐 **"수입 기준"이라고 꼭 같이 적어주세요.** 같은 이유로 표에 있는
"현지 총수입"도 그 나라 시장 규모가 아니에요.

### 2. 매력도 점수는 "남은 파이"입니다

점수 = **여유 시장 50% + 시장 성장률 50%**.

여유 시장은 `그 나라 총수입 × (1 − 한국 점유율)`, 즉 **아직 한국 몫이 아닌 수입액**입니다.
점수보다 이 금액을 보세요. "폴란드는 남은 파이가 20억 달러이고 연 24%씩 큰다"가
"88.4점"보다 훨씬 쓸모 있습니다.

두 축 모두 **절대 기준**입니다(여유 시장 1천만~100억 달러, 성장률 −10%~+20%).
어느 나라를 같이 조회하든 같은 나라는 같은 점수가 나옵니다.
다른 날 다른 품목으로 돌린 점수와도 비교할 수 있습니다.

순위에서 빠진 나라는 두 종류이고 **뜻이 정반대**입니다. `측정불가`는 데이터가 없어 비교를
못 한 것이고(나쁜 시장이 아닙니다), `규모 미달`은 데이터가 있고 실제로 작은 시장이에요.
작은 시장도 우리한테는 크다면 기준선을 낮춰서 다시 볼 수 있습니다.

### 3. "여유 시장"이 크다고 빈 시장이 아닙니다

여유 금액이 크다고 자리가 빈 게 아니에요. 이미 다른 나라가 앉아 있을 수 있거든요.
그래서 표에 1위 공급국을 같이 띄우고, 한 나라가 60% 넘게 쥐고 있으면 ⚠️ 를 붙여둡니다.

<details>
<summary><b>그 외 알아두면 좋은 것 (펼치기)</b></summary>

- **순위에서 빠진 나라는 "나쁜 시장"이 아닙니다.** 데이터가 없어 측정을 못 한 겁니다.
- **단가(금액÷중량) 변화는 원인을 알 수 없습니다.** 가격이 오른 것인지 비싼 제품
  비중이 늘어난 것인지 구분되지 않습니다. "프리미엄화됐다"고 읽으면 대개 틀립니다.
- **한국 수출액은 FOB, 상대국 수입액은 CIF** 기준이라 같은 거래도 금액이 다릅니다.
  두 소스를 섞어 점유율을 계산하면 안 됩니다.
- **HS 6자리까지만** 볼 수 있습니다. 10자리(HSK)는 관세청 오픈API가 따로 필요합니다.
- 최신 데이터는 나라마다 **2~6개월 늦게** 들어옵니다. 자동으로 있는 데까지 물러나 조회합니다.
- 한국 신고 수출액과 상대국 신고 수입액이 크게 어긋나면(2배 이상) **리포트가 경고합니다.**
  제3국 경유 재수출이나 상대국 통계 커버리지 부족 신호입니다.

전체 내용 → [`data-notes.md`](plugins/trade-stats/skills/trade-stats-lookup/references/data-notes.md)

</details>

## 🔒 하지 않는 것

**바이어 회사 이름은 못 알려드려요.** 도구가 부족해서가 아니라 **법이 그렇습니다.**
한국은 관세법상 수출입 신고정보가 비밀유지 대상이라 어느 회사가 무엇을 얼마에
수출했는지가 어디에도 공개되지 않습니다. 관세청도 무역협회도 마찬가지입니다.
다른 무료 도구를 찾아 헤매지 않으셔도 됩니다.

기업 단위 데이터는 **선하증권(B/L)을 공개하는 나라**에서만 나옵니다. 미국이나 인도 같은 곳입니다.
Panjiva, ImportYeti, Volza 같은 유료 서비스를 씁니다. 한국과 EU, 일본, 중국은 이 방법으로도 나오지 않습니다.

**수출 절차나 관세, 인증은 이 도구가 확인한 내용이 아닙니다.** Claude가 아는 일반 지식으로
답은 하지만 검증된 내용은 아닙니다. 특히 관세율은 계속 바뀌고 있어서
[미국 HTS](https://hts.usitc.gov)나 관세청 FTA 포털, KOTRA에서 꼭 다시 확인하세요.

<details>
<summary><b>🛠 직접 명령어로 쓰기, 개발 (펼치기)</b></summary>

### CLI

```bash
cd plugins/trade-stats/skills/trade-stats-lookup/scripts

python3 analyze.py market   --hs 3907                    # 상위 10개 교역국 (3~5분)
python3 analyze.py market   --hs 3304 --countries 베트남,인도 --monthly 24
python3 analyze.py discover --hs 3304                    # 전 세계 225개국 발굴 (6~10분)
python3 analyze.py discover --hs 3304 --min-market 1000000   # 소량 품목이면 기준선을 낮춘다
python3 fetch_comtrade.py hs-search "화장품"             # HS코드 찾기
python3 fetch_comtrade.py rank   --hs 3907 --year 2025
python3 fetch_comtrade.py mirror --hs 3907 --importer VN --year 2024
```

`python3` 3.11 이상이 필요합니다. 조회 결과는 `~/.cache/trade-stats-lookup/`에 7일간
보관되어 같은 질문은 즉시 답합니다.

무료 공개 API라 요청 간격을 두고 호출합니다. 사내에서 여러 명이 같은 인터넷을 쓴다면
`TRADE_STATS_MIN_INTERVAL=6` 처럼 간격을 늘려주세요.

### 테스트

```bash
python3 tests/record_fixtures.py   # 최초 1회 (픽스처는 레포에 없습니다)
./tests/run_tests.sh               # 오프라인 142개, 네트워크 불필요
./tests/run_tests.sh --live        # + 실제 API 계약 검증
./package.sh                       # 검증 후 배포용 zip 생성
```

테스트는 녹화한 실제 API 응답을 스킬 자체 캐시로 재생합니다. mock 레이어가 없어
현실과 어긋날 일이 없고, 픽스처에 없는 요청은 조용히 네트워크로 새지 않고 실패합니다.

라이브 계약 테스트는 upstream 스펙 변경을 감지하는 조기경보입니다. 오프라인 스위트는
녹화본을 재생하므로 정의상 이걸 잡을 수 없습니다. 매주 월요일 CI가 돌리고,
실패하면 자동으로 이슈를 엽니다.

스킬이 실제로 호출되는지(트리거)는 코드 테스트로 잡을 수 없어 별도 절차로 돕니다.
[`tests/TRIGGER_TESTS.md`](tests/TRIGGER_TESTS.md), [`tests/README.md`](tests/README.md)

### 레포 구조

```
trade-skills/
├─ .claude-plugin/marketplace.json
├─ plugins/trade-stats/skills/trade-stats-lookup/
│  ├─ SKILL.md
│  ├─ scripts/      comtrade.py, customs.py, fetch_comtrade.py, analyze.py, tariff.py
│  └─ references/   한국어 HS 색인, 국가 코드, 데이터 주의사항
├─ tests/           오프라인 142개 + 라이브 계약 12개
└─ package.sh       검증 + zip 생성
```

</details>

## 🗺 로드맵

| 기능 | 상태 |
|---|---|
| 시장 우선순위 (`market`) | ✅ v0.1 |
| 역방향 품목 조회 (`products`) | ✅ v0.1 |
| 관세율 비교 (`tariff`) | ✅ v0.1 |
| **전 세계 신규 시장 발굴 (`discover`)** | ✅ v0.2 |
| **매력도 절대 점수 재설계** | ✅ v0.2 |
| **관세청 HSK 10단위 (`domestic`)** | ✅ v0.2 (인증키 선택) |
| 바이어 후보 발굴 | 검토 중 (무료 경로는 전시회, 웹 검증까지) |
| 현지어 콜드메일 초안 | 예정 |

## 📄 라이선스

**코드**는 MIT입니다 ([`LICENSE`](LICENSE)).

**함께 들어 있는 참조 데이터는 MIT가 아닙니다** ([`NOTICE`](NOTICE)).
특히 `hs.json`의 품목 설명은 **세계관세기구(WCO)가 저작권을 주장하는 HS 노멘클레이처**입니다.
UN Comtrade에서 받았다는 사실이 제3자 재배포 권한을 주지는 않으니, 포크하거나 상용으로
쓰시기 전에 확인하세요. 한국어 색인(`hs_ko.json` 등)은 이 프로젝트의 작업물이고 MIT입니다.

무역통계 출처: [United Nations Comtrade](https://comtrade.un.org).
유엔은 이 프로젝트를 보증하지 않습니다.

---

<div align="center">
<a id="english"></a>

# trade-skills — English

### Pick your export market with numbers, not instinct.

Name a product. No HS code, no API key, no signup.

[한국어](#trade-skills) · **English**

</div>

---

> [!WARNING]
> **Thirty seconds before you use this.** Miss these and you get numbers that are
> correct and conclusions that are backwards.
>
> - **"Share" here means share of imports**, not market share — domestic producers are absent from the data.
> - **No buyer company names.** Not a tool limitation; Korean customs declarations are confidential by law.
> - **Export procedures and tariffs are not verified by this tool.** Check tariff rates independently.
>
> Details → [Reading the numbers](#reading-en)

---

## ⚡ Install

**Claude Code**

```
/plugin marketplace add bonghyunyang/trade-skills
/plugin install trade-stats@trade-skills
```

**Cowork · claude.ai** — download `trade-stats-lookup.zip` from
[Releases](https://github.com/bonghyunyang/trade-skills/releases) and upload it under
**Settings → Capabilities → Skills**.

An internet connection is all you need. No key to request, no `pip install`.

## 💬 Try it

> "Which countries should we target for cosmetics?"

> "Compare lithium battery markets across our top trading partners"

> "HS 3907 — how does Vietnam look?"

> "Where haven't we sold cosmetics yet?"

Built for Korean exporters: `reporter` is fixed to Korea and the reports are in Korean.

## 🧭 Two modes

|  | Command | Coverage | Time |
|---|---|---|---|
| Rank markets you already know | `market` | Named countries, or Korea's top 10 partners | 3–5 min |
| **Find markets you have never sold to** | `discover` | **All 225 Comtrade reporters** | 6–10 min |

The default target list is Korea's top 10 trading partners, which are by definition
countries you already sell to — no new market can come out of that set. `discover`
scans every reporting country instead, then you narrow to two or three and run
`market` on those.

A real run on HS 3304 put **Poland first**: imports grew from $1.49B (2023) to
$2.31B (2025), +24.3% a year, while Korean exports went from $57.5M to $304M — 5.3x.
Poland is not in Korea's top 10, so the default preset could never have surfaced it.

## 📊 What you get

For one HS code, across ten markets by default (3–5 minutes on a cold cache, under a second on a warm one):

| Column | Meaning |
|---|---|
| Local total imports | What that country buys from the world |
| **Market CAGR** | How fast **the market** is growing |
| Korea's exports + CAGR | How fast **your** sales into it are growing |
| Korea's share | Share **of imports** — see the warning above |
| Top supplier | The incumbent, flagged ⚠️ at 60%+ |
| Attractiveness | untapped market 50% + market CAGR 50% |
| Untapped market | local total imports × (1 − Korea's share) — the money still on the table |

Plus per-country supplier tables, three CSVs (UTF-8 BOM, opens straight in Excel),
and a Markdown report.

**The gap between the two CAGRs is usually the most useful number on the page.**

| Pattern | Reading |
|---|---|
| Market ↑ · your exports ↓ | **Losing share** |
| Market ↓ · your exports ↑ | **Likely an entrepôt** — the real destination is elsewhere |
| Market ↑ · your exports ↑↑ | **Gaining share** — push here now |

## 🤔 Why this exists

Written by someone who did overseas sales, for that job.

**Market research eats half a day per product.** Deciding which country to go
after first means opening KOTRA reports, KITA's K-stat, and ITC Trade Map
separately, typing the HS code into each, and copying numbers into a spreadsheet.
The questions being asked are simple — where are we losing share, where is there
still room — but getting to them is not.

**So the decision ends up being made on instinct.** The country where the last
trade show produced the most business cards. Ask for the reasoning and it is
"the market is big." Whether the market is actually growing, who is capturing
that growth, and whether any room is left usually goes unchecked.

**Buyer discovery is the next problem, and the first one has already exhausted
you.** Pick the wrong market and the contact list length does not matter.

Tools that just produce numbers already exist. The failure mode is numbers that
**quietly lead somewhere wrong**: import share mistaken for market share, an
entrepôt read as a promising market, a country with no data read as a bad market.
So the warnings are not buried in documentation — they are printed inside the
report itself.

<a id="reading-en"></a>

## ⚠️ Reading the numbers

- **Share of imports is not market share.** "Korea holds 53% in Vietnam" means 53%
  of *imported* instant noodles — the local manufacturers who actually dominate
  that market are absent from the dataset entirely. Highest risk in food,
  automotive, steel, and cosmetics. For the same reason, "local total imports" is
  not the size of that country's market.
- **The score is absolute, so it travels.** Both axes are fixed scales — untapped
  market $10M–$10B, market CAGR −10%…+20% — so a country scores the same whoever
  else is in the query, and scores from separate runs are comparable. The ceiling
  is the point: without it the score just tracks market size (measured at
  Spearman +0.89) and tells you that big markets are big.
- **Two different reasons to be unranked.** `측정불가` means a required figure is
  missing and the country could not be compared — not that it is a bad market.
  `규모 미달` means the data is there and the market is genuinely small. Lower
  `--min-market` if your business runs on smaller volumes.
- **Untapped is not an empty market.** A low Korean share may mean someone else is
  already sitting there, so the incumbent supplier is shown alongside it.

<details>
<summary><b>More caveats (expand)</b></summary>

- **A country excluded from the ranking is not a bad market** — it could not be measured.
- **Unit price is `value ÷ weight`.** Its movement mixes price changes with
  product-mix changes and the two cannot be separated above HS 6-digit. Not a
  quality signal.
- **FOB vs CIF.** Korea reports exports FOB, partners report imports CIF. Never
  compute a share by mixing the two.
- **HS 6-digit maximum.** National 8/10-digit subdivisions are not comparable
  across countries and are not in Comtrade.
- Latest data lags 2–6 months per reporter; the skill steps back automatically.
- When Korea's reported exports and the partner's reported imports diverge by 2x or
  more, the report flags it — a re-export or coverage signal.

Full detail: [`data-notes.md`](plugins/trade-stats/skills/trade-stats-lookup/references/data-notes.md) (Korean)

</details>

## 🔒 Boundaries

**No company-level data.** Korean customs declarations are confidential by law, so
no source gives you exporter name × product × value. Buyer names require paid
bill-of-lading data (Panjiva, ImportYeti, Volza) from countries that publish B/Ls —
the US and India do; Korea, the EU, Japan, and China do not.

**One optional feature needs a key.** Everything above is keyless. Only the HSK
10-digit lookup (`domestic`) uses Korea Customs Service data, which has no public
unauthenticated tier. It is free to register and the skill prints step-by-step
instructions when you actually need it. What it buys you: your exact product line
rather than a 6-digit bucket, a unit price you can read as price rather than
product mix, and figures roughly a year fresher than Comtrade. It does **not**
produce shares or market size — no country publishes 10-digit import statistics,
so that denominator does not exist.

**Export procedures, tariffs, and certification are not verified here.** Claude can
answer from general knowledge, but this tool did not check it. US tariff policy has
been changing since 2025 — verify at [US HTS](https://hts.usitc.gov) and with your
customs authority.

<details>
<summary><b>🛠 CLI · Development (expand)</b></summary>

```bash
cd plugins/trade-stats/skills/trade-stats-lookup/scripts
python3 analyze.py market   --hs 3907    # rank a known shortlist (3-5 min)
python3 analyze.py discover --hs 3304    # scan all 225 reporters (6-10 min)
python3 fetch_comtrade.py hs-search "화장품"
```

Requires `python3` 3.11+. Responses cache for 7 days under
`~/.cache/trade-stats-lookup/`. This runs against UN Comtrade's free
unauthenticated tier: requests are paced, `Retry-After` is honored, and the
interval cannot be set below one second. Raise `TRADE_STATS_MIN_INTERVAL` on a
shared office IP; set `TRADE_STATS_CONTACT` so the publisher can reach you.

```bash
python3 tests/record_fixtures.py   # once — fixtures are gitignored
./tests/run_tests.sh               # 142 offline tests, no network
./tests/run_tests.sh --live        # + real API contract tests
./package.sh                       # verify, then build the zip
```

Tests replay recorded API responses through the skill's own cache layer, so there
is no mock layer to drift out of sync, and an un-fixtured request fails loudly
instead of silently going to the network. The live contract suite is the
early-warning system for upstream schema changes — the offline suite replays
recordings and cannot catch those. It runs weekly in CI and opens an issue on
failure.

Skill triggering cannot be covered by unit tests; see
[`tests/TRIGGER_TESTS.md`](tests/TRIGGER_TESTS.md).

</details>

## 📄 License

Code is MIT ([`LICENSE`](LICENSE)).

**Bundled reference data is not MIT** ([`NOTICE`](NOTICE)). The commodity
descriptions in `hs.json` are World Customs Organization Harmonized System
nomenclature, obtained via UN Comtrade's public reference endpoint; that does not
by itself convey WCO redistribution rights. Check your position before forking or
shipping commercially.

Trade statistics from [United Nations Comtrade](https://comtrade.un.org).
The United Nations does not endorse this project.

---

<div align="center">

**감으로 찍던 시장 선정을, 근거 있는 결정으로.**

</div>
