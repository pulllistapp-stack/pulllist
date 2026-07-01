# PullList — Onboarding Flow

> **목적**: 신규 유저 signup 후 "첫 카드 등록 → 첫 매물 알림 → Pro 컨버전" 까지의 여정 설계.
> **자매 문서**: `tier-design.md` (기능 경계) · `pricing.md` (가격).
> **최근 갱신**: 2026-07-01 (초안)

---

## 0. 지금 상태 한 줄

Signup → 성공 시 `/portfolio` 로 리다이렉트 → **빈 스크린**. 데스크탑 유저에겐 무엇을 해야할지 UX 힌트 없음. 스캔 CTA는 mobile-only. 이 문서에서 재설계.

---

## 1. 핵심 지표 (North Star)

각 스텝의 성공/실패는 이 지표로 판단.

| Stage | 지표 | 목표 |
|---|---|---|
| Signup 완료 → 첫 카드 등록 | 20분 이내 | 60% |
| 첫 카드 등록 → 첫 위시리스트 | 24시간 이내 | 40% |
| 첫 위시리스트 → 첫 알림 감지 | 7일 이내 | 30% |
| 첫 알림 감지 → Pro 트라이얼 시작 | 30일 이내 | 5-10% |
| Pro 트라이얼 → 결제 완료 | 트라이얼 종료 시 | 20%+ |

---

## 2. 원칙 (locked)

1. **Time-to-first-wow ≤ 60초**. Signup 완료 후 유저가 "오, 좋다" 하는 순간까지 1분.
2. **빈 스크린 절대 안 됨**. `/portfolio`, `/wishlist`, `/collection` 등 유저 데이터 필요한 페이지는 빈 상태에서 반드시 액션 3개 이상 제안.
3. **온보딩 위저드는 최소한**. 3스텝 이상 강제 위저드 금지. 유저는 사이트 자체를 탐색하고 싶어서 왔음.
4. **Pro 언급은 명확한 trigger 에서만**. 알림 설정 · N번째 카드 등록 등. Signup 직후 pricing 페이지 뜨기 금지.
5. **Email verification 은 blocking 아님**. 즉시 사용 가능, 알림 실제 발송 (외부 채널) 시에만 verify 요구.
6. **모바일 우선 flow, 데스크탑 대안 있음**. 스캔은 mobile-only 지만 데스크탑도 이하 flow 로 대응.
7. **온보딩 진행률은 명시적 UI 로 노출**. "3개 남았어요" 배지 · 프로그레스 바.

---

## 3. Post-Signup Flow (결정 대기)

### Q1. 첫 스크린 선택

Signup 완료 후 어디로 리다이렉트?

- **옵션 A** — `/portfolio` + 강력한 empty state
  - "첫 카드 추가 3가지 방법" 카드 뷰: 📷 스캔 (mobile) · 🔍 검색 · 🔥 트렌딩에서 선택
  - 하단에 "인기 카드 지금 등록" 미니 그리드 (top 10 movers, one-click add)
- **옵션 B** — `/onboarding` 위저드 (3스텝)
  - Step 1: 좋아하는 세트 3개 선택 (또는 스킵)
  - Step 2: 언어 선택 (EN / JP / KR)
  - Step 3: 알림 채널 선택 (인앱 벨 default)
- **옵션 C** — `/trending` 리다이렉트
  - 즉시 "재밌는 것" 노출 (트렌딩 top 3 podium)
  - 각 카드에 heart · plus 버튼으로 인터랙션 유도
  - Portfolio 는 top nav 에 링크만
- **옵션 D** — `/` (홈) 리다이렉트, 로그인 상태로 유저별 커스텀 홈
  - Hero 위에 유저 이름 · 진행률 배지
  - 하단에 "지금 뭘 할까?" 3-카드 (트렌딩 / 검색 / 스캔)

