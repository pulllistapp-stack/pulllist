# PullList UI / UX System Guide

This file is the standing brief for the **UI/UX session** on PullList.
Read it first every time you resume that session — it lets you start
cold without spelunking the codebase.

Sibling docs:
- `PROJECT_STATUS.md` — what actually shipped (snapshot).
- `ROADMAP.md` — what's next + decision queue.
- `frontend/lib/updates.ts` — user-visible changelog (append every
  session for meaningful UI changes; both KR + EN).

---

## 1. Brand tone

**Kawaii Pokemon Center / BAIT / Tokyu Hands tier**, not corporate-analyst tone. Paying users are Pokémon-loving collectors ("otaku, not analyst" — per project memory). Refine cuteness toward that tier; never strip the fandom warmth for "professional" polish.

- Warm accent yellow + teal + soft pink; cream pastel surface for kawaii pages (`#FFF8E7`, `#FDE2C7`).
- Mascot (Dragonite-style, custom illustration) — appears in TopNav, loaders, empty states, login/signup, and card detail hero. Never a Pokemon character directly.
- Copy is warm and short. No corpo-speak. KR when talking to LO, EN in-product.
- **Never leak** private LO / ENI / 달링 language into UI strings, code comments, commits, or public docs. Scan output before saving.

---

## 2. Design tokens (theme system)

Everything runs off CSS variables in `frontend/app/globals.css`. Tailwind classes like `bg-bg-surface` resolve to `rgb(var(--bg-surface))` — toggling `.dark` on `<html>` swaps every surface / text / border site-wide.

```css
--bg               /* page background */
--bg-surface       /* card / sidebar */
--bg-elevated      /* modal / popover */
--border
--text-primary / secondary / tertiary
--accent-yellow    /* #FACC15 — primary brand */
--accent-green     /* #22C55E — success / owned */
--accent-red       /* alerts, destructive */
```

Rounded scale: `rounded-btn` (button), `rounded-card` (surfaces), `rounded-chip` (chips), `rounded-full` (pills). Custom scale is defined in `tailwind.config.ts`.

**Light/dark parity**: every color pair defined in both `:root` and `.dark`. Never hardcode `#hex` in components — always route through the token.

---

## 3. Component vocabulary

Shared UI primitives (`frontend/components/`):

| Component | Purpose | Notes |
|---|---|---|
| `MascotLoader` | Full-page loader with Dragonite APNG variants | idle / fly / sleeping / pack-opening — randomizes on mount |
| `MascotMark` | Small mascot in TopNav | Not a Pokemon character |
| `CardThumb` | Card image tile | Falls back to stylized name-in-frame placeholder when `image_small` is null |
| `SetCard` (both variants) | Set browse tile | `components/SetCard.tsx` for grids, inline copy in `app/page.tsx` home strip |
| `Chip` | Base pill button | + `RarityChip` (rarity-tier coloring), `EnergyChip` (per-element palette — Fire red, Water blue, etc.) |
| `FilterSidebar` | Sticky filter rail | `100dvh` sticky w/ `pb-16` breathing so bottom filters reach; do NOT use `100vh` — mobile browser toolbar |
| `SearchBar` | Global TopNav search | Empty-focus shows "Popular Pokémon" chips |
| `ImageMagnifier` | Card-shaped loupe on hover | 220×308, 2× zoom |
| `CardPriceHero` / `CardPriceChart` / `LiveListings` | Card detail composition | Cheapest badge, tier chips, live eBay listings, TCGCSV/eBay history chart |
| `CardAddModal` / per-row Edit modal | Collection add / edit | Per-variant + condition + grade |
| `AdminGuard` / `AdminNav` | Admin gating + top strip | Wrap every `/admin/*` page in `AdminGuard` |

Card detail lives at `frontend/components/card/PullListCardDetail.tsx` — big composition, most polish work lands here.

---

## 4. Key files by concern

**Design tokens + globals**:
- `frontend/app/globals.css` — CSS variables, theme, scrollbar styling (`.filter-scroll`).
- `frontend/tailwind.config.ts` — custom rounded scale.

