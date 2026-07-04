/**
 * Internal-only changelog for the /admin/updates dashboard.
 *
 * Each entry captures one user-facing change in both KR and EN so the
 * admin can flip languages without translating in their head. Bug
 * fixes and pure refactors that nobody outside the build cares about
 * are omitted — this is "what shipped that a user might notice", not
 * a git log mirror.
 *
 * Add new entries to the TOP of the array. The page sorts by date
 * descending so newest always lands on top regardless of file order;
 * keeping the file order matched to display order makes diffs
 * legible during PR review.
 *
 * Date format: YYYY-MM-DD (ISO). Time format: HH:MM (24h) when known,
 * omit otherwise. KR is the primary language LO writes in; EN is the
 * translation. Both are required so the toggle stays consistent.
 */

export type UpdateEntry = {
  date: string;
  time?: string;
  emoji?: string;
  kr: string;
  en: string;
};

export const UPDATES: UpdateEntry[] = [
  // ── 2026-07-04 ─────────────────────────────────────────────────
  {
    date: "2026-07-04",
    emoji: "🎛️",
    kr: "카드/세트 페이지 사이드바 스크롤 수정 — 사이드바 자체 스크롤로 PRICE / ILLUSTRATOR 필터까지 다 도달 가능. 모바일 브라우저 툴바 자동 반영 (100dvh)",
    en: "Cards/Sets page sidebar scroll fix — PRICE and ILLUSTRATOR filters at the bottom are now reachable via the sidebar's own scrollbar. Mobile browser toolbar auto-accounted for (100dvh)",
  },
  {
    date: "2026-07-04",
    emoji: "🎨",
    kr: "카드 상세 페이지에 일러스트레이터 표시 + '이 작가의 다른 카드 보기' 버튼 추가 — 클릭하면 해당 작가의 모든 카드 리스트로 이동",
    en: "Card detail now shows the illustrator with a 'See more by this artist' button — click to browse every card by the same illustrator",
  },
  // ── 2026-07-03 ─────────────────────────────────────────────────
  {
    date: "2026-07-03",
    emoji: "🎴",
    kr: "일본판 언넘버드 프로모 이미지 추가 105장 — pokumon.com WP REST API로 카드별 매칭. 1996-2005 벌크(JPP-U1996)는 79% 커버까지 상승, Battle Road 2007-2008 시대 트레이너 supporter 카드 (Roseanne's Research, Bebe's Search, Cynthia's Feelings 등) 다 확보. 전체 언넘버드 이미지 커버리지 26% → 48%.",
    en: "Japanese Unnumbered Promo images — 105 additional card scans landed via pokumon.com's WP REST API. 1996-2005 bucket now at 79% coverage; the Battle Road 2007-2008 trainer supporter lineup (Roseanne's Research, Bebe's Search, Cynthia's Feelings…) is complete. Total unnumbered image coverage 26% → 48%.",
  },
  {
    date: "2026-07-03",
    emoji: "🏆",
    kr: "일본판 언넘버드 프로모 496장 신규 (20개 연도별 세트) — Bulbapedia table-row 파싱 + redirect 추적 + JP 파일명 매칭. Pokémon Illustrator ($1M+), Trophy Card No.1/2/3 Trainer, Imakuni? Corocoro, Playmat Slowpoke, Pikachu-Jigglypuff-Clefairy Jumbo 등 컬렉터 코어 카드 74장 이미지 확보. 나머지 422장은 이름/변형 태그/발매 채널 명확하지만 이미지 소스 매칭 불가로 placeholder.",
    en: "Japanese Unnumbered Promos — 496 cards seeded across 20 year-bucketed sets. Bulbapedia table-row parse + redirect dedupe + strict JP-filename matching. 74 cards land with correct scans including Pokémon Illustrator (\\$1M+), Trophy Card No.1/2/3 Trainer, Imakuni? CoroCoro, Playmat Slowpoke, Pikachu-Jigglypuff-Clefairy Jumbo. Remaining 422 have names + variant tags + release channel notes but no matched JP scan on Bulbapedia (placeholder shown).",
  },
  {
    date: "2026-07-03",
    emoji: "🏝️",
    kr: "일본판 서던아일랜드 (Southern Islands) 18장 + P 프로모 45장 추가 — Bulbapedia 크롤. JPP-SI 세트 stub이 실제 카드로 채워짐, JPP-P는 10 → 55장으로 확장.",
    en: "Japanese Southern Islands (18 cards) + P Promos (45 cards) added via Bulbapedia crawl. JPP-SI stub is now populated, JPP-P grew 10 → 55.",
  },
  {
    date: "2026-07-03",
    emoji: "📦",
    kr: "일본판 카탈로그 대폭 확장 — 138개 세트 + 6,538장 신규 (총 311 세트 / 20,900장). BW 메인라인 (Black/White/Red Collection, Dark Rush, Psycho Drive, Freeze Bolt 등), HGSS/L era (Clash at the Summit, HeartGold/SoulSilver Collection), SM 서브셋 (SMA-SMN, SM1p-SM5p starter decks), XY concept packs (XYA-XYH), SwSh/SV starter+battle decks 전부 import. Limitless TCG 출처.",
    en: "Japanese catalog massive expansion — 138 new sets + 6,538 cards (now 311 sets / 20,900 cards). BW mainline (Black/White/Red Collection, Dark Rush, Psycho Drive, Freeze Bolt etc.), HGSS/L era (Clash at the Summit, HeartGold/SoulSilver Collection), SM sub-sets (SMA-SMN, SM1p-SM5p starter decks), XY concept packs (XYA-XYH), SwSh/SV starter+battle decks all imported. Source: Limitless TCG.",
  },
  // ── 2026-07-02 ─────────────────────────────────────────────────
  {
    date: "2026-07-02",
    emoji: "🆕",
    kr: "일본판 MEGA 에라 최신 세트 2개 신규 import — M4 「ニンジャスピナー」 (Ninja Spinner, 3월 발매, 120장) + M5 「アビスアイ」 (Abyss Eye, 5월 발매, 81장). TCGdex는 아직 미indexed지만 Limitless에서 카드+이미지 다 확보. M5 레어도는 EN 미출시로 임시 NULL, 시간 지나 자동 채워짐.",
    en: "Two newest Japanese MEGA-era sets imported — M4 Ninja Spinner (Mar release, 120 cards) + M5 Abyss Eye (May release, 81 cards). Pulled from Limitless (TCGdex hasn't indexed them yet); rarities on M5 stay NULL until the EN equivalent print list appears.",
  },
  // ── 2026-06-30 ─────────────────────────────────────────────────
  {
    date: "2026-06-30",
    emoji: "📈",
    kr: "트렌딩에 Modern / Classic 에라 필터 추가 — BW 발매(2011-03-01) 기준으로 분리. Modern = BW 이후, Classic = WOTC~HGSS. 빈티지 리자몽과 최신 SAR 시세 각각 분리해서 볼 수 있음",
    en: "Trending: Modern / Classic era filter added — split at BW launch (2011-03-01). Modern = BW onwards, Classic = WOTC through HGSS. Vintage Charizard movement now watchable separately from modern SAR pack-pull hype",
  },
  {
    date: "2026-06-30",
    emoji: "📈",
    kr: "트렌딩 eBay 1d 필터 부활 — Mon+Thu 크론 하에서 '1d'를 '지난 실질 스냅샷 이후'로 재정의. 지난 크론 대비 변동 있는 카드 3,155장 노출",
    en: "Trending eBay 1d filter restored — under the Mon+Thu cron cadence, '1d' now means 'since the last substantial sync' (3,155 cards with movement since prev cron)",
  },
  {
    date: "2026-06-30",
    emoji: "📈",
    kr: "트렌딩 eBay 소스 정상화 — Mon+Thu 크론 스케줄에 맞춰 7d/30d/90d 최소 스냅샷 임계값을 소스별로 분리 (7d에서 카드 3,398개 다시 노출)",
    en: "Trending eBay source restored — separated the minimum-snapshot floor per source so it matches the Mon+Thu cron cadence (3,398 cards re-eligible in the 7d window)",
  },
  {
    date: "2026-06-30",
    emoji: "🛒",
    kr: "포트폴리오 카드 삭제 확인 임계값 완화 — 1~9장 삭제는 원클릭 확인, 10장 이상만 'DELETE' 타이핑 요구",
    en: "Portfolio delete confirmation eased — 1-9 cards delete with a single click, only 10+ requires typing 'DELETE'",
  },
  {
    date: "2026-06-30",
    emoji: "🎴",
    kr: "일본판 e-Card 시대 (E1-E5, 2001-2002) 카드 이미지 489장 채워짐 — nazonobasho.com 출처. E1은 기존 영문판 이미지에서 일본판 네이티브 스캔으로 교체. JP 이미지 커버리지 97.4% → 99.94% (잔여 9장만). 1996년부터 현재까지 모든 일본판 빈티지 시대 카드 이미지 라이브러리 완성.",
    en: "Japanese e-Card era (E1-E5, 2001-2002) — 489 card images filled via nazonobasho.com. E1 swapped from the EN variant to native JP scans. JP image coverage 97.4% → 99.94% (only 9 cards remain). The vintage Japanese illustration library is now complete from 1996 through the modern era.",
  },
  {
    date: "2026-06-30",
    emoji: "🃏",
    kr: "일본판 PCG 시리즈 (홀론의 연구탑부터 さいはての攻防까지, 2004-2006) 카드 이미지 720장 채워짐 — learn-book.com 출처. JP 이미지 커버리지 92.4% → 97.4%. e-Card 시대 4세트 (E2-E5)만 남음.",
    en: "Japanese PCG series (Holon Research Tower through Battle at Furthest Ends, 2004-2006) — 720 card images filled via learn-book.com. JP image coverage 92.4% → 97.4%. Only 4 e-Card era sets (E2-E5) remain.",
  },
  {
    date: "2026-06-30",
    emoji: "🖼️",
    kr: "일본판 빈티지 카탈로그 이미지 ~775장 새로 채워짐 (PMCG1-6 / E1 / VS1 / web1) — 1996년 1세대 베이스세트부터 e-Card 시대까지 카드 일러스트 라이브러리 완성. 영문 1:1 매핑 카드는 EN variant 이미지 (디자인 동일, 텍스트만 영어), JP-only 세트는 일본판 스캔. JP 이미지 커버리지 87% → 92.4%.",
    en: "Japanese vintage catalog: ~775 card images newly filled (PMCG1-6 / E1 / VS1 / web1) — illustrations now in place for the 1996 Base Set through the e-Card era. 1:1 EN-equivalent sets use the EN variant image (same artwork, English text); JP-only sets use native JP scans. JP image coverage 87% → 92.4%.",
  },
  // ── 2026-06-29 ─────────────────────────────────────────────────
  {
    date: "2026-06-29",
    emoji: "🏷️",
    kr: "일본판 카탈로그 레어도 97.5% coverage 달성 (14,362장 중 NULL 366장) — Limitless EN-equivalents 풀스윕 (1,773장 신규) + Bulbapedia 풀스윕으로 JP-native tier polish (SR/SAR/HR/RRR 정확도 개선, 8,234장 update) + JPP 프로모 2,009장 일괄 'Promo'. UI 필터에서 SR/SAR만 보이던 누락 거의 해소.",
    en: "Japanese rarity backfill: 97.5% coverage now (366 NULL / 14,362) — full Limitless EN-equivalent sweep (1,773 newly filled) + Bulbapedia sweep for JP-native tier polish (8,234 rows updated for SR/SAR/HR/RRR accuracy) + 2,009 JPP promos blanket-filled as 'Promo'. The 'missing rarity' gap that hid SR/SAR cards from filters is mostly closed.",
  },
  {
    date: "2026-06-29",
    emoji: "🗺️",
    kr: "일본판 SM / XY / CP 시리즈 44개 세트 신규 import (3,392장, Limitless TCG 출처) — JP 카탈로그 14,362장 / 135 세트로 확장",
    en: "Japanese catalog: 44 SM / XY / CP sets imported (3,392 cards via Limitless TCG) — total JP now 14,362 cards across 135 sets",
  },
  {
    date: "2026-06-29",
    emoji: "🗺️",
    kr: "일본판 카탈로그 25개 세트 신규 노출 (PMCG / VS / web / E-card / PCG 빈티지 + SV 스타터) — 약 1,949장 추가 브라우즈 가능",
    en: "Japanese catalog: 25 sets newly visible (vintage PMCG / VS / web / E-card / PCG + modern SV starters) — ~1,949 more browseable cards",
  },
  {
    date: "2026-06-29",
    emoji: "💰",
    kr: "세트 가치 표시 = TCGplayer 미드 합계로 변경 (그레이드 슬랩이 잡히는 high 대신)",
    en: "Set value headline now sums TCGplayer mid prices (instead of high, which catches graded slabs)",
  },
  {
    date: "2026-06-29",
    emoji: "🔍",
    kr: "검색창 비어있을 때 'Popular Pokémon' 칩 표시 (변형 많은 포켓몬 TOP 10)",
    en: "Empty search input now shows 'Popular Pokémon' chips (top 10 by card variant count)",
  },
  {
    date: "2026-06-29",
    emoji: "🗺️",
    kr: "프로모 세트 중복 정리 + 맥도날드 세트 통합 (363장 중복 제거, 13개 빈 세트 삭제)",
    en: "Promo set duplicate cleanup + McDonald's set merge (363 dupes removed, 13 empty sets dropped)",
  },
  {
    date: "2026-06-29",
    emoji: "🗺️",
    kr: "퍼스트파트너 일러스트 시리즈 2 별도 세트로 복원, 메가에라 프로모 로고 추가",
    en: "First Partner Illustration Series 2 restored as standalone set, Mega Evolution promo got its logo",
  },
  {
    date: "2026-06-29",
    emoji: "🗑️",
    kr: "Player Placement Trainer Promos 세트 삭제 (TCGplayer에서도 카드 이미지 없는 세트)",
    en: "Removed Player Placement Trainer Promos set (no card images available even on TCGplayer)",
  },

  // ── 2026-06-28 ─────────────────────────────────────────────────
  {
    date: "2026-06-28",
    emoji: "📸",
    kr: "카드 스캔 UI 전면 개편 — 카와이 카메라 + 인식 결과 확인 화면",
    en: "Card scan UI overhaul — kawaii camera + recognition confirm screen",
  },
  {
    date: "2026-06-28",
    emoji: "📸",
    kr: "스캔 중 '카드 읽는 중…' 마스코트 애니메이션, 토치 버튼, 갤러리 선택 버그 수정",
    en: "Scanning mascot animation, working torch toggle, gallery-picker bug fix",
  },
  {
    date: "2026-06-28",
    emoji: "⚡",
    kr: "스캔 캐시 — 같은 카드 두 번 찍으면 Claude API 안 거치고 즉시 결과 (이미지 해시 매칭)",
    en: "Scan cache — re-scanning the same card skips Claude API, instant result via perceptual hash",
  },
  {
    date: "2026-06-28",
    emoji: "🗺️",
    kr: "메가에라 프로모 세트(MEP) + WoTC부터 SV까지 30개 프로모 세트 일괄 추가 (1,630장)",
    en: "Mega Evolution Promo (MEP) + 30 promo sets seeded from WoTC through SV era (1,630 cards)",
  },

  // ── 2026-06-27 ─────────────────────────────────────────────────
  {
    date: "2026-06-27",
    emoji: "🛒",
    kr: "Live Listings 개선 — 새로고침 버튼, Raw/Graded 뱃지, 미끼 매물 자동 제외",
    en: "Live Listings polish — refresh button, Raw/Graded corner badge, bait-scam outlier filter",
  },
  {
    date: "2026-06-27",
    emoji: "🤖",
    kr: "Newsbot 검색 엔진 강화 — Serper /news + 신뢰 도메인 우회 + 토픽 필터링",
    en: "Newsbot search upgrade — Serper /news endpoint + trusted-domain bypass + topic filtering",
  },
  {
    date: "2026-06-27",
    emoji: "🎨",
    kr: "어드민에서 로컬 이미지 업로드 가능 (Vercel Blob 연동)",
    en: "Admin can now upload local images directly (Vercel Blob integration)",
  },

  // ── 2026-06-26 ─────────────────────────────────────────────────
  {
    date: "2026-06-26",
    emoji: "🚩",
    kr: "카드 데이터 오류 신고 기능 + 어드민 처리 화면",
    en: "Card data-quality report flow + admin triage dashboard",
  },
  {
    date: "2026-06-26",
    emoji: "💰",
    kr: "카드 가격 수동 새로고침 (🔄 버튼, 'Up to date!' 표시)",
    en: "Manual card-price refresh button with 'Up to date!' confirmation flash",
  },
  {
    date: "2026-06-26",
    emoji: "📈",
    kr: "트렌딩 가격대에 $500+ 구간 추가 ($100과 $1000 사이)",
    en: "Trending feed: added $500+ tier (between $100 and $1000 buckets)",
  },
  {
    date: "2026-06-26",
    emoji: "📱",
    kr: "모바일 메뉴에 뉴스 링크 추가",
    en: "Mobile drawer now includes the News link",
  },
  {
    date: "2026-06-26",
    emoji: "💰",
    kr: "TCGCSV 가격 동기화를 일일($1+) + 월간(저가 카드) 두 단계로 분리",
    en: "TCGCSV price sync split into daily (≥$1) and monthly bulk tiers",
  },

  // ── 2026-06-24 ─────────────────────────────────────────────────
  {
    date: "2026-06-24",
    emoji: "🤖",
    kr: "Newsbot 일일 크론 활성화 (매일 21:00 KST = 8am ET 자동 발행)",
    en: "Newsbot daily cron live (publishes every day at 8am ET / 21:00 KST)",
  },
  {
    date: "2026-06-24",
    emoji: "💰",
    kr: "세트 가치를 컴플리션 가격 범위로 표시 (최저 합 ~ 최고 합)",
    en: "Set value shows completion-cost range (sum of lows ~ sum of highs)",
  },

  // ── 2026-06-23 ─────────────────────────────────────────────────
  {
    date: "2026-06-23",
    emoji: "🛒",
    kr: "포트폴리오 행마다 편집 모달 + 변형(홀로/리버스) 칩 표시",
    en: "Portfolio per-row Edit modal + variant chip for non-default prints",
  },
  {
    date: "2026-06-23",
    emoji: "🛒",
    kr: "카드 추가 모달 — '나도 이 카드 가지고 있어요' 원클릭 + 풀옵션 추가",
    en: "Card-add modal — single-tap 'I have this' + full-options add flow",
  },
  {
    date: "2026-06-23",
    emoji: "🔍",
    kr: "검색 결과 정렬 옵션 (관련도/가격/발매일)",
    en: "Search results sort dropdown (relevance / price / release date)",
  },
  {
    date: "2026-06-23",
    emoji: "📈",
    kr: "트렌딩 가격 필터를 구간 형태로 변경 ($100+, $1000+ 추가)",
    en: "Trending price filter switched to bands ($100+, $1000+ added)",
  },
  {
    date: "2026-06-23",
    emoji: "🛒",
    kr: "포트폴리오 일괄 삭제 모드 + 첫번째 파트너 시리즈 1/2 로고 추가",
    en: "Portfolio bulk-delete mode + First Partner Series 1/2 logos",
  },

  // ── 2026-06-22 ─────────────────────────────────────────────────
  {
    date: "2026-06-22",
    emoji: "🤖",
    kr: "Newsbot Phase 1 — 매일 자동 뉴스 크롤링 + 분류 + Claude로 본문 생성 + 발행",
    en: "Newsbot Phase 1 — daily crawl + classify + Claude-generated body + auto-publish",
  },
  {
    date: "2026-06-22",
    emoji: "🗺️",
    kr: "퍼스트파트너 일러스트 컬렉션 시리즈 1+2 추가 (18장)",
    en: "First Partner Illustration Collection Series 1 + 2 added (18 cards)",
  },
  {
    date: "2026-06-22",
    emoji: "🎨",
    kr: "뉴스 본문에 인라인 이미지 자동 임베드, 히어로 썸네일 weserv 프록시",
    en: "News articles auto-embed inline images, hero thumbnails routed through weserv proxy",
  },

  // ── 2026-06-21 ─────────────────────────────────────────────────
  {
    date: "2026-06-21",
    emoji: "📰",
    kr: "뉴스 섹션 오픈 — 마크다운 포스트 + 조회수 + 카테고리별 탐색",
    en: "News section launched — Markdown posts + view counts + category browsing",
  },
  {
    date: "2026-06-21",
    emoji: "🔒",
    kr: "어드민 사용자 관리 패널 + 소프트 삭제 + 미들웨어",
    en: "Admin users panel + soft delete + middleware guard",
  },
  {
    date: "2026-06-21",
    emoji: "🔒",
    kr: "안티봇 1단계 — 허니팟, IP별 레이트 리밋, 일회용 이메일 차단",
    en: "Anti-bot Phase 1 — honeypot field, per-IP rate limit, disposable email blocklist",
  },
  {
    date: "2026-06-21",
    emoji: "💰",
    kr: "TCGCSV가 TCGplayer 가격 전담 (pokemontcg.io는 Cardmarket만)",
    en: "TCGCSV owns TCGplayer pricing (pokemontcg.io demoted to Cardmarket only)",
  },
  {
    date: "2026-06-21",
    emoji: "🔍",
    kr: "포켓몬 도감 번호 기반 다국어 검색 (예: 'Charizard' 검색 → リザードン도 함께 노출)",
    en: "Cross-language search via Pokédex number (e.g. 'Charizard' surfaces リザードン too)",
  },
  {
    date: "2026-06-21",
    emoji: "📈",
    kr: "트렌딩 화면을 Bulk vs Chase 희귀도로 분리 (수집가 관점별 다른 신호)",
    en: "Trending split into Bulk vs Chase rarity tiers (different signals for different audiences)",
  },
  {
    date: "2026-06-21",
    emoji: "🎨",
    kr: "마스코트 변형 추가 (잠자기 / 팩 오픈 / 부드러운 듀오 / 픽셀 솔로)",
    en: "Mascot variants added (sleeping, pack-opening, smooth duo, pixel solo)",
  },

  // ── 2026-06-20 ─────────────────────────────────────────────────
  {
    date: "2026-06-20",
    emoji: "🌐",
    kr: "일본판 카탈로그 통합 (3,061장 본세트 + 1,991장 프로모) + 지역 탭",
    en: "Japanese catalog imported (3,061 expansion + 1,991 promo cards) + region tabs",
  },
  {
    date: "2026-06-20",
    emoji: "🛒",
    kr: "Live Listings — 판매자 신뢰도 + 가격 이상치 자동 플래깅 + 액세서리 노이즈 제거",
    en: "Live Listings — seller trust tier + price anomaly flagging + accessory denylist",
  },
  {
    date: "2026-06-20",
    emoji: "🛒",
    kr: "포트폴리오 가치 TOP 10 카드 (랭크 뱃지 포함)",
    en: "Portfolio: Top 10 cards by value with rank badges",
  },
  {
    date: "2026-06-20",
    emoji: "🎨",
    kr: "이미지 돋보기 (카드 모양 루페, 2배 확대) — 디테일 확인용",
    en: "Image magnifier (card-shaped loupe, 2× zoom) for detail inspection",
  },

  // ── 2026-06-19 ─────────────────────────────────────────────────
  {
    date: "2026-06-19",
    emoji: "🌐",
    kr: "한국어 세트명 매핑 + EN/KR 토글 (예: 'Scarlet & Violet' ↔ '스칼렛&바이올렛')",
    en: "Korean set-name mapping + EN/KR toggle (e.g. 'Scarlet & Violet' ↔ '스칼렛&바이올렛')",
  },

  // ── 2026-06-18 ─────────────────────────────────────────────────
  {
    date: "2026-06-18",
    emoji: "🔒",
    kr: "Google 계정 로그인 + 계정 삭제 + 법적 페이지(개인정보/이용약관) + 쿠키 배너",
    en: "Google sign-in + account deletion + legal pages (privacy/terms) + cookie banner",
  },
  {
    date: "2026-06-18",
    emoji: "📱",
    kr: "런칭 폴리시 — 커스텀 404/500, 글로벌 스켈레톤, 사이트맵, robots.txt",
    en: "Launch polish — custom 404/500 pages, global skeleton, sitemap, robots.txt",
  },
  {
    date: "2026-06-18",
    emoji: "📈",
    kr: "트렌딩 SQL 측 집계로 OOM 해결 + 가격 보존 크론",
    en: "Trending OOM fix via SQL-side aggregation + retention cron",
  },

  // ── 2026-06-17 ─────────────────────────────────────────────────
  {
    date: "2026-06-17",
    emoji: "💰",
    kr: "TCGplayer 카드별 1년치 가격 히스토리 백필 완료",
    en: "TCGplayer 1-year price history backfilled per card",
  },
  {
    date: "2026-06-17",
    emoji: "🛒",
    kr: "어필리에이트 링크 자동 래핑 (TCGplayer Impact + eBay EPN)",
    en: "Affiliate link auto-wrap (TCGplayer Impact + eBay EPN)",
  },
  {
    date: "2026-06-17",
    emoji: "🛒",
    kr: "포트폴리오 OG 이미지 자동 생성 + CSV 내보내기",
    en: "Portfolio OG image auto-generation + CSV export",
  },
  {
    date: "2026-06-17",
    emoji: "💰",
    kr: "TCGplayer low/high 가격대를 일반(언그레이드) NM 범위로 자동 클립",
    en: "TCGplayer low/high prices auto-clipped to typical raw-NM range",
  },

  // ── 2026-06-16 ─────────────────────────────────────────────────
  {
    date: "2026-06-16",
    emoji: "🎨",
    kr: "카드 상세 페이지 전면 개편 — 3카드 히어로 + low/mid/high 가격 차트 + 호버 툴팁",
    en: "Card detail page redesign — 3-card hero + low/mid/high chart with hover tooltip",
  },
  {
    date: "2026-06-16",
    emoji: "🛒",
    kr: "포트폴리오 공유 — 토큰 URL + 옵트인 토글 (총자산 숨기기 등)",
    en: "Portfolio sharing — non-enumerable token URL + opt-in privacy toggles",
  },
  {
    date: "2026-06-16",
    emoji: "💰",
    kr: "eBay 스냅샷 — 그레이드 슬랩 자동 제외 + 희귀도별 절대 가격 상한",
    en: "eBay snapshots — graded-slab title filtering + per-rarity absolute price ceiling",
  },

  // ── 2026-06-15 ─────────────────────────────────────────────────
  {
    date: "2026-06-15",
    emoji: "📸",
    kr: "카드 스캐닝 V1 — Claude Vision API + 카메라 캡처 → 카드 자동 식별",
    en: "Card scanning V1 — Claude Vision API + camera capture → auto-identify",
  },
  {
    date: "2026-06-15",
    emoji: "📱",
    kr: "PWA Phase 1 — 매니페스트, 서비스 워커, 모바일 레이아웃",
    en: "PWA Phase 1 — manifest, service worker, mobile-ready layout",
  },

  // ── 2026-06-14 ─────────────────────────────────────────────────
  {
    date: "2026-06-14",
    emoji: "🆕",
    kr: "위시리스트 기능 (목표가 설정 모달 + 모니터링 + 별도 페이지)",
    en: "Wishlist feature — target-price modal, monitoring, dedicated page",
  },
  {
    date: "2026-06-14",
    emoji: "🆕",
    kr: "포트폴리오 V1 + 일일 스냅샷 (총자산 변동 추적)",
    en: "Portfolio v1 + daily snapshot (total value over time)",
  },
  {
    date: "2026-06-14",
    emoji: "🛒",
    kr: "Live Listings — 썸네일, 필터 칩, 신뢰 뱃지, 새로고침 버튼",
    en: "Live Listings — thumbnails, filter pills, trust badges, refresh button",
  },
  {
    date: "2026-06-14",
    emoji: "🎨",
    kr: "사이트 전체 라이트/다크 테마 + TopNav 토글",
    en: "Site-wide light/dark theme via CSS variable tokens + TopNav toggle",
  },
  {
    date: "2026-06-14",
    emoji: "🎨",
    kr: "Variant 디자인 패스 — 마스코트, on-fire 강조, dragon-scouts empty state",
    en: "Variant design pass — mascot in TopNav, on-fire callout, dragon-scouts empty state",
  },
  {
    date: "2026-06-14",
    emoji: "💰",
    kr: "일일 TCGplayer + Cardmarket 가격 동기화 크론 가동",
    en: "Daily TCGplayer + Cardmarket price sync cron live",
  },
  {
    date: "2026-06-14",
    emoji: "💰",
    kr: "eBay를 신규 가격 소스로 추가 — 일일 스냅샷 + 가격 히스토리 차트",
    en: "eBay added as price source — daily snapshots + price history chart",
  },
  {
    date: "2026-06-14",
    emoji: "🔒",
    kr: "로그인/회원가입 페이지 리디자인 + 비밀번호 강도 미터 + 마스코트 히어로",
    en: "Login/signup redesign + password strength meter + mascot hero",
  },
  {
    date: "2026-06-14",
    emoji: "🆕",
    kr: "트렌딩 페이지 + 홈 히어로 + 최신 세트 + 필터 사이드바",
    en: "Trending page + home hero + latest sets strip + filter sidebar",
  },

  // ── 2026-06-12 ~ 2026-06-11 ────────────────────────────────────
  {
    date: "2026-06-11",
    emoji: "📱",
    kr: "모바일 햄버거 메뉴 (내비 + 인증 드로어)",
    en: "Mobile hamburger menu with nav + auth drawer",
  },
  {
    date: "2026-06-11",
    emoji: "⚡",
    kr: "API 응답 메모리 캐시 (5분 TTL) — 페이지 전환 즉시 반응",
    en: "In-memory API cache (5min TTL) for snappy navigation",
  },
  {
    date: "2026-06-11",
    emoji: "🆕",
    kr: "카드 이전/다음 내비게이션 + 키보드 단축키",
    en: "Prev/next card navigation with keyboard hotkeys",
  },
  {
    date: "2026-06-11",
    emoji: "🎉",
    kr: "PullList 첫 런칭 — 카드 카탈로그 + 컬렉션 트래커 + 필터 + 인증",
    en: "PullList initial launch — catalog + collection tracker + filters + auth",
  },
];
