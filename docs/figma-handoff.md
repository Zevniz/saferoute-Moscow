# SafeRoute Figma handoff

Design source: [SafeRoute Apple Minimal Redesign](https://www.figma.com/design/hZn31Z6alrXnUoxyyKCrmq)

This file is the repo-local handoff for the Figma board created during the Apple Minimal redesign pass. The live implementation stays code-first in React, but the board is now the shared visual source for the current UI direction.

## Product direction

- Map-first layout: the map is the workspace, panels are lightweight overlays.
- Apple/Liquid Glass mood: translucent white glass, soft blur, squircle corners, calm blue accent.
- Russian-first utility copy: labels explain state and action, not marketing.
- No placeholders: live tabs only expose real search, routes, navigation, layers, and settings.

## Visual tokens

- Glass opacity: `0.72-0.86`.
- Blur: `26-36px`.
- Radius: `28-34px` for major panels, softer rounded pills for controls.
- Accent: SafeRoute blue, currently `#006FE6`.
- Shadows: ambient tinted blue shadows, minimal hard borders.

## Implemented in code

- App tabs: `Поиск`, `Маршруты`, `Навигация`, `Слои`, `Настройки`.
- Search: real `/api/search`, autocomplete, empty/error states.
- Routes: real `car`, `walk`, `bike`, active route beacon, ETA, distance, safety, calories when relevant.
- Navigation: real route `instructions[]`, GPS status, progress sheet.
- Layers: real UI map toggles only.
- Settings: `/api/health`, motion policy, routing source, Figma design source.

## Motion notes

- Shared policy: `MotionConfig reducedMotion="user"`.
- Panel and search entrance: `280-320ms` ease-out.
- Route cards: `40ms` stagger.
- Route reveal: real GeoJSON source animation.
- Camera: `fitBounds` from route geometry, not midpoint jumps.

## Access note

The Figma connector account that created the board is `rnva822@gmail.com`. If the browser shows "Request access", open Figma with that account or share the file from that account.