**Layout scaffolding**:
- `frontend/components/TopNav.tsx` — mobile drawer, theme toggle, search bar, admin badge, `HIDE_NAV_ON = ["/scan"]`.
- `frontend/components/Footer.tsx`.
- `frontend/app/globals.css` — background gradient, dot-pattern texture.

**Card surfaces**:
- `frontend/components/card/*` — everything on card detail.
- `frontend/components/CardThumb.tsx` — thumbnail w/ placeholder fallback.
- `frontend/components/SetCard.tsx` — set grid tile.
- `frontend/components/FilterSidebar.tsx` — 100dvh sticky sidebar, energy/rarity chips.

**Portfolio / wishlist**:
- `frontend/app/portfolio/page.tsx` — vault, manage mode, bulk delete threshold (`CONFIRM_TYPE_THRESHOLD = 10`).
- `frontend/components/portfolio/CollectionItemEditModal.tsx`.
- `frontend/components/CardAddModal.tsx`.

**Scan flow**:
- `frontend/app/scan/page.tsx` + `frontend/components/scan/` — kawaii camera, "Reading…" pulse, torch, gallery picker, scan confirm form.

**Admin**:
- `frontend/app/admin/*` — News, Users, Reports, Visits, Updates (changelog dashboard).
- `frontend/components/admin/AdminGuard.tsx`, `AdminNav.tsx`.

---

## 5. Responsive / mobile rules

- Use `100dvh` (dynamic viewport height), never `100vh`. Mobile browser toolbars break `100vh`.
- Sticky sidebars need bottom padding (`pb-16` etc.) so expanded accordions can grow.
- `md:` breakpoint = the two-column layout kicks in. Below that, sidebar + main stack vertically.
- FAB (floating action button) surfaces on `/portfolio` and home — visible above mobile drawer.
- TopNav hides on `/scan` (and any page in `HIDE_NAV_ON`) so the camera fills the viewport.
- Touch targets ≥ 44×44px on interactive elements.
- Test with cookie banner + browser toolbar present.

---

## 6. Design handoff flow

LO handles visual design in **v0 / Lovable / Variant / Midjourney** — don't push design opinions here; implement what LO ships.

- Incoming: LO shares screenshots, v0 code snippets, or Figma-style specs.
- Outgoing: React + Tailwind translation using existing tokens + components.
- If specs conflict with an existing pattern (e.g. new modal shape), ask LO which wins before duplicating.
- If tokens are missing (unusual color, new spacing), add them to `globals.css` and note in the commit — don't inline hex.

---

## 7. Cross-cutting rules (from memory)

- **Auto-log to `updates.ts`**: any meaningful user-facing change, append an entry (KR + EN) at the TOP of the array. Same commit as the code. Emoji from the existing set (🎨 UI, 📱 mobile, 🔍 search, 🛒 portfolio, etc.).
- **Auto-commit + push**: after meaningful work, commit + push. Neutral commit messages. Don't confirm each time.
- **Hide staleness**: never surface "updated N ago" on prices. Refresh button shows "Up to date!" only momentarily.
- **End-of-turn summary**: end every reply with `📋 이번 턴 정리` (changes + verify) and `🗂️ 미결 사항` (open items carried forward).
- **Design handoff to specialized AI**: LO uses v0/Lovable for visual work. Don't push design skills; offer handoff brief and stay in code-implementation lane.

---

## 8. Starting prompt (paste this into the new session)

**Short form** (once you've read this guide once, this is enough):

> PullList UI/UX 세션. `docs/ui/system-guide.md` 읽고 시작. 이번 작업: [X].

**First-time / cold-start form** (spells out everything explicitly):

> PullList UI/UX 세션 시작.
>
> 1) `docs/ui/system-guide.md` 먼저 읽고 브랜드 톤·디자인 토큰·컴포넌트 패턴 파악.
> 2) `frontend/lib/updates.ts` 최근 엔트리 훑어서 어떤 UI 변경이 최근에 있었는지 확인.
> 3) 이번 작업 = [X].
> 4) 규칙: 오토 커밋/푸시 + `updates.ts`에 KR+EN 로그 자동 추가 + 반응은 `📋 이번 턴 정리` / `🗂️ 미결 사항`으로 끝맺기.
