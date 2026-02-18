# NoiseCancel 경쟁사 분석 리포트

> 분석일: 2026-02-18

---

## 1. 시장 개요

LinkedIn 피드 노이즈 필터링/큐레이션 시장은 크게 4가지 카테고리로 나뉜다:

| 카테고리 | 접근 방식 | 대표 제품 |
|---|---|---|
| **브라우저 확장** | DOM 조작으로 피드 요소 숨김 | LinkOff, MyFeedIn, Feed Cleaner |
| **AI 모니터링 SaaS** | 키워드/AI 기반 멘션 모니터링 → 알림 | Octolens, Shield |
| **피드 차단/생산성** | 피드 자체를 제거해 집중력 향상 | BeTimeful, FeedBlocker, News Feed Eradicator |
| **오픈소스/개발자 도구** | 소셜 미디어 분석/큐레이션 에이전트 | LangChain Social Media Agent, Gobo |

**NoiseCancel의 포지션**: AI 분류 + Slack 전달 + 피드백 루프를 결합한 **CLI 기반 개인 큐레이션 파이프라인** — 기존 카테고리에 정확히 맞는 경쟁자가 없는 **블루오션 영역**

---

## 2. 직접 경쟁사 상세 분석

### 2.1 MyFeedIn — 가장 유사한 경쟁자

| 항목 | 내용 |
|---|---|
| **URL** | https://myfeedin.co |
| **형태** | Chrome 확장 프로그램 |
| **핵심 기능** | 커스텀 피드 생성, 특정 크리에이터만 팔로우하는 필터 피드, 광고/알고리즘 추천 제거, 팀 협업 (큐레이션 리스트 공유) |
| **가격** | 무료 (첫 커스텀 피드 1개), 유료 구독 (추가 피드) |
| **평점** | Chrome Web Store 5/5 |
| **강점** | 직관적 UI, LinkedIn 피드를 Netflix 워치리스트처럼 큐레이션, 하루 10분이면 충분 |
| **약점** | 데스크탑 Chrome 전용, AI 분류 없음 (수동 크리에이터 지정), 피드백 루프 없음, 모바일 미지원 |

**vs NoiseCancel**: MyFeedIn은 "누구의 글을 볼지" 수동 선택, NoiseCancel은 "어떤 종류의 글이 가치 있는지" AI가 자동 판단. 우리가 더 자동화되고, 규칙 기반 커스터마이징이 가능.

---

### 2.2 LinkOff

| 항목 | 내용 |
|---|---|
| **URL** | https://github.com/njelich/LinkOff |
| **형태** | Chrome/Firefox/Edge 확장 (오픈소스) |
| **핵심 기능** | 콘텐츠 타입별 필터 (polls, videos, promoted), 특정 회사/사람 숨기기, 키워드 필터링, 광고 차단, 다크모드 |
| **가격** | 무료 (오픈소스) |
| **강점** | 무료, 크로스 브라우저, 세밀한 필터 옵션, 오픈소스로 커뮤니티 기여 가능 |
| **약점** | 규칙 기반만 (AI 없음), "가치 있는 콘텐츠" 판별 불가, 외부 전달(Slack) 없음, 피드백 학습 없음 |

**vs NoiseCancel**: LinkOff는 단순 키워드/타입 필터, NoiseCancel은 AI가 맥락을 이해하고 분류. "이 포스트가 왜 가치 있는지" reasoning 제공.

---

### 2.3 LinkedIn Content Filter (AI Chrome Extension)

| 항목 | 내용 |
|---|---|
| **URL** | Medium 블로그 프로젝트 (akankshaagarwal007) |
| **형태** | Chrome 확장 (개인 프로젝트) |
| **핵심 기능** | OpenAI GPT로 모든 포스트에 0.0~1.0 품질 점수 부여, 임계값 이하 포스트 숨김 |
| **가격** | 오픈소스 (API 비용 별도) |
| **강점** | AI 기반 품질 판별의 개념 증명, GPT 활용 |
| **약점** | 개인 프로젝트 수준 (프로덕션 레벨 아님), 단순 점수만 (카테고리/규칙 없음), Slack 전달 없음, 피드백 루프 없음 |