**추천: A + D 결합**. Signup → `/` (로그인 상태 홈) 리다이렉트, 유저 이름 배지 + 진행률 (0/5 스텝) + "지금 뭘 할까?" 3-카드. `/portfolio` 를 첫 스크린으로 두면 빈 상태의 심리적 무게 큼. 위저드 (B) 는 진지 컬렉터엔 불필요, 초심자엔 stall 요인.

### Q2. 첫 카드 등록 흐름

Empty portfolio → 첫 카드까지 최단 경로.

- **옵션 A** — 스캔 (mobile-only)
- **옵션 B** — 검색 → 카드 디테일 → "+" 버튼
- **옵션 C** — 트렌딩 top 30 뷰에서 원클릭 add (heart + plus 다 인라인)
- **옵션 D** — 세트 페이지에서 벌크 add (owned 체크박스 → "이 중 XX개 등록" 버튼)
- **옵션 E** — 인기 세트 미니 뷰 (Chaos Rising 등 최근 화제 세트 4-6장 노출) — 첫 스크린 유저용 hook

**추천: C + E 조합**. 트렌딩 원클릭 + 인기 세트 hook 모두 유저의 "첫 카드" 결정 부담을 낮춤. 검색 (B) 은 유저가 이미 이름 아는 경우만, empty portfolio 유저의 대다수는 "뭘 등록하지?" 상태.

### Q3. Pro upsell 타이밍

Pro 언급을 어느 순간에?

- **옵션 A** — Signup 직후 pricing 페이지 배지 (하단 "Pro 알아보기" 링크만)
- **옵션 B** — 특정 액션 trigger — 첫 위시리스트 등록 시 인라인 "Free 는 인앱 벨 · 하루 1회 다이제스트, Pro 는 실시간 + Discord/Push" 카드
- **옵션 C** — N번째 카드 등록 시 (예: 5장) — "포트폴리오 진지하시네요, Pro 시작 트라이얼?"
- **옵션 D** — 30일 리텐션 후 — "PullList 한 달 됐네요, Pro 트라이얼 어떠세요?"
- **옵션 E** — B + C + D 다 (여러 trigger)

**추천: B (첫 위시리스트) + D (30일 리텐션)**. 이유:
- B 는 알림 설정 자체가 "Pro 가치" 이해 순간 — 인라인 비교가 명확
- D 는 리텐션 확인된 유저 대상 → 컨버전 rate 최대
- C 는 트리거 노이즈 (5장은 empty state 벗어난 자연 이벤트일 뿐)
- E 는 push 밀도 과다 = anti-pattern (`tier-design.md` §6)

Signup 직후 (A) 는 명시적 pricing 링크만 (top nav), 팝업/모달 금지.

### Q4. Email verification 흐름

PROJECT_STATUS §5 Sprint 1: Resend 통합 예정.

- **옵션 A** — Signup 시 즉시 verify 이메일 발송, verify 안 하면 로그인 blocked
- **옵션 B** — Signup 시 verify 이메일 발송, verify 안 하면 알림 발송 (이메일 채널) 만 blocked
- **옵션 C** — Signup 시 verify 이메일 발송, 무엇도 blocked 안 함, 유저 스스로 언제든 verify

**추천: B**. 이유:
- Friction 최소화 (signup → 즉시 사용, 이메일 확인 스텝 skip 가능)
- 스팸 계정 방지 는 알림 채널 gate 로 충분 (스팸 signup 은 알림 목적이 아니라 컬렉션 스팸 · 봇 시그널)
- 이메일 verify banner 는 대시보드 상단 (dismiss 가능) 에 노출

### Q5. 언어 preference

- **옵션 A** — 브라우저 `Accept-Language` 자동 감지 → 첫 로드에 default 언어 (EN/JP/KR) 설정
- **옵션 B** — Signup 완료 스크린에 언어 명시 선택
- **옵션 C** — 감지 + 최소한 선택 (감지된 언어로 default, 상단에 "언어 변경" 링크)

**추천: C**. 감지 정확도 문제 · JP 유저인데 브라우저 KR 인 케이스 등 대비. Sub-tab 언어 변경 UI 는 이미 사이트 곳곳에 있어야 함 (top nav).

