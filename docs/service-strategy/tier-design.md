# PullList — Tier Design

> **목적**: Free / Pro 티어 사이 경계를 어디에 그을지, 각 티어가 무엇을 판매하는지 정리.
> **자매 문서**: `pricing.md` (가격) · `onboarding-flow.md` (유저 유입 후 흐름).
> **최근 갱신**: 2026-07-01 (초안)

---

## 0. 지금 상태 한 줄

Free 온리. Pro 티어는 PROJECT_STATUS §4에 선언만 되어 있고 실제 결제/게이팅 미도입. 결제 통합은 Sprint 2 예정 (LemonSqueezy).

---

## 1. 원칙 (locked)

이 원칙들은 재논의 없이 티어 설계의 축으로 사용한다.

1. **Free는 진짜 forever free**. 카탈로그 · 컬렉션 · 위시리스트 · 포트폴리오 · 트렌딩 · 가격 히스토리 · 크로스 랭귀지 검색 · 스캔 · 공개 포트폴리오 공유는 어떤 경우에도 Free에 남긴다.
2. **Pro는 세 축으로 판다**: (a) 알림의 진짜배기 (실시간 · 채널 다양성 · 무제한 개수), (b) 심화 데이터 (다중 등급 · 1년+ 차트 · 예측/스프레드 인사이트), (c) 편의 (광고 제거 · CSV import · 다중 포트폴리오 · 우선 rate limit).
3. **광고는 Free tier 유지 축**이다. Free 유저의 존재가 아이덴티티 (컬렉터 커뮤니티) + AdSense/EPN/TCGplayer 수익원. Free 유저 수 자체가 자산.
4. **티어는 최대 2개**. Team / Family / Enterprise 는 정식 오픈 6개월+ 이후에나 검토. 지금은 Free / Pro 이분법.
5. **feature gating 은 quota 가 아닌 capability 위주로**. "월 3장 스캔 vs 무제한 스캔" 보다 "인앱 벨 vs 실시간 push+Discord" 처럼 질 자체의 격차로 판다. quota gate는 세컨더리.
6. **Free 유저가 눈에 띄게 답답하지 않아야 함**. Free가 데모/트라이얼이 아니라 완결된 도구여야 커뮤니티가 큰다. Pro는 "동력이 되는 유저에게 파워툴"이지 "핵심 기능 잠금해제"가 아님.
7. **VIP 뱃지 같은 상징적 보상**은 유효. 사이트 곳곳 (프로필, 공개 포트폴리오, 댓글이 생기면 그 옆) 에 표시. 실제 기능보다 자기표현이 큰 hook.

---

## 2. Free tier — 확정 기능 (Locked)

이 목록은 PROJECT_STATUS §4 + 지금까지 빌드된 것 기반. Pro에 넘길 후보 아님.

### 카탈로그 & 검색
- EN / JP / KR 통합 카탈로그 (43,000+ cards / 500+ sets)
- 크로스 랭귀지 검색 (Charizard ↔ リザードン ↔ 리자몽)
- Rarity / Set / Artist / HP / Price / Condition / Owned 필터 사이드바
- 카드 디테일 페이지 전체 (히어로, 이미지 매그니파이어, 가격 차트, 라이브 매물, 이웃 카드, variant 탭)
- 세트 페이지 (완성 진행률, 필터 칩, 카드 그리드)

### 컬렉션
- 무제한 카드 등록
- Variant · Condition · Grade · Qty · 취득일 · 구매가 · 소스 · 노트
- Row-level 편집 · ROI 계산 · CSV export
- Portfolio: 자산 그래프 (성장 차트) · Top 10 · Asset Mix 도넛 · 세트별 그룹 뷰
- Manage 모드 (벌크 삭제)

### 위시리스트
- 무제한 카드 등록 (heart toggle)
- Target price · Priority · Notes
- 위시리스트 페이지 & 필터

### 스캔
- 카드 스캔 (Claude Haiku 4.5 비전)
- Free quota: **일 5회** (§4 결정 대기 참조)

### 트렌딩 & 인사이트
- 7d / 30d / 90d 트렌딩
- Bulk / Chase tier 분할
- Top 3 podium · sparklines · $ floor 필터
- 가격 히스토리 차트 최대 **90d**

### 알림 (인앱 벨만)
- 헤더 종 아이콘 (§6 Notification MVP)
- 하루 1회 batched (다이제스트) — 실시간 아님
- Discord / Push / Email 없음
- 활성 알림 최대 **3장** (§4 결정 대기 참조)

### 공개 / 공유
- 공개 포트폴리오 공유 (share_token URL)
- Per-section toggle (value / growth / wishlist / all_cards)
- Public viewer + OG 이미지