**vs NoiseCancel**: 가장 개념적으로 유사하지만, NoiseCancel은 다중 카테고리 분류, 사용자 정의 규칙, Slack 전달, 피드백 학습까지 포함하는 완전한 파이프라인.

---

### 2.4 Octolens

| 항목 | 내용 |
|---|---|
| **URL** | https://octolens.com |
| **형태** | SaaS 웹 앱 |
| **핵심 기능** | 브랜드 멘션 모니터링 (LinkedIn, Reddit, X, GitHub 등), AI 관련성 필터링, Slack/Email/Webhook 전달, 키워드 트렌드 분석 |
| **가격** | Individual $19/월, Startup $59/월, Scale $69/월 (7일 무료 체험) |
| **평점** | Capterra/GetApp 좋은 평가 |
| **강점** | 멀티 플랫폼, AI 관련성 점수, Slack 연동, 프로덕션 레벨 SaaS |
| **약점** | B2B 브랜드 모니터링 특화 (개인 피드 큐레이션 아님), 월 $19~69 비용, 키워드 15개 제한 (Scale), API 없음, 자기 피드가 아닌 공개 멘션만 모니터 |

**vs NoiseCancel**: Octolens는 "남들이 우리 브랜드를 언급한 것"을 찾는 도구, NoiseCancel은 "내 피드에서 나에게 가치 있는 것"을 찾는 도구. 목적이 근본적으로 다름.

---

### 2.5 FeedEngine

| 항목 | 내용 |
|---|---|
| **URL** | Chrome Web Store |
| **형태** | Chrome 확장 프로그램 |
| **핵심 기능** | LinkedIn 콘텐츠 큐레이션/발견, 포스트 인사이트 통계, 프로필 정보, 개인 브랜딩/리드 생성 지원 |
| **가격** | 무료 |
| **평점** | Chrome Web Store 5.0/5.0 (1,200+ 리뷰) |
| **강점** | 높은 사용자 만족도, 콘텐츠 발견에 강점 |
| **약점** | 노이즈 "제거"보다 콘텐츠 "발견/보강" 중심 — 필터링 도구가 아님 |

### 2.6 LinkedIn AI Post Detector

| 항목 | 내용 |
|---|---|
| **URL** | Chrome Web Store |
| **형태** | Chrome 확장 프로그램 |
| **핵심 기능** | LinkedIn 포스트의 AI 생성 여부 감지, Red/Amber/Green 상태 표시, "Filter AI" 토글로 AI 생성 포스트 필터링 |
| **가격** | 무료 |
| **강점** | AI 생성 콘텐츠 스팸 감지라는 독특한 포지셔닝, 간단한 UX |
| **약점** | AI 생성 여부만 판별, 콘텐츠 품질/관련성 판단 불가 |

**vs NoiseCancel**: 흥미로운 단일 기능 도구. NoiseCancel의 분류 규칙에 "AI 생성 여부"를 추가 시그널로 활용할 수 있음.

### 2.7 Shield (LinkedIn Analytics)

| 항목 | 내용 |
|---|---|
| **URL** | https://www.shieldapp.ai |
| **형태** | SaaS 웹 앱 + Chrome 확장 |
| **핵심 기능** | LinkedIn 오가닉 포스트 분석 (임프레션, 인게이지먼트, 팔로워 성장), 전체 포스트 히스토리 분석, 최고 성과 포스트 식별, Earned Media Value 계산 |
| **가격** | Starter $8/월, Creator $16/월, Influencer $25/월 (연간 기준, 10-14일 무료 체험) |
| **강점** | 2019년부터 운영, LinkedIn 분석 특화, 저렴 |
| **약점** | **분석 도구**이지 필터링 도구가 아님 — "내 포스트 성과 측정"이 목적 |

