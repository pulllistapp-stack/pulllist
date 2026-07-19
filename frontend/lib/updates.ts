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
  // ── 2026-07-19 ─────────────────────────────────────────────────
  {
    date: "2026-07-19",
    emoji: "🔄",
    kr: "Bulk 스캔을 pHash 매칭에서 **Gemini 자동 호출** 로 완전 전환. Single 모드에서 Gemini 가 검증됐고 (LO 실전 테스트 완료), pHash 는 실전 정확도가 0% 여서 매칭 알고리즘으로는 부적합 판정. 새 흐름: 매 500ms 프레임 pHash 계산 → 직전 프레임이랑 hamming < 5 (안정) 인지 체크 → 2틱 연속 안정 (~1초) 이면 카드 aspect 로 crop 한 480×670 JPEG 를 Gemini 로 보냄 → 응답 (2-3초) → 감지 배너. pHash 는 이제 '카메라 움직였는지' 판정에만 쓰임 (안정성 감지는 pHash 강점). 유저가 3-5초 카드 안정적으로 대는 시간 = 2초 안정성 + 3초 Gemini ≈ 5초 per 카드. Add/Skip 후 5초 재감지 안 함. 100장 벌크 세션 비용 ≈ **$0.01** (Gemini 무료 티어 하루 1500회 안에 여유). 카탈로그 fetch / closest 진단 라인 / pHash 매칭 로직 다 제거해서 코드 훨씬 짧아짐. 하단 힌트에 세션 스캔 카운트 표시 (비용 투명성).",
    en: "Bulk scan flow moved off pHash catalog matching onto **auto-firing Gemini calls**. Single-mode Gemini verified in LO's field test; pHash was landing at ~0 % real-world accuracy so it's not viable as the matcher. New loop: every 500 ms hash the frame, compare to previous — 2 consecutive frames within hamming ≤ 5 (≈1 s of the camera holding still) fires a card-aspect-cropped 480×670 JPEG to Gemini. Response (~2-3 s) surfaces as the detection banner. pHash's new job is only 'has the frame settled?' — which is what pHash is actually good at. Per-card end-to-end: ~1 s stability + ~3 s vision ≈ 4-5 s hold time; Add/Skip locks the same card out for 5 s. Cost for a 100-card bulk sort: about $0.01, well inside Gemini's 1500-req/day free tier. Removed the catalog fetch, the closest-match diagnostic, and the pHash matching logic — the bulk code shrunk substantially. Idle hint now shows a session scan counter so LO can see roughly how many vision calls (and therefore cents) this session consumed.",
  },
  {
    date: "2026-07-19",
    emoji: "🧪",
    kr: "스캔 Vision provider A/B 테스트 세팅. Bulk 모드 pHash 정확도가 실전에서 0% 라 대안 검증 중. Claude Haiku 4.5 ($0.003/스캔) 대신 Google Gemini 2.0 Flash ($0.0001/스캔, ~30배 저렴) 로 교체 가능성 테스트. 새 엔드포인트 /api/v1/cards/scan-gemini 추가 (기존 /cards/scan 이랑 완전 동일한 request/response, pHash 캐시도 공유). 프론트는 URL 쿼리 파라미터로 토글: /scan (default = Claude) vs /scan?vision=gemini. 아직 정식 릴리스 X — LO 가 GEMINI_API_KEY 를 Render 에 세팅 후 iPhone 에서 양쪽 몇 장씩 시도해서 정확도 비교하는 단계. Gemini 가 만족스러우면 Bulk 모드를 auto-Gemini 로 전환 (셔터 없이 3~5초 마다 자동 발사, 100장 정리에 약 $0.01). google-genai==1.16.0 requirements.txt 에 추가.",
    en: "Scan Vision provider A/B test scaffolding. Bulk-mode pHash accuracy landed at ~0 % in the field, so kicking the tires on cheaper alternatives before either doubling down on pHash or falling back to per-scan LLM calls. New /api/v1/cards/scan-gemini endpoint mirrors /cards/scan (same request / response shape, shares the pHash cache table) but routes to Google Gemini 2.0 Flash — roughly 30x cheaper than Claude Haiku 4.5 ($0.0001 vs $0.003 per scan) at similar accuracy. Frontend picks the provider via URL query param: /scan (default = Claude) vs /scan?vision=gemini. Not a real rollout yet — LO adds GEMINI_API_KEY to Render env, runs a few cards through both flows on iPhone single-shot mode, and if Gemini holds up we swap bulk mode to auto-Gemini (no shutter, fires every 3-5 s, ~$0.01 per 100-card bulk sort). google-genai==1.16.0 added to requirements.",
  },
  {
    date: "2026-07-19",
    emoji: "🖼️",
    kr: "**zh-tw 세트 로고 100% 커버리지** — Taiwan 훈련가 사이트(카드 DB 전용)에 세트 마케팅 아트가 없어서 방금 임포트한 27개 zh-tw 세트가 다 로고 NULL 로 렌더되던 문제. Google Image Search 로 먼저 시도 → 첫 요청은 성공하는데 두번째부터 봇 감지로 imgs 0 반환. Bing Image Search 로 피벗 (동일 headless-Chrome stack 으로 zh-TW 마켓 쿼리 3/3 일관 성공). 검색어 패턴 `寶可夢 {클린이름} 卡盒` (擴充包/挑戰牌組/戰術牌組 등 상품 접두사 스트립 후). 결과는 Bing 의 안정적인 프록시 (th.bing.com/th/id/OIP.<hash>?w=400&h=400) — 원본 리테일 사진 hot-link 보호에 안 걸리게 Bing이 이미 재호스팅한 상태. 27/27 매칭 성공, 총 소요 ~2.5분 (2초 sleep 정중 대기). 이제 /sets?region=zh-tw 열면 M시리즈 (16) + SV시리즈 (11) 모두 실물 팩 사진으로 표시.",
    en: "**zh-tw set logos hit 100% coverage** — the Taiwan trainer site is card-DB only (no per-set marketing art) so all 27 zh-tw sets were rendering with a null logo. Tried Google Image Search first — first query returns rich results but bot detection kicks in on request #2 and serves empty pages. Pivoted to Bing Image Search (same headless-Chrome stack, 3/3 consistent hits on zh-TW market queries). Query shape: `寶可夢 {clean_name} 卡盒` after stripping product-type prefixes (擴充包 / 挑戰牌組 / 戰術牌組). Results use Bing's stable thumbnail proxy (th.bing.com/th/id/OIP.<hash>?w=400&h=400) — because Bing already re-hosts the underlying retail-shop photos we bypass source-site hot-link protection entirely. 27/27 matched in ~2.5 min (2 s polite sleep between queries). /sets?region=zh-tw now shows every M-series (16) and SV-series (11) tile with a real pack photo.",
  },
  {
    date: "2026-07-19",
    emoji: "🏷️",
    kr: "**리전 탭 라벨에 언어 명시 추가** — 그동안 'China' / 'Taiwan' 만 표기해서 처음 방문한 유저는 두 탭의 차이 (간체 vs 번체) 를 즉시 파악 못했음. LO 도 유입 UX 관점에서 lump vs split 고민을 제기 → 데이터는 분리 유지가 컬렉터 정확도 위해 필수 (다른 마켓/다른 셋 코드/다른 인쇄) 지만 라벨을 'China (Simplified)' / 'Taiwan (Traditional)' 로 명시하면 캐주얼 브라우저도 '아 둘 다 중문이구나' 즉시 인지. 컬렉터 정확성 + 유입 명확성 둘 다 챙기는 최소 변경.",
    en: "**Region tab labels now show script variant** — the previous 'China' / 'Taiwan' labels made new visitors work to figure out the CN/TW split is Simplified vs Traditional Chinese. Keeping the underlying data split is non-negotiable for collector accuracy (different market, different set codes, different print runs) — but relabeling to 'China (Simplified)' / 'Taiwan (Traditional)' lets casual browsers see at a glance that both are Chinese variants. Minimum change that keeps the strict data model while removing the acquisition-side confusion LO flagged.",
  },
  {
    date: "2026-07-19",
    emoji: "🔀",
    kr: "**미스라벨된 zhcn-SV7~SV10 7세트 → zh-tw 로 재라벨** — CN Simplified 카탈로그에 들어와있던 SV7 (星晶奇跡) / SV7a (樂園騰龍) / SV8 (超電突圍) / SV8a (太晶慶典ex) / SV9 (對戰搭檔) / SV9a (熱風競技場) / SV10 (火箭隊的榮耀) 이 사실 번체자 대만판이었던 것 (跡/慶/對/龍 등 번체 형태). TCGdex zh-cn API 가 소스에서부터 잘못 라벨링한 것. 이번에 zh-tw 리전이 정식으로 생겼으니 원 위치로 이동. Set ID + Card ID 접두사 zhcn- → zhtw- 변경, language 컬럼 zh-tw 로 변경, 시리즈는 '朱＆紫 (Scarlet & Violet)' bilingual 포맷 부여. 총 7세트 / 829 카드 이관. 트랜잭션 감싸서 안전 실행. 이제 Taiwan 탭에 SV era 완전 커버 (SV7 ~ SV11W/B + SVQP/QL) + Mega era 16세트 = 총 27세트 / 3,725 카드.",
    en: "**Relabeled 7 mislabeled zhcn-SV7~SV10 sets to zh-tw** — SV7 (星晶奇跡) / SV7a (樂園騰龍) / SV8 (超電突圍) / SV8a (太晶慶典ex) / SV9 (對戰搭檔) / SV9a (熱風競技場) / SV10 (火箭隊的榮耀) were sitting in the CN Simplified catalog but their names are actually Traditional Chinese (跡/慶/對/龍 give it away — Simplified would use 迹/庆/对/龙). Root cause: TCGdex's zh-cn API mislabels them at source. Now that we have a proper zh-tw region, they're moved home: set + card ID prefix flipped zhcn- → zhtw-, language column updated, series canonicalized to '朱＆紫 (Scarlet & Violet)'. 7 sets / 829 cards migrated in a single transaction. Taiwan tab now fully covers the SV era (SV7 through SV11W/B + SVQP/QL) plus 16 Mega era sets = 27 total / 3,725 cards.",
  },
  {
    date: "2026-07-19",
    emoji: "🇹🇼",
    kr: "**Taiwan (번체자) 카탈로그 신규 추가** — TCGdex 의 zh-tw 피드가 stale (SV9a 에서 stop) 이라 지금까지 대만 시장 신작을 우리 카탈로그에서 못 보고 있었음. 대만은 사실 2025-08 부터 超級進化 (Mega Evolution) era 열어서 지금 (2026-07) 까지 벌써 16개 세트 판매 중 — 「烈獄狂火X」 「超級進化夢想ex」 「虛無歸零」 「忍者飛旋」 「深淵之瞳」 등 JP MEGA 시리즈 (M1S/M1L/M2/M2a/MC/M3/M4/M5) 의 대만판. Taiwan Pokemon Company 공식 훈련가 사이트 (asia.pokemon-card.com/tw) 크롤링해서 20개 세트 (16 Mega + 4 최근 SV: 純白閃焰, 漆黑伏特, ex초급덱 皮卡丘/噴火龍), 총 2,896 카드 임포트 완료. Frontend 에 🇹🇼 Taiwan 리전 탭 추가. 시리즈는 KR/CN 과 같이 bilingual 포맷 (超級進化 (Mega Evolution)). 카드 이미지는 완전 커버 (Taiwan 공식 CDN /tw/card-img/ 경로). 세트 로고는 이번 임포트 스코프 안이 아니라 별도 백필 트랙 예정 (KR 처럼 리테일 사이트 스크레이핑).",
    en: "**Added Taiwan (Traditional Chinese) catalog** — TCGdex's zh-tw feed had gone stale (last set SV9a, Q1-2025) so we'd been blind to Taiwan's market for a year+. Taiwan actually opened the 超級進化 (Mega Evolution) era back in 2025-08 and by mid-2026 has 16 Mega sets on shelf — Taiwanese editions of the JP MEGA series (M1S/M1L/M2/M2a/MC/M3/M4/M5) plus tactical decks and challenge decks. Scraped Taiwan Pokemon Company's official trainer site (asia.pokemon-card.com/tw) for 20 expansions (16 Mega + 4 recent SV: 純白閃焰, 漆黑伏特, ex-starter Pikachu/Charizard), totalling 2,896 cards. Added a 🇹🇼 Taiwan region tab in the frontend. Series stored bilingually (超級進化 (Mega Evolution)) to match the KR/CN canonicalization. Card images fully covered (Taiwan official CDN /tw/card-img/). Set logos out of scope this pass — the trainer site is a pure card database with no per-set marketing art; will backfill from retail sites next, same pattern as the KR logo track.",
  },
  {
    date: "2026-07-19",
    emoji: "🇨🇳",
    kr: "CN (중문 간체) 카탈로그 **디듑 + 중국어 이름 정리**. Root cause: KR→CN 정리 작업 (128개 세트 zhcn-c-* 로 이동) 이후, TCGdex 에서 원래 임포트했던 56개 native 로우 (`zhcn-CSV5C`, `zhcn-CBB3C` 등) 가 빈 껍데기 (0 카드, 0 로고) 로 남아있었음. 이 빈 껍데기들은 진짜 중국어 이름 (太晶盛聚 등) + 정확한 시리즈 분류 (朱&紫) 는 갖고 있었는데, moved 128개 로우는 카드/로고 다 있지만 이름은 영어/한글 (Terastal Gathering / '슈퍼 일렉트릭 브레이커') + 시리즈는 null 이나 'OTHER' 였음. 결과적으로 같은 물리적 세트가 UI 에 두 개 다른 이름으로 표시되는 상황. 픽스: `merge_cn_natives_into_moved.py` — 같은 릴리즈일 페어 (98쌍) 에 대해 native 의 중국어 name/name_local/series 를 primary moved (해당 날짜 최다 카드 SKU) 로 승격, 부제로 기존 영어 이름은 `name_en` 에 보존, sub-SKU 들에는 시리즈만 전파. 시리즈는 KR 정리 때랑 동일 패턴으로 bilingual 포맷 (朱&紫 → '朱&紫 (Scarlet & Violet)'). 병합 후 빈 native 48개 삭제. 최종: 184 → 136 세트 (-48), 로고 커버리지 94% (128/136). 남은 8 native 는 별도 이슈 (7개는 사실 번체자 zh-tw 미스라벨, 1개는 진짜 CN Battle Party Reward Pack).",
    en: "CN (Simplified Chinese) catalog **dedupe + Chinese-name canonicalization**. Root cause: after the KR→CN cleanup (128 sets moved to `zhcn-c-*`), the original TCGdex CN import's 56 rows (`zhcn-CSV5C`, `zhcn-CBB3C`, etc.) sat as empty shells (0 cards, 0 logos). The shells had the proper Chinese names (太晶盛聚, etc.) + correct series classification (朱&紫) but no card/logo data. Meanwhile the 128 moved rows had all the card/logo data but their `name` was English or Korean (\"Terastal Gathering\" / \"슈퍼 일렉트릭 브레이커\") with series null or 'OTHER'. Net effect: same physical set surfaced twice under two different names in the CN catalog UI. Fix: `merge_cn_natives_into_moved.py` — for each same-release-date pair (98 pairs), promote the native's Chinese name/name_local/series onto the primary moved row (highest card count on that date), preserve the original English/Korean name in `name_en` as subtitle, propagate series to all sub-SKUs on that date. Series stored as bilingual `朱&紫 (Scarlet & Violet)` — same pattern as the KR canonicalization. Empty natives deleted after merge (48 rows). Result: 184 → 136 sets (−48), 94 % logo coverage (128/136). 8 natives remain: 7 turned out to be Traditional Chinese mislabeled as `zh-cn` (SV7/SV7a/SV8/SV8a/SV9/SV9a/SV10 — needs zh-tw relabel), 1 is a genuine CN Battle Party Reward Pack (`CSMPiC`).",
  },
  {
    date: "2026-07-19",
    emoji: "🕵️",
    kr: "Bulk 스캔 오탐 진단 + 픽스. LO 가 손바닥 올려도 랜덤 카드 (dist 16) 뜨는 문제 리포트 → 카탈로그 덤프 분석. 원인 두 개: (1) **placeholder 이미지 클러스터** — 146개 카드가 image_small 이 다 같은 URL (Bulbapedia 의 'Japanese card back' generic 이미지) 이라 같은 pHash (9f323898e4331b8f) 공유. 40개 클러스터 총 645장이 저주파 콘텐츠 (손바닥, 어두운 배경 등) 랑 우연히 dist 16 근처 매치 → 팬텀 카드. (2) 카메라→카탈로그 매치 threshold 22 가 애매하게 낮음. 픽스: (A) 백엔드 catalog 엔드포인트에서 10회+ 중복 hash 제외 (645장 노이즈 필터), (B) threshold 22 → 26 완화, (C) BulkScanPanel 에 진단 라인 추가 — 매 tick 최근접 매치 + dist 항상 표시 (임계값 이하면 배너, 이상이면 회색 힌트). LO 가 카드 대고 있을 때 진짜 dist 얼마 나오는지 실시간으로 볼 수 있음. 알고리즘 자체는 검증 완료 (Python imagehash vs JS 알고리즘 hamming distance 0 — 완전 일치).",
    en: "Bulk scan false-positive diagnosis + fix. LO reported that a hand palm matched to a random card at dist 16 → dumped the catalog and analyzed hash frequencies. Two causes: (1) **Placeholder image clustering** — 146 catalog rows all point to the same Bulbapedia 'Japanese card back' URL, so they all share pHash 9f323898e4331b8f. 40 such clusters totalling 645 cards pull low-content camera frames (empty hands, dark backgrounds) toward random detections around dist 16. (2) The camera→catalog match threshold of 22 was awkward — too tight for legit cards to hit, loose enough that noise clusters slipped through. Fix: (A) catalog endpoint now excludes any hash appearing more than 10 times (drops the 645-card noise floor), (B) threshold bumped 22 → 26, (C) BulkScanPanel shows a diagnostic line every tick — nearest match + distance always visible (banner if below threshold, muted hint if above). LO can now see exactly how close a real card lands even when it doesn't clear the bar. Algorithm itself is verified — a Python transcription of the JS pHash produces the same 16-hex output as Python imagehash bit-for-bit for real card images, so any residual drift is camera-vs-render noise, not a coding bug.",
  },
  {
    date: "2026-07-19",
    emoji: "🎯",
    kr: "Bulk 스캔 정확도 대개선 (첫 릴리스 때 ~0% 매치율이었던 이유 진단 + 3중 픽스). 원인: (1) 카메라 raw 프레임 (보통 16:9) 을 그대로 32×32 로 resize 해서 해싱. 카탈로그는 카드 aspect (3:4 ≈ 0.716) 이라 두 입력이 완전히 다르게 왜곡됨 → DCT 낮은주파수 겹칠 리 없음. (2) Canvas 기본 resize 가 bilinear-low 라 1280×720 → 32×32 극단 축소에서 aliasing 심함. PIL Lanczos 랑 어긋남. (3) match threshold 18 이 너무 타이트. 픽스: (A) computeCardCrop() 로 비디오 정중앙에서 3:4 aspect 로 crop 하고 6% 안쪽으로 인셋 (align 브래킷 안쪽) → 배경 / 손 / 여백 다 제외, (B) imageSmoothingQuality: 'high' 로 downscale 품질 개선 → Lanczos-스러운 필터, (C) threshold 18 → 22 로 완화. 이 세 개로 실전 정확도 크게 오를 것.",
    en: "Bulk scan accuracy overhaul (diagnosed why the first release matched ~0 % of cards + shipped a three-part fix). Root causes: (1) I was hashing the whole raw camera frame — typically 16:9 — while the catalog images are 3:4 (~0.716), so the 32×32 downscale warped the two inputs completely differently and the DCT low-frequency bins never lined up. (2) Canvas defaults to bilinear-low, which aliases badly on extreme downscales like 1280×720 → 32×32 and drifts from PIL's Lanczos that seeded the catalog hashes. (3) The match threshold of 18 was too tight for camera-vs-render noise. Fix: (A) computeCardCrop() picks the largest centered 3:4 rectangle in the video source and pulls in 6 % on each side — background, hand and rounded viewfinder rim drop out of the hash. (B) Canvas smoothingQuality forced to 'high' — closest thing to Lanczos the browser offers. (C) Threshold bumped to 22. Should turn real-world hit rate from ~0 % into something usable; will keep tuning based on live testing.",
  },
  {
    date: "2026-07-19",
    emoji: "🇰🇷",
    kr: "KR 세트 로고 **100% 커버리지** 달성 — 이전 pokemonstore.co.kr 스크레이핑으로 최근 SV/MEGA 56개 세트 로고 확보한 상태였는데, 남은 143개 (SM/S/BW/XY-era, pokemonstore 재고 없는 것들) 를 Naver 이미지 검색 Playwright 스크레이퍼로 일괄 회수. Naver 는 Google 대비 봇 감지 관대하고 한글 콘텐츠 최적이라 143/143 = 100% 매칭. Naver 이미지 프록시 `search.pstatic.net/common/?src=...` 로 감싼 결과 URL 을 decode 해서 원본 (Naver 스마트스토어 셀러 이미지 shop1.phinf.naver.net / 블로그 첨부 blogfiles.naver.net / Coupang thumbnail 등) 저장. N페이 프로모 배너 (항상 첫 결과 위치) 는 자동 skip. 최종 220/220 = 100% (naver 116 + pokemonstore 58 + 기타 23 + namuwiki 13 + collectory 6 + coupang 4). 이제 /sets?region=ko 열면 모든 세트에 실제 팩 사진 이미지 뜸. 다음 단계: 안정성 확보 위해 Cloudflare R2 로 이미지 자체 미러링 (원본 CDN 죽어도 우리 CDN 은 유지 — pokemonkorea.co.kr 도메인이 최근 410 gone 됐던 것 같은 재발 방지).",
    en: "KR set logos hit **100% coverage** — the earlier pokemonstore.co.kr scrape covered 56 recent SV/MEGA-era sets, and today's Naver Image Search Playwright scraper closed the remaining 143 (SM / S / BW / XY-era sets that Pokemon Korea's store no longer carries). Naver has softer bot detection than Google and is Korean-content-first, which produced a 143/143 = 100% match rate. Extractor decodes Naver's proxy wrapper `search.pstatic.net/common/?src=<encoded>` so we store the underlying image URL (Naver Smart Store seller photos on shop1.phinf.naver.net / blog attachments on blogfiles.naver.net / Coupang thumbnails / etc.) rather than the proxy redirect that could 403 later. The N페이 promo banner that always occupies slot 0 gets skipped automatically. Final source split across the 220 KR sets: naver 116 + pokemonstore 58 + other 23 + namuwiki 13 + collectory 6 + coupang 4. Every set tile in /sets?region=ko now shows a real pack photo. Next: mirror all these images to Cloudflare R2 so our catalog survives any single source CDN going 410 (as pokemonkorea.co.kr recently did).",
  },
  {
    date: "2026-07-19",
    emoji: "📦",
    kr: "실드 (Sealed) 컬렉션 편집 기능 대폭 확장 — 이제 부스터 박스 / ETB / 번들 등에 상태 (Sealed / Opened / Damaged), 구매가, 획득 소스, 획득일, 메모까지 카드 컬렉션이랑 똑같은 정도로 기록 가능. 개별 타일 hover 하면 편집 (연필) · 가격 히스토리 (그래프) · 삭제 3개 액션 나옴. 편집 모달에서 구매가 입력하면 실시간 P/L (수량 × 단가 vs 시세) 표시돼서 실드 상품이 얼마나 오르내렸는지 즉시 확인. 그레이딩은 실드 상품에 개념이 아니라 뺐고 (박스는 감정 안 함) 조건도 sealed/opened/damaged 3버킷으로 딱 필요한 만큼만 (더 세분화하면 주관적 등급 매기기 되니까 의도적으로 coarse).",
    en: "Sealed collection now tracks the same ROI metadata as singles — condition (sealed / opened / damaged), purchase price, source (bought / traded / gift), acquired date, notes. Hover any owned tile for a 3-button action rail: edit (pencil), price chart (opens the product detail chart), remove (trash). The edit modal runs a live P/L calc (qty × unit price vs market × qty) so you see immediately whether a box is up or down. Grading is deliberately excluded (boxes don't get slabs) and condition is intentionally coarse (3 buckets, not shelfwear-vs-mint-sealed grading) — any finer split would demand an authority nobody publishes for sealed.",
  },
  {
    date: "2026-07-19",
    emoji: "🗂️",
    kr: "포트폴리오 화면 상단 미리보기를 카드 / 실드 반반으로 나눔 — 이전엔 Top 10 카드가 오른쪽 컬럼 전체 (~1000px) 를 다 먹어서 실드 상품 소유자는 자기 박스/ETB 를 히어로 어디에서도 못 봤음. 이제 좌우 5-across × 2 행 그리드 두 개, 왼쪽 = 카드 Top 10, 오른쪽 = 실드 Top 10 (line value = market × qty 기준이라 ×2 ETB 는 ×1 두 개보다 위). xl (≥1280px) 에선 좌우, 그 이하 뷰포트에선 세로 스택. 그리고 카드 콜렉션 페이지의 'Vault by set' 섹션 — 20+ 카드 세트는 기본 접힘 + 헤더 클릭으로 아코디언 확장. 마스터 셋 완주해서 500장 있는 유저 등이 페이지 무한 스크롤 지옥 겪던 것 해결. 상단 'Expand all / Collapse all' 배지로 일괄 토글.",
    en: "Portfolio landing page split the top preview panel 50/50 between cards and sealed. Previously Top-10 cards ate the entire ~1000px right column and sealed owners never saw their boxes/ETBs in the hero at all. Now: 5-across × 2-row grid on both sides — left is Top 10 cards, right is Top 10 sealed ranked by line value (market × qty so a ×2 ETB ranks above a ×1 of the same box). Stacks vertically below xl (1280px). Additionally, the Vault-by-set section on the same page now folds each set independently: sets with more than 20 owned items start collapsed with a chevron + count + set total (users owning a completed Master Set were scrolling through 500 tiles); an 'Expand all / Collapse all' pill row handles bulk toggle.",
  },
  {
    date: "2026-07-19",
    emoji: "💎",
    kr: "새 페이지 /trending/grading — 카드가 그레이드 슬랩으로 얼마짜리가 되는지 (프리미엄) 랭킹. 예: raw $109 카드가 PSA 10 슬랩으로 $85,000 = ×775 배. 등급 (PSA 10 / CGC 10 / BGS 10 / BGS 10 BL / TAG 10) + 언어 (전체 / EN / JP) + Sold-only 토글 (기본 ON, 어이없는 asking $999,999 앵커 가격 필터링). 데이터 이상값 방지 위해 multiplier 300× 상한 + 최소 2 sale 필터. 카드 상세 페이지의 Graded Prices 그리드도 이 김에 리팩터 — 10 등급 티어들 (PSA 10 / CGC 10 / BGS 10 / BGS 10 BL / TAG 10) 만 첫 열에 노출, 9/9.5 등 하위 등급들은 'Show lower grades' 토글로 접힘. 그리드 4-col → 5-col 로 딱 맞게 채워짐.",
    en: "New page /trending/grading — ranks cards by their graded-slab premium (tier price ÷ raw market). Example: a raw $109 card becomes an $85,000 PSA 10 slab = ×775. Filter chips for tier (PSA 10 / CGC 10 / BGS 10 / BGS 10 BL / TAG 10), language (All / EN / JP), and a Sold-only toggle (default ON so vintage-seller anchor listings at $999,999 don't spike the top). Guardrails: 300× multiplier ceiling to gate outliers, minimum 2 sold samples so single-listing medians don't dominate. Card-detail Graded Prices grid also polished — the five grade-10 tiers (PSA 10 / CGC 10 / BGS 10 / BGS 10 BL / TAG 10) now sit in a clean 5-across row; lower grades (9 / 9.5) fold behind a 'Show lower grades' toggle so the primary row reads at a glance.",
  },
  {
    date: "2026-07-19",
    emoji: "🇰🇷",
    kr: "KR 세트 로고 대량 백필 — 브라우저에서 KR 세트 열면 대부분 텍스트 fallback (로고 이미지 없음) 이던 문제 해결. 죽은 pokemonkorea.co.kr URL 15개 우선 nuke (도메인 410 gone 상태로 유저 브라우저에 broken image 뜨던 것) → pokemonstore.co.kr (KR 공식 스토어, NHN Commerce ShopBy) 카테고리 페이지 Playwright 스크레이핑 → 상품 상세 페이지 title + og:image 뽑아서 세트명 fuzzy 매칭 (SequenceMatcher, threshold 0.70). 액세서리 (덱 케이스 / 카드 실드 / 플레이매트 / 리필 / 슬리브 등 12종 토큰) 는 자동 skip. 확장팩 카테고리 248 상품 처리 → 액세서리 141개 skip / 매칭 55 성공 / no_match 49. 최종 결과: pokemonstore 소스로 KR 세트 56개 로고 확보. 남은 146개 (옛날 SM/S/BW/XY-era 재고 없는 세트들) 는 다음 phase.",
    en: "Bulk KR set logo backfill — most KR set browser tiles previously fell through to the text-only fallback because logo_url was NULL. Two-part fix. (1) Nuked 15 dead pokemonkorea.co.kr URLs — that domain went 410 gone and the URLs were serving broken images in user browsers. (2) Playwright scraper against pokemonstore.co.kr (Pokemon Korea's official store, NHN Commerce ShopBy): loads each category with pageSize=500 in one shot (248 products in 확장팩), visits every product-detail page, extracts document.title + og:image, then fuzzy-matches the Korean title against sets.name (SequenceMatcher, ≥0.70). Accessory products (12 token blocklist: 덱 케이스, 카드 실드, 플레이매트, 리필, 슬리브, 데미지 카운터, etc.) are skipped so a deck case's photo doesn't overwrite the actual set's logo. Run summary: 141 accessories skipped, 55 sets matched + written, 49 no confident match, 2 rendering misses. Also normalized protocol-relative `//shopby-images…` URLs to `https://…` so Next/Image renders them. Net: 56 KR sets now carry a proper logo (was ~15 dead + a few collectory). 146 sets still without a logo — mostly SM/S/BW/XY-era that pokemonstore no longer stocks.",
  },
  {
    date: "2026-07-19",
    emoji: "🐞",
    kr: "Bulk 모드 스캔 무한 로딩 리그레션 픽스 두 개. (1) 백엔드 라우팅 충돌: /api/v1/cards/phash-catalog 이 기존 /cards/{card_id} 캐치올에 잡혀서 항상 404 'Card not found' 로 떨어짐 — 'phash-catalog' 을 card_id 로 해석. pHash 엔드포인트를 별도 sub-router 로 옮겨서 /api/v1/scan/phash-catalog + /api/v1/scan/phash-catalog/stats 로 이동. (2) 프론트 useEffect 재시도 루프: 카탈로그 fetch 실패 → catalogLoading 이 true→false 로 돌면서 effect 재실행 → guard 통과 (catalog 여전히 null) → 재fetch → 무한 loading↔error 사이클. Guard 에 catalogError 조건 추가해서 실패하면 자동 재시도 안 함. 에러 배너에 명시적 Retry 버튼 추가.",
    en: "Bulk scan infinite-loading regression — two fixes. (1) Backend route conflict: /api/v1/cards/phash-catalog was being intercepted by the existing /cards/{card_id} catch-all — FastAPI parsed 'phash-catalog' as a card_id and returned 404 'Card not found' before the pHash handler ran. Moved both pHash endpoints onto a dedicated sub-router so they now live at /api/v1/scan/phash-catalog and /api/v1/scan/phash-catalog/stats, clear of the cards catch-all. (2) Frontend useEffect retry loop: a failed fetch flipped catalogLoading true→false, which changed the effect's deps and re-armed the fetch (catalog was still null, guard passed), so the panel thrashed in a loading ↔ error cycle. Added catalogError to the guard so a failed fetch stays failed until the user retries, and surfaced an explicit Retry button in the error banner.",
  },
  {
    date: "2026-07-19",
    emoji: "📸",
    kr: "스캔 화면에 Bulk 모드 추가 (Phase 2). 카메라 상단 [Single | Bulk] 토글로 전환. Bulk 모드는 셔터 없음 — 카드를 프레임에 대면 500ms 마다 자동으로 뷰파인더 프레임 pHash 계산 → 43k 카탈로그 해시랑 hamming distance 매칭 → 카드 인식되면 이름 / 가격 / 스캔 확신도랑 함께 [+ Add] 배너 뜸. 유저가 Add 누르면 컬렉션에 default (variant=normal / condition=NM / qty=1) 로 즉시 저장 + 하단 세션 리스트에 썸네일 쌓임. Skip 누르면 6초 동안 같은 카드 재감지 안 함 (같은 카드 안 치웠을 때 오탐 방지). Claude Vision API 호출 0회 — 매칭이 브라우저 안에서 끝나서 벌크 세션 비용 $0. 정확도는 Claude 보다 약간 낮음 (약 85-90% vs 95%) — 홀로 / 각도 심한 카드는 놓칠 수 있음. 벌크 정리 워크플로에 최적. 인프라: /api/v1/cards/phash-catalog 엔드포인트 (약 500KB gzipped, HTTP 캐시), lib/phash.ts 클라이언트 매처 (32×32 DCT-II, 64-bit hex 해시, popcount 기반 hamming). ⚠️ 실사용 전에 관리자 GH Actions 로 backfill-card-phashes 워크플로 한 번 실행해서 catalog 채워야 함.",
    en: "Scan screen — Bulk mode shipped (Phase 2). New [Single | Bulk] toggle in the camera header. Bulk mode drops the shutter — the app auto-hashes the viewfinder frame every 500 ms and does a nearest-neighbour lookup against the 43 k card pHash catalog. When a match is found, a floating [+ Add] banner surfaces with the card's name / price / match distance. Tapping Add pushes the row into the user's collection with sensible defaults (variant=normal / condition=NM / qty=1) and thumbnails stack up in a session strip below the viewfinder. Skip suppresses re-detection of the same card for 6 s so a card left in frame doesn't spam-fire. Zero Claude vision calls per detection — the match runs entirely in-browser, so a hundred-card bulk sort is $0 in API cost (vs ~$0.30 for the per-shot Claude flow). Accuracy is a touch lower than Claude (roughly 85-90 % vs 95 %+) — heavy foils and sharp angles can slip past; falls back to plain single-shot mode any time. Infra: /api/v1/cards/phash-catalog endpoint (~500 KB gzipped, browser-cached), lib/phash.ts client matcher (32×32 DCT-II, 64-bit hex hash, popcount-based hamming search). ⚠️ Requires the admin to trigger the backfill-card-phashes GH Actions workflow once to populate cards.image_phash before bulk mode has anything to match against.",
  },
  {
    date: "2026-07-19",
    emoji: "🚑",
    kr: "PC 웹에서 스크롤이 멈춰있던 리그레션 긴급 픽스. 원인: 가로 밀림 방지용으로 html + body 둘 다에 overflow-x: hidden 을 걸어놨는데, 데스크탑 브라우저 (특히 크롬) 가 두 개를 다 스크롤 컨테이너로 인식하면서 어느 게 primary root scroller 인지 헷갈려함 → wheel + 스크롤바가 반응 안함. overflow-x: clip 으로 교체. clip 은 오버플로를 시각적으로 자르기만 하고 스크롤 컨테이너를 만들지 않아서 root scroller 는 그대로 window 로 유지됨. 가로 밀림 안전망은 그대로 유효.",
    en: "Emergency fix: desktop web scrolling stopped working after the earlier horizontal-shift patch. Root cause: we set overflow-x: hidden on both html and body as a safety net, which promotes both to scroll containers — Chrome (and other desktop browsers) then get confused about which one is the primary root scroller, so the wheel and scrollbar stopped responding. Switched both to overflow-x: clip, which clips overflow visually without creating a scroll container. The window remains the true root scroller, and the horizontal-shift safety net still holds.",
  },
  {
    date: "2026-07-19",
    emoji: "🛠️",
    kr: "관리자 페이지 mobile 폴리시 3종. (1) /admin/news 포스트 행 액션 버튼 (Publish/Hide/Unhide/View/Edit/Delete) — 모바일에선 텍스트 라벨 숨기고 아이콘만 보이게 (title 툴팁 유지). 6개 버튼이 우측에 쌓여있어서 포스트 타이틀이 15자로 잘리던 걸 완화 — 이제 타이틀 컬럼이 훨씬 여유. (2) /admin/news 헤더 — flex-wrap 추가하고 'New post' 링크에 shrink-0 붙여서 좁은 폭에서 자연스러운 wrap. (3) /admin/visits 'Per-user visits' 테이블 — 외부 wrapper 가 overflow-hidden 이라 내용이 뷰포트 초과해도 잘렸음. 다른 두 테이블처럼 안쪽에 overflow-x-auto div 추가해서 가로 스크롤. (4) /admin/reports 스코프 (Card/Set) + 상태 (Open/Resolved/Won't fix/All) 탭 — 두 pill 그룹이 나란히 있었는데 좁은 폭에서 안전하게 wrap 되도록 상위 flex-wrap 컨테이너로 묶음.",
    en: "Admin pages — three mobile polish passes. (1) /admin/news post-row action buttons (Publish/Hide/Unhide/View/Edit/Delete) collapse to icon-only on mobile with the text label wrapped in hidden sm:inline; title tooltips carry the copy on hover. Frees a ton of room in the title column — before, the six buttons ate the row and truncated post titles at ~15 chars. (2) /admin/news header now has flex-wrap and 'New post' has shrink-0 so it wraps below the description on narrow screens instead of squeezing sideways. (3) /admin/visits 'Per-user visits' table sat inside an overflow-hidden card wrapper (no horizontal scroll), so any oversize row got clipped. Added an inner overflow-x-auto div mirroring the pattern the anon-sessions and recent-activity tables already use. (4) /admin/reports scope pills (Card/Set reports) and status pills (Open / Resolved / Won't fix / All) were siblings pinned side-by-side — wrapped them in a flex-wrap parent so on narrow widths the status group drops to the next row instead of pushing past the viewport.",
  },
  {
    date: "2026-07-19",
    emoji: "🧩",
    kr: "마스터세트 상세 페이지 (예: Perfect Order) 헤더가 모바일에서 완전히 무너져있던 문제 수정. 원인: 헤더 flex 컨테이너가 flex-wrap 인데 타이틀 컬럼이 min-w-0 flex-1 이라 무한 shrink 가능 → 옆에 붙은 Share + Browse full set 버튼이 자리 차지하면 타이틀 컬럼이 60px 로 쪼그라들고 'Perfect Order' 가 두 줄, 메타데이터 (2026-03-27 · Base 0/124 · Master 0/124) 는 토큰 하나씩 6줄로 wrap. 버튼 그룹에 w-full md:w-auto 붙여서 모바일에선 무조건 다음 줄로 wrap → 타이틀 컬럼 full width 회복. 데스크탑은 그대로 옆에 나란히.",
    en: "Fixed: the master-set detail page (e.g. Perfect Order) header was totally broken on mobile. Root cause: the header flex container was flex-wrap but the title column had min-w-0 flex-1, so it could shrink indefinitely — with the Share + Browse-full-set button group beside it eating the row, the title column collapsed to ~60px and the h1 wrapped mid-title ('Perfect' / 'Order'), while the metadata ('2026-03-27 · Base 0/124 · Master 0/124') wrapped one token per line down six rows. Added w-full md:w-auto on the button group so on mobile it wraps onto its own row, giving the title column the full width back. Desktop layout unchanged.",
  },
  {
    date: "2026-07-19",
    emoji: "↔️",
    kr: "모바일에서 페이지 전체가 손가락 스와이프로 좌우 밀리던 문제 수정. 원인: 뷰포트보다 넓은 자식 요소가 있으면 body 가 가로 스크롤 가능해지고, 세로 스크롤 각도 삐끗하면 페이지 전체가 밀림. 3단 처방: (A) globals.css 에 html + body { overflow-x: hidden } 안전망. 오버플로 나도 문서 자체는 안 밀림. (B) Portfolio 액션 버튼 열 (Manage / Export CSV / Share / Scan a card) — 이너 래퍼가 shrink-0 라 flex-wrap 이 안 걸렸음. shrink-0 제거해서 좁은 화면에선 자동 줄바꿈. (C) 관리자 서브네비 (News / Users / Reports / Visits / Updates) — 5개 탭이 mobile 폭 초과. 컨테이너에 overflow-x-auto + 아이템에 shrink-0 붙여서 안쪽만 가로 스크롤, 스크롤바는 숨김.",
    en: "Fixed: on mobile the whole page slid sideways under a finger swipe. Root cause: a single child wider than the viewport lets body scroll horizontally, and any vertical-scroll angle that isn't perfectly vertical then shifts every page element. Three-part fix: (A) globals.css sets overflow-x: hidden on html + body as a safety net so no future oversized element can hijack document scroll. (B) Portfolio action row (Manage / Export CSV / Share / Scan a card) — the inner wrapper was shrink-0, which defeated its own flex-wrap; dropped shrink-0 so the buttons wrap onto a second row on narrow screens. (C) Admin sub-nav (News / Users / Reports / Visits / Updates) — five tabs busted the mobile width; put overflow-x-auto on the nav (with edge-to-edge -mx-4 px-4 so it scrolls flush with the page gutter) and shrink-0 on each item; scrollbar hidden.",
  },
  {
    date: "2026-07-19",
    emoji: "🎯",
    kr: "스캔 화면이 손가락 드래그로 위 아래 흔들리던 이슈 수정. 원인 두 가지: (1) iOS Safari 러버밴드 바운스가 사이트 전체에 살아있었음 → globals.css 에 overscroll-behavior: none 적용해서 앱 셸 느낌으로 통일 (PWA 대응). (2) ScanCamera / ScanConfirm 아웃터가 min-h-100dvh 라 콘텐츠 조금만 넘쳐도 페이지 자체가 스크롤 됐음 → fixed inset-0 로 뷰포트에 완전 고정하고, 콘텐츠 넘칠 땐 main 안에서만 스크롤 (overscroll-contain 으로 바운스 격리). 이제 카메라 화면은 안 밀림, confirm 화면은 폼이 길어도 헤더/푸터 고정된 채 안쪽만 움직임.",
    en: "Fixed: the scan screen shifting under finger drag. Two root causes stacked: (1) iOS Safari rubber-band bounce was site-wide → globals.css now sets overscroll-behavior: none for an app-shell feel (also closes the PWA polish item from earlier). (2) ScanCamera / ScanConfirm outer containers used min-h-[100dvh], so any content overflow made the whole page scroll → outers now use fixed inset-0 pinned to viewport, and if content overflows it scrolls inside main only (overscroll-contain traps the bounce). Camera screen no longer shifts, and the long confirm form scrolls internally while the header + footer stay locked.",
  },
  {
    date: "2026-07-19",
    emoji: "🗂️",
    kr: "KR 세트 분류 대청소 — 브라우저에서 (1) 같은 이름 세트가 두세 개씩 뜨는데 클릭하면 카드는 하나에만 있고 다른 하나는 텅 빈 문제, (2) 시리즈 chip 이 '검과 방패' 와 'Sword & Shield' 처럼 같은 시대인데 두 이름으로 갈라져 보이는 문제, (3) 세트가 MAIN / DECK 로 그룹핑 안 되고 flat 하게 쌓이는 문제 한번에 정리. (A) '트리플렛비트' 로 잘못 붙어있던 빈 CS* 스텁 14개 삭제, (B) TCGdex 판 + collectory 재판이 겹쳐 이중으로 있던 SM 계열 9쌍 (풀메탈월 / 챔피언로드 / 더블블레이즈 / 얼터제네시스 / 알로라 달빛&햇빛 / 플라스마 스파크 / 창공의 카리스마 / GG엔드) 을 canonical ko-SM* 로 병합 (중복 카드 764장 정리, 유니크 1장 이동, ko-c-* 9행 삭제), (C) 시리즈 이름을 '검과 방패 (Sword & Shield)' 처럼 한/영 병기로 통일 (193개 rename), (D) set_type 이 전부 NULL 이던 220개 KR 세트에 MAIN (193) / DECK (27) 자동 분류. 이제 /sets?region=ko 열면 시리즈 chip 도 깔끔하고 스타터/트레이너 박스는 하단 デッキ商品 섹션으로 자동 이동.",
    en: "KR set classification cleanup — three-in-one fix for the browser mess: (1) same-name sets appearing twice with cards only in one, (2) series chips fracturing the same era across '검과 방패' vs 'Sword & Shield', (3) set_type being NULL on every KR row so MAIN / DECK grouping never kicked in. (A) Deleted 14 empty CS* stubs mis-tagged 트리플렛비트, (B) merged 9 SM-era dup pairs where the collectory --include-new-sets pass created a ko-c-* twin of an already-existing TCGdex row (풀메탈월 / 챔피언로드 / 더블블레이즈 / 얼터제네시스 / 알로라 달빛&햇빛 / 플라스마 스파크 / 창공의 카리스마 / GG엔드) — moved 1 unique card into the canonical ko-SM* slot, skipped 764 dup card rows, dropped 9 ko-c-* rows, (C) canonicalized series to bilingual 'Korean (English)' format across 193 rows (검과 방패 (Sword & Shield) / 스칼렛・바이올렛 (Scarlet & Violet) etc.), (D) populated set_type on all 220 remaining KR sets (193 MAIN + 27 DECK) via the same Korean name-pattern classifier the JP catalog uses ('스타터 덱' / '덱 빌드 BOX' / '프리미엄 트레이너 박스' → DECK). /sets?region=ko now groups starter decks + trainer boxes into the bottom デッキ商品 section like the JP tab does.",
  },
  {
    date: "2026-07-19",
    emoji: "🐛",
    kr: "스캔 화면에서 상단 컨트롤 (뒤로가기 / PullList pill / 플래시) 이 iOS 다이내믹아일랜드에 겹치던 버그 수정. ScanCamera + ScanConfirm 헤더에 safe-area-inset-top 반영, 하단 셔터 / 추가 버튼도 홈 인디케이터에 안 눌리게 safe-area-inset-bottom 적용. 함께 발견: 저번 턴 body 에 무조건 pb-4.5rem 걸어놓은 게 스캔 페이지처럼 자체 100dvh 잡는 화면에서 오버플로 유발. Bottom nav 안 뜨는 페이지에선 여백도 필요없어야 하니 spacer 를 BottomTabNav 안으로 옮김 (같은 hide 조건 공유).",
    en: "Fixed: on the scan screen, the top controls (back / PullList pill / flash) overlapped iOS Dynamic Island. Added safe-area-inset-top to the ScanCamera + ScanConfirm headers, and safe-area-inset-bottom to the shutter / add-to-collection footers so the home indicator no longer crowds them. Also caught a regression from the previous turn — body carried an unconditional pb-4.5rem which caused pages with their own 100dvh container (scan) to overflow. Moved the spacer into BottomTabNav itself so it shares the nav's hide list; pages that hide the nav no longer inherit dead padding.",
  },
  {
    date: "2026-07-19",
    emoji: "🧹",
    kr: "KR 카탈로그 정리 — 이전 대량 import (collectory) 가 CN/US/JP 세트도 KR 로 잘못 넣어서 브라우저에 태晶盛聚 (中), Chaos Rising (US), Battle Academy (CN) 같은 게 섞여있던 문제 수정. 각 세트 카드 이미지 CDN 경로로 지역 판정 (majority vote) 후: CN 128 세트 (12,890 카드) → CN 카탈로그로 이동, US 99 + JP 28 + scrydex 4 = 131 세트 (7,750 카드) → 삭제 (이미 EN/JP 카탈로그에 있음), KR 147 유지. 결과: KR 세트 502 → 243, CN 세트 56 → 184, EN 187 완전 미변경 (safeguard 유지). 이제 /sets?region=ko 에는 한국 발매판만.",
    en: "KR catalog cleanup — a prior bulk import (collectory --include-new-sets) pulled every un-matched set into KR regardless of actual locale, so 太晶盛聚 (CN), Chaos Rising (US), Battle Academy (CN) etc. all appeared as Korean sets in the browser. Classified each ko-c-* set by the CDN prefix of its cards' image URLs (majority vote): CN 128 sets / 12,890 cards → moved to CN region, US 99 + JP 28 + scrydex 4 = 131 sets / 7,750 cards → deleted (already covered by EN/JP catalogs), KR 147 kept. Net: KR sets 502 → 243, CN sets 56 → 184, EN 187 rows completely untouched (script safeguard enforced). /sets?region=ko now shows only Korean releases.",
  },
  {
    date: "2026-07-19",
    emoji: "📱",
    kr: "모바일 하단 탭 네비 신설 — 화면 하단에 고정된 5개 탭 (Sets / Portfolio / Scan / Wishlist / Me) 이 모든 모바일 화면에 뜸. Scan 은 가운데 강조된 노란 원형 CTA 로 승격 (기존 우측 하단 ScanFAB 완전히 대체). 아이콘은 lucide-react. 로그아웃 상태에선 Me 탭이 'Sign in' 으로 바뀜. 몰입형 스캔 카메라 (`/scan`), auth (`/login`, `/signup`), 자체 하단 CTA 있는 카드 상세 (`/cards/[id]`) 에선 자동 숨김. 데스크탑 (md+) 에선 안 뜸. body min-h 에 safe-area 반영한 하단 여백 추가해서 콘텐츠 안 가려짐.",
    en: "Mobile bottom tab bar shipped — five fixed tabs on every mobile screen (Sets / Portfolio / Scan / Wishlist / Me). Scan lives as the elevated yellow FAB in the center slot and fully replaces the old bottom-right ScanFAB. Icons from lucide-react. Logged-out users see the last tab as 'Sign in' instead of 'Me'. Auto-hidden on the immersive scan camera (/scan), auth pages (/login, /signup), and the card detail page (/cards/[id]) which has its own sticky buy CTA. Desktop (md+) is unchanged. Body padding-bottom respects safe-area so no page content sits behind the bar.",
  },
  {
    date: "2026-07-19",
    emoji: "📱",
    kr: "iOS 노치 / 다이나믹아일랜드 / 홈 인디케이터 safe-area 지원 — PWA standalone 모드에서 상단 nav 가 노치 뒤로 밀리거나 하단 스캔 FAB / 쿠키 배너가 홈 인디케이터에 겹치던 문제 수정. viewport-fit: cover 로 콘텐츠가 노치 밑까지 뻗도록 하고, 모든 sticky / fixed 요소 (TopNav, ScanFAB, CookieBanner, Footer) 에 env(safe-area-inset-*) 패딩 적용. 랜드스케이프 좌우 노치 컷도 대응. body min-height 를 100dvh 로 바꿔서 iOS Safari 주소창 등장 / 사라짐 layout jank 완화. 모바일 UX 개편 1단계 (다음: 하단 탭 네비 / 관리자 페이지 mobile 대응).",
    en: "iOS notch / dynamic island / home-indicator safe-area support — in standalone PWA the sticky top nav slid under the notch and the scan FAB + cookie banner overlapped the home indicator. Added viewport-fit: cover so content extends behind system UI, and every sticky / fixed element (TopNav, ScanFAB, CookieBanner, Footer) now pads with env(safe-area-inset-*). Landscape notch cut-outs handled too. Body min-height switched to 100dvh to reduce iOS Safari's URL-bar show/hide layout jank. Phase 1 of a mobile UX pass — bottom tab nav and mobile-friendly admin pages coming next.",
  },
  {
    date: "2026-07-19",
    emoji: "🇰🇷",
    kr: "한국판 (KR) 카탈로그 정식 오픈 — 세트 페이지 상단 리전 탭에 🇰🇷 Korea + 🇨🇳 China 신규 추가. TCGdex 로 KR 세트 91개 (SV6 변환의 가면 / SV5a 크림슨헤이즈 / SV4M 미래의 일섬 등) + CN 세트 56개 (太晶盛聚 / 星彩晶璃 등) landing. KR 카드는 TCGdex 가 세트 메타만 있고 카드 arrays 비어있어서 collectory.cc (한국 팬 아카이브) 로 카드 8,475장 fill — 99% 한국 스캔 이미지 (cdn.collectory.cc) 사용. 76/91 KR 세트 카드 커버 (나머지 15세트는 collectory 에도 없는 옛날 promo). URL 은 JP 와 코드 충돌 방지 위해 KR 은 ko- 접두어 (예: /sets/ko-SV6), CN 은 zhcn- 접두어 사용. 가격 시세는 KR/CN 아직 미지원 (별도 phase 예정).",
    en: "Korean (KR) catalog officially open — set page's region tab bar adds 🇰🇷 Korea and 🇨🇳 China alongside USA / Japan. TCGdex ingest landed 91 KR sets (SV6 변환의 가면 / SV5a 크림슨헤이즈 / SV4M 미래의 일섬 etc.) + 56 CN Simplified sets (太晶盛聚 / 星彩晶璃 etc.). TCGdex only carried set metadata for KR (empty cards arrays), so a second pass via collectory.cc (a Korean fan archive) filled 8,475 KR card rows with 99% native Korean scans on cdn.collectory.cc. 76 of 91 KR sets fully populated — the remaining 15 are legacy promos collectory doesn't index either. To avoid PK collision with JP (TCGdex uses the same set/card ids across all locales), KR ids get a `ko-` prefix (e.g. /sets/ko-SV6) and CN gets `zhcn-`. KR/CN pricing not yet wired — separate phase later.",
  },
  {
    date: "2026-07-19",
    emoji: "🎯",
    kr: "세트 페이지와 카드 상세 페이지의 가격 표시 통일 — 카드 상세는 TCGplayer + eBay median 을 절반씩 섞은 컨센서스 (예: $75.65) 를 보여주는데, 세트 페이지 카드 타일은 TCG 원본 값 ($81.80) 만 보여줘서 유저가 '세트페이지 가격은 업데이트가 안된다' 고 오해했음. Refresh 엔드포인트 3곳 + 매일 밤 TCGCSV sync 다 컨센서스 저장하도록 수정. 5,673 장 카탈로그 한 번에 재계산해서 즉시 반영. 이제 두 화면 값 일치.",
    en: "Set-page and card-detail pages now show the SAME price — card detail computed a consensus (TCG + eBay)/2 client-side (e.g. $75.65) while set-page tiles read raw TCG from the DB ($81.80). Users read the mismatch as 'the set page never updates.' Fixed at three writers (unified Refresh, legacy Refresh, nightly TCGCSV sync) so the persisted headline market_price_usd is the consensus itself, and ran a one-shot backfill against prod that reblended 5,673 catalog rows in 55 seconds. Both views now agree on the same number.",
  },
  {
    date: "2026-07-19",
    emoji: "📊",
    kr: "eBay graded 스크레이퍼 BGS/TAG 커버리지 개선 (Round 5 검증 완료) — Round 4 에서 BGS 10 write rate 가 4.8% 로 낮았음 (PSA 10 은 37.5%). eBay 가 'BGS 10 Beckett Black Label' 처럼 특수 쿼리에는 검색어를 조용히 완화해서 무관 아이템 반환하는게 원인. 3가지 픽스 조합: (B) BGS/TAG 티어 MIN=1 + 재시도 3회, (C) BGS 시노님 fallback — 'BGS' 대신 'Beckett' 로 2차 쿼리 시도 (셀러들이 둘 다 씀), (D) URL 정렬을 '가장 최근 판매' 로 변경. Round 5 결과: BGS 10 → 10.6% (**2.2x 개선**), TAG 10 → 15.6% (1.5x), PSA 10 → 47.7% (+10pp). 등급별 시세는 여전히 분리 저장 (LO 요구사항: '슬랩은 등급별 가격이 진짜 중요함').",
    en: "eBay graded scraper — BGS/TAG recall lift (verified in Round 5). Round 4 wrote only 4.8% on BGS 10 (vs 37.5% on PSA 10). Root cause: eBay silently relaxes narrow queries like 'BGS 10 Beckett Black Label' on datacenter IPs and returns trending Pokemon items. Three-part fix: (B) MIN=1 + max_attempts=3 across all BGS/TAG tiers, (C) Beckett synonym fallback pass — sellers list slabs as either 'BGS 10' or 'Beckett 10', so a second pass with the swap catches the other half; classify_grade routes both into the same bgs* buckets so grade purity survives, (D) sort URL by ended-time ascending so freshest sales land on page 1. Round 5 results: BGS 10 → 10.6% (**2.2x lift**), TAG 10 → 15.6% (1.5x), PSA 10 → 47.7% (+10pp thanks to the sort change alone). Per-grade prices still stored separately per LO's constraint that slab prices per grade are the important part.",
  },
  // ── 2026-07-16 ─────────────────────────────────────────────────
  {
    date: "2026-07-16",
    emoji: "🎁",
    kr: "sv09 Journey Together / sv10 Destined Rivals Sealed 탭에 Triple Whammy Tin 3종 (Tyranitar / Darkrai / Slaking) 추가. 이 상품은 TCGCSV 에서 특정 세트 소속이 아니라 'Miscellaneous Cards & Products' 그룹에 있어서 기존 세트별 sealed 인제스트가 놓쳤음. 두 세트 다 미러 배치 — sv09 canonical / sv10 mirror. 실제 마켓 $23-25 반영. 30주년 Pokemon Center ETB 도 별도 SKU 로 추가 (일반 ETB 와 이미지 공유, TCGCSV 미추적이라 수동 seed).",
    en: "Added the 3 Triple Whammy Tin variants (Tyranitar / Darkrai / Slaking) to both sv09 Journey Together and sv10 Destined Rivals sealed tabs — TCGCSV files these under 'Miscellaneous Cards & Products' rather than either set, so the per-set sealed ingest was skipping them. Mirrored across both sets (sv09 canonical, sv10 mirror) with real TCGCSV market prices ($23-25). Also added the 30th Celebration Pokemon Center ETB as a separate SKU sharing the regular ETB's image — TCGCSV doesn't track the PC exclusive variant so the row is synthetic.",
  },
  {
    date: "2026-07-16",
    emoji: "🎯",
    kr: "eBay Sold 스크레이퍼 대공사 — 정확도 대폭 개선. 오늘 발견된 issue 5개 다 픽스: (1) 카드 번호 오탐 (예: '170 HP' 를 카드 #170 로 오해) → 슬래시 포맷 (170/181) 우선 매치로 방지. (2) eBay 가 datacenter IP (GH Actions) 에 검색어를 조용히 완화해서 관련 없는 booster/타 세트 카드 반환 → URL 에 최소 가격 파라미터 `_udlo=raw×0.3` 추가로 필터. (3) MIN=5 임계가 얇은 시세 카드 (BGS Black Label, TAG grader 등) 다 폐기 → 유니버설 MIN=2 (BGS 10 BL 은 1). (4) CGC PRISTINE 10 등급이 'raw' 로 오분류 → 전용 패턴 추가. (5) Refresh 클릭 시 옛날 오염 데이터 자동 청소. 결과: sm9-170 Latias & Latios SIR 는 기존 $1,169 (잘못) → $15,949 PSA 10 실 sold median 으로 정확 반영.",
    en: "Major eBay sold-scraper overhaul — 5 issues fixed today: (1) card number false-positives (e.g. '170 HP' matching card #170) prevented via slash-format (170/181) priority matching; (2) eBay silently substituting our search on datacenter IPs (GH Actions runners) with unrelated Booster Bundles / wrong-set Latias cards — fixed by injecting `_udlo=raw×0.3` price floor into the search URL, killing 95% of the noise upstream; (3) MIN=5 threshold was throwing away real data on thin-market tiers (BGS Black Label, TAG grader) — universal MIN=2 (BGS 10 BL kept at 1); (4) CGC PRISTINE 10 slabs were classified as 'raw' — added dedicated pattern (was silently missing $17k sold listings); (5) old contaminated snapshots now cleaned up on Refresh. Result: sm9-170 Latias & Latios SIR PSA 10 went from $1,169 wrong → $15,949 real sold median.",
  },
  {
    date: "2026-07-16",
    emoji: "🏠",
    kr: "홈페이지 카탈로그 통계 업데이트 — Cards 31,000+ → 43,000+ (실측 43,087장: EN 21,250 + JA 21,837), Sets 340+ → 500+ (실측 503개: EN 187 + JA 316). about / pricing / signup 페이지도 함께 반영",
    en: "Homepage catalog stats refreshed — Cards 31,000+ → 43,000+ (actual 43,087: EN 21,250 + JA 21,837), Sets 340+ → 500+ (actual 503: EN 187 + JA 316). Also updated on about / pricing / signup pages",
  },
  {
    date: "2026-07-16",
    emoji: "🔁",
    kr: "카드 페이지 Refresh 버튼 로직 재작업 — (1) 한 번 클릭에 raw 시세 (TCGCSV) 와 graded 시세 (eBay sold) 를 동시에 갱신. Raw 는 즉시 반영되고 graded 는 2-3분 후 랜딩. (2) 오래된 오염 데이터 자동 청소 — Refresh 시점에 15분보다 오래된 eBay 스냅샷을 먼저 삭제해서, 새 스크레이프가 필터에 걸려 뭐 못 써도 예전에 잘못 매칭됐던 숫자 (예: sm9-170 Latias & Latios SIR 가 $1,169 로 잘못 뜨던 케이스) 는 즉시 사라짐. (3) 쿨다운 5분 → 24시간 (TCGplayer 자체가 하루 1-2번만 갱신하니까 그 이상 자주해도 같은 숫자, GH Actions 부담만 늘어남). raw 는 여전히 즉시 반응, graded 는 하루 1회로 안정.",
    en: "Refresh button on card pages reworked — (1) One click now updates BOTH raw prices (TCGCSV, instant) AND graded prices (eBay sold, ~3 min via GitHub workflow). (2) Stale contaminated data now gets nuked on refresh — snapshots older than 15 min from eBay sources are deleted before the new scrape fires, so cases where an old bad match (e.g. sm9-170 Latias & Latios SIR reading $1,169 because '170 HP' in the title got mis-parsed as card #170) get cleared immediately even if the new scrape can't find enough sold copies to replace them. (3) Cooldown bumped from 5 min to 24 hours per card — TCGplayer only updates its market price 1-2×/day and eBay sold history doesn't move faster than that either, so more frequent clicks just cost GH Actions minutes without changing the numbers.",
  },
  {
    date: "2026-07-16",
    emoji: "🎁",
    kr: "デッキ商品 (Deck Products) 섹션 세트 타일에 'Sealed value' 표시 추가 — 스타터 덱 / 빌드박스 / 트레이너 박스는 실제로 카드가 아니라 sealed 상품 자체가 세트이기 때문에 기존 'Set value' 는 항상 비어있었음. 이제 세트에 붙어있는 sealed 상품들의 가격 합계를 'Sealed value' 로 표시. 현재 118 개 DECK 세트 중 23 개에 라벨 뜸 (SI, SMP2, WCS23, SVM, SK, SVG, SM0, SVD, SVB, SVP1, SVHK, SVN, SVHM, MC, SVAW 등). TCGCSV 그룹 abbreviation 이 빈 두 그룹에 groupId 오버라이드 추가로 SVM/MC 신규 부착. 나머지 95 세트는 TCGCSV 자체에 sealed SKU 가 없거나 부모 expansion 그룹에 카드 singles 와 섞여있어서 eBay Browse API 폴백 필요 (task #33 로고 백필 방식)",
    en: "Deck Products section now shows a 'Sealed value' pill on set tiles — starter decks, build boxes, and trainer boxes have no card rows on our side (the SKU IS the whole set) so the existing 'Set value' line was blank on every DECK tile. Backend now sums the market prices of sealed products attached to each set and the frontend surfaces it as a new pill, DECK-type only. Live on 23 of 118 JP DECK sets today (SI, SMP2, WCS23, SVM, SK, SVG, SM0, SVD, SVB, SVP1, SVHK, SVN, SVHM, MC, SVAW, and more). Added groupId overrides for two TCGCSV umbrella groups whose empty abbreviation was silently skipping SVM/MC. The remaining 95 sets either have no sealed SKU on TCGCSV or the SKU is bundled inside a parent expansion group alongside card singles — reaching those needs an eBay Browse API fallback (same technique task #33 used for DECK logos)",
  },
  {
    date: "2026-07-16",
    emoji: "🇯🇵",
    kr: "일본어 카드 시세 커버리지 대폭 확장 — 그동안 JP 카탈로그에는 이름은 있는데 가격은 '$?' 로 남아있던 카드가 15,000장 넘게 있었음. TCGCSV 의 Pokemon Japan 카테고리와 카드 번호 기반으로 매칭 (JP 카탈로그는 일본어 이름 '스트라이크' 로 저장돼있고 TCGCSV 는 영어 이름 'Scyther' 로 저장돼있어서 이름 매칭은 안 통함 — 번호는 언어 무관하니까 그걸로 조인) 해서 15,408장 (98.7%) 에 TCGplayer product id 붙임. 이어서 첫 가격 sync 돌려서 20,254장 EN + JP 카드 시세 갱신 + 25,234개 히스토리 스냅샷 추가. 이제 SVHK, S12a, SV11B, S8a, S6a, SM12 같은 세트 열면 대부분 카드에 시세 붙어있음. 매일 밤 도는 sync 도 이제 EN + JP 두 카테고리 다 순회하니까 앞으로 자동 유지됨. 남은 116개 세트는 TCGCSV 자체에 없는 미공개/초창기/서브 세트라 별도 소스 필요",
    en: "Japanese card price coverage jumped from a couple hundred to ~15k cards — the JP catalog had names but the 'Market' tile stayed '$?' on 98% of rows because TCGCSV's JP category stores English names (Scyther) while our catalog stores Japanese names (ストライク), so a name-based join returned almost nothing. Switched to number-based matching (card number is language-invariant and unique within a set) and populated tcgplayer_product_id on 15,408 of 15,611 JP cards (98.7%). Then ran the first EN + JP price sync in one pass: 20,254 cards refreshed, 25,234 history snapshots inserted, 0 group errors. Open any modern JP set now (SVHK, S12a, SV11B, S8a, S6a, SM12) and prices are live for most singles — S8a Mew UR shows $775, S6a Eevee Heroes chase at $255. The nightly TCGCSV sync now loops both category 3 (EN) and category 85 (JP) so this stays fresh automatically. Remaining 116 JP sets don't exist on TCGCSV (early/unreleased/sub-sets) — those need a separate source (snkrdunk / cardmarket) later",
  },
  // ── 2026-07-15 ─────────────────────────────────────────────────
  {
    date: "2026-07-15",
    emoji: "🔄",
    kr: "카드 페이지에 'Refresh' 버튼 추가 — Graded Prices 섹션에서 사인인 상태로 클릭하면 해당 카드의 eBay 실 판매 + 매물 데이터를 즉시 다시 스크랩. 약 2-3분 걸리고 페이지 새로고침하면 tile 갱신됨. 데이터 얇은 카드 (특히 vintage CGC / TAG) 는 버튼이 초록으로 강조돼서 눈에 잘 띔. 카드당 30분 쿨다운 (베타 중엔 5분).",
    en: "Card pages now have a 'Refresh' button — signed-in users can click it in the Graded Prices section to trigger a fresh eBay scrape for that specific card (both sold and active-listing data). Takes ~2-3 minutes; reload the page after to see updated tiles. On thin-data cards (especially vintage CGC / TAG), the button glows green so it's hard to miss. Per-card 30-min cooldown (5 min during beta).",
  },
  {
    date: "2026-07-15",
    emoji: "🏅",
    kr: "그레이딩 tile 10종으로 확장 — 기존 PSA 10/9, CGC 10/9 에 BGS 10/9.5/9 와 TAG 10/9.5/9 추가. TAG (Technical Authentication & Grading) 는 요즘 chase 카드에서 급부상 중이라 우선 지원. 각 grader 는 고유 색상 (PSA 초록 / CGC 티얼 / BGS 인디고 / TAG 로즈) 으로 시각 구분. 데이터는 자동 sweep + 유저 Refresh 로 순차 채워짐. 데이터 얇은 카드는 sold 대신 매물 median (Asking) 을 황색으로 표시 — 헷갈리지 않게 항상 라벨링.",
    en: "Graded Prices grid expanded from 4 to 10 tiles — added BGS 10/9.5/9 and TAG 10/9.5/9 alongside existing PSA and CGC tiers. TAG (Technical Authentication & Grading) is a hot newer service on modern chases so it gets first-class support. Each grader family has its own accent color (PSA green / CGC teal / BGS indigo / TAG rose). When sold data is thin (common for vintage CGC), tiles fall back to active-listing medians shown in amber and clearly labeled 'Asking' — sold and asking never get blended into one number.",
  },
  {
    date: "2026-07-15",
    emoji: "💰",
    kr: "PSA/CGC 등급 시세가 실제 낙찰가 기준으로 자동 정제됨 — 셀러들이 매물을 시세보다 10-30% 위로 올리는 경향 때문에 기존 매물 median 은 부풀려져 있었음. 이제 실 판매가 (sold) 데이터가 있으면 초록 tile 로 표시되고, 없으면 매물 median (Asking) 을 황색으로 안내. Sold 초록 tile 하단에는 판매 건수도 함께 표시 (예: '18 sales').",
    en: "Graded tier prices now refined against actual clearing prices — sellers routinely list slabs 10-30% above the true market so the old asking-median tiles ran hot. Sold-based medians (real clearing price) render as green tiles; when no sold data exists yet, the tile falls back to an amber Asking median with a clear label. Green sold tiles show the sample size too (e.g. '18 sales') so you can gauge confidence at a glance.",
  },
  // ── 2026-07-14 ─────────────────────────────────────────────────
  {
    date: "2026-07-14",
    emoji: "🎯",
    kr: "PSA/CGC 시세 tile에 '실 판매가 (sold)' 데이터 반영 시작 — 기존에는 eBay에 올라온 매물 가격 (asking) median 이었는데, 판매자들이 슬랩을 실제 낙찰가보다 10-30% 위에 올리는 경향 때문에 시세가 부풀려져 보였음. 이제 Playwright 로 eBay sold listings 를 직접 스크래핑해서 실제 팔린 가격 median 을 표시. 같은 등급에 sold + asking 데이터 둘 다 있으면 sold 를 우선 표시. 첫 커버리지: 190장 chase 카드 (PSA 10, PSA 9, CGC 10, CGC 9 4개 tier). Umbreon SIR PSA 10 예: 매물 median $7,949 → 실 판매 median $6,950-7,050 (12% 조정), Charizard CGC 10 매물 $9,500 → 실 판매 $3,358 (65% 조정 — asking 이 크게 왜곡돼있었음). 카드 상세페이지 Graded Prices 섹션의 'ebay_sold' 태그로 소스 확인 가능. Vintage 카드 (Shining Charizard 등) 는 CGC 슬랩 자체가 시장에 얇게 거래돼서 CGC tile 은 여전히 비어있을 수 있음 (데이터 문제가 아니라 시장 현실). 주간 자동 rotation 으로 tier별로 순차 갱신, 필요시 관리자가 full sweep 트리거 가능",
    en: "Graded price tiles (PSA/CGC) now display actual sold prices — previously the medians were pulled from ACTIVE eBay listings (asking prices), but sellers routinely list slabs 10-30% above the clearing price. Playwright now scrapes eBay's sold-listings pages directly and reports the median of what actually cleared. When both sold and asking data exist for the same grade, sold takes precedence. Initial coverage: 190 chase cards across all four tiers (PSA 10 / PSA 9 / CGC 10 / CGC 9). Umbreon SIR PSA 10 example: asking median $7,949 → real sold median ~$6,950-7,050 (12% adjustment). Charizard CGC 10: asking $9,500 → sold $3,358 (65% adjustment — asking was heavily distorted). Look for the 'ebay_sold' source tag under each tile on the card detail page. Vintage cards (Shining Charizard etc.) may still show empty CGC tiles because those slabs trade thinly — not a data bug, just market reality. Weekly automated rotation refreshes each tier on its own day; admin can trigger a full sweep on demand.",
  },
  // ── 2026-07-13 ─────────────────────────────────────────────────
  {
    date: "2026-07-13",
    emoji: "🗂️",
    kr: "Series 페이지 신설 — /series 에서 시대 (Scarlet & Violet, Sword & Shield, Sun & Moon 등) 별로 브라우징 가능. 각 시리즈 페이지 (/series/scarlet-and-violet 등) 에는 그 시대 소속 모든 세트 + 모든 sealed 상품 한 화면에 집계. TopNav 에도 Series 링크 추가, /sets/[id] 헤더의 'Series · X' 라벨도 클릭 가능. 시리즈 → 세트 → 카드/sealed 자연스러운 계층",
    en: "Series pages are live — /series lets you browse Pokémon TCG by era (Scarlet & Violet, Sword & Shield, Sun & Moon, and every earlier cycle). Each series page collects every set + every sealed product in that era on one screen. Series link added to the top nav; the 'Series · X' label on set pages now deep-links to the corresponding series. Natural nav flow: series → set → cards or sealed",
  },
  {
    date: "2026-07-13",
    emoji: "📦",
    kr: "Sealed 상품 컬렉션 + 위시리스트 활성화 — 상품 상세 페이지에 'Mark as owned' / 'Add to wishlist' 버튼 추가. 유저가 소유한 박스/ETB/번들을 카드처럼 트래킹 가능. /portfolio 에 새 'Sealed' 탭에서 owned + wishlist 그리드 + 총 가치 표시. 카드 컬렉션 반쪽자리에서 완전한 인벤 관리로 승격",
    en: "Sealed products are now trackable — the detail page adds Mark as owned + Add to wishlist buttons, mirroring the card collection flow. Your sealed inventory (boxes, ETBs, bundles, tins, blisters) lives under the new Sealed tab on /portfolio with owned + wishlist grids and a total-value stat. Collection tracking is no longer just for singles",
  },
  {
    date: "2026-07-13",
    emoji: "📈",
    kr: "Sealed 상품 가격 히스토리 차트 신설 — 상품 상세 페이지 아래쪽에 30일/90일/6개월/1년 가격 차트. TCGCSV 매일 스냅샷 저장 기반. 박스 시세가 stable 인지 매수 타이밍인지 시각적 판단 가능. 지금은 오늘부터 축적 (~1주일 지나면 실용 차트)",
    en: "Sealed products get a price history chart — every product detail page now shows a 30d / 90d / 6M / 1Y line chart with range low / high stats. Backed by daily TCGCSV snapshots (starting today; a week's data will make the chart genuinely useful). Answers whether a box is trending up or trending down before you commit to the buy",
  },
  {
    date: "2026-07-13",
    emoji: "🧾",
    kr: "Sealed 카탈로그 커버리지 3배 확장 — 기존 7세트 (Mega Evolution 시대만) 에서 39세트로 확장, 총 상품 320 → 963개. SV, SWSH, XY, SM, HGSS 등 모든 현대 시대 세트가 이제 sealed 라인업 포함. TCGCSV 이름 매칭 알고리즘으로 매일 자동 갱신",
    en: "Sealed catalog expanded from 7 sets to 39 sets (320 → 963 SKUs). Every modern era — Scarlet & Violet, Sword & Shield, Sun & Moon, XY, HGSS — now carries its full sealed lineup: Booster Boxes, ETBs, Bundles, Premium Collections, Tins, Blisters, Build & Battle boxes",
  },
  {
    date: "2026-07-13",
    emoji: "🎯",
    kr: "세트 상세 페이지 헤더 재디자인 — 기존 작은 완성도 카드 → 큰 헤더 배너로 승격. Master 완성률 원형 링, Master Owned/Total + Full Set Owned/Total 카운트, 하단에 Full Set (빨강) + Master (청록) 진행바. 219장 세트가 130장 base + 89장 secret 로 나뉘어 있는게 즉시 파악됨. 로그아웃 유저도 세트 총 사이즈 학습 가능",
    en: "Set detail page gets a header-scale completion widget — Master completion ring (%), Master + Full Set owned/total counts, and stacked Full Set (red) + Master (teal) progress bars. Now instantly clear that a 219-card set is really 130 base + 89 secret / SIR / hyper-rares. Non-logged-in visitors also see the set totals so they can learn what's in the era before signing up",
  },
  {
    date: "2026-07-13",
    emoji: "🃏",
    kr: "세트 상세 페이지 Cards | Sealed 탭 분리 — 이전엔 카드 그리드 위에 sealed 상품이 stack 돼있어서 스크롤이 길었음. 이제 두 탭으로 분리, URL 도 유지 (`?tab=sealed` 새로고침해도 그대로). Sealed 탭에서 유저는 그 세트의 박스/ETB/번들 라인업 한 눈에",
    en: "Set detail pages now split into Cards | Sealed tabs — no more scrolling past a sealed grid to find the cards section (or vice versa). Tab state persists in the URL so refreshing lands you back on the same view. The Sealed tab surfaces every box, ETB, bundle, premium collection, tin, and blister for that set in one grid",
  },
  {
    date: "2026-07-13",
    emoji: "🎖️",
    kr: "Multi-Grade 가격 타일 활성화 — 카드 상세 페이지 가격 차트 아래 새 섹션 'Graded Prices' 추가 (PSA 10 / PSA 9 / CGC 10 / CGC 9 4개 타일). 앞으로 들어오는 eBay 리스팅이 title 기반으로 자동 분류돼서 각 등급별 median 가격이 별도 저장됨. 첫 크론 돌기 전엔 대부분 'No sold listings indexed yet' 상태 → 며칠 지나면 인기 카드부터 채워짐. 기존 raw 스냅샷은 title 정보가 없어서 재분류 불가라 grade='raw' 유지 (일부 슬랩 오염 포함, 새 파이프라인 돌면서 자연 감소)",
    en: "Multi-Grade price tiles are live — a new 'Graded Prices' section under the price chart on card detail pages shows PSA 10 / PSA 9 / CGC 10 / CGC 9 medians. Every incoming eBay listing now runs through a title classifier and gets bucketed by grade before we compute the median, so slabbed prices no longer contaminate the raw sold-listings number. Most tiles will read 'No sold listings indexed yet' until the next few daily crons — chase cards populate first. Historical raw snapshots stay grade='raw' (their listing titles weren't stored, so retroactive reclassification isn't possible) and will phase out as the new pipeline runs",
  },
  {
    date: "2026-07-13",
    emoji: "⚡",
    kr: "Database 인프라 이관 — Neon Free 티어에서 Render Postgres 로 옮김. 백엔드랑 동일 리전 (Ohio) 이라 DB 왕복 시간 5-15ms → <1ms. 페이지 로딩이 데이터 많은 곳 (세트 리스트, 카드 브라우저) 에서 약간 빨라짐. 유저 데이터 전량 이관 확인 (컬렉션, 위시리스트, 마스터셋, 가격 히스토리 51만 개 스냅샷 다 그대로). 백엔드 성능 최적화 4개도 같이 배포됨 — Products 페이지 CDN 캐시, TCGCSV 크론 skip-if-unchanged (57% 스킵), Visit tracking SQL 집계, Set 페이지 sealed products 세션 캐시",
    en: "Database infrastructure moved — migrated from Neon Free tier to Render Postgres in the same Ohio region as the backend, dropping DB round-trip latency from 5-15ms to <1ms. You'll see snappier loads on data-heavy screens (set list, card browser). All user data transferred verbatim: collections, wishlists, master sets, and 515k price snapshots. Four backend performance optimizations shipped alongside — CDN caching on /products, skip-if-unchanged on the daily TCGCSV sync (57% of cards skipped), SQL aggregation for visit tracking, and session cache for set-page sealed products",
  },
  {
    date: "2026-07-13",
    emoji: "📦",
    kr: "Sealed 상품 카탈로그 신설 — /products 페이지에서 Booster Box / Elite Trainer Box / Booster Bundle / Premium Collection / Tin / Blister / Build&Battle 다 브라우징 가능. 7개 EN 세트 (ME01~ME05, Ascended Heroes, 30th Celebration) 총 200+ sealed 상품 TCGCSV 에서 자동 인제스트. 상품 상세페이지엔 이미지, 가격, TCGplayer affiliate 링크, 그리고 EV (Expected Value) 계산기 위젯 포함 — 세트 안 카드들 시세 기반으로 '박스 뜯으면 대충 얼마 값어치' 표시 + sealed premium/discount % 도. 세트 상세 페이지 하단에도 그 세트의 sealed 상품 그리드 붙음",
    en: "Sealed products catalog is live — /products lets you browse Booster Boxes, ETBs, Bundles, Premium Collections, Tins, Blisters, Build & Battle boxes. Auto-ingested 200+ SKUs from TCGCSV across the 7 recent EN sets (ME01–ME05, Ascended Heroes, 30th Celebration). Detail pages carry image, market price, TCGplayer buy link, plus an Estimated Value widget — modelled from the set's rarity-weighted card prices so you can see \"crack for value\" vs \"sealed premium\" at a glance. Set detail pages also grow a sealed-products row at the top",
  },

  // ── 2026-07-07 ─────────────────────────────────────────────────
  {
    date: "2026-07-07",
    emoji: "🎴",
    kr: "30th Celebration (me30) 세트에 Classic Collection 리프린트 11장 추가 (38 → 49장) — Charizard (Base Set), Pikachu (Base Set), Palkia LV.X (Great Encounters), Uxie (Legends Awakened), Lugia (Aquapolis), Darkrai & Cresselia LEGEND top/bottom (Triumphant), Pikachu & Zekrom-GX (Team Up), Zacian V (SS Base), Raikou Amazing Rare (Vivid Voltage), Arceus VSTAR (Brilliant Stars). 번호 CC01-CC11 (정확한 프린트 번호는 확정되면 갱신), rarity=Classic Collection, 이미지는 리프린트 아트 공개될 때까지 null",
    en: "30th Celebration (me30): added 11 Classic Collection reprints (38 → 49 cards) — Charizard (Base Set), Pikachu (Base Set), Palkia LV.X (Great Encounters), Uxie (Legends Awakened), Lugia (Aquapolis), Darkrai & Cresselia LEGEND top/bottom (Triumphant), Pikachu & Zekrom-GX (Team Up), Zacian V (SS Base), Raikou Amazing Rare (Vivid Voltage), Arceus VSTAR (Brilliant Stars). Placeholder CC01-CC11 numbering until real print numbers land; rarity=Classic Collection; images null until anniversary reprint art is public",
  },
  // ── 2026-07-06 ─────────────────────────────────────────────────
  {
    date: "2026-07-06",
    emoji: "🔗",
    kr: "Master Sets 공개 공유 링크 추가 — 바인더 detail 페이지 상단에 'Share' 버튼 → 클릭하면 공개 URL 모달 (원샷 mint, 복사, revoke). `/p/masters/{token}` 로 열면 로그인 없이 소유자의 바인더를 read-only 로 볼 수 있음 (진행률·소유 카드·커버 이미지 다 포함). Revoke 하면 즉시 404",
    en: "Master Sets can now be shared via a public URL — Share button on the binder detail page opens a modal that mints, copies, or revokes the token. Anyone with `/p/masters/{token}` can view the binder read-only (progress, owned cards, cover image all visible). Revoking the token 404s the URL immediately",
  },
  {
    date: "2026-07-06",
    emoji: "📚",
    kr: "카드 상세 페이지에 '내 Master Sets' 배지 추가 — 카드 열면 그 카드가 속한 세트에 대한 유저 본인의 마스터 세트 진행률과 링크가 표시됨. 마스터 세트가 없으면 대신 'Track {세트명} in a Master Set' 프롬프트로 유도. 사이드 필터 안 들어가고 바로 확인 가능",
    en: "Card detail pages now show 'In your master set' badge — open any card and you'll see your own master set progress for that card's set (with a link straight to the binder). If you don't have one for that set yet, a friendly 'Track {set} in a Master Set' prompt takes its place",
  },
  {
    date: "2026-07-06",
    emoji: "🛠",
    kr: "Admin `/admin/reports` 에 세트 리포트 통합 — 상단 Card / Set 스코프 토글 추가. 세트 로고·이름 + 리포터·리졸버 정보로 카드 리포트랑 동일한 layout 으로 볼 수 있음. Resolve/Won't fix/재오픈 다 동작. 이전엔 세트 리포트 DB 에만 쌓이고 UI 에서 안 보였음",
    en: "Admin /reports now covers set-scoped reports too — added a Card / Set scope toggle at the top. Set reports render in the same row layout (logo, category chip, reporter, resolution note) so triage doesn't require re-parsing. Resolve / Won't fix / re-open all work. Before this, set reports only lived in the DB",
  },
  {
    date: "2026-07-06",
    emoji: "🔗",
    kr: "Master Sets 바인더 지퍼를 4면으로 확장 — 이전엔 바닥에만 붙어있던 지퍼를 top / right / bottom / left 네 방향 다 감싸는 zip-around 스타일로 재구성. 실제 카드 가디언 바인더의 외곽 지퍼 그대로. 수평 스트립은 양 끝에 6% 여백을 남겨서 수직 스트립이 코너에서 만날 때 이빨끼리 안 겹침. Pull tab 은 이제 오른쪽 → 중앙 하단으로 이동 (실물 지퍼 바인더에서 체인이 만나는 지점)",
    en: "Master Sets binder zipper now wraps the whole shell — the previously bottom-only strip is replaced by four (top / right / bottom / left) so the binder reads as a proper zip-around like a real card guardian. Horizontals leave a 6% margin on each end so the verticals can meet them at the corners without their teeth overlapping. Pull tab moved from the right to dead center-bottom (where the chain actually meets on a physical zip binder)",
  },
  {
    date: "2026-07-06",
    emoji: "🧷",
    kr: "Master Sets 바인더 스파인 정리 — 원래 가운데 있던 은색 링 3개 제거하고, 실제 카드 가디언 바인더처럼 두 페이지 사이에 얕은 크리즈 (홈) 만 남김. 다크 그림자 + 미세한 하이라이트 2겹으로 실제 폴딩된 나일론 느낌. 바닥에는 CSS로 그린 실제 지퍼 추가 — repeating-linear-gradient 로 은색 이빨 (teeth) + 위아래 fabric tape + 오른쪽에 pull tab (핀홀까지) 붙여서 진짜 지퍼처럼 보임",
    en: "Master Sets binder spine cleanup — dropped the three silver rings that used to sit on the centre gutter (per LO's reference photo, real card-guardian binders don't show them from this angle). Left just a shallow crease down the middle: dark shadow band + faint highlight ridges = folded nylon feel. Also added a real CSS zipper along the bottom edge — silver teeth (repeating-linear-gradient), fabric tape above and below, plus a metallic pull tab with a pinhole for the ring on the right. All CSS, no image assets",
  },
  {
    date: "2026-07-06",
    emoji: "🕸",
    kr: "Master Sets 바인더 안쪽에 mesh 질감 추가 — 그동안 검정 그라디언트로만 채워져있던 페이지 배경에 미세한 dot pattern 을 두 겹 오프셋으로 덧입혀서 실제 카드 바인더의 perforated ballistic nylon (구멍 뚫린 검정 나일론) 처럼 보이게 함. 6px 간격 dot + 3px 오프셋으로 half-step, 반짝임 무게 다르게 해서 그리드가 아니라 짜여진 mesh 로 읽힘. 카드는 여전히 유일한 색감으로 도드라짐",
    en: "Master Sets binder interior now has a mesh texture — the previously flat black gradient gets two offset radial-gradient dot layers on top, so the pages read as real perforated ballistic-nylon binder pockets instead of a solid black wash. 6px dot grid with a 3px half-step offset and two different opacities so the pattern feels woven, not gridded. Cards still pop as the only colour",
  },
  {
    date: "2026-07-06",
    emoji: "📄",
    kr: "Master Sets 페이지 넘김이 두 번 튀던 버그 fix — motion.div의 `key` 에 spreadIndex를 넣어놨는데 중간에 spread를 교체하면 key가 바뀌면서 AnimatePresence가 '다른 페이지'로 인식해서 애니메이션을 처음부터 다시 재생. 앞 절반 (0→90°) → 리셋 → 뒷 절반 (0→90°) 이 되어서 한 번 넘기는데 두 장 넘어가는 것처럼 보였음. key를 flip 전 스냅샷 destination index 기준으로 바꿔서 flip 내내 identity 안정 유지. 겸사겸사 넘어가는 페이지에 self-shadow (앞면은 0→55% 어두워지고, 뒷면은 55%→0 밝아지는) 오버레이 추가해서 실제로 페이지가 빛을 받았다 잃었다 하는 느낌",
    en: "Master Sets page-flip fix: what looked like TWO pages flipping in sequence was actually one flip getting restarted mid-way. The motion.div's key included spreadIndex, and swapping the spread at the arc's midpoint changed the key → AnimatePresence unmounted the sheet and mounted a fresh one that replayed the animation from rotateY 0. So the visual was 0→90° → snap-back → 0→90° = double flip. Keying on the destination index (set at start, cleared at end) keeps identity stable for the whole 900ms arc. Also added a self-shadow crossfade — the outgoing face darkens as it turns away, the incoming face brightens as it lands, so the page actually reads as catching light instead of just spinning",
  },
  {
    date: "2026-07-06",
    emoji: "🧵",
    kr: "Master Sets 바인더 디테일 폴리싱 — (1) 커버 어떤 이미지를 씌우든 (마스코트든 유저 커스텀 이미지든) 최상단에 dashed 스티치 테두리가 항상 뜸. 실제 바인더의 재봉 자국 느낌. 밝은 커버든 어두운 커버든 다 보이게 어두운 그림자 + 밝은 실 2겹 레이어. (2) 바인더 안쪽 (펼쳤을 때 페이지 배경) 을 크림색 종이에서 검정 나일론으로 변경 — LO 참조 사진처럼 카드가 유일한 색감이고 배경은 완전 다크. 페이지 번호는 흰색 40% 로 조정, 카드 포켓도 다크 베이스에 서브틀 인셋 섀도로 실감 나게",
    en: "Master Sets binder polish — (1) Cover now always shows a dashed-stitch border as the top layer, regardless of whether you're using the default mascot or a custom uploaded image. Two-layer (dark shadow + light thread) so the stitches read on any cover art, matching real card-guardian binders. (2) Inside pages swapped from cream paper to black nylon — the cards are the only colour, background stays flat dark. Page numbers and empty-pocket marks recoloured for the dark base; pocket sleeves darkened with subtle inset shadow so cards pop",
  },
  {
    date: "2026-07-06",
    emoji: "🖼",
    kr: "Master Sets 바인더 대공사 — (1) 처음 열면 검은 나일론 커버로 덮여있고, 탭하면 열리는 UX. (2) 커버 중앙에 기본 마스코트 (Dragonite) 박혀있고, 유저가 자기 이미지 업로드해서 커스텀 커버 가능. 이미지는 브라우저에서 자동으로 1200px + JPEG 85% 로 리사이즈해서 500KB 이하로 압축 후 저장, 교체할 때마다 이전 이미지 덮어써져서 스토리지 안 참. (3) 애니메이션 자연스럽게 — 넘김 시간 600ms → 900ms, ease curve 부드럽게, 페이지 뒷면에 진짜 다음 스프레드 왼쪽 페이지가 렌더링되어 실물 책 넘기는 감각, 넘어가는 동안 스프레드 위에 그림자 살짝 지는 depth cue 추가. (4) 페이지 넘기기 아이콘 (◀ / ▶) 이 가장자리 hover 시 뜨고, 하단에 진짜 클릭 가능한 Prev / Next 버튼 추가. (5) 팔레트를 크림 가죽에서 다크 차콜 + 은색 링 으로 변경 (LO 참조 이미지의 지퍼 바인더 톤)",
    en: "Master Sets binder overhaul — (1) Opens as a closed dark-nylon cover; tap or Enter to open. (2) Default cover shows the mascot + set name; users can upload a custom image which is resized in-browser to ~1200px JPEG 85% and stored under 500KB. Uploading a new one overwrites the old — no orphan blobs. (3) Page-turn animation smoothed — 600ms → 900ms, gentler ease, and the back of the flipping sheet now shows the actual destination-left page for a real book feel. Ambient shadow darkens the resting spread mid-flip for depth. (4) Edge zones widened to 12% and reveal a floating chevron on hover — the previous invisible 10% strip was un-discoverable. Added real bottom Prev / Next buttons for good measure. (5) Palette swapped from cream leather to charcoal + silver rings to match the modern zip-binder reference",
  },
  {
    date: "2026-07-06",
    emoji: "🇯🇵",
    kr: "일본판 세트 필터 사이드바 레어도 표기를 EN 라벨(Rare Secret / Illustration Rare…) 대신 실제 카드에 찍힌 JP 코드(C/U/R/RR/RRR/AR/SR/SAR/HR/UR/CHR/CSR/SSR)로 렌더링 — 일본판 브라우저는 EN 카탈로그와 다른 taxonomy 표시. 3단 감지: (1) URL의 `?language=ja`, (2) 세트 자체가 JP면 세트 상세 페이지에서 강제, (3) 세트의 실제 레어도 분포에 JP 코드가 하나라도 있으면 자동으로 JP 모드로 스위치. 언어별로 남는 잔여 라벨은 Misc 섹션에서 필터링되어 두 taxonomy가 뒤섞이지 않음. 함께 남아있던 JP 카드 7,869장의 EN 스타일 라벨을 JP 코드로 재매핑 (Rare Secret → UR, Illustration Rare → AR, Special Illustration Rare → SAR 등)",
    en: "JP set filter sidebar now renders rarity labels using JP codes (C/U/R/RR/RRR/AR/SR/SAR/HR/UR/CHR/CSR/SSR) — the actual codes printed on the cards — instead of pokemontcg.io English labels. Three-tier language detection: (1) explicit `?language=ja`, (2) set-detail pages force JP when the set is JP, (3) data sniff — if the set's rarities include any JP-native code, swap taxonomies automatically. Leftover labels from the other language get filtered out of the Misc bucket so you never see two taxonomies at once. Also remapped 7,869 JP cards whose rarity was still an EN label (Rare Secret → UR, Illustration Rare → AR, Special Illustration Rare → SAR, etc.)",
  },
  {
    date: "2026-07-06",
    emoji: "⚠",
    kr: "세트 상세 페이지 (Sets → 세트 하나 클릭) 우측 상단에 'Report an issue' 버튼 추가 — 카드 몇 장 빠진 것 같거나, 이미지가 잘못됐거나, 세트 이름·로고·발매일이 틀렸을 때 4가지 카테고리 (Missing cards / Wrong images / Wrong info / Other) 로 신고 가능. 로그인 없이도 익명 신고 가능",
    en: "Set pages: added a Report an issue button next to the set metadata — 4 categories (Missing cards / Wrong images / Wrong info / Other) so you can flag when a set has gaps, broken images, or wrong logo/release-date/name. Anonymous submissions accepted; if you're signed in the report attaches to your account",
  },
  {
    date: "2026-07-06",
    emoji: "🔙",
    kr: "필터·페이지네이션·정렬 클릭할 때마다 뒤로가기 히스토리에 하나씩 쌓이던 문제 fix — 이제 레어도 3개 고르고 정렬 바꾸고 페이지 넘겨도 뒤로가기 한 번이면 원래 있던 목록 페이지 (예: /sets 또는 /cards) 로 바로 돌아감. 브라우저 세션 히스토리를 필터 상태로 오염시키던 `router.push` 를 `router.replace` 로 전환",
    en: "Back-button fix: every filter tap / rarity toggle / pagination click used to push a new history entry, so after browsing you'd hit back 8 times to escape. Now filters and pagination REPLACE the URL instead of pushing — one Back always returns you to whatever list page brought you here (/sets, /cards)",
  },
  {
    date: "2026-07-06",
    emoji: "📖",
    kr: "Master Sets 바인더가 실제 바인더처럼 3D 스프레드로 변신 — 이전엔 3x3 그리드가 세로로 쭉 이어졌는데, 이제 크림 종이 페이지 두 장이 나란히 펼쳐지고 가운데 놋쇠 3링 + 가죽 셸이 감싸는 모양. 페이지 옆 가장자리 클릭하면 rotateY 3D 애니메이션 (600ms cubic-bezier) 으로 넘어감. ←/→/Home/End 키보드 nav, 카드 이름으로 점프하는 검색바도 위쪽에 붙음. 3x3 = 스프레드 당 18장, 4x3 = 24장, 4x4 = 32장 — 128장 세트면 3x3 기준 8스프레드. 소유 카드는 컬러 + ✓, 미소유는 grayscale + 40% opacity 그대로. 플라스틱 슬리브 반사감 + 스파인 쪽 그림자로 종이 두께 표현",
    en: "Master Sets binder now reads as a real open binder instead of a scrolling grid — two cream paper pages laid out side by side, three brass rings down the center, leather shell wrapping the whole thing. Click either outer edge to flip; the page turns with a 3D rotateY animation (~600ms). ArrowLeft/Right + Home/End work; there's a card-name search that jumps to whichever spread contains the match. Spread capacity scales with binder size — 3x3 → 18 slots per spread (a 128-card set = 8 spreads), 4x3 → 24, 4x4 → 32. Owned cards render in colour with a ✓; missing ones stay grayscale + 40% opacity. Plastic-sleeve gloss on each pocket, gutter shadow near the spine, subtle page-thickness cues so it doesn't feel flat",
  },
  {
    date: "2026-07-06",
    emoji: "📖",
    kr: "포트폴리오에 Master Sets 섹션 추가 — 세트 하나 골라서 완성해나가는 걸 바인더처럼 시각화. 3×3 (9포켓) / 4×3 (12포켓) / 4×4 (16포켓) 바인더 크기 선택, 소유 카드는 컬러 + ✓ 배지, 미소유는 실루엣, 상단에 진행률 바. Base 뷰 (한 카드당 한 슬롯, 128/128 채우면 완성) 와 Master 뷰 (reverse holo / holofoil / normal 다 별개 슬롯으로 계산) 토글 가능. 카드번호순 / 레어도순 정렬도 즉시 스위치. 100% 채우면 진행률 바가 초록으로 바뀜. EN 세트만 지원 (JP는 variant 인덱싱 후 오픈)",
    en: "Portfolio: added a Master Sets section — pick a set, watch it fill up in a binder-style grid. Choose 3×3 (9-pocket), 4×3 (12-pocket), or 4×4 (16-pocket) pages. Owned cards render in colour with a ✓ badge; missing ones stay silhouetted. Progress bar up top swaps to green at 100%. Toggle Base view (one slot per card — hit 128/128 to complete) and Master view (every TCGplayer variant — reverse holo / holofoil / normal each count) without leaving the page; same for number vs rarity sort. EN sets only for now — JP opens once variant indexing lands",
  },
  // ── 2026-07-05 ─────────────────────────────────────────────────
  {
    date: "2026-07-05",
    emoji: "🌏",
    kr: "Cards 탭 검색바 밑에 지역 (All · 🇺🇸 EN · 🇯🇵 JP) 칩 추가 — 이제 EN 카탈로그만 or JP 카탈로그만 좁혀서 브라우징 가능. URL의 `language` 파라미터로 저장돼서 링크 공유해도 필터 유지됨. 사이드바 안 열고 상단에서 바로 스위치 가능한 게 목적. KR 카탈로그는 준비되면 추가",
    en: "Cards page: added an All · 🇺🇸 EN · 🇯🇵 JP region row right under the search bar — one tap narrows the whole grid to just that print language without needing to dig into the sidebar. The choice sticks in the URL (`?language=en` etc.) so shared links keep the filter. KR chip drops in once the KR catalog is live",
  },
  {
    date: "2026-07-05",
    emoji: "🎴",
    kr: "30th Celebration (me30) 세트가 전체 38장으로 완성 — 저번 라운드에서 프로모 세트(mep)에 잘못 배정되어있던 30주년 관련 18장 (Alolan Exeggutor 094, Lucario 095, Moltres 096, Articuno 097, Zapdos 098, Greninja ex 099, Sylveon ex 100, Nidorina 101 + Pokémon Center 변종, Victini 102, Zeraora 103, Mewtwo 104, Mew 105, Ditto 106, 그리고 SIR 4장 — Pikachu ex 107, Espeon ex 108, Pikachu ex 109, Umbreon ex 110)을 me30 세트로 이동. 이제 브라우저에서 30th Celebration 클릭하면 38장 다 뜸",
    en: "30th Celebration (me30) set now shows the full 38-card lineup — 18 cards that had been miscategorised under the 'Promo' set last pass (Alolan Exeggutor 094 → Ditto 106 + the four Special Illustration Rares: Pikachu ex 107, Espeon ex 108, Pikachu ex 109, Umbreon ex 110, plus a Pokémon Center variant Nidorina 101) have been reassigned to me30. Browsing the set now surfaces every 30-stamp card in one place",
  },
  {
    date: "2026-07-05",
    emoji: "🔐",
    kr: "로그인 유지 방식 개선 — 이제 브라우저를 20일 닫아뒀다가 돌아와도 로그인 유지, iPhone Safari에서도 (기존엔 iOS ITP 때문에 7일마다 갑자기 로그아웃되던 버그 있었음). 내부적으로는 짧게 만료되는 access token + 60일짜리 refresh cookie를 자동 rotation. 로그아웃 버튼도 이제 서버 세션까지 실제로 죽임. 기존 로그인 화면의 '30일 동안 로그인 유지' 체크박스는 실제로 백엔드에 전달 안 되던 UI-only였어서 제거 (지금은 기본이 60일이라 체크박스 자체가 불필요)",
    en: "Login persistence overhauled — close the browser for 20 days and you'll still be signed in when you come back, iOS Safari included (previously ITP was silently wiping storage every ~7 days). Under the hood: short-lived access tokens paired with a 60-day refresh cookie that rotates on every use. The logout button now genuinely kills the session server-side too. The old 'Stay logged in for 30 days' checkbox on the login page was UI-only — the value never actually reached the backend — so it's gone; 60 days is now the default",
  },
  {
    date: "2026-07-05",
    emoji: "🔢",
    kr: "카드 정렬 옵션에 '카드 번호 · 높은 순' 추가 — 기존 낮은 순과 함께 세트 내 체이스 카드 (128/128, 158/128 등)부터 먼저 볼 수 있음",
    en: "Sort menu: added 'Card number · high to low' — pairs with the existing low-to-high option so the chase / secret cards at the tail (128/128, 158/128, etc.) can be surfaced first",
  },
  {
    date: "2026-07-05",
    emoji: "🎴",
    kr: "30th Celebration (me30) 카드 20장 실물 데이터로 완성 — Common 7 (Victini 013, Espeon 069, Umbreon 091, Eevee 116/117/118, Zeraora 057) / Double Rare 4 (Greninja ex 021, Espeon ex 070, Sylveon ex 071, Umbreon ex 092) / Illustration Rare 4 (Lapras 131, Drifloon 136, Lycanroc 138, Hisuian Zorua 145) / Pikachu 3 (036/037/047) / Futuristic Rare 2 (Mewtwo ex 157, Mew ex 158). 각 카드 이미지에서 실제 번호·HP·타입·레어도·아티스트 추출. 나머지 11 리프린트 카드 (base1/dp4/hgss4/swsh 등)는 다음 라운드",
    en: "30th Celebration (me30) — 20 cards now carry real metadata pulled straight from the card scans: Common 7 (Victini 013, Espeon 069, Umbreon 091, Eevee 116/117/118, Zeraora 057), Double Rare 4 (Greninja ex 021, Espeon ex 070, Sylveon ex 071, Umbreon ex 092), Illustration Rare 4 (Lapras 131, Drifloon 136, Lycanroc 138, Hisuian Zorua 145), Pikachu 3 (036/037/047), Futuristic Rare 2 (Mewtwo ex 157, Mew ex 158). Real numbers / HP / types / rarities / artists all read from the actual card images since the filenames were unreliable. 11 historical reprints (base1 / dp4 / hgss4 / swsh) next pass",
  },
  {
    date: "2026-07-05",
    emoji: "🎴",
    kr: "메가에볼루션 프로모 (MEP) 30주년 프로모 18장 완성 (#094~110) — Alolan Exeggutor, Lucario, Moltres, Articuno, Zapdos, Greninja ex, Sylveon ex, Nidorina (regular + Pokemon Center 스탬프 variant), Victini, Zeraora, Mewtwo, Mew, Ditto, Pikachu ex ×2, Espeon ex, Umbreon ex. pokecottage 이미지에서 실제 번호 판독",
    en: "Mega Evolution Promo (MEP) — full 18-card 30th-anniversary promo lineup now landed (#094~110): Alolan Exeggutor, Lucario, Moltres, Articuno, Zapdos, Greninja ex, Sylveon ex, Nidorina (regular + Pokémon Center stamp), Victini, Zeraora, Mewtwo, Mew, Ditto, Pikachu ex ×2, Espeon ex, Umbreon ex. Numbers read directly off the pokecottage-mirrored scans",
  },
  {
    date: "2026-07-05",
    emoji: "🎉",
    kr: "30th Celebration (me30) 세트 이름 정리 — 'ME: 30th Celebration' → '30th Celebration' (에라 접두사 제거). 로고는 pokemon.com 공식 wordmark 그대로 유지",
    en: "30th Celebration (me30) set rename — 'ME: 30th Celebration' → '30th Celebration' (dropped era prefix). Logo stays on pokemon.com's official wordmark",
  },
  {
    date: "2026-07-05",
    emoji: "🃏",
    kr: "Pitch Black (ME5) 카드 이름·레어도·타입 118장 백필 — Bulbapedia 세트 리스트에서 파싱. Lurantis ex, Mega Delphox ex, Mega Zeraora ex, Mega Slowbro ex, Mega Chandelure ex, Mega Darkrai ex 등 다 노출됨. 이미지·가격은 발매 후 TCGCSV 인덱싱되면 자동. BSP 프로모 8장 + 미커버 2장은 별도 처리 필요",
    en: "Pitch Black (ME5) — 118 cards backfilled with real names, rarities, and types from Bulbapedia's set article. Lurantis ex, Mega Delphox ex, Mega Zeraora ex, Mega Slowbro ex, Mega Chandelure ex, Mega Darkrai ex all visible. Images and prices auto-fill once TCGCSV indexes the individual cards. 8 BSP promos + 2 uncovered rows still pending",
  },
  {
    date: "2026-07-05",
    emoji: "🗂️",
    kr: "일본판 세트 브라우저 대개편 — 세트를 5가지 타입으로 분류 (MAIN 158 / DECK 116 / PROMO_LEGACY 12 / PROMO_NEW 20 / STUB 26). 스타터셋·프리컨스트럭트 덱·트레이너 박스 등 116개 '덱 상품'은 페이지 맨 밑 별도 섹션으로 이동. 새 언넘버드 프로모 20개 (JPP-U 년도별)는 5년 단위 (1996-2005 / 2006-2010 / 2011-2015 / 2016-2020 / 2021-2025) 그룹핑. 카드 시딩 안 된 stub 26개 hidden. Triplet Beat 중복 8개 세트 정리.",
    en: "Japanese set browser reorganized — sets now categorized into 5 types (MAIN 158 / DECK 116 / PROMO_LEGACY 12 / PROMO_NEW 20 / STUB 26). 116 deck products (starter sets, preconstructed decks, trainer boxes, build boxes) moved to a dedicated section at the bottom. 20 new Unnumbered Promo year-buckets grouped into 5-year windows (1996-2005 / 2006-2010 / 2011-2015 / 2016-2020 / 2021-2025). 26 unseeded stubs hidden. Cleaned up 8 duplicate Triplet Beat stubs.",
  },
  // ── 2026-07-04 ─────────────────────────────────────────────────
  {
    date: "2026-07-04",
    emoji: "🎨",
    kr: "필터 사이드바 정리 — Card Type의 Pokémon 중복 통합 (5,138장 é 정규화), Energy Type을 기본 접힘 + 속성별 색상 (불빨 물파 풀초 뇌노 등), NULL supertype 카드 16k+ 장을 'Other' 버킷으로 명시 노출",
    en: "Filter sidebar cleanup — merged Card Type's 'Pokémon' duplicate (5,138 rows normalized to é), Energy Type collapsed by default + color-coded per element (Fire red, Water blue, Grass green, Lightning amber…), and 16k+ cards with NULL supertype now surface under an explicit 'Other' bucket",
  },
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
