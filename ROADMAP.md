# PullList — Roadmap & Decision Log

> **목적**: 앞으로 할 작업의 single source of truth.
> PROJECT_STATUS.md = "지금까지 만든 것" 스냅샷.
> ROADMAP.md (이 파일) = "앞으로 할 것" 우선순위 + 결정 대기 사항.
>
> 마지막 큰 정리: 2026-06-27 (친구 베타 단계, Neon 80% transfer 사용 중)

---

## 0. 지금 우리 단계 한 줄

**Friends-beta + Pre-Launch.** Render+Neon+Vercel 다 free tier, 9 유저 (친구 + organic 3명), AdSense 심사 중, 결제/유료화 미도입. 정식 오픈까지 디자인 + 알림 시스템 + Neon Launch 결제가 critical path.

---

## 1. 이번 주 ~ 다음 주 (Top 5 Priority)

이게 가장 ROI 좋은 5개. 다른 거 보지 말고 위에서 아래로 진행 추천.

### #1. 30d 통계 위젯 — 1.5시간 ⚡
- **무엇**: 카드 디테일 페이지에 작은 위젯 — "30일 최저 / 평균 / 최고 / 변동성".
- **왜**: 우리 `card_price_snapshots` 데이터 이미 있어서 SQL aggregate 하나로 끝남. 컬렉터들이 "이 가격이 stable 한가" 즉답.
- **레이어**: 백엔드 (1 endpoint) + 프론트 (1 위젯).
- **출처**: Collectory 파쿠리 Tier A.

### #2. Cross-Set 같은 Pokémon 위젯 — 1.5시간 ⚡
- **무엇**: 카드 디테일 하단에 "다른 세트의 ${Pokémon}" 그리드. Mewtwo 카드 보면 모든 set의 Mewtwo 카드들 표시.
- **왜**: 같은 Pokémon collect 하려는 컬렉터 패턴 정확히 캐치. 페이지 → 페이지 navigation chain 늘려서 engagement ↑.
- **레이어**: 백엔드 (간단한 query — `Card.national_pokedex_numbers` 같은 dex_number) + 프론트 (그리드).
- **출처**: Collectory 파쿠리 Tier A.

### #3. Release Calendar `/releases` 페이지 — 2시간 ⚡
- **무엇**: 미래 발매 예정 set 목록 + 카운트다운. `Set.release_date` 이미 있음.
- **왜**: SEO + 재방문 ↑ ("어비스아이 언제 나와?" 검색 캐치). Pokémon 컬렉터 행동 패턴 정확.
- **레이어**: 백엔드 (`/sets/upcoming` endpoint) + 프론트 (새 페이지).
- **출처**: Collectory 파쿠리 Tier A.

### #4. 이미지 Hash 캐시 (스캔 비용 절감) — 3시간
- **무엇**: 카드 스캔할 때 perceptual hash (pHash) 계산 → DB에서 이전 매칭 결과 찾아 즉시 반환. Claude API 호출 줄임.
- **왜**: 같은 카드 재스캔 시 비용 0 + 즉시 반환. 친구 베타 규모에선 비용 미미하지만 인프라로 깔아두면 정식 오픈 시 대비.
- **레이어**: 백엔드 (`scan_cache` 테이블 + pHash 라이브러리). Neon에 충분히 fit (5년 쓸 만큼 storage 여유).
- **출처**: 스캔 강화 Phase 1.

### #5. Cross-Market 가격 갭 배너 — 2-3시간
- **무엇**: 카드 디테일에 "🇰🇷 ₩X / 🇯🇵 ¥Y / 🇺🇸 $Z — 최대 75% 차이" 배너. arbitrage 정보 강조.
- **왜**: 우리만의 강력한 USP. KR/JP/US 카탈로그 다 있는데 비교 UI 없음. Collectory 핵심 기능이지만 우리도 데이터는 있음.
- **레이어**: 백엔드 (dex_number + set release_date 기반 cross-language card matching — 좀 까다로움) + 프론트 (배너).
- **출처**: Collectory 파쿠리 Tier B.

**총 시간 추정: 12-13시간** = 2-3일 작업.

---

## 2. 그 다음 (Top 5 끝나고 2-4주 이내)

### #6. 알림 시스템 MVP — 알림 인프라 + 인앱 벨
- **무엇**: 위시리스트 카드의 실제 매물이 target 이하로 떴을 때 알림. **첫 채널: 인앱 벨 (헤더 종 아이콘 + 빨간 점)**.
- **왜**: 프리미엄 핵심 가치. "그냥 시세가 닿았어요"가 아닌 "지금 이 가격에 살 수 있는 매물이 떴어요" + EPN affiliate 딥링크.
- **레이어**:
  - 백엔드: `notifications` 테이블 + `seen_listings` 테이블 + 폴링 잡 (GitHub Actions cron) + 매물 매칭 로직
  - 프론트: 헤더 벨 컴포넌트 + 알림 리스트 페이지
  - **인프라 영향**: 폴링 잡이 eBay quota 먹음 → 친구 베타에서 글로벌 dedupe로 OK, 정식 오픈 시 Notification 트리거 직전에 **Neon Launch ($19) upgrade 권장**