### Q6. 온보딩 미션 (게이미피케이션)

ROADMAP_IDEAS §engagement 🔵 티어 아이템: "3개 미션 → Pro 1일 무료".

- **옵션 A** — 스킵 (게이미피케이션 안 함, `tier-design.md` §6 anti-패턴)
- **옵션 B** — 경량 미션 3개 → 완료 시 아무 보상 없이 진행률 100% 표시 (성취감만)
- **옵션 C** — 미션 5개 → 완료 시 Pro 트라이얼 3일 (게이미피케이션 + hook)
- **옵션 D** — 미션 3개 → 완료 시 초기 100명 Founding Collector 뱃지 (`pricing.md` §2 Q5 B 안과 연동)

**추천: D**. 이유:
- Founding Collector 뱃지는 정식 오픈 초기 100명 한정 스테이터스 → 미션 완료 유도 강함
- Pro 트라이얼 (C) 은 별도 채널로 관리 (트라이얼은 어차피 명시 opt-in)
- 완전 스킵 (A) 은 empty state 유저에게 "뭘 해야 하지?" 답 없음
- 미션 예시: "카드 5장 등록 · 위시 1장 · 프로필 사진 업로드"

### Q7. 초심자 vs 컬렉터 분기

Signup 초기에 "얼마나 컬렉트하셨나요?" 물어서 다른 flow?

- **옵션 A** — 분기 안 함, 통합 flow
- **옵션 B** — 3옵션 뜨기: 초심자 / 재개 컬렉터 / 프로 컬렉터 → 다른 미션 세트
- **옵션 C** — 실 데이터 기반 자동 분기 (등록 카드 수 · 세트 다양성) → 미션 다른

**추천: A**. 이유:
- 분기는 UX 복잡도 상승 대비 정확도 낮음 (self-report 편향)
- 통합 flow 로 시작 → 데이터 쌓이면 옵션 C 검토 (미래)

### Q8. 데스크탑 우선 vs 모바일 우선

스캔은 mobile-only 인데, 첫 카드 등록 흐름을 어느 디바이스 기준으로?

- **옵션 A** — 모바일 우선 (스캔 강조), 데스크탑은 검색·트렌딩 대안
- **옵션 B** — 데스크탑 우선 (검색·트렌딩 강조), 모바일 유저에게 QR 로 데스크탑 유도
- **옵션 C** — 각 디바이스에 최적화된 별도 flow

**추천: C**. 이유:
- 모바일: 스캔 hook 이 압도적 (박스 오픈 → 즉시 스캔) → 첫 화면 하단에 스캔 FAB
- 데스크탑: 트렌딩/검색 강조 → 첫 화면에 트렌딩 top 6 인라인 그리드 + 검색 바
- Empty state 안내 문구는 디바이스별로 다르게

---

## 4. 제안 Post-Signup Flow (v0 draft)

Q1-Q8 답변 후 이 섹션 잠금. 현재는 추천안 기준 초안.

### 4.1 데스크탑 (Signup → 홈)

```
[Signup 완료 이메일 · 즉시 dismiss 가능]
       ↓
[/ 홈 (로그인 상태)]
       ↓
┌──────────────────────────────────────┐
│  안녕하세요, {display_name}!            │
│                                      │
│  진행률 [░░░░░] 0/5                    │
│                                      │
│  ┌────────┬────────┬────────┐        │
│  │  🔍    │  🔥    │  📷    │        │
│  │ 검색해서 │ 트렌딩에서│ 스캔    │        │
│  │  등록   │  등록   │(모바일) │        │
│  └────────┴────────┴────────┘        │
│                                      │
│  트렌딩 top 6 인라인 그리드              │
│  (heart + plus 원클릭)                │
│                                      │
│  이번주 인기 세트 미니 뷰                │
└──────────────────────────────────────┘
```

### 4.2 모바일 (Signup → 홈)