---

## 3. 간접 경쟁사

### 3.0 Quuu — AI 콘텐츠 큐레이션

| 항목 | 내용 |
|---|---|
| **URL** | https://quuu.co |
| **형태** | SaaS 웹 앱 |
| **핵심 기능** | AI 기반 콘텐츠 추천 (일 6개), 브랜드 보이스 맞춤, 최적 게시 시간 분석, LinkedIn/X/Facebook 지원 |
| **가격** | $19.79/월 (7일 무료 체험) |
| **평점** | Product Hunt 4.9/5.0 (69 리뷰), 50,000+ 마케터 사용 |
| **강점** | 콘텐츠 큐레이션에 특화, 브랜드 맞춤형 |
| **약점** | "게시할 콘텐츠 추천" 도구 — 피드 소비 필터링이 아님, 마케터 관점 |

### 3.0.1 Feedly

| 항목 | 내용 |
|---|---|
| **URL** | https://feedly.com |
| **형태** | SaaS 웹/모바일 앱 |
| **핵심 기능** | RSS 기반 멀티소스 콘텐츠 수집, AI 기사 요약/하이라이트, 키워드 알림, Buffer/Hootsuite 연동 |
| **가격** | Basic 무료, Pro $5/월, Market Intelligence $1,600~2,400/월 |
| **강점** | 성숙한 제품, 강력한 AI, 방대한 소스 |
| **약점** | RSS 기반이라 LinkedIn 피드 직접 필터링 불가, 고급 AI는 고가 |

**vs NoiseCancel**: Feedly는 RSS/뉴스 큐레이션, NoiseCancel은 LinkedIn 피드 큐레이션. 보완 관계에 가까움.

### 3.1 BeTimeful

| 항목 | 내용 |
|---|---|
| **URL** | https://www.betimeful.com |
| **핵심 기능** | 뉴스피드 자체를 제거 (DM/포스팅은 가능), 시간 제한 접근 (1/5/10분) |
| **플랫폼** | iOS, Android, Chrome, Safari |
| **가격** | 무료 (Pro: 14일 체험 후 유료) |
| **약점** | 피드를 아예 숨기므로 가치 있는 콘텐츠도 못 봄 — **NoiseCancel과 정반대 철학** |

### 3.2 News Feed Eradicator

| 항목 | 내용 |
|---|---|
| **URL** | Chrome Web Store |
| **핵심 기능** | 피드 영역을 영감주는 인용구로 대체 |
| **가격** | 무료 |
| **약점** | "all or nothing" 접근 — 필터링이 아니라 제거 |

### 3.3 Saner Social Media (SSM)

| 항목 | 내용 |
|---|---|
| **URL** | Chrome Web Store |
| **핵심 기능** | 피드 숨기기/대체, 다크모드, 일시 차단 해제 |
| **평점** | 4.7/5 |
| **강점** | 오픈소스, 크로스 플랫폼 |
| **약점** | 동일한 "all or nothing" 문제 |

---

## 4. 개발자/오픈소스 도구

### 4.1 LangChain Social Media Agent

| 항목 | 내용 |
|---|---|
| **URL** | https://github.com/langchain-ai/social-media-agent |
| **핵심 기능** | 콘텐츠 소싱/큐레이션/스케줄링, Human-in-the-loop, Slack 인제스트, Cron 기반 자동화 |
| **기술** | TypeScript, LangGraph, LangChain |
| **강점** | LangChain 공식 프로젝트, 잘 설계된 아키텍처, 커스터마이징 가능 |
| **약점** | **콘텐츠 생성/게시 도구**이지 소비 필터링 도구가 아님, LinkedIn 스크래핑 없음, 복잡한 셋업 |