### 커뮤니티 / 데이터 참여
- 카드 데이터 품질 리포트 (Wrong price / image / name / other)

### 광고
- Google AdSense · Mediavine/Ezoic (10k MAU 이후) · 어필리에이트 링크 (TCGplayer / eBay)

---

## 3. Pro tier — 확정 기능 (Locked)

### 광고 제거
- AdSense · Mediavine · 사이드바 스폰서 슬롯 전부 제거
- 어필리에이트 링크는 유지 (Pro 유저에게도 리다이렉트 valid)

### 알림 (실시간 + 채널 확장)
- **인스턴트 push** (매물 감지 후 5-30분 이내 — eBay quota 상황에 따라)
  - eBay Growth Check 통과 시 (30-50k/일 quota): 5분 폴링, 실시간에 가까움
  - Growth Check 미통과 (5k/일 quota): 30분 폴링, 지연 있음
- **Discord 웹훅** (개인 서버 지정)
- **Web Push** (PWA)
- **이메일** (Resend paid tier)
- 활성 알림 **무제한**
- 알림당 EPN 딥링크 (매물 URL 직접)

> **의존성**: Pro 실시간 알림의 폴링 빈도는 eBay Growth Check 결과에 따라 조정. 5분 폴링을 마케팅에 명시하기 전에 Growth Check 통과 확인 필수. (ROADMAP §3 "eBay Growth Check 재도전" 참조)

### 심화 데이터
- **가격 히스토리 최대 1년** (Free 90d 대비)
- **Multi-grade 가격 분해** — Raw / PSA 10 / PSA 9 / BGS 9.5 tier별 median + 최근 매물
- **Cross-Market 가격 갭** — KR / JP / US 비교 배너 + 아비트라지 지표
- **Portfolio 데일리 다이제스트 이메일** — 전날 밤 자산 변동 요약

### 편의
- **Multiple portfolios** — 개인 / 투자용 / 그레이딩용 분리
- **CSV / Excel import** (export는 Free에도 있음)
- **스캔 무제한** (Free 5/일 대비)
- **API rate limit 상향** (트렌딩 등)
- **얼리 액세스** — 새 기능 2주 먼저

### 상징적
- 프로필 · 공개 포트폴리오 · 리포트 옆 **VIP 뱃지**
- 정식 오픈 초기 100명 대상 **얼리 어답터 뱃지** (별개, `pricing.md` §5 참조)

---

## 4. 결정 대기 (LO 답 필요)

각 결정 후 §2/§3 에 잠금.

### Q1. 스캔 quota — Free / Pro 각각 (`pricing.md` §0.5.7 반영)

**중요**: Pro "무제한" 은 원가 리스크 큼 (`pricing.md` §0.5.2 남용 시 유저당 $4.50/월 원가 → 매출 $5.99 의 75% 잡아먹음). Pro 도 fair-use 상한 필요.

**Free 옵션:**
- **A1** — Free 5/일 · 실사용 20% 잡으면 원가 $0.14/월/유저 (현재 UI 명시)
- **A2** — Free 3/일 · 원가 $0.09/월/유저 (원가 최적화)
- **A3** — Free 시간당 1회 rate limit · daily quota 대신 spike 방지

**Pro 옵션:**
- **B1** — Pro 100/일 fair-use (하루 100장 = 극한 컬렉터 상한, 대부분 유저는 도달 안 함)
- **B2** — Pro 3000/월 상한 (월 flexible, 한 번에 많이 쓸 수 있음)
- **B3** — Pro 무제한 + 스캔 남용 감지 로직 (30일 rolling 평균 > 500/월 시 admin 알림, 개별 대응)