```
[/ 홈 (로그인 상태)]
       ↓
┌──────────────────────┐
│  안녕하세요, {name}!    │
│  진행률 [░░░░░] 0/5     │
│                      │
│  ┌───────────────┐   │
│  │ 📷 스캔으로 등록 │   │
│  │  (탭)          │   │
│  └───────────────┘   │
│                      │
│  🔥 트렌딩 top 3      │
│  (스와이프 그리드)      │
│                      │
│  🔍 검색 · 세트 브라우저 │
│                      │
│  [FAB: 스캔]          │
└──────────────────────┘
```

### 4.3 온보딩 미션 세트 (Q6 D안 채택 시)

3개 미션:
1. **첫 카드 5장 등록** — 스캔 · 검색 · 트렌딩 아무 방식 OK
2. **첫 위시리스트 1장** — target price 설정 → 알림 시스템 소개 인라인
3. **프로필 사진 업로드** — 표시 이름 + 마스코트 아바타 default, 커스텀 가능

완료 시:
- 프로필에 **Founding Collector 뱃지** 부여 (초기 100명 한정)
- Pro 트라이얼은 별도 유도 (§3 Q3 B trigger 로 커버)

---

## 5. 미래 검토 (Not committed)

정식 오픈 후 데이터 보고 재검토.

- **Referral 시스템** — 친구 3명 초대 시 Pro 1개월 무료
- **연말 통계 이메일** — "당신의 2026 컬렉션" (마쓰다지루시 · Wrapped 스타일)
- **초심자 튜토리얼 시리즈** — News 카테고리 (`Guide`) 를 온보딩 시퀀스로 지정
- **커뮤니티 discord 초대** — Pro 유저 exclusive 채널

---

## 6. 지표 트래킹 (analytics 훅)

각 스텝에 이벤트 훅 심어야 지표 (§1) 계산 가능.

| Event | Property | Trigger |
|---|---|---|
| `signup_completed` | user_id, method (email/google) | POST /auth/signup 성공 |
| `onboarding_home_viewed` | user_id | GET / (첫 로그인 상태) |
| `first_card_added` | user_id, method (scan/search/trending), card_id | POST /collection (첫 등록) |
| `first_wishlist_added` | user_id, card_id, target_usd | POST /wishlist (첫 등록) |
| `first_alert_fired` | user_id, listing_id, delta_percent | Notification queue 진입 |
| `pro_upsell_shown` | user_id, trigger (wishlist/30d) | Modal 렌더 |
| `pro_trial_started` | user_id | Lemon Squeezy webhook |
| `pro_paid_conversion` | user_id, plan (monthly/yearly) | Lemon Squeezy webhook |

이 이벤트들은 self-hosted `visit_logs` 확장으로 처리 (외부 analytics 서비스 도입 아님, 최소 데이터).

---

## 7. Anti-패턴 (하지 말 것)

- **강제 위저드 3+ 스텝**. 스킵 옵션 없는 위저드 = friction.
- **Signup 직후 pricing 모달**. 하드셀 anti-pattern.
- **Email verify 요구 하면서 무엇도 못 하게**. Friction 크고 컨버전 낮음.
- **Empty state 없이 빈 그리드만**. UX 무성의 시그널.
- **온보딩 진행률 안 보임**. 유저가 "지금 몇 단계"인지 모르는 채 헤매기.
- **미션 완료 없이 미션 창 반복 노출**. 진행률 dismiss 옵션 필요.

---

## 8. 이 문서 사용법

- Q1-Q8 결정 후 §4 flow 잠금 → 프론트엔드 `/` 페이지 재작업 · `/portfolio` empty state 재작업 참조
- Signup → 홈 리다이렉트 변경은 `frontend/app/signup/page.tsx` + `frontend/app/page.tsx` 에서 처리
- Onboarding 이벤트 훅 (§6) 은 백엔드 events 테이블 + POST /events 엔드포인트로 처리 (미착수)

*Generated 2026-07-01 (초안). Q1-Q8 결정 답변 후 §4 flow 잠금.*
