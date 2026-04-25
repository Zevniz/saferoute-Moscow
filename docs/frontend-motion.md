# Frontend Motion System

## Motion Policy

The app uses one Motion policy at the root:

- `MotionConfig` with `reducedMotion="user"`.
- `LayoutGroup` for shared layout transitions.
- Route cards use `layout` and a shared `layoutId` beacon for active-card movement.

## Route Reveal

The map route reveal is real GeoJSON data animation:

1. `getProgressiveGeometry()` receives the selected route geometry and reveal progress.
2. The `Source` data is updated with a partial `LineString` or `MultiLineString`.
3. MapLibre renders the line progressively instead of faking the effect with CSS.

## Camera

After every successful route change, the app computes geometry bounds and calls `fitBounds()` with stage-specific padding. Navigation mode gets more top and bottom padding for the instruction chip and trip sheet.

## Navigation Mode

Navigation mode uses:

- `navigator.geolocation.watchPosition`
- nearest-route projection through `getRouteProgressForPosition()`
- active maneuver calculation with `begin_shape_index` and `end_shape_index`
- automatic reroute when the device stays off-route for consecutive GPS samples

If GPS permission is denied, the UI still shows the first real backend maneuver, but automatic maneuver progression is paused.

## Search

Search is debounced autocomplete backed by `/api/search`. Users can use mouse selection, Enter, ArrowUp, ArrowDown, and Escape. The browser does not call Nominatim directly.