**vs NoiseCancel**: 방향이 반대 — LangChain Agent는 "포스팅할 콘텐츠 큐레이션", NoiseCancel은 "소비할 콘텐츠 큐레이션"

### 4.2 Gobo (MIT Media Lab)

| 항목 | 내용 |
|---|---|
| **URL** | https://github.com/mitmedialab/gobo |
| **핵심 기능** | 투명한 피드 필터링, 왜 포스트가 포함/제외됐는지 설명, 커스텀 필터 |
| **기술** | Python/JavaScript |
| **강점** | 학술 프로젝트로 투명성 강조, 필터 로직 시각화 |
| **약점** | 유지보수 중단된 것으로 보임, LinkedIn 미지원, 웹앱 (CLI 아님) |

### 4.3 Postiz

| 항목 | 내용 |
|---|---|
| **URL** | https://github.com/gitroomhq/postiz-app |
| **핵심 기능** | AI 기반 소셜 미디어 스케줄링, 분석 |
| **강점** | 오픈소스, 셀프호스팅, AI 기능 내장 |
| **약점** | 게시 도구이지 소비/필터링 도구가 아님 |

---

## 5. 경쟁 포지셔닝 매트릭스

```
                        AI 분류 능력
                        높음
                          │
            Octolens      │      ★ NoiseCancel
            (SaaS)        │      (CLI + AI + Slack)
                          │
            Feedly AI     │      LinkedIn Content Filter
                          │      (Chrome + GPT, 프로토타입)
  ────────────────────────┼──────────────────────────
        LinkOff           │      Quuu
        (규칙기반)         │      (게시 큐레이션)
                          │
  AI Post Detector        │      MyFeedIn
  (단일기능)               │      (수동 큐레이션)
                          │
        BeTimeful         │      Shield
        (완전차단)         │      (분석 전용)
                        낮음

  브라우저 내 필터        ←─→    외부 전달 (Slack 등)
```

### 전체 비교표

| 제품 | 유형 | AI | 피드 필터링 | LinkedIn | 가격 | 오픈소스 |
|---|---|---|---|---|---|---|
| **★ NoiseCancel** | **CLI** | **Claude** | **AI 분류+규칙** | **O** | **API비용 ~$5/월** | **O** |
| MyFeedIn | Chrome 확장 | X | 수동 큐레이션 | O | 프리미엄 | X |
| LinkOff | Chrome/Firefox | X | 규칙 기반 | O | 무료 | O |
| LinkedIn Content Filter | Chrome 확장 | GPT | AI 품질 점수 | O | API 비용 | O |
| FeedEngine | Chrome 확장 | X | 콘텐츠 발견 | O | 무료 | X |
| AI Post Detector | Chrome 확장 | O | AI생성 감지만 | O | 무료 | X |
| Octolens | SaaS | O | 멘션 모니터링 | O | $19~69/월 | X |
| Shield | SaaS | X | 분석 전용 | O | $8~25/월 | X |
| Quuu | SaaS | O | 게시 추천 | O | $19.79/월 | X |
| Feedly | SaaS/앱 | O | RSS 기반 | 간접 | $0~2,400/월 | X |
| BeTimeful | 앱/확장 | X | 전체 차단 | O | 프리미엄 | X |
| News Feed Eradicator | Chrome 확장 | X | 전체 제거 | O | 무료 | X |
| Gobo (MIT) | 웹 앱 | ML | ML 필터 | X | 무료 | O |
| LangChain Agent | 프레임워크 | LLM | 게시 큐레이션 | O | API 비용 | O |

---

## 6. NoiseCancel의 차별화 요소 (Competitive Moat)

