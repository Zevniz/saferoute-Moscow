import { Accessibility, Bike, Car, Gauge, Layers as LayersIcon, Navigation2, Route, Scale, Search, Settings, ShieldCheck } from "lucide-react";

export const CURRENT_LOCATION = {
  lat: 55.7558,
  lon: 37.6173,
  label: "Моё местоположение",
};

export const INITIAL_VIEW_STATE = {
  longitude: CURRENT_LOCATION.lon,
  latitude: CURRENT_LOCATION.lat,
  zoom: 12.9,
  pitch: 45,
  bearing: -10,
};

export const MAP_STYLE = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json";
export const FIGMA_DESIGN_URL = "https://www.figma.com/design/hZn31Z6alrXnUoxyyKCrmq";
export const OFF_ROUTE_THRESHOLD_METERS = 85;
export const OFF_ROUTE_SAMPLE_LIMIT = 3;

export const PROFILE_OPTIONS = [
  { id: "car", label: "Авто", icon: Car },
  { id: "walk", label: "Пешком", icon: Route },
  { id: "bike", label: "Вело", icon: Bike },
];

export const SCORING_MODE_OPTIONS = [
  { id: "safest", label: "Самый безопасный", icon: ShieldCheck },
  { id: "fastest", label: "Самый быстрый", icon: Gauge },
  { id: "balanced", label: "Баланс", icon: Scale },
  { id: "accessible", label: "Доступный", icon: Accessibility },
];

export const APP_TABS = [
  { id: "search", label: "Поиск", shortLabel: "Поиск", icon: Search },
  { id: "routes", label: "Маршруты", shortLabel: "Маршр.", icon: Route },
  { id: "navigation", label: "Навигация", shortLabel: "Навиг.", icon: Navigation2 },
  { id: "layers", label: "Слои", shortLabel: "Слои", icon: LayersIcon },
  { id: "settings", label: "Настройки", shortLabel: "Настр.", icon: Settings },
];

export const TAB_COPY = {
  search: {
    title: "Поиск",
    subtitle: "Реальный autocomplete по Москве через SafeRoute API",
  },
  routes: {
    title: "Маршруты",
    subtitle: "Авто, пешком и вело без transit-заглушек",
  },
  navigation: {
    title: "Навигация",
    subtitle: "Манёвры из Valhalla и live GPS progress",
  },
  layers: {
    title: "Слои",
    subtitle: "Только реальные переключатели интерфейса карты",
  },
  settings: {
    title: "Настройки",
    subtitle: "Состояние runtime, GPS и motion policy",
  },
};

export const DEFAULT_LAYER_OPTIONS = {
  route: true,
  pins: true,
  gpsAccuracy: true,
  routeEmphasis: true,
  sidewalkQuality: false,
};

export const PANEL_TRANSITION = {
  duration: 0.32,
  ease: [0.22, 1, 0.36, 1],
};

export const OVERLAY_TRANSITION = {
  duration: 0.28,
  ease: [0.22, 1, 0.36, 1],
};