**추천: A1 + B1 (Free 5/일 · Pro 100/일 fair-use)**. 이유:
- Free 5/일은 커뮤니티가 편안하게 쓸 수치 (박스 오프닝 하나 = 카드 10장, 이틀에 나눠 감내 가능).
- Pro 100/일 = 3000/월 상한. 정상 유저 (100회/월) 의 30배 여유. 극한 컬렉터 (박스 5-6개 일괄 오픈) 감내.
- 100회/일 도달 유저 = 알림 카드 발송 (VIP 뱃지 안내 + fair-use 정책 문구), 200회/일 도달 = 24시간 스캔 lock.
- 이 상한 시 Pro 유저 원가 최대치 = $0.54/월 (OCR pre-pass 반영) — 매출 $5.07 의 11%. 마진 확보.
- OCR pre-pass (ROADMAP #7) 도입 시 원가 60% 절감, quota 상한 상향 여유.

**대안 각도** — B3 (무제한 + 감지) 를 갈 경우: 마케팅 시그널 강함 ("무제한 스캔!") 이지만 아웃라이어 유저 개별 대응 필요. 초기엔 B1 로 시작, 데이터 쌓이면 B3 검토.

### Q2. 알림 개수 — Free 3장 vs 다른 값?
알림은 Pro의 핵심 hook.

- **옵션 A** — Free 3장 · Pro 무제한 (현재 초안)
- **옵션 B** — Free 5장 · Pro 무제한 (약간 관대)
- **옵션 C** — Free **0장** (Pro exclusive) · Pro 무제한 (알림은 완전 유료 기능)
- **옵션 D** — Free 무제한 (channel gate 만) — 벨 알림만 무제한, Discord/Push/Email 만 Pro

**추천: D** — 알림 개수는 무제한, 채널만 gate. 이유: (a) 개수 gate는 유저가 "제일 갖고 싶은 3장" 골라야 해서 사용성 스트레스 큼, (b) 채널 gate는 "인앱 벨" vs "폰 알람" 이라는 명확한 UX 차이라 upsell 이해 쉬움, (c) 알림 시스템의 원가 (eBay 폴링) 는 채널 수와 무관, 유저 수와 비례 — 개수 gate 실효 없음. Pokefy가 알림 개수로 gate 하는데, 우리가 무제한으로 뚫으면 명확한 차별화.

### Q3. Multi-portfolio — Pro exclusive?
- **옵션 A** — Pro exclusive (현재 안)
- **옵션 B** — Free 2개 · Pro 무제한
- **옵션 C** — 모두 Free (Pro 에는 다른 hook 만)

**추천: A**. Multi-portfolio는 진지한 컬렉터 (투자용, 그레이딩용 분리) 시그널 = Pro 페르소나 정확히 일치. Free 유저는 1개면 충분.

### Q4. VIP-only 인사이트 — 무엇을 넣을지?
ROADMAP_IDEAS §VIP 후보:
- (a) Graded-card 스프레드 (Raw vs PSA10 차이 %)
- (b) 예측 30일 가격 (linear regression / EMA)
- (c) 위시리스트 트렌드 리포트 (내 위시 아이템들의 최근 30일 종합)
- (d) 매물 히트맵 (시간대별 매물 등장 빈도 → 언제 사야 매물 확률 최대)
- (e) Set completion 예산 시뮬레이션 (현재 시세 기준 남은 카드 총액)

**추천: a + c + e** 초기 세트. b는 예측 정확도 논란 리스크, d는 데이터 밀도 부족. a는 grading 결정 도구로 강력, c는 개인화 정확, e는 컬렉터 결심 도구.

### Q5. 3티어 대안 (Enthusiast tier) 검토?
- **옵션 A** — 2티어 유지 (Free / Pro)
- **옵션 B** — 3티어 (Free / Pro / Enthusiast)
  - Enthusiast (연 $99+): VIP 뱃지 골드 버전, 카드쇼 티켓 추첨, 얼리 액세스 4주 (Pro 2주 대비), 커뮤니티 디스코드 채널 액세스, 연 1회 세트 완성 스티커 · PullList 굿즈 발송

**추천: A** (지금은). 이유: 친구 베타 규모에서 3티어는 UX 복잡도 대비 매출 미미. 정식 오픈 6개월 후 Pro MRR 데이터 보고 재검토. Enthusiast는 미래 예약 (문서에만 남김).

### Q6. Free "Discovery" 얼리버드 — 첫 100명에게 뭘?
- **옵션 A** — 없음 (Free가 이미 강해서 얼리버드 프리미엄 무의미)
- **옵션 B** — 초기 100명은 **Founding Collector 뱃지** (Free 유지, 상징 보상만)
- **옵션 C** — 초기 100명은 **Pro 3개월 무료 트라이얼** (컨버전 시 lifetime 20% 할인)
- **옵션 D** — 초기 100명은 **Pro lifetime $29** 1회 결제 (친구+베타 감사)

**추천: B + C 조합**. Founding Collector 뱃지는 상징적 (0원 원가), Pro 3개월 무료로 hook 만들되 lifetime deal은 위험 (Pro 매출 캐니벌라이즈).

### Q7. Sealed 카탈로그 티어 어디에?
ROADMAP §8: Sealed (박스 / ETB / 부스터 번들 / 틴) 별도 카탈로그 예정.

- **옵션 A** — Free (카드와 동일하게 취급)
- **옵션 B** — Sealed 트래킹 자체는 Free, sealed 가격 히스토리 심화만 Pro (1y history 처럼)
- **옵션 C** — 완전 Pro exclusive

**추천: B**. Sealed 트래킹 자체를 Pro-gate 하면 컬렉터의 자연스러운 워크플로우 (박스 열기 + 카드 등록) 흐름이 끊김. 심화 데이터 계층에만 Pro 적용.

---

## 5. Feature Matrix (요약 표)

| 기능 | Free | Pro |
|---|---|---|
| 카탈로그 (31k+ 카드) | ✅ | ✅ |
| 크로스 랭귀지 검색 | ✅ | ✅ |
| 컬렉션 등록 (무제한) | ✅ | ✅ |
| Portfolio (기본 그래프) | ✅ | ✅ |
| Portfolio 개수 | 1 | 무제한 |
| CSV export | ✅ | ✅ |
| CSV / Excel import | — | ✅ |
| 위시리스트 등록 | ✅ | ✅ |
| 스캔 | 5/일 (Q1) | 100/일 fair-use (Q1) |
| 트렌딩 (7d/30d/90d) | ✅ | ✅ |
| 가격 히스토리 | 90d | 1y |
| Multi-grade 가격 분해 | — | ✅ |
| Cross-Market 갭 배너 | — | ✅ |
| Graded 스프레드 인사이트 | — | ✅ |
| Set completion 예산 시뮬레이션 | — | ✅ |
| 알림 (인앱 벨) | ✅ (하루 1회 batch) | ✅ 실시간 |
| 알림 (Discord / Push / Email) | — | ✅ |
| 알림 개수 | 무제한 (Q2 D안) | 무제한 |
| Portfolio 데일리 다이제스트 | — | ✅ |
| 공개 포트폴리오 공유 | ✅ | ✅ |
| 카드 데이터 리포트 | ✅ | ✅ |
| Sealed 트래킹 | ✅ | ✅ |
| Sealed 심화 데이터 | — | ✅ |
| 광고 | 있음 | 제거 |
| VIP 뱃지 | — | ✅ |
| 얼리 액세스 (새 기능) | 정규 | 2주 먼저 |
| API rate limit | 표준 | 상향 |

---

## 6. Anti-패턴 (하지 말 것)

- **핵심 카탈로그 기능 Pro-gate 금지**. Pokefy가 알림만 유료로 팔아서 컬렉터가 "그럼 나머지 정보는 어디서?" 이탈. 우리는 카탈로그 자체가 도구.
- **Quota로 답답함 조성 금지**. Free의 스캔 5/일은 자연스러운 상한이지, 페이월 뚫으려는 페인 유발이 아님.
- **Trial 후 Free 삭제 금지**. 트라이얼 만료 시 Free 로 자연 downgrade, 데이터 삭제 없음.
- **Pro에게만 새 카드 세트 노출 금지**. 카탈로그는 전체 유저 공유.
- **광고를 Pro 로 회유 금지**. "광고 짜증나서 결제" 는 정당하지만, 의도적 광고 밀도 상향 = anti-pattern.
- **"무제한" 을 원가 계산 없이 마케팅 금지**. Pro 스캔은 fair-use 상한 (100/일) 이 명시적으로 있어야 함. "실질 무제한" 은 marketing 문구로 허용, "무제한" 단독은 금지 (`pricing.md` §0.5.2 참조).
- **Fixed 인프라 비용 이해 없이 가격 결정 금지**. `pricing.md` §0.5 unit economics 필수 참조.

---

## 7. 미래 검토 (Not committed)

정식 오픈 6개월 후 재검토 대상.

- **Enthusiast tier** ($99+/년) — VIP 뱃지 골드, 카드쇼 티켓 추첨, 굿즈 발송, Pro 4주 얼리 액세스
- **Team / Family tier** — 3-5인 공동 포트폴리오 뷰 (트레이더 그룹, 가족 컬렉션)
- **Enterprise / API tier** — 카드샵 / 인플루언서 대상, 커스텀 알림 워크플로우 + 화이트 라벨
- **Marketplace / P2P features** — buy-offer, 옥션, 인앱 메시징 (ROADMAP_IDEAS ⚪ 티어)

---

## 8. 이 문서 사용법

- 결정 대기 (§4) 답나오면 이 문서 lock 상태로 반영 → `pricing.md` §1 로 링크
- Feature matrix (§5) 는 `/pricing` 페이지 렌더링용 소스로 사용
- 새 기능 아이디어 있으면 ROADMAP_IDEAS.md 에 먼저, 여기엔 확정 후 반영

*Generated 2026-07-01 (초안). 결정 대기 답변 후 v1 잠금.*