- **작업**: ~3-5일
- **다음 단계**: Discord 웹훅 → Web Push (PWA)

### #7. OCR Pre-Pass (스캔 비용 50% 절감) — 1-2일
- **무엇**: 카드 스캔할 때 Tesseract/PaddleOCR로 먼저 텍스트 추출 → 이름+번호 매치되면 Claude 안 부름 → 매치 실패 시에만 Claude fallback.
- **왜**: 정식 오픈 시 100k scan/월 = $300 → $100-150. 친구 베타에선 효과 작지만 미리 깔면 OK.
- **레이어**: 백엔드 (PaddleOCR Python lib + matching 로직). Neon 무관, CPU 사용.
- **작업**: 1-2일

### #8. Sealed 카탈로그 ingest + UI — 2-3일
- **무엇**: 박스 / ETB / 부스터 번들 / 틴 / 핀 컬렉션 등 sealed 상품도 카드처럼 카탈로그 + 가격 추적.
- **왜**: Collectory 검증된 segment + TCGCSV에 이미 sealed 데이터 있음. 우리 디테일 페이지 모델 거의 재사용.
- **레이어**:
  - 백엔드: `SealedProduct` 모델 + `migrate_sealed_products.py` + TCGCSV ingest 스크립트
  - 프론트: `/sealed` 페이지 + 디테일 페이지
- **DB 부담**: 1,500-2,500 sealed row 추가 (카드 31k 대비 미미)
- **작업**: 2-3일

### #9. Multi-Grade 가격 분해 — 3-4시간
- **무엇**: 카드별 Raw / PSA 10 / PSA 9 / BGS 9.5 등 grade-tier별 median 가격 + 최근 매물 별도 표시.
- **왜**: 컬렉터의 grading 결정 핵심 데이터. Collectory의 가장 강한 기능.
- **레이어**: 백엔드 (eBay listing title regex로 grade 추출 → tier별 aggregate) + 프론트 (디테일 페이지 새 섹션)
- **출처**: Collectory 파쿠리 Tier B.

### #10. v0/Variant 디자인 결과 받기 → React 구현
- **무엇**: LO가 v0/Variant에서 5-6 컨셉 받은 메인페이지 디자인 결과 → 픽한 컨셉 React로 구현
- **왜**: 사이트 톤 정착 못 하면 다른 기능들 다 디자인 mismatch
- **레이어**: 프론트 전부 (디자인 → React + Tailwind 매핑)
- **블록**: LO가 v0/Variant 결과 가져오기 대기 중

### #10.1 "Signed-in devices" UI (auth follow-up) — 1-2시간
- **무엇**: `/settings/security` 페이지 — 백엔드가 이미 exposing 하는 `GET /auth/sessions`를 리스트로 렌더. 각 세션에 device_label, 마지막 사용 시간, "이 기기" 표시, 개별 revoke 버튼(single-session revoke는 future — 지금은 "Log out of all other devices" 버튼만 필요), "Log out everywhere" 버튼(`POST /auth/logout-all`).
- **왜**: Level 3 auth (2026-07-05) 완료로 백엔드는 이미 준비됨. 컬렉터한테 "내 계정이 어디서 로그인돼 있나" 표시하면 신뢰 UX + 나중에 Pro tier에 자연스럽게 얹기 좋음.
- **레이어**: 프론트만 — 페이지 하나 + `listSessions()` / `logoutAllDevices()` API 헬퍼 이미 있음.
- **후속**: 개별 세션 revoke 하려면 백엔드에 `DELETE /auth/sessions/{id}` 추가 (지금 스코프 밖).

### #10.5 JP 카탈로그 rarity backfill ✅ (2026-06-29)

**원래 계획 폐기 사유**: 원안은 Playwright + pokemon-card.com 풀스윕이었는데 probe 결과 두 갭 모두 그 source로 해결 불가:
- pokemon-card.com search는 **현재 regulation만 indexed** — PMCG/VS/web/E/PCG 검색 0건 (빈티지 dropped).
- pokemon-card.com **rarity 자체를 표시 안 함** (`backfill_jp_rarity_bulbapedia.py` 도크에 이미 명시되어있던 사실, 원안 ROADMAP이 이걸 못 보고 쓰여짐).
- 즉 Playwright 새 스크레이퍼는 두 갭 다 zero coverage.

**실제로 진행** (rarity-only):
- **Limitless EN-equivalents** — `backfill_jp_rarity.py` 풀스윕 → **1,773장 신규 채움** (Gap B SM0/SM6-12a, XY2-10, CP1-6, SMP2 신규 import 거의 다)
- **Bulbapedia set-list 매핑 확장** — `backfill_jp_rarity_bulbapedia.py` 에 SM/XY/CP/빈티지 (PMCG, E, PCG, VS, web) 슬러그 추가 + 풀스윕 → **8,234장 update** (JP-native tier polish: RRR/AR/SAR/HR/UR 등)
- **JPP Promo 일괄** — `backfill_jpp_promo_rarity.py` 신규 (JPP-* NULL rarity = 'Promo') → **2,009장 신규 채움** (JPP-BW/DP/XY/S/SM/SV/P)

