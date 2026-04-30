import {
  Accessibility,
  Bike,
  Car,
  Gauge,
  HelpCircle,
  Map,
  Route,
  Scale,
  ShieldCheck,
} from "lucide-react";

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
export const FIGMA_DESIGN_URL = "https://www.figma.com/design/gkjKug87pDh4PmKIOVdKK7/iOS-and-iPadOS-26--Community-?node-id=215-105157&p=f&t=gXWxZ1gfEsQvfWiW-0";
export const OFF_ROUTE_THRESHOLD_METERS = 85;
export const OFF_ROUTE_SAMPLE_LIMIT = 3;

export const PROFILE_OPTIONS = [
  { id: "car", label: "Авто", shortLabel: "Авто", description: "Дорожный граф", icon: Car },
  { id: "walk", label: "Пешком", shortLabel: "Пешком", description: "Тротуары и переходы", icon: Route },
  { id: "bike", label: "Колёса", shortLabel: "Колёса", description: "Самокаты и велосипеды", icon: Bike },
];

export const SCORING_MODE_OPTIONS = [
  { id: "safest", label: "Безопасный", shortLabel: "Безопасно", description: "Меньше рискованных участков", icon: ShieldCheck },
  { id: "fastest", label: "Быстрый", shortLabel: "Время", description: "Минимальное время в пути", icon: Gauge },
  { id: "balanced", label: "Баланс", shortLabel: "Баланс", description: "Темп и спокойствие", icon: Scale },
  { id: "accessible", label: "Доступный", shortLabel: "Доступ", description: "Мягче к уклонам и ширине", icon: Accessibility },
];

export const APP_TABS = [
  { id: "route", label: "Маршрут", shortLabel: "Маршрут", icon: Route },
  { id: "map", label: "Карта", shortLabel: "Карта", icon: Map },
  { id: "about", label: "О сервисе", shortLabel: "О сервисе", icon: HelpCircle },
];

export const TAB_COPY = {
  route: {
    title: "Маршрут",
    subtitle: "Старт, финиш, режим и понятные варианты пути по Москве",
  },
  navigation: {
    title: "Навигация",
    subtitle: "Следующий манёвр и прогресс по выбранному маршруту",
  },
  map: {
    title: "Карта",
    subtitle: "Видимость маршрута, точек и вспомогательных оверлеев",
  },
  about: {
    title: "О сервисе",
    subtitle: "Что учитывает SafeRoute и где данные пока ограничены",
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
  type: "spring",
  stiffness: 420,
  damping: 38,
  mass: 0.86,
};

export const OVERLAY_TRANSITION = {
  duration: 0.24,
  ease: [0.22, 1, 0.36, 1],
};

export const PAGE_TRANSITION = {
  duration: 0.26,
  ease: [0.22, 1, 0.36, 1],
};

export const SHEET_TRANSITION = {
  type: "spring",
  stiffness: 360,
  damping: 36,
  mass: 0.9,
};

export const CARD_TRANSITION = {
  type: "spring",
  stiffness: 520,
  damping: 42,
  mass: 0.78,
};

export const PRESS_TRANSITION = {
  duration: 0.12,
  ease: [0.2, 0, 0, 1],
};
