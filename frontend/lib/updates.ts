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
  // ── 2026-07-06 ─────────────────────────────────────────────────
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