**최종 JP rarity coverage**: 14,362장 중 NULL 366장 = **97.5%**. 잔여는 SV4a/SV8a/S12a multi-print 페이지 일부 + SVK/SVLS/SVLN 마이너 special sets (Bulbapedia 매핑 없음).

**ROADMAP 추정 오류 정리**:
- "Gap B 3,392장" → 실제 1,831장 (지금 잔여 < 60장).
- "8 missing sets (SM1-5/SM11/XY5/XY8)" → JP 명명 컨벤션상 SM1 = SM1M+SM1S+SM1+ 같이 sub-set으로 쪼개져있고, 모두 이미 DB에 import 됨. Missing 0.
- "Gap A 1,861장 vintage image" → 여전히 갭. §10.6으로 이관.

### #10.6 JP 빈티지 image backfill ✅ (2026-06-30)

**문제**: PMCG1-6 / VS1 / web1 / E1-E5 / PCG1-9 = **1,861장 `image_small IS NULL`**. 컬렉터 시장 핵심 (베이스 리자몽 JP 1996, No.1 Trainer 등).

**Dead end 확인된 source**:
| Source | 결과 |
|---|---|
| pokemon-card.com search | 빈티지 indexed 안 됨 (현 regulation only) |
| TCGdex /v2/ja sets + 단건 | 404 |
| Bulbapedia 카드 list page | row마다 generic placeholder thumbnail만 |
| pkmncards.com | vintage set queries returns "no results" |
| Cardrush JP | Cloudflare 403 (playwright-stealth로도 막힘) |
| yuyu-tei JP | URL pattern dead, base 페이지만 200 |
| Pokellector | 모든 JP era 슬러그 `/sets` 로 redirect |
| pokemon.fandom.com | 카드 페이지 403 (Wikia 차단) |
| Bulbapedia archives File: 직검색 | 추측 파일명 다 404, search API 0 results |

**해법 — Bulbapedia 카드 wiki 페이지 deep crawl**:
- Set 페이지 (`/wiki/Base_Set_(TCG)` 등)에서 `_(SetName_NNN)$` 패턴 anchor만 정확히 추출
- 각 카드 wiki 페이지 fetch → `<a href=/wiki/File:...> class="mw-file-description"` candidates 다 모음
- **set-token 매칭 preference** — anchor href의 SetName ("Base_Set" → "BaseSet")이 image filename에 포함되는 candidate 선택. 카드 페이지가 promo / cross-set reprint image 먼저 보여줘도 정확한 base set image pick (정확도 75% → 98%).
- thumb URL → original full-res 자동 변환
- `images_only=True` 패턴: `WHERE set_id=:s AND language='ja' AND number_int=:n AND image_small IS NULL` (idempotent)
- **`backfill_jp_images_bulbapedia.py`** 신규 작성

**중간에 잡힌 critical bug (2026-06-30)**: 초기 PMCG/E/PCG mapping이 EN equivalent에 잘못 매핑되어 (PMCG1=Base_Expansion_Pack은 사실 e-Card Expedition, 진짜는 Base_Set; PCG4="金の空、銀の海"인데 Mirage_Forest로 매핑됨 등) **1,296장 잘못된 카드 image** 채워질 뻔. Audit 스크립트가 set.name JP ↔ EN equivalent cross-check로 발견. 즉시 rollback 후 `vintage_audit.json` 기반 정확한 매핑으로 재작성.

**최종 결과**:
- ✅ PMCG1 (Base Set 1996, 102장) / PMCG2 (Jungle, 48장) / PMCG3 (Fossil, 48장) / PMCG4 (Team Rocket, 65장) / PMCG5 (Gym Heroes, 96장) / PMCG6 (Gym Challenge, 98장)
- ✅ E1 (Expedition Base Set, 128장)
- ✅ VS1 (140장, JP-only) / web1 (46장, JP-only) — 첫 풀스윕에서 채워짐, mapping 정확
- **합계 ~775장 image_small 채움**, JP image coverage 87% → **92.4%** (1,090 → 1,090 NULL 잔여)

**카드 image 출처 주의**: PMCG/E1 sets는 Bulbapedia가 EN variant image를 surface — JP 디자인 거의 동일하지만 텍스트만 영어. VS1/web1는 자동으로 JP image. 컬렉터에게 placeholder보다는 훨씬 의미 있음.

### #10.6.1 JP 빈티지 image — PCG1-9 ✅ (2026-06-30, learn-book.com)

