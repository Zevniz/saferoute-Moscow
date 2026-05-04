# Liquid Glass UI

SafeRoute uses a restrained, Apple-inspired Liquid Glass interaction layer for floating controls. `liquid-glass-react` is kept as the package reference, but the live UI currently uses the CSS fallback layer because the native displacement layer produced an oversized translucent artifact in the in-app browser. It is not a brand copy and it is not a decorative skin for the whole product.

## Purpose

Liquid Glass is allowed only where it improves spatial hierarchy over the map:

- compact search and command toolbar;
- primary route actions such as “Построить маршрут” and “Начать навигацию”;
- navigation controls such as “Варианты” and “Завершить”;
- floating maneuver card and bottom trip sheet;
- map zoom/theme controls;
- compact segmented controls for profile and route priority.

The effect must make controls feel touchable and layered, while keeping the map readable.

## Do Not Use

Do not apply Liquid Glass to:

- long trust/explainability text;
- “Что мы знаем / Что мы не знаем” route details;
- beta safety limits, privacy copy, docs/about text;
- dense lists or settings rows;
- the full sidebar background;
- the map background or route line;
- inactive safety-layer explanations.

Long-form safety copy must stay calm, opaque, and highly readable. Для длинных блоков объяснений, trust-copy и ограничений публичной беты Liquid Glass не используется. Visual polish must never make limitations feel less important.

## Implementation

The reusable wrapper lives at:

`src/components/ui/LiquidGlassShell.jsx`

It supports:

- `variant`: `button`, `card`, `pill`, `toolbar`;
- `tone`: `neutral`, `primary`, `danger`, `success`;
- `interactive`;
- `disabled`;
- `className`;
- any normal DOM props, handlers, and ARIA labels.

The wrapper keeps the real semantic element (`button`, `form`, `div`, etc.) and renders the library effect as a non-interactive background layer. Click handlers, focus rings, keyboard navigation, and disabled states stay on the real control.

## Fallback

The live fallback renders a polished glass material using:

- `backdrop-filter`;
- translucent background tokens;
- a thin border;
- inner highlight;
- soft shadow.

The CSS tokens are:

- `--glass-bg`
- `--glass-bg-strong`
- `--glass-border`
- `--glass-highlight`
- `--glass-shadow`
- `--glass-blur`
- `--glass-radius-pill`
- `--glass-radius-card`
- `--glass-tint-primary`
- `--glass-tint-danger`

`liquid-glass-react` currently declares a React 19 peer dependency. SafeRoute is still on React 18, so `.npmrc` uses `legacy-peer-deps=true` for this compatibility bridge. The native layer should stay disabled until it is verified without layout artifacts. Remove that bridge when the app upgrades to React 19 or if the library is replaced.

## Accessibility

- Controls remain real semantic controls.
- Visible focus rings must not be removed.
- Disabled controls must look and behave disabled.
- No meaning may be conveyed by hover or glass distortion alone.
- Contrast must remain readable in light and dark theme.
- `prefers-reduced-motion` keeps the same readable CSS material and avoids extra distortion or elastic motion.

## Performance

- Do not wrap every chip or row.
- Keep the effect to a small number of floating/navigation elements.
- Do not apply the effect to map layers or repeated route timeline rows.
- Mobile uses the same functional controls, but CSS blur/tints must stay lightweight.

## Dark Mode

Dark mode uses separate glass tokens, darker translucent fills, weaker highlights, and stronger contrast for text. Route safety, beta-limit, and privacy text remains on readable surfaces rather than glass.