| 차별점 | 설명 | 경쟁자 대비 |
|---|---|---|
| **AI 맥락 분류** | Claude API로 포스트 내용을 이해하고 카테고리 분류 | LinkOff(키워드만), MyFeedIn(수동) 대비 우월 |
| **사용자 정의 규칙** | YAML 기반 boost/suppress/include 규칙 시스템 | 대부분의 확장이 단순 키워드 매칭만 지원 |
| **Slack 전달** | 분류된 고가치 콘텐츠를 Slack으로 푸시 | 브라우저 확장들은 "LinkedIn을 열어야" 볼 수 있음 |
| **피드백 루프** | 👍/👎 피드백 → 자동 규칙 생성 → 정확도 개선 | 어떤 경쟁자도 이 기능 없음 |
| **CLI + 자동화** | cron job으로 완전 자동화 가능, headless 실행 | 브라우저 확장은 브라우저가 열려있어야 함 |
| **투명한 추론** | 각 분류에 대한 reasoning 제공 | Gobo가 유사한 철학이나 유지보수 중단 |
| **로컬/프라이버시** | 데이터가 로컬 SQLite에 저장, SaaS 의존 없음 | Octolens 등 SaaS는 데이터가 서버에 저장 |
| **비용 효율** | Claude Haiku 배치 처리로 월 $1~5 수준 예상 | Octolens $19~69/월, Shield $6~99/월 |

---

## 7. 위협 및 리스크

| 리스크 | 심각도 | 대응 방안 |
|---|---|---|
| **LinkedIn 스크래핑 차단** | 높음 | anti-detection 모듈, 사람 행동 모방, 세션 TTL 관리 |
| **LinkedIn TOS 위반** | 중간 | 개인 피드 열람만 (대량 크롤링 아님), 오픈소스로 개인 사용 강조 |
| **LinkedIn 네이티브 필터 개선** | 중간 | 2025년 "My Network" 탭 테스트 중 — AI 분류+외부 전달은 네이티브로 불가 |
| **GPT/Claude API 비용 변동** | 낮음 | Haiku 모델 + 배치 처리로 비용 최소화, 모델 교체 용이한 설계 |
| **브라우저 확장의 AI 통합** | 중간 | MyFeedIn이 AI를 추가하면 위협 — 그러나 CLI+Slack 파이프라인은 다른 유즈케이스 |

---

## 8. 시장 기회

1. **"소비" 측면의 AI 큐레이션은 블루오션**: 대부분의 AI 소셜 도구가 "생성/게시"에 집중. "소비/필터링" AI 도구는 거의 없음
2. **개발자/파워유저 타겟**: CLI 도구를 선호하는 기술 사용자층이 명확히 존재
3. **"LinkedIn을 안 열어도 되는" 가치**: Slack으로 핵심 콘텐츠만 받는 워크플로우는 생산성 도구로 포지셔닝 가능
4. **피드백 기반 개인화**: 시간이 지날수록 정확도가 올라가는 flywheel 효과
5. **멀티 플랫폼 확장 가능성**: 같은 파이프라인으로 X(Twitter), Reddit 등 확장 가능

---

## 9. 결론 및 구현 제안

### 우선순위 높은 차별화 기능 (MVP)
1. **AI 분류 + reasoning** — 이것이 핵심 가치. 정확도가 생명
2. **Slack 전달** — "LinkedIn을 열지 않아도 된다"는 핵심 UX
3. **피드백 버튼** — flywheel의 시작점

### 경쟁자에서 배울 점
- **MyFeedIn**: "하루 10분이면 충분" 같은 시간 절약 메시지가 효과적
- **LinkOff**: 콘텐츠 타입별 필터 (polls, videos 등)는 규칙에 포함할 것
- **Octolens**: Slack 전달 + AI 관련성 점수 조합이 검증된 패턴
- **Gobo**: 투명한 필터링 설명은 신뢰 구축에 중요

### 포지셔닝 제안
> "LinkedIn의 노이즈를 AI가 걸러주고, 가치 있는 콘텐츠만 Slack으로 보내드립니다. 피드를 차단하는 게 아니라, 피드에서 금을 캐냅니다."