**LO 제보**: learn-book.com이 일본판 카드 list를 portrait grid로 hosting. PCG1-9 (`/pokemon-cardlist-pcg{N}/`) 모두 indexed, 파일명 패턴 매우 깨끗 (`pcg9001.jpg` = PCG9 #001).

**해법 — `backfill_jp_images_learnbook.py`** 신규:
- Playwright `wait_until="domcontentloaded"` + 30 scrolls (lazy-load 강제, networkidle은 PCG3에서 timeout)
- 356x500 portrait images (`img.wp-image-*` class) 추출
- 파일명 regex `/pcg(\d+)(\d{3})\.(jpg|png)` → set_num + card_num 추출
- expected set_num match만 사용 (cross-set embedded image 차단)
- DB upsert `WHERE set_id=:s AND language='ja' AND number_int=:n AND image_small IS NULL`

**결과**: **720/722 PCG 카드** image 채움. PCG2(1), PCG6(1) 잔여 = page에 그 number 없음 (사실상 100%).

### #10.6.2 JP 빈티지 image — E1-E5 ✅ (2026-06-30, nazonobasho.com)

**LO 제보**: nazonobasho.com이 e-Card era JP 카드 (E1-E5) 풀 indexed. URL pattern 매우 깨끗: `e{N}_{rarity}_{NUM:03d}_{name}_copy.jpg` (예: `e1_B_128_airmd_copy.jpg`). 정적 HTML — httpx만으로 OK (Playwright 불필요).

**해법 — `backfill_jp_images_nazonobasho.py`** 신규:
- 각 `/cardlist-e{N}/` page fetch
- tighter regex `e{N}_[A-Za-z]+_(\d{1,3})_` 로 number 추출 (thumbnail size suffix `-WxH` 노이즈 제거)
- DB upsert `WHERE set_id=:s AND language='ja' AND number_int=:n AND image_small IS NULL`

**결과**: E1 (128) + E2 (90) + E3 (90) + E4 (91) + E5 (90) = **489장 채움**. E1은 기존 Bulbapedia EN variant → **JP native scan으로 swap** (텍스트 일본어). 3장만 page에 없음 (`needed but not on page`).

**최종 JP image coverage: 99.94%** (14,353/14,362, NULL 9장 잔여 — VS1 3 / E2 2 / E5 1 / PCG2 1 / PCG6 1 / web1 1)

### #10.6.3 JP 빈티지 image — PMCG2-6 (354장, open) 🔍

**문제**: PMCG2 (ポケモンジャングル) / PMCG3 (化石の秘密) / PMCG4 (ロケット団) / PMCG5 (リーダーズスタジアム) / PMCG6 (闇からの挑戦) = **354장 image NULL** (2026-06-30 audit 후 rollback).

**rollback 사유**: 처음에 naive EN equivalent mapping (PMCG6 → Gym_Challenge 등) 적용 → audit 결과:
- PMCG2 Jungle: 2/10 mismatch
- PMCG3 Fossil: 3/10
- PMCG4 Team Rocket: 3/10
- PMCG5 Gym Heroes: 3/10
- **PMCG6 Gym Challenge: 7/10** ← naive 매핑 명백히 fail

핵심 원인: **JP Gym era는 96+98=194장**으로 EN Gym Heroes+Challenge 132+132=264장과 numbering 완전 다름. JP "Leaders' Stadium" + "Challenge from Darkness" 는 EN Gym과 cross-mapping이 split. Jungle/Fossil/Team Rocket도 partial mismatch.

**시도된 source — 다 dead end**:
- learn-book.com sitemap 검사 → modern only (SV/XY/SM/PCG), PMCG era 없음
- nazonobasho.com → e-Card only, PMCG era 없음
- pokemon-card.com / TCGdex → 빈티지 indexed 안 됨
- pkparaiso/pokebeach/pokemonpedia/etc 5+ 사이트 → 403/dead/EN-centric

**남은 가능성**:
- **Wayback Machine** — 옛 pokemon-card.com 빈티지 카드 image (2002-2005년 archive)
- **Bulbapedia JP-specific File: 검색** — `File:KogasArbokChallengefromDarkness.jpg` 같은 패턴
- **수동 sourcing** — top 50 가치 카드만 일본 옥션/eBay listing image
- **placeholder UI** — set logo + JP name only

**새 세션 부트스트랩**:
> PullList §10.6.3: PMCG2-6 (354장) JP image. Bulbapedia JP-specific search 또는 Wayback Machine 시도.

### ✅ JP 카탈로그 백필 정리 (2026-06-30 종료)

- JP rarity coverage: **97.5%** (NULL 366)
- JP image coverage: **97.47%** (NULL 364 — 거의 다 PMCG2-6, +미세 9장)
- 빈티지 source 매핑 정리 (audit-verified):
  - **PMCG1** (Base Set, 102장) + **E1** (Expedition, 128장) → Bulbapedia
  - **VS1** (143장), **web1** (47장) → Bulbapedia JP-only pages
  - **PCG1-9** (720장) → learn-book.com Playwright render
  - **E2-E5** (361장) → nazonobasho.com httpx native JP scans
  - **PMCG2-6** (354장) → **open §10.6.3** (모든 public source dead end)

### #10.7 JP 가격 데이터 소스 붙이기 ⏸️ (open, 다음 세션 대상)

**문제**: JP 카드 14,362장 다 있는데 `market_price_usd / mid / low / high` 전부 NULL. TCGCSV/TCGplayer는 EN 카탈로그 전용, pokemontcg.io는 Cardmarket EU/EN 위주. Cross-Market 가격 갭 배너 (§1 #5) 프리미엄 기능이 이 데이터 없이는 unblock 안 됨.

**후보 소스**:
| 소스 | 커버리지 | 라이선스 | 스크레이핑 난이도 |
|---|---|---|---|
| **yuyu-tei.jp** | 현행 JP 시장 최대, JPY 시세, 다수 컨디션 | 재판매업체 페이지 (약관 확인 필요) | 중 — SSR HTML, 페이지네이션 |
| **cardrush.jp** | 현행 + 일부 빈티지 | Cloudflare 403 (이번 세션 확인됨) | 상 — stealth 우회 필요 |
| **hareruya2.com** | 현행 chase + 빈티지 SR | 정적 페이지 다수 | 중 |
| **pokedata.io** | JP 지원, 시세 API 지원 | 유료 (free tier limited) | 하 — API 호출만 |
| **Snkrdunk / Mercari** | 실시간 매물 | Cloudflare + 폰넘버 인증 | 상 |
| **TCGCSV JP-Ext (?)** | 미확인 — TCGCSV 가끔 JP-extended 데이터 |  | 미확인 |

**추천 순서**: (1) TCGCSV가 JP를 확장 지원하는지 먼저 probe (한 endpoint 확인만) → (2) yuyu-tei.jp 파일럿 (100장 probe) → (3) 규모 결정.

**엔드 타깃**: 최소 chase-tier 카드들 (RR/SR/SAR/UR/HR) 시세만이라도 붙이면 Cross-Market 갭 배너 unblock. Common/Uncommon은 후순위.

**새 세션 부트스트랩** (LO 신호 시):
> PullList §10.7: JP 가격 소스 붙이기. TCGCSV JP extension 여부 probe → yuyu-tei.jp 파일럿 → 100장 probe 후 규모 판단.

---

## 3. 정식 오픈 직전 (오픈 1-2주 전)

### 인프라 업그레이드
- **Neon Launch ($19/월) 결제** — Notification 시스템 들어가면 transfer + storage 양쪽 다 늘어남. Launch가면 10 GB transfer / 10 GB storage. 정식 오픈 ~6개월 buffer.
- **Render Starter ($7/월)** 결제 검토 — 콜드 스타트 50초 → 0초. 정식 오픈 후 첫 visitor 경험에 영향 큼. 친구 베타는 그냥 free 유지.
- ~~**eBay cron daily 복구** — 정식 오픈 시 `0 7 * * *` 로 revert~~ ⚠️ **재검토 대상** — 2026-06-30 Growth Check 거절 이후 5k/day 캡 확정. Mon+Thu 유지가 안전. 재도전 성공 시에만 복구 검토.
- **Sentry 통합** — production error monitoring. 첫 유저 1000명 단계에서 사이트 깨지면 즉시 알림. ~2시간 작업.
- **`visit_logs` 90일 retention + aggregate job** — 오래된 raw 데이터 monthly 통계로 압축 후 삭제. Storage 폭증 방지. ~3시간.

### 데이터 정합성 마무리
- **Mudkip/Espeon Live Listings 확인** (이미 머지된 PR #10/#11 효과 검증)
- **다음 eBay 스냅샷 후 fpic + SET VALUE range 검증**
- **Team Aqua's Kyogre 6.29x 케이스 조사**
- **RARITY_GROUPS 3개 추가**: Special Rare / Character Super Rare / Character Holo Rare

### 비즈니스
- **eBay Growth Check — 1차 거절 (2026-06-30)**. Nishtha Gupta 응답: "business policies" boilerplate로 거절, 사유 특정 없음. **10일 재개방 창구 활용 필수** (deadline: **~2026-07-10 ET**).
  - 재도전 앵글 (원 요청보다 훨씬 강하게 쓸 것):
    - **EPN 트래픽 실적 데이터 첨부** — 5339157076 campid 기준 지난 30일 clicks + conversions + attributed revenue. Growth Check 심사에서 가장 힘 있는 지렛대.
    - **구체적 손실 수치 제시** — "5k 캡 때문에 매일 3,500장 스킵 → collectors가 우리 사이트에서 이탈 → 그 트래픽 eBay 도달 실패".
    - **구체적 요청 티어** — 5k → 50k 대신 5k → 15k / 30k / 50k 옵션 3개 제시 (accommodate 가능성 높이기).
    - **compliance 재확인** — no bulk redistribution, EPN 부착, user data non-persistence 다시 강조.
  - **Fallback (재거절 시)**:
    - Snapshot cron $1+ floor + Mon+Thu 유지 (현재 상태) → 정식 오픈 시에도 이 구조로 감. **`0 7 * * *` 복귀 계획 취소**.
    - Live listings 클라이언트 캐시 5분 → 15분 상향.
    - `$5+` 티어 above로 daily 축소 (~3-4k calls), 그 아래는 monthly로.
    - JP/KR 카탈로그 가격은 eBay 의존 낮추고 대체 소스 (TCGCSV EN 유지 + JP 로컬 소스 §10.7) 우선.
- **AdSense 승인 확인** — 안 됐으면 LO 직접 follow-up
- **Growth Check 승인 확인** — 1-4주 대기 중
- **쿠팡 파트너스 가입 여부 결정** — LO 한국 사업자 자격 + 가입 → KR traffic 수익화 채널 활성
- **친구 베타 strict gating 결정** — invite code OR organic 허용. 기본 추천: 무료 organic 유지
- **Unknown 유저 3명에게 이메일** — 시장 조사 ("어떻게 찾으셨어요?")

### UX 마무리
- **모바일 missing 기능 풀 패스** — 각 페이지 폰에서 한 번씩 확인
- **차트 안정화** — outlier smoothing / 모바일 반응형 / sparse data fallback (LO가 어느 차트 어떤 문제인지 알려줘야 함)
- **Error message UX 분류** — 429/500/404 등 사용자 친화 메시지
- **펼치기 row 높이 popover 대안** — 현재 portfolio expand 시 row 높이 불일치 → popover 패턴 검토

---

## 4. 정식 오픈 후 (1-3개월)

### 알림 채널 확장
- **Discord 웹훅 통합** — 유저 본인 서버에 알림 받기
- **Web Push (PWA)** — service worker + VAPID. 폰 홈화면 설치 유저용
- **이메일** — Resend 유료 티어 (도메인 워밍 완료 후)

### 스캔 강화 Phase 2
- **센터링 측정 MVP** — OpenCV 기반. 모던 bordered 카드만 지원. ~2-3일 작업. **정확도 = 평판** 이라 신중. Beta 라벨 + disclaimer 필수
- **시각적 overlay** — 검출된 border 표시 → 유저 신뢰
- **PSA 10 시세와 연계** — "이 카드 10등급 받으면 X원" 의사결정 도구

### Premium tier 도입
- **Lemon Squeezy 결제 연결**
- **Free vs Premium 차별화**:
  - Free: 일 1회 알림 묶음 / 인앱 벨만 / 5장 센터링/월
  - Premium ($7-9/월): 실시간 알림 / Discord+Push / 무제한 센터링 / Multi-grade 자동 추적

### Collectory 파쿠리 Tier C
- **PSA Pop Report 통합** — PriceCharting API 또는 PSA 스크래핑
- **실거래 (sold listings) history** — eBay Marketplace Insights API 신청
- **다국어 UI** — 한국어 / 일본어 토글 (콘텐츠는 영어, UI만 i18n)

### TCG accessory 어필리에이트 (스케일 커진 후)
- **Vault X 어필리에이트 프로그램** — 2026-07-05 조사한 스펙:
  - **커미션 7.5%** / 쿠키 30일 / PayPal 지급
  - **⚠️ 6개월 무판매 시 계정 삭제** — 트래픽 확보 후 지원해야 유의미
  - **개인 크리에이터 조건** (Pokemon: IG/TikTok/X 5k, YT 3k, Whatnot 1k 중 1) — PullList 브랜드로는 지금 fit 안 맞음. 재오픈 2026년 7월 중.
  - **재검토 트리거**: (a) 정식 오픈 후 월 활성 유저 1k+ 확보, (b) LO 개인 소셜 크리에이터 5k+ 도달, (c) B2B 파트너십 이메일 직접 문의 시도 조건 충족 시
- **대체 어필리에이트 후보** (Vault X 안 되면):
  - **Ultimate Guard** (Impact.com), **Dragon Shield** (~5%), **Ultra Pro** — 소매 채널 통해
  - **역방향 통합**: 우리 카드 상세 페이지에 슬리브/바인더 어필리에이트 embed → eBay/TCGplayer 어필리에이트 옆에 accessory 채널 추가
- **가치**: 컬렉터 사이트 특성상 자연스러움. eBay 5k quota 걱정 없는 순수 revenue 채널

---

## 5. Layer별 작업 목록 (전체 backlog)

### 5.1 서버 / 컴퓨트
- [ ] Render Starter $7/월 결제 검토 (콜드 스타트 제거)
- [ ] Notification 폴링 잡 인프라 (GitHub Actions OR 별도 worker)
- [ ] 정식 오픈 후 백엔드 인스턴스 multi-worker 전환 (현재 single instance, in-memory state 의존)
- [ ] Upstash Redis (무료 10k commands/day) — Notification hot state 캐시용 (Notification MVP 들어갈 때)

### 5.2 스토리지 / DB
- [ ] **Neon Launch $19/월 upgrade** — Notification 들어가기 직전 (storage + transfer 양쪽 풀림)
- [ ] `visit_logs` 90일 retention + aggregate job
- [ ] `card_price_snapshots` archival — 1년 이상은 S3 parquet + DuckDB (정식 오픈 후 6개월)
- [ ] 이미지 R2 / S3 셋업 — 센터링 측정 학습 데이터 모을 때
- [ ] Full-text search 별도 인프라 — 100k+ card 도달 시 MeiliSearch
- [ ] `scan_cache` 테이블 (이미지 hash 캐시)
- [ ] `SealedProduct` 모델 + 마이그레이션

### 5.3 백엔드 (FastAPI)
- [ ] `GET /cards/{id}/stats?days=30` — 30d min/avg/max/volatility
- [ ] `GET /cards/{id}/same-pokemon` — cross-set 같은 Pokémon 카드
- [ ] `GET /sets/upcoming` — release calendar용
- [ ] `POST /cards/scan` 에 hash 캐시 + OCR pre-pass 통합
- [ ] `POST /cards/scan/centering` — 센터링 측정 endpoint
- [ ] `GET /cards/{id}/grade-prices` — Multi-grade tier 가격
- [ ] `GET /cards/{id}/cross-market` — KR/JP/US 가격 비교
- [ ] `POST /notifications/poll` — Notification 폴링 잡 진입점
- [ ] `GET /notifications` — 유저 알림 리스트
- [ ] `POST /notifications/{id}/read` — 알림 읽음 처리
- [ ] Sealed product CRUD endpoints
- [ ] `PATCH /admin/visits/aggregate` — 오래된 visit_logs 압축 trigger

### 5.4 프론트엔드 (Next.js)
- [ ] 30d 통계 위젯 (카드 디테일)
- [ ] Cross-set 같은 Pokémon 그리드 (카드 디테일)
- [ ] `/releases` 페이지
- [ ] Cross-market 가격 갭 배너 (카드 디테일)
- [ ] Multi-grade 가격 분해 섹션 (카드 디테일)
- [ ] 헤더 종 아이콘 + 빨간 점 + 알림 dropdown
- [ ] `/notifications` 페이지 (전체 알림 history)
- [ ] `/sealed` 페이지 (sealed product 브라우저)
- [ ] Sealed product 디테일 페이지
- [ ] v0/Variant 메인페이지 디자인 → React 구현
- [ ] 차트 안정화 (CardPriceChart + PortfolioGrowthChart)
- [ ] 모바일 missing 기능 풀 패스
- [ ] Error message UX 분류 (429/500/404)
- [ ] Portfolio 펼치기 popover 검토
- [ ] 센터링 측정 UI (사진 업로드 + border overlay + 결과)

### 5.5 인프라 / 배포
- [ ] `.github/workflows/notification-poll.yml` — Notification 폴링 (매 N분)
- [ ] `.github/workflows/visit-aggregate.yml` — 매월 visit_logs 압축
- [ ] `daily-ebay-snapshot.yml` 정식 오픈 시 cron 데일리로 revert
- [ ] Sentry SDK 설치 (frontend + backend)
- [ ] Render Starter 결제 (콜드 스타트 제거)
- [ ] Neon Launch 결제

### 5.6 비즈니스 / 운영
- [x] ~~eBay dev support quota bump 메일 작성 + 발송~~ 2026-06-30 거절 회신. **재도전은 별도 항목** (§3 비즈니스 상단 참고).
- [ ] **eBay Growth Check 재도전 (~2026-07-10 마감)** — EPN 실적 데이터 확보 + 티어 3-옵션 제안
- [ ] 쿠팡 파트너스 가입 (LO 사업자 자격 확인 후)
- [ ] 친구 베타 strict gating 결정 (invite code or 무료 organic)
- [ ] Unknown 유저 3명 (Mario / Seungho / Kyrie) 이메일 — "어떻게 찾으셨어요?"
- [ ] AdSense 승인 follow-up
- [ ] Growth Check 진행 상황 follow-up
- [ ] Series 3 (2026-08-07) 리시드
- [ ] Lemon Squeezy 결제 통합 (Premium tier 시작 시)

### 5.7 데이터 정합성 / 검증
- [ ] Mudkip/Espeon Live Listings — PR #10/#11 효과 확인
- [ ] 다음 eBay 스냅샷 (월요일) 후 fpic + SET VALUE range 확인
- [ ] Team Aqua's Kyogre 6.29x 케이스 조사
- [ ] RARITY_GROUPS에 3개 추가: Special Rare / Character Super Rare / Character Holo Rare
- [ ] 며칠 후 Neon transfer 추세 확인 (tier-sync 효과)

### 5.8 문서 / 메모리
- [ ] PROJECT_STATUS §3.12 newsbot 단락 추가
- [ ] 메모리 경로 "PullList" → "PokeRadar" 정리 (메모리 파일 + MEMORY.md)
- [ ] 이 ROADMAP 매번 큰 작업 후 갱신

---

## 6. 결정 대기 (LO 답 필요)

각 항목 결정해주면 바로 진행 가능:

| 결정 | 옵션 | 영향 |
|---|---|---|
| 이번 주 작업 시작 — Top 5 중 어디부터? | #1 30d 통계 / #2 Cross-set / #3 Release / #4 Hash 캐시 / #5 Cross-market | 작업 1.5-3시간 |
| 알림 첫 채널 | 인앱 벨 단독 / 인앱 벨 + Discord 동시 | 작업 1일 차이 |
| 친구 베타 strict gating | invite code (조여서 출시 전 닫기) / organic 허용 (현재) | 작업 2-3시간 |
| 쿠팡 파트너스 가입 | LO 자격 있음 → 가입 시작 / 없음 → 스킵 | KR 수익화 채널 |
| Neon Launch upgrade 시점 | 지금 / Notification 직전 / transfer 한도 진짜 터질 때 | $19/월 결제 시작 시점 |
| Sealed 위시리스트 통합 방식 | `target_type` 컬럼 (단일 테이블) / WishlistItemCard + WishlistItemSealed 분리 | 코드 구조 차이 |
| v0/Variant 디자인 픽 | 결과 받으면 어느 컨셉 갈지 | 사이트 톤 정착 |
| 차트 안정화 대상 | LO가 어느 차트의 어떤 문제인지 알려줘야 진행 가능 | 작업 범위 |

---

## 7. 트래킹 메트릭 (정기 확인)

| 메트릭 | 현재 | 임계 | 확인 주기 |
|---|---|---|---|
| Neon transfer / 5 GB | 80% | 90%에서 Launch upgrade | 주 1회 |
| Neon storage / 0.5 GB | 56% | 80%에서 정리 / upgrade | 주 1회 |
| Neon compute / 100 CU-hrs | 55% | 80%에서 worry | 주 1회 |
| eBay quota / 5,000/day | ~3,500 | Mon+Thu만 사용 중 | 매주 |
| 총 유저 | 9 | 100 도달 시 정식 오픈 준비 | 매일 visit dashboard |
| 일일 unique 방문 | (집계 시작) | 100+ 되면 SEO 영향 분석 | `/admin/visits` |
| 스캔 비용 (Claude Haiku) | < $5/월 | $50/월 도달 시 OCR 도입 | 월 1회 |
| GitHub Actions 사용 시간 | < 100분/월 | 1,500분/월 free 이내 | 월 1회 |

---

## 8. 절대 안 함 리스트 (의도적 스킵)

LO가 명시적으로 제외한 작업 — 다시 제안하지 말 것:

- **장터 (직접 마켓플레이스)** — payment + KYC + 분쟁 처리. eBay/TCGplayer affiliate가 우리 모델
- **3vs3 배틀 / 메모리 게임 / 시세 맞추기** — entertainment side-feature, core 흐림
- **출석체크 / 게이미피케이션 onboarding** — 인위적 engagement, 우리는 진짜 데이터로 끌어옴
- **Custom 카드 만들기** — niche, low ROI
- **다중 카드 batch 스캔** — LO가 명시적으로 안 한다고 함
- **포켓몬 노래 / YouTube Music 링크** — off-topic
- **사주 / 운세** — off-topic
- **카드 이미지 자체 저장** (현재 weserv 프록시면 충분, R2는 센터링 학습 데이터용으로만)

---

## 9. 위험 / 의존 / 외부 요인

| 위험 | 영향 | 완화 방법 |
|---|---|---|
| eBay Growth Check 거부 | 정식 오픈 시 quota 부족 가능 | 사전에 dev support 메일 + Premium 폴링 빈도 조절 |
| AdSense 거부 | 광고 수익 0 (EPN + TCGplayer만) | EPN 단독으로도 viable, 다시 신청 |
| Render free tier 콜드 스타트 | 정식 오픈 시 첫 visitor 50초 대기 | Render Starter $7/월 또는 사전 warm-up cron |
| Neon free tier 한도 초과 | DB 일시 정지 | Launch $19 결제 미리 |
| 디자인 작업 지연 | 모든 후속 작업 디자인 mismatch | v0/Variant 결과 받은 다음 React 빠르게 |
| 친구 베타 churn | early validation 못 함 | 알림 시스템 + Multi-grade 같은 high-value 기능 빠르게 |

---

## 10. 이 문서 사용법

- **세션 시작 시**: `git pull` 후 이 파일 읽고 우선순위 확인
- **새 작업 끝나면**: 해당 항목 [ ] → [x] 표시 + PROJECT_STATUS.md §3.x / §11 업데이트
- **큰 결정 났을 때**: §6 결정 대기 → 결정 후 §1-3 우선순위로 반영
- **분기마다**: 전체 재정렬 (current stage 변경 반영)

---

*Generated 2026-06-27. Auto-update when major milestones flip.*
