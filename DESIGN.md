# ModelSmith: Design System ("The Forge")

> Register: **product** (design serves the product) for the app shell,
> **brand** (design IS the product) for the landing page.

## Concept

ModelSmith is named for the smith: someone who takes raw metal and forges it
into something precise and useful. The entire visual language is built on that
metaphor: **molten amber on forged steel**. Every AI/dev tool ships blue-violet
gradients; this one ships the warm glow of a working forge on deep charcoal.

Physical scene (per Impeccable dark-mode rule): a machinist's workshop at
night: low ambient light, warm incandescent task lighting, dark oiled steel
surfaces. Dark mode is the only mode; warmth comes from the accent, the paper-
warm text, and the ember glow: never from a cream background.

## Color strategy: COMMITTED

One saturated molten amber carries the identity across 30–60% of key surfaces
(CTAs, active states, the landing forge visual). Everything else is warm
tinted-neutral steel. No second brand hue: ember orange exists only inside
the forge gradient and error/warn semantics.

| Token          | Value     | Role                                    |
| -------------- | --------- | --------------------------------------- |
| `--bg`         | `#0d0b08` | Page background (warm near-black)       |
| `--bg2`        | `#141109` | Raised background                       |
| `--panel`      | `#17140d` | Tile/panel surface                      |
| `--panel2`     | `#1e1a11` | Hover surface, inputs                   |
| `--line`       | `#2b2517` | Hairline borders (warm, not gray)       |
| `--line2`      | `#3d3520` | Strong borders, focus rings base        |
| `--text`       | `#f0ebdf` | Paper-warm primary text                 |
| `--dim`        | `#a99f8c` | Secondary text (≥4.5:1 on --bg)        |
| `--faint`      | `#6f6656` | Tertiary text, placeholders             |
| `--accent`     | `#ffb224` | Molten amber: CTAs, active, links      |
| `--accent2`    | `#ffc95e` | Amber hover/soft                        |
| `--ember`      | `#ff6b2c` | Ember orange: forge gradient only      |
| `--good`       | `#4ade80` | Success states                          |
| `--bad`        | `#f87171` | Failure states                          |
| `--warn`       | `#e8c252` | Warning states                          |

Neutrals carry ~0.008 chroma toward amber (warm), never default gray.
Body text contrast ≥ 4.5:1; `--faint` is never used for body copy.

## Typography

Pairing on contrast: **Space Grotesk** (geometric display) + **Inter**
(humanist UI) + **JetBrains Mono** (metrics/IDs). Never two similar sans.

- Hero (landing): `clamp(2.6rem, 5.6vw, 4.6rem)`, `-0.03em`, `text-wrap: balance`
- App h1: 26px/700/-0.02em; h2: 17px/650; h3: 14.5px/650
- Body: 14px Inter, 1.6 line-height; prose max 68ch, `text-wrap: pretty`
- All metrics/IDs/hashes: JetBrains Mono with `font-variant-numeric: tabular-nums`
- Display letter-spacing floor −0.04em (never tighter)

## Spacing & layout

4px base scale (4/8/12/16/24/32/48/64). Rhythm varies between sections :
landing sections breathe at 96–120px vertical, app content at 24px gaps.
Bento grid: 12-col, `repeat(12, 1fr)`, gap 14px. Cards have ONE level of
nesting maximum: never cards inside cards.

## Motion

Ease-out expo only: `cubic-bezier(0.16, 1, 0.3, 1)`. Entrances: 12–16px
translate + fade, 550–700ms, 40–60ms stagger. Never animate layout
properties; transform/opacity only. Every animation has a
`prefers-reduced-motion` fallback that renders final state immediately.

## Materials

Solid warm panels with 1px hairlines are the default surface. Exactly ONE
glass surface exists: the command palette (blur 18px). Modals are solid
panels with heavy shadow. The forge glow (amber radial) appears only on the
landing hero visual and the recommended plan card.

## Banned (the AI look: checked on every change)

Side-stripe accent borders · gradient text · decorative glassmorphism ·
SaaS hero-metric template · identical icon+heading+text card grids ·
uppercase tracked eyebrows on every section · numbered section markers ·
corners > 22px · blue-purple gradients of any kind.

## Voice

Plain, confident, specific. Numbers over adjectives ("−80% size", not
"dramatically smaller"). Errors say what happened and what to do next.
