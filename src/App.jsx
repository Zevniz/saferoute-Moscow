import React, { startTransition, useDeferredValue, useEffect, useRef, useState } from "react";
import { AnimatePresence, LayoutGroup, MotionConfig, animate, motion } from "framer-motion";
import Map, { Layer, Marker, Source } from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import {
  CheckCircle2,
  Compass,
  Eye,
  EyeOff,
  ExternalLink,
  Layers as LayersIcon,
  Loader2,
  Menu,
  Navigation2,
  Radio,
  RotateCcw,
  Route,
  Search,
  ShieldCheck,
} from "lucide-react";
import {
  APP_TABS,
  CURRENT_LOCATION,
  DEFAULT_LAYER_OPTIONS,
  INITIAL_VIEW_STATE,
  MAP_STYLE,
  PAGE_TRANSITION,
  PANEL_TRANSITION,
  PROFILE_OPTIONS,
  SCORING_MODE_OPTIONS,
  SHEET_TRANSITION,
} from "./config/safeRoute";
import {
  EmptyState,
  EndpointStack,
  NavigationInstructionCard,
  PanelHeader,
  RouteCard,
  SearchResults,
  StatusBanner,
  ToggleRow,
  TripSheet,
  WeatherChip,
} from "./components/AppPanels";
import { DataCoverageNote } from "./components/DataLayersStatus";
import { ErrorRecoveryCard, RouteEmptyState, RouteLoadingState, SearchEmptyState } from "./components/PlannerStates";
import { SegmentedControl } from "./components/RouteControls";
import { SafetyScorePanel } from "./components/SafetyScore";
import { NativeSection, StatusRow } from "./components/SystemList";
import { useHealth } from "./hooks/useHealth";
import { useSidewalkCells } from "./hooks/useSidewalkCells";
import {
  formatDistance,
  formatInstructionMeta,
  getDefaultRouteId,
  getGeometryBounds,
  getInstructionPresentation,
  getProgressiveGeometry,
  normalizeRoutePayload,
} from "./lib/route-utils";
import { buildDestinationLabel, cn, getViewportPadding } from "./lib/ui";
import { useNavigationProgress } from "./hooks/useNavigationProgress";
import { useRoutes } from "./hooks/useRoutes";
import { useSearch } from "./hooks/useSearch";

export default function App() {
  const mapRef = useRef(null);
  const searchInputRef = useRef(null);
  const commandNavRef = useRef(null);
  const requestIdRef = useRef(0);

  const [query, setQuery] = useState("");
  const [origin, setOrigin] = useState(CURRENT_LOCATION);
  const [destination, setDestination] = useState(null);
  const [activeEndpoint, setActiveEndpoint] = useState("destination");
  const [profile, setProfile] = useState("walk");
  const [routeMode, setRouteMode] = useState("safest");
  const [plannerStage, setPlannerStage] = useState("idle");
  const [activeTab, setActiveTab] = useState("route");
  const [routes, setRoutes] = useState([]);
  const [selectedRouteId, setSelectedRouteId] = useState(null);
  const [feedback, setFeedback] = useState(null);
  const [panelOpen, setPanelOpen] = useState(true);
  const [sectionMenuOpen, setSectionMenuOpen] = useState(false);
  const [layerOptions, setLayerOptions] = useState(DEFAULT_LAYER_OPTIONS);
  const [routeProgress, setRouteProgress] = useState(0);
  const [searchResults, setSearchResults] = useState([]);
  const [highlightedResultIndex, setHighlightedResultIndex] = useState(0);
  const [isAutocompleteOpen, setIsAutocompleteOpen] = useState(false);
  const { health, loading: isHealthLoading, loadHealth } = useHealth();
  const postgresReady = health?.services?.postgres?.status === "ok";
  const sidewalkCellsAwaitingHealth = layerOptions.sidewalkQuality && !health;
  const sidewalkCellsBlocked = layerOptions.sidewalkQuality && health && !postgresReady;
  const {
    cells: sidewalkCells,
    loading: sidewalkCellsLoading,
    error: sidewalkCellsError,
  } = useSidewalkCells({ enabled: layerOptions.sidewalkQuality && postgresReady, mapRef });
  const { loading: isSearching, search } = useSearch();
  const { loading: isRouting, loadRoutes } = useRoutes();

  const selectedRoute = routes.find((route) => route.id === selectedRouteId) ?? routes[0] ?? null;
  const deferredQuery = useDeferredValue(query);
  const {
    activeInstructionIndex,
    gpsStatus,
    livePosition,
    rerouting: isRerouting,
    setActiveInstructionIndex,
  } = useNavigationProgress({
    enabled: plannerStage === "navigating",
    selectedRoute,
    destination,
    profile,
    onReroute: ({ origin: nextOrigin, destination: nextDestination, profile: nextProfile }) =>
      requestRoutes({
        nextProfile,
        nextOrigin,
        nextDestination,
        successStage: "navigating",
        failureStage: "navigating",
      }),
  });
  const animatedGeometry = selectedRoute ? getProgressiveGeometry(selectedRoute.geometry, routeProgress) : null;
  const animatedRoute = selectedRoute && animatedGeometry ? { ...selectedRoute, geometry: animatedGeometry } : null;
  const activeInstructions = selectedRoute?.properties?.instructions ?? [];
  const activeInstruction = activeInstructions[activeInstructionIndex] ?? activeInstructions[0] ?? null;
  const nextInstruction = activeInstructions[activeInstructionIndex + 1] ?? null;
  const navigationHint = getInstructionPresentation(activeInstruction, nextInstruction);
  const originMarker = plannerStage === "navigating" && livePosition ? livePosition : origin;
  const primaryActionLabel = selectedRoute ? "Начать навигацию" : "Построить маршрут";
  const primaryActionBusy = isSearching || isRouting;
  const plannerVisible = plannerStage !== "navigating" || panelOpen;
  const commandBarVisible = plannerStage !== "navigating";
  const activeSearchPoint = activeEndpoint === "origin" ? origin : destination;
  const searchPlaceholder = activeEndpoint === "origin" ? "Откуда начнём маршрут?" : "Куда едем по Москве?";
  const searchAriaLabel = activeEndpoint === "origin" ? "Введите точку отправления" : "Введите точку назначения";
  const mobileSheetState = selectedRoute && activeTab === "route" ? "medium" : "expanded";
  const activeAppTab = APP_TABS.find((tab) => tab.id === activeTab) ?? APP_TABS[0];

  useEffect(() => {
    loadHealth();
  }, []);

  useEffect(() => {
    if (!sectionMenuOpen) {
      return undefined;
    }

    function handlePointerDown(event) {
      if (commandNavRef.current?.contains(event.target)) {
        return;
      }
      setSectionMenuOpen(false);
    }

    function handleEscape(event) {
      if (event.key === "Escape") {
        setSectionMenuOpen(false);
      }
    }

    window.addEventListener("pointerdown", handlePointerDown);
    window.addEventListener("keydown", handleEscape);

    return () => {
      window.removeEventListener("pointerdown", handlePointerDown);
      window.removeEventListener("keydown", handleEscape);
    };
  }, [sectionMenuOpen]);

  useEffect(() => {
    if (!selectedRoute) {
      setRouteProgress(0);
      return undefined;
    }

    setRouteProgress(0);
    const controls = animate(0, 1, {
      duration: 0.72,
      ease: [0.2, 0, 0, 1],
      onUpdate: (value) => setRouteProgress(value),
    });

    return () => controls.stop();
  }, [selectedRoute?.id]);

  useEffect(() => {
    if (!selectedRoute) {
      return undefined;
    }

    const bounds = getGeometryBounds(selectedRoute.geometry);
    if (!bounds) {
      return undefined;
    }

    const timeoutId = window.setTimeout(() => {
      mapRef.current?.fitBounds(bounds, {
        padding: getViewportPadding(plannerStage),
        duration: 1250,
        maxZoom: plannerStage === "navigating" ? 14.8 : 14.2,
      });
    }, 120);

    return () => window.clearTimeout(timeoutId);
  }, [plannerStage, selectedRoute?.id]);

  useEffect(() => {
    const trimmedQuery = deferredQuery.trim();
    if (!plannerVisible || trimmedQuery.length < 2 || trimmedQuery === activeSearchPoint?.label) {
      setSearchResults([]);
      setIsAutocompleteOpen(false);
      return undefined;
    }

    const controller = new AbortController();
    const timeoutId = window.setTimeout(async () => {
      setIsAutocompleteOpen(true);
      try {
        const payload = await search(trimmedQuery, 5, {
          signal: controller.signal,
        });
        startTransition(() => {
          setSearchResults(payload);
          setHighlightedResultIndex(0);
        });
      } catch (error) {
        if (error.name !== "AbortError") {
          startTransition(() => {
            setSearchResults([]);
            setFeedback({ type: "error", message: error.message || "Поиск временно недоступен" });
          });
        }
      }
    }, 260);

    return () => {
      controller.abort();
      window.clearTimeout(timeoutId);
    };
  }, [activeSearchPoint?.label, deferredQuery, plannerVisible, search]);

  async function requestRoutes({
    nextProfile = profile,
    nextOrigin = origin,
    nextDestination = destination,
    nextMode = routeMode,
    successStage = "planned",
    failureStage = "idle",
  } = {}) {
    if (!nextDestination) {
      startTransition(() => {
        setFeedback({
          type: "neutral",
          message: "Сначала выберите точку назначения, и мы построим маршрут.",
        });
      });
      return;
    }

    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;

    startTransition(() => {
      setFeedback(null);
      setPlannerStage(successStage === "navigating" ? "navigating" : "loading");
    });

    try {
      const payload = await loadRoutes({
        origin: nextOrigin,
        destination: nextDestination,
        profile: nextProfile,
        mode: nextMode,
        alternatives: 3,
      });

      const normalized = normalizeRoutePayload(payload, {
        profile: nextProfile,
        origin: nextOrigin,
        destination: nextDestination,
      });

      if (!normalized.routes.length) {
        throw new Error("Маршрут не найден для выбранного режима.");
      }

      if (requestId !== requestIdRef.current) {
        return;
      }

      const defaultRouteId = getDefaultRouteId(normalized.routes, nextProfile);
      startTransition(() => {
        setOrigin(nextOrigin);
        setRoutes(normalized.routes);
        setSelectedRouteId(defaultRouteId);
        setPlannerStage(successStage);
        setActiveTab("route");
        setFeedback(null);
      });
    } catch (error) {
      if (requestId !== requestIdRef.current) {
        return;
      }

      startTransition(() => {
        setRoutes(successStage === "navigating" ? routes : []);
        setSelectedRouteId(successStage === "navigating" ? selectedRouteId : null);
        setPlannerStage(failureStage);
        setFeedback({
          type: "error",
          message: error.message || "Маршрут временно недоступен.",
        });
      });
    } finally {
      // `useRoutes` manages the shared loading state.
    }
  }

  function focusSearchField() {
    window.requestAnimationFrame(() => {
      searchInputRef.current?.focus();
      searchInputRef.current?.select();
    });
  }

  function formatMapPointLabel(endpoint, point) {
    const prefix = endpoint === "origin" ? "Старт на карте" : "Финиш на карте";
    return `${prefix}: ${point.lat.toFixed(5)}, ${point.lon.toFixed(5)}`;
  }

  async function applyEndpointPoint(endpoint, point, { flyTo = true } = {}) {
    const nextOrigin = endpoint === "origin" ? point : origin;
    const nextDestination = endpoint === "destination" ? point : destination;

    startTransition(() => {
      if (endpoint === "origin") {
        setOrigin(point);
      } else {
        setDestination(point);
      }
      setQuery(point.label);
      setSearchResults([]);
      setIsAutocompleteOpen(false);
      setPanelOpen(true);
      setActiveTab("route");
      setSectionMenuOpen(false);
      setFeedback(null);
      if (!nextDestination) {
        setRoutes([]);
        setSelectedRouteId(null);
        setPlannerStage("idle");
      }
    });

    if (flyTo) {
      mapRef.current?.flyTo({
        center: [point.lon, point.lat],
        zoom: 14.2,
        duration: 1100,
      });
    }

    if (nextDestination) {
      await requestRoutes({
        nextProfile: profile,
        nextOrigin,
        nextDestination,
      });
    }
  }

  async function chooseSearchResult(result) {
    const nextPoint = {
      lat: Number(result.lat),
      lon: Number(result.lon),
      label: buildDestinationLabel(result, query.trim()),
      kind: result.kind,
    };

    await applyEndpointPoint(activeEndpoint, nextPoint);
  }

  function handleEndpointSelect(endpoint) {
    setActiveEndpoint(endpoint);
    setPanelOpen(true);
    setSectionMenuOpen(false);
    setActiveTab("route");
    setQuery(endpoint === "origin" ? origin.label : destination?.label ?? "");
    setSearchResults([]);
    setIsAutocompleteOpen(false);
    setFeedback({
      type: "neutral",
      message:
        endpoint === "origin"
          ? "Введите старт в верхней строке или кликните точку на карте."
          : "Введите финиш в верхней строке или кликните точку на карте.",
    });
    focusSearchField();
  }

  async function handleMapClick(event) {
    if (plannerStage === "navigating") {
      return;
    }

    const lngLat = event.lngLat;
    if (!lngLat) {
      return;
    }

    const nextPoint = {
      lat: Number(lngLat.lat),
      lon: Number(lngLat.lng),
      label: formatMapPointLabel(activeEndpoint, { lat: Number(lngLat.lat), lon: Number(lngLat.lng) }),
      kind: "map",
    };

    await applyEndpointPoint(activeEndpoint, nextPoint, { flyTo: false });
  }

  async function handleSearch(event) {
    event.preventDefault();
    const trimmedQuery = query.trim();

    if (!trimmedQuery) {
      startTransition(() => {
        setFeedback({
          type: "neutral",
          message: "Введите адрес, название места или ориентир в Москве.",
        });
      });
      return;
    }

    setPanelOpen(true);
    startTransition(() => {
      setActiveTab("route");
      setSectionMenuOpen(false);
      setFeedback(null);
    });

    try {
      const result = searchResults[highlightedResultIndex] ?? searchResults[0];
      if (result) {
        await chooseSearchResult(result);
        return;
      }

      const results = await search(trimmedQuery, 5);
      if (!results.length) {
        throw new Error("Ничего не найдено. Попробуйте другой адрес или ориентир.");
      }
      await chooseSearchResult(results[0]);
    } catch (error) {
      startTransition(() => {
        setPlannerStage("idle");
        setFeedback({
          type: "error",
          message: error.message || "Не удалось найти место на карте.",
        });
      });
    }
  }

  function handleSearchKeyDown(event) {
    if (!isAutocompleteOpen || !searchResults.length) {
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlightedResultIndex((index) => (index + 1) % searchResults.length);
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlightedResultIndex((index) => (index - 1 + searchResults.length) % searchResults.length);
    }

    if (event.key === "Escape") {
      setIsAutocompleteOpen(false);
    }
  }

  async function handleSwap() {
    if (!destination) {
      startTransition(() => {
        setFeedback({
          type: "neutral",
          message: "Сначала выберите точку назначения, чтобы поменять точки местами.",
        });
      });
      return;
    }

    const nextOrigin = destination;
    const nextDestination = origin;

    startTransition(() => {
      setOrigin(nextOrigin);
      setDestination(nextDestination);
      setQuery(nextDestination.label);
      setActiveEndpoint("destination");
      setFeedback(null);
    });

    await requestRoutes({
      nextProfile: profile,
      nextOrigin,
      nextDestination,
    });
  }

  async function handleProfileChange(nextProfile) {
    if (nextProfile === profile) {
      return;
    }

    startTransition(() => {
      setProfile(nextProfile);
      setActiveTab("route");
      setFeedback(null);
    });

    if (destination) {
      await requestRoutes({
        nextProfile,
        nextOrigin: origin,
        nextDestination: destination,
      });
    }
  }

  async function handleRouteModeChange(nextMode) {
    if (nextMode === routeMode) {
      return;
    }

    startTransition(() => {
      setRouteMode(nextMode);
      setActiveTab("route");
      setFeedback(null);
    });

    if (destination) {
      await requestRoutes({
        nextProfile: profile,
        nextOrigin: origin,
        nextDestination: destination,
        nextMode,
      });
    }
  }

  function handleStartNavigation() {
    if (!selectedRoute) {
      if (destination) {
        requestRoutes();
      } else {
        startTransition(() => {
          setFeedback({
            type: "neutral",
            message: "Найдите точку назначения, чтобы начать навигацию.",
          });
        });
      }
      return;
    }

    startTransition(() => {
      setPlannerStage("navigating");
      setActiveTab("route");
      setPanelOpen(false);
      setSectionMenuOpen(false);
      setFeedback(null);
      setActiveInstructionIndex(0);
    });
  }

  function handleResetRoute() {
    startTransition(() => {
      setRoutes([]);
      setSelectedRouteId(null);
      setPlannerStage("idle");
      setActiveTab("route");
      setSectionMenuOpen(false);
      setFeedback(null);
    });
  }

  function handleShowPlanner() {
    startTransition(() => {
      setActiveTab("route");
      setPanelOpen(true);
      setSectionMenuOpen(false);
    });
  }

  function handleShowRouteOptions() {
    startTransition(() => {
      setPlannerStage("planned");
      setActiveTab("route");
      setPanelOpen(true);
      setSectionMenuOpen(false);
    });
  }

  function handleTabSelect(tabId) {
    startTransition(() => {
      setActiveTab(tabId);
      setPanelOpen(true);
      setSectionMenuOpen(false);
    });

    if (tabId === "about") {
      loadHealth();
    }
  }

  function handleSectionMenuToggle() {
    startTransition(() => {
      setPanelOpen(true);
      setSectionMenuOpen((open) => !open);
    });
  }

  function handleMapZoom(delta) {
    const map = mapRef.current?.getMap?.() ?? mapRef.current;
    if (!map) {
      return;
    }

    if (delta > 0 && typeof map.zoomIn === "function") {
      map.zoomIn({ duration: 220 });
      return;
    }

    if (delta < 0 && typeof map.zoomOut === "function") {
      map.zoomOut({ duration: 220 });
      return;
    }

    const currentZoom = typeof map.getZoom === "function" ? map.getZoom() : INITIAL_VIEW_STATE.zoom;
    map.zoomTo?.(currentZoom + delta, { duration: 220 });
  }

  function renderSectionMenu() {
    return (
      <AnimatePresence>
        {sectionMenuOpen ? (
          <motion.div
            className="section-menu material-panel"
            role="dialog"
            aria-label="Меню разделов SafeRoute"
            initial={{ opacity: 0, y: -8, scale: 0.975 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.985 }}
            transition={PAGE_TRANSITION}
          >
            <div className="section-menu-header">
              <div>
                <p className="section-menu-kicker">Разделы</p>
                <p className="section-menu-title">Что открыть?</p>
              </div>
              <span className="section-menu-current">{activeAppTab.shortLabel ?? activeAppTab.label}</span>
            </div>
            <nav className="section-menu-list" aria-label="Разделы SafeRoute">
              {APP_TABS.map((tab) => {
                const Icon = tab.icon;
                const active = activeTab === tab.id;

                return (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => handleTabSelect(tab.id)}
                    className={cn("section-menu-item", active && "section-menu-item-active")}
                    aria-current={active ? "page" : undefined}
                  >
                    <span className="section-menu-item-icon" aria-hidden="true">
                      <Icon size={18} />
                    </span>
                    <span className="section-menu-item-copy">
                      <span className="section-menu-item-title">{tab.label}</span>
                      <span className="section-menu-item-subtitle">
                        {tab.id === "route"
                          ? "Поиск, режим и варианты пути"
                          : tab.id === "map"
                            ? "Видимость маршрута и точек"
                            : "Бета, источники и честные ограничения"}
                      </span>
                    </span>
                  </button>
                );
              })}
            </nav>
            <p className="section-menu-note">
              Главный экран остаётся про маршрут. Служебные данные и настройки карты живут здесь, чтобы не перегружать поиск.
            </p>
          </motion.div>
        ) : null}
      </AnimatePresence>
    );
  }

  function toggleLayerOption(optionId) {
    setLayerOptions((current) => ({
      ...current,
      [optionId]: !current[optionId],
    }));
  }

  function renderAttributionLinks(className = "") {
    return (
      <div className={cn("text-[11px] font-semibold text-on-surface-variant", className)} aria-label="Атрибуция карты и данных">
        <a
          className="text-primary underline-offset-2 hover:underline"
          href="https://www.openstreetmap.org/copyright"
          target="_blank"
          rel="noreferrer"
        >
          © OpenStreetMap contributors
        </a>
        <span className="mx-1 text-outline">·</span>
        <a
          className="text-primary underline-offset-2 hover:underline"
          href="https://carto.com/attributions"
          target="_blank"
          rel="noreferrer"
        >
          CARTO
        </a>
      </div>
    );
  }

  function renderRouteEndpointSummary() {
    if (!selectedRoute || !destination) {
      return (
        <EndpointStack
          origin={origin}
          destination={destination}
          activeEndpoint={activeEndpoint}
          onSelectEndpoint={handleEndpointSelect}
          onSwap={handleSwap}
        />
      );
    }

    return (
      <div className="route-trip-summary">
        <div className="route-trip-summary-main">
          <div className="route-trip-point">
            <span className="route-trip-dot route-trip-dot-origin" aria-hidden="true" />
            <span className="truncate">{origin.label}</span>
          </div>
          <div className="route-trip-point">
            <span className="route-trip-dot route-trip-dot-destination" aria-hidden="true" />
            <span className="truncate">{destination.label}</span>
          </div>
        </div>
        <div className="route-trip-actions">
          <button type="button" onClick={() => handleEndpointSelect("origin")} className="route-trip-edit">
            Старт
          </button>
          <button type="button" onClick={() => handleEndpointSelect("destination")} className="route-trip-edit">
            Финиш
          </button>
        </div>
      </div>
    );
  }

  function renderPanelContent() {
    if (activeTab === "map") {
      return (
        <div className="min-h-0 flex-1 overflow-y-auto pr-2">
          <div className="space-y-5">
            <NativeSection title="На карте" eyebrow="Отображение">
              <ToggleRow
                icon={layerOptions.pins ? Eye : EyeOff}
                title="Точки маршрута"
                subtitle="Показывает старт, финиш и текущую позицию во время навигации."
                enabled={layerOptions.pins}
                onToggle={() => toggleLayerOption("pins")}
              />
              <ToggleRow
                icon={Radio}
                title="Точность GPS"
                subtitle="Мягкий радиус вокруг текущей позиции. Не меняет маршрут и оценку."
                enabled={layerOptions.gpsAccuracy}
                onToggle={() => toggleLayerOption("gpsAccuracy")}
              />
            </NativeSection>

            <NativeSection title="Линия маршрута" eyebrow="Визуализация">
              <ToggleRow
                icon={layerOptions.route ? Eye : EyeOff}
                title="Показывать маршрут"
                subtitle="Включает выбранную GeoJSON-линию на карте."
                enabled={layerOptions.route}
                onToggle={() => toggleLayerOption("route")}
              />
              <ToggleRow
                icon={Compass}
                title="Акцент выбранного пути"
                subtitle="Делает активную линию заметнее без изменения геометрии."
                enabled={layerOptions.routeEmphasis}
                onToggle={() => toggleLayerOption("routeEmphasis")}
              />
            </NativeSection>
            {sidewalkCells?.features?.length ? (
              <NativeSection title="Оверлеи" eyebrow="Реальные наблюдения">
                <ToggleRow
                  icon={ShieldCheck}
                  title="Ячейки качества тротуаров"
                  subtitle={`Показано ${sidewalkCells.features.length} H3-ячеек качества и свежести.`}
                  enabled={layerOptions.sidewalkQuality}
                  onToggle={() => toggleLayerOption("sidewalkQuality")}
                />
              </NativeSection>
            ) : null}
          </div>
        </div>
      );
    }

    if (plannerStage === "navigating") {
      const instructions = selectedRoute?.properties?.instructions ?? [];
      const currentInstruction = instructions[activeInstructionIndex] ?? instructions[0] ?? null;
      const nextPanelInstruction = instructions[activeInstructionIndex + 1] ?? null;

      return (
        <div className="flex min-h-0 flex-1 flex-col">
          {selectedRoute ? (
            <>
              <div className="navigation-overview quiet-panel mb-4 rounded-[1.2rem] px-4 py-4">
                <div className="flex items-start gap-3">
                  <div className="navigation-overview-icon inline-flex h-11 w-11 items-center justify-center rounded-[0.9rem] bg-primary text-on-primary">
                    {isRerouting ? <Loader2 size={19} className="animate-spin" /> : <Navigation2 size={19} />}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-bold text-outline">
                      {isRerouting ? "Перестраиваем" : "Следующий манёвр"}
                    </div>
                    <div className="mt-1 line-clamp-2 text-base font-black leading-5 tracking-tight text-on-surface">
                      {isRerouting ? "Ищем лучший путь" : navigationHint.title}
                    </div>
                    <div className="mt-2 text-sm font-medium leading-5 text-on-surface-variant">
                      {gpsStatus || navigationHint.subtitle}
                    </div>
                    <div className="navigation-overview-metrics mt-3 grid grid-cols-2 gap-2 text-sm font-bold text-on-surface">
                      <span>{selectedRoute.properties?.estimated_mins ?? "--"} мин</span>
                      <span>{formatDistance(selectedRoute.properties?.distance_m)}</span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="navigation-panel-actions mb-4 grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={handleShowRouteOptions}
                  className="secondary-route-button inline-flex items-center justify-center gap-2 rounded-full bg-white/62 px-4 py-3 text-sm font-bold text-on-surface-variant transition-all hover:bg-white/78 active:scale-[0.985]"
                >
                  <Route size={15} />
                  Варианты
                </button>
                <button
                  type="button"
                  onClick={() => handleTabSelect("map")}
                  className="secondary-route-button inline-flex items-center justify-center gap-2 rounded-full bg-white/62 px-4 py-3 text-sm font-bold text-on-surface-variant transition-all hover:bg-white/78 active:scale-[0.985]"
                >
                  <LayersIcon size={15} />
                  Карта
                </button>
              </div>

              <div className="min-h-0 flex-1 overflow-y-auto pr-2">
                {nextPanelInstruction ? (
                  <div className="instruction-next-card mb-3 rounded-[1rem] bg-white/58 px-4 py-3">
                    <div className="text-xs font-bold text-outline">После этого</div>
                    <div className="mt-1 text-sm font-bold text-on-surface">{nextPanelInstruction.text}</div>
                    <div className="mt-1 text-xs font-medium text-outline">{formatInstructionMeta(nextPanelInstruction)}</div>
                  </div>
                ) : null}

                <details className="maneuver-list-details" open={false}>
                  <summary className="maneuver-list-summary">
                    <span>Все манёвры</span>
                    <span>{instructions.length || 0}</span>
                  </summary>
                  <div className="mt-2 space-y-2 pb-4">
                    {instructions.slice(0, 24).map((instruction, index) => (
                      <button
                        key={`${instruction.index}-${instruction.begin_shape_index}-${index}`}
                        type="button"
                        onClick={() => setActiveInstructionIndex(index)}
                        className={cn(
                          "instruction-row flex w-full items-start gap-3 rounded-[1rem] px-4 py-3 text-left transition-all",
                          index === activeInstructionIndex ? "bg-white/82 text-on-surface" : "hover:bg-white/55",
                        )}
                      >
                        <span className={cn("mt-1 h-2.5 w-2.5 rounded-full", index === activeInstructionIndex ? "bg-primary" : "bg-outline-variant")} />
                        <span className="min-w-0 flex-1">
                          <span className="block text-sm font-bold text-on-surface">{instruction.text}</span>
                          <span className="mt-1 block text-xs font-medium text-outline">
                            {formatInstructionMeta(instruction)}
                          </span>
                        </span>
                      </button>
                    ))}
                  </div>
                </details>
                {currentInstruction ? (
                  <p className="mt-3 text-xs font-medium leading-5 text-outline">
                    Подсказки взяты из рассчитанного маршрута. SafeRoute не добавляет выдуманные повороты.
                  </p>
                ) : null}
              </div>

              <div className="mt-4">
                <button
                  type="button"
                  onClick={handleResetRoute}
                  className="primary-route-button inline-flex w-full items-center justify-center gap-2 rounded-full bg-error px-4 py-4 text-sm font-bold text-on-error transition-all active:scale-[0.985]"
                >
                  Завершить
                </button>
              </div>
            </>
          ) : (
            <EmptyState title="Навигация появится после маршрута" icon={Navigation2}>
              Сначала выберите точку назначения и реальную альтернативу. Здесь появятся манёвры без эвристических подсказок.
            </EmptyState>
          )}
        </div>
      );
    }

    if (activeTab === "legacy-search") {
      return (
        <div className="flex min-h-0 flex-1 flex-col">
          <div className="mb-5">
            <EndpointStack
              origin={origin}
              destination={destination}
              activeEndpoint={activeEndpoint}
              onSelectEndpoint={handleEndpointSelect}
              onSwap={handleSwap}
            />
          </div>

          <AnimatePresence mode="wait">
            <StatusBanner feedback={feedback} loading={isRouting} />
          </AnimatePresence>

          <div className="min-h-0 flex-1 overflow-y-auto pr-2">
            <SearchEmptyState />

            {destination ? (
              <motion.button
                type="button"
                layout
                onClick={() => handleTabSelect("route")}
                className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-full bg-white/66 px-5 py-3 text-sm font-bold text-on-surface-variant transition-all hover:bg-white/82 active:scale-[0.985]"
              >
                <Route size={15} />
                Открыть варианты маршрута
              </motion.button>
            ) : null}
          </div>
        </div>
      );
    }
    if (activeTab === "legacy-navigation") {
      const instructions = selectedRoute?.properties?.instructions ?? [];

      return (
        <div className="flex min-h-0 flex-1 flex-col">
          {selectedRoute ? (
            <>
              <div className="quiet-panel mb-4 rounded-[1.55rem] px-5 py-5">
                <div className="flex items-center gap-3">
                  <div className="inline-flex h-12 w-12 items-center justify-center rounded-[1.15rem] soul-gradient text-on-primary">
                    {isRerouting ? <Loader2 size={20} className="animate-spin" /> : <Navigation2 size={20} />}
                  </div>
                  <div className="min-w-0">
                    <div className="truncate text-lg font-black tracking-tight text-on-surface">
                      {isRerouting ? "Перестраиваем маршрут" : navigationHint.title}
                    </div>
                    <div className="mt-1 truncate text-sm font-medium text-on-surface-variant">
                      {gpsStatus || navigationHint.subtitle}
                    </div>
                  </div>
                </div>
              </div>

              <div className="min-h-0 flex-1 overflow-y-auto pr-2">
                <div className="space-y-2 pb-4">
                  {instructions.slice(0, 12).map((instruction, index) => (
                    <button
                      key={`${instruction.index}-${instruction.begin_shape_index}-${index}`}
                      type="button"
                      onClick={() => setActiveInstructionIndex(index)}
                      className={cn(
                        "instruction-row flex w-full items-start gap-3 rounded-[1.2rem] px-4 py-3 text-left transition-all",
                        index === activeInstructionIndex ? "bg-white/82 text-on-surface" : "hover:bg-white/55",
                      )}
                    >
                      <span className={cn("mt-1 h-2.5 w-2.5 rounded-full", index === activeInstructionIndex ? "bg-primary" : "bg-outline-variant")} />
                      <span className="min-w-0 flex-1">
                        <span className="block text-sm font-bold text-on-surface">{instruction.text}</span>
                        <span className="mt-1 block text-xs font-medium text-outline">
                          {formatInstructionMeta(instruction)}
                        </span>
                      </span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="mt-4 grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={handleStartNavigation}
                  className="soul-gradient inline-flex items-center justify-center gap-2 rounded-full px-4 py-4 text-sm font-bold text-on-primary shadow-[0_18px_36px_rgba(0,88,188,0.2)] transition-all active:scale-[0.985]"
                >
                  <Navigation2 size={15} />
                  Поехали
                </button>
                <button
                  type="button"
                  onClick={handleResetRoute}
                  className="inline-flex items-center justify-center gap-2 rounded-full bg-white/62 px-4 py-4 text-sm font-bold text-on-surface-variant transition-all hover:bg-white/78 active:scale-[0.985]"
                >
                  <RotateCcw size={15} />
                  Завершить
                </button>
              </div>
            </>
          ) : (
            <EmptyState title="Навигация появится после маршрута" icon={Navigation2}>
              Сначала выберите точку назначения и реальную альтернативу. Здесь появятся реальные манёвры маршрута без эвристических подсказок.
            </EmptyState>
          )}
        </div>
      );
    }

    if (activeTab === "legacy-layers") {
      return (
        <div className="min-h-0 flex-1 overflow-y-auto pr-2">
          <div className="space-y-5">
            <NativeSection title="Карта" eyebrow="Отображение">
              <ToggleRow
                icon={layerOptions.pins ? Eye : EyeOff}
                title="Пины старта и финиша"
                subtitle="Показывает выбранные точки маршрута на карте."
                enabled={layerOptions.pins}
                onToggle={() => toggleLayerOption("pins")}
              />
              <ToggleRow
                icon={Radio}
                title="Пульс GPS"
                subtitle="Показывает визуальную точность текущей позиции."
                enabled={layerOptions.gpsAccuracy}
                onToggle={() => toggleLayerOption("gpsAccuracy")}
              />
            </NativeSection>

            <NativeSection title="Маршрут" eyebrow="Визуализация">
              <ToggleRow
                icon={layerOptions.route ? Eye : EyeOff}
                title="Линия маршрута"
                subtitle="Включает GeoJSON-линию выбранного варианта."
                enabled={layerOptions.route}
                onToggle={() => toggleLayerOption("route")}
              />
              <ToggleRow
                icon={Compass}
                title="Акцент маршрута"
                subtitle="Делает выбранную линию заметнее, не меняя геометрию."
                enabled={layerOptions.routeEmphasis}
                onToggle={() => toggleLayerOption("routeEmphasis")}
              />
            </NativeSection>

            <NativeSection title="Данные" eyebrow="Доступность">
              <ToggleRow
                icon={ShieldCheck}
                title="Ячейки телеметрии"
                subtitle={
                  sidewalkCellsLoading
                    ? "Загружаем реальные H3-агрегаты..."
                    : sidewalkCellsAwaitingHealth || isHealthLoading
                      ? "Проверяем PostGIS перед загрузкой H3-слоя..."
                    : sidewalkCellsBlocked
                      ? "PostGIS сейчас недоступен; слой включится после восстановления API."
                      : sidewalkCellsError
                      ? sidewalkCellsError
                      : sidewalkCells?.features?.length
                        ? `Показано ${sidewalkCells.features.length} H3-ячеек качества и свежести.`
                        : "Слой доступен только при реальных агрегатах; сейчас данных нет."
                }
                enabled={layerOptions.sidewalkQuality}
                onToggle={() => toggleLayerOption("sidewalkQuality")}
              />
              <StatusRow
                icon={ShieldCheck}
                title="Покрытие, тротуары, свет и переходы"
                subtitle="Активные слои приходят из проверенных OSM-данных и отражаются в оценке только при наличии данных."
                tone="success"
              />
            </NativeSection>

            <NativeSection title="Пока недоступно" eyebrow="Без имитации">
              <StatusRow
                icon={LayersIcon}
                title="Бордюры, зоны СИМ, трафик, плотность пешеходов и телеметрия"
                subtitle="Не отображаются как активные и не влияют на оценку, пока нет легального источника и проверки."
                tone="muted"
              />
            </NativeSection>
          </div>
        </div>
      );
    }

    if (activeTab === "about") {
      return (
        <div className="min-h-0 flex-1 overflow-y-auto pr-2">
          <div className="space-y-5">
            <NativeSection title="Публичная бета" eyebrow="Коротко">
              <StatusRow
                icon={ShieldCheck}
                title="Маршруты строятся по реальному графу Москвы"
                subtitle="Оценка использует активные OSM-факторы, переходы и только те причины, которые вернул API."
                tone="success"
              />
              <StatusRow
                icon={LayersIcon}
                title="Ограниченные слои не подменяются"
                subtitle="Бордюры, зоны СИМ, измеренный трафик, плотность пешеходов и телеметрия не влияют на маршрут без проверенных данных."
                tone="muted"
              />
            </NativeSection>

            <NativeSection title="Комфорт" eyebrow="Интерфейс">
              <StatusRow
                icon={CheckCircle2}
                title="Мягкие анимации"
                subtitle="Движение интерфейса спокойное и уменьшается, если это задано в системных настройках."
                tone="success"
              />
              <StatusRow
                icon={ShieldCheck}
                title="Проверенный маршрут"
                subtitle={selectedRoute ? "Построен по реальному графу и возвращён API без подмены причин." : "Появится после построения маршрута."}
                tone={selectedRoute ? "success" : "neutral"}
              />
              <a
                href="https://www.openstreetmap.org/copyright"
                target="_blank"
                rel="noreferrer"
                className="native-row native-row-neutral transition-all hover:bg-white active:scale-[0.99]"
              >
                <div className="native-row-leading">
                  <ExternalLink size={18} aria-hidden="true" />
                </div>
                <div className="native-row-copy">
                  <div className="native-row-title">Источники карты</div>
                  <div className="native-row-subtitle">Атрибуция OpenStreetMap и CARTO всегда остается видимой в публичной сборке.</div>
                </div>
              </a>
            </NativeSection>
          </div>
        </div>
      );
    }

    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="mb-4">
          {renderRouteEndpointSummary()}
        </div>

        <div className="planner-control-stack mb-4 space-y-4">
          <SegmentedControl label="Профиль" options={PROFILE_OPTIONS} value={profile} onChange={handleProfileChange} />
          <SegmentedControl label="Приоритет" options={SCORING_MODE_OPTIONS} value={routeMode} onChange={handleRouteModeChange} compact />
        </div>

        <AnimatePresence mode="wait">
          <StatusBanner feedback={feedback} loading={isRouting} />
        </AnimatePresence>

        <div className="min-h-0 flex-1 overflow-y-auto pr-2">
          {isRouting && routes.length === 0 ? (
            <RouteLoadingState />
          ) : feedback?.type === "error" ? (
            <ErrorRecoveryCard feedback={feedback} onRetry={destination ? () => requestRoutes() : null} />
          ) : routes.length > 0 ? (
            <div className="space-y-4 pb-4">
              {routes.map((route, index) => (
                <RouteCard
                  key={route.id}
                  route={route}
                  index={index}
                  isActive={route.id === selectedRouteId}
                  onSelect={setSelectedRouteId}
                />
              ))}
              {selectedRoute ? (
                <details className="route-details-disclosure">
                  <summary className="route-details-summary">
                    <span>Почему такая оценка</span>
                    <span>{selectedRoute.properties?.score?.total ?? selectedRoute.properties?.safety_index ?? "--"}/100</span>
                  </summary>
                  <div className="route-details-content">
                    <SafetyScorePanel route={selectedRoute} />
                    <DataCoverageNote score={selectedRoute?.properties?.score} />
                  </div>
                </details>
              ) : null}
            </div>
          ) : (
            <RouteEmptyState />
          )}
        </div>

        <div className="route-action-stack mt-5 space-y-3">
          <div className="route-safety-note flex items-center gap-2 text-xs font-medium text-on-surface-variant">
            <ShieldCheck size={14} className="text-primary" />
            <span>
              {selectedRoute
                ? selectedRoute.properties?.score
                  ? `Индекс безопасности: ${selectedRoute.properties?.safety_index ?? "--"}%`
                  : "Индекс безопасности недоступен без проверенного графа"
                : "Постройте маршрут, чтобы оценить безопасность пути"}
            </span>
          </div>

          <button
            type="button"
            onClick={handleStartNavigation}
            disabled={primaryActionBusy || !destination}
            className="primary-route-button soul-gradient inline-flex w-full items-center justify-center gap-2 rounded-full px-5 py-4 text-sm font-bold tracking-[0.14em] text-on-primary shadow-[0_18px_36px_rgba(0,88,188,0.22)] transition-all hover:opacity-92 active:scale-[0.985] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {primaryActionBusy ? <Loader2 size={16} className="animate-spin" /> : <Navigation2 size={16} />}
            <span>{primaryActionLabel}</span>
          </button>

          {selectedRoute ? (
            <button
              type="button"
              onClick={handleResetRoute}
              className="secondary-route-button inline-flex w-full items-center justify-center gap-2 rounded-full bg-white/58 px-5 py-3 text-sm font-semibold text-on-surface-variant transition-all hover:bg-white/72 active:scale-[0.985]"
            >
              <RotateCcw size={14} />
              <span>Сбросить маршрут</span>
            </button>
          ) : null}
        </div>
      </div>
    );
  }

  return (
    <MotionConfig reducedMotion="user" transition={PANEL_TRANSITION}>
      <LayoutGroup>
        <div className="app-shell relative h-screen w-screen overflow-hidden bg-surface text-on-surface">
          <div className="absolute inset-0 z-0">
            <Map
              ref={mapRef}
              initialViewState={INITIAL_VIEW_STATE}
              mapStyle={MAP_STYLE}
              attributionControl={false}
              onClick={handleMapClick}
            >
              {layerOptions.sidewalkQuality && sidewalkCells?.features?.length ? (
                <Source id="sidewalk-quality" type="geojson" data={sidewalkCells}>
                  <Layer
                    id="sidewalk-quality-fill"
                    type="fill"
                    paint={{
                      "fill-color": [
                        "case",
                        ["<", ["get", "quality_score"], 55],
                        "#ff453a",
                        ["<", ["get", "quality_score"], 75],
                        "#ffcc00",
                        "#34c759",
                      ],
                      "fill-opacity": 0.22,
                    }}
                  />
                  <Layer
                    id="sidewalk-quality-line"
                    type="line"
                    paint={{
                      "line-color": "#0070eb",
                      "line-width": 1,
                      "line-opacity": 0.18,
                    }}
                  />
                </Source>
              ) : null}

              {animatedRoute && layerOptions.route ? (
                <Source id="active-route" type="geojson" data={animatedRoute}>
                  <Layer
                    id="route-shadow"
                    type="line"
                    layout={{ "line-join": "round", "line-cap": "round" }}
                    paint={{
                      "line-color": "#0058bc",
                      "line-width": layerOptions.routeEmphasis ? 12 : 8,
                      "line-opacity": layerOptions.routeEmphasis ? 0.14 : 0.08,
                    }}
                  />
                  <Layer
                    id="route-core"
                    type="line"
                    layout={{ "line-join": "round", "line-cap": "round" }}
                    paint={{
                      "line-color": "#0070eb",
                      "line-width": layerOptions.routeEmphasis ? 4.8 : 3.6,
                      "line-opacity": 0.96,
                    }}
                  />
                </Source>
              ) : null}

              {layerOptions.pins ? (
                <Marker longitude={originMarker.lon} latitude={originMarker.lat}>
                  <div className="relative">
                    {layerOptions.gpsAccuracy ? <div className="origin-ping" /> : null}
                    <div className="relative h-3 w-3 rounded-full bg-primary shadow-[0_0_0_10px_rgba(0,88,188,0.18)]" />
                  </div>
                </Marker>
              ) : null}

              {destination && layerOptions.pins ? (
                <Marker longitude={destination.lon} latitude={destination.lat}>
                  <div className="h-3 w-3 rounded-[4px] bg-error shadow-[0_0_0_10px_rgba(186,26,26,0.14)]" />
                </Marker>
              ) : null}

              <div
                className="map-attribution absolute bottom-4 left-4 z-10 max-w-[calc(100vw-2rem)] rounded-full bg-white/82 px-3 py-1.5 text-[11px] font-semibold text-on-surface-variant shadow-[0_10px_26px_rgba(20,36,56,0.12)] backdrop-blur-xl"
                aria-label="Map and enrichment data attribution"
              >
                {renderAttributionLinks()}
              </div>
            </Map>
            <motion.div
              className="map-atmosphere pointer-events-none absolute inset-0"
              initial={false}
              animate={{
                opacity: plannerStage === "navigating" ? 0.62 : 1,
                x: panelOpen ? 0 : -8,
              }}
              transition={PAGE_TRANSITION}
            />
          </div>

          <div className="custom-map-zoom" aria-label="Масштаб карты">
            <button
              type="button"
              className="maplibregl-ctrl-zoom-in"
              aria-label="Увеличить карту"
              onClick={() => handleMapZoom(1)}
            >
              +
            </button>
            <button
              type="button"
              className="maplibregl-ctrl-zoom-out"
              aria-label="Уменьшить карту"
              onClick={() => handleMapZoom(-1)}
            >
              −
            </button>
          </div>

          <AnimatePresence>
            {plannerVisible ? (
              <>
                {commandBarVisible ? (
                  <motion.nav
                    ref={commandNavRef}
                    layout
                    initial={{ opacity: 0, y: -18, scale: 0.985 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -10, scale: 0.99 }}
                    transition={SHEET_TRANSITION}
                    className="fixed left-0 top-0 z-50 w-full px-4 pt-4 md:w-auto"
                  >
                    <form
                      onSubmit={handleSearch}
                      className="command-bar material-toolbar mx-auto flex w-full max-w-2xl items-center gap-1 rounded-[1.5rem] px-3 py-3 md:mx-0 md:max-w-xl"
                    >
                      <button
                        type="button"
                        aria-label={sectionMenuOpen ? "Закрыть разделы" : "Открыть разделы"}
                        aria-expanded={sectionMenuOpen}
                        aria-haspopup="dialog"
                        title="Разделы"
                        onClick={handleSectionMenuToggle}
                        className={cn("icon-button", sectionMenuOpen && "icon-button-active")}
                      >
                        <Menu size={18} />
                      </button>

                      <Search size={17} className="ml-1 text-outline" />

                      <input
                        ref={searchInputRef}
                        value={query}
                        onChange={(event) => {
                          setQuery(event.target.value);
                          setActiveTab("route");
                          setSectionMenuOpen(false);
                        }}
                        onFocus={() => {
                          setActiveTab("route");
                          setSectionMenuOpen(false);
                          if (searchResults.length) {
                            setIsAutocompleteOpen(true);
                          }
                        }}
                        onKeyDown={handleSearchKeyDown}
                        className="w-full border-none bg-transparent px-2 py-2 text-sm font-medium text-on-surface placeholder:text-outline focus:outline-none"
                        placeholder={searchPlaceholder}
                        aria-label={searchAriaLabel}
                        aria-autocomplete="list"
                        aria-expanded={isAutocompleteOpen}
                      />

                      <button
                        type="submit"
                        className="route-search-submit ml-2 inline-flex h-10 items-center justify-center rounded-full bg-primary px-4 text-sm font-bold text-on-primary transition-all hover:bg-primary/90 active:scale-[0.97] disabled:opacity-60"
                        disabled={primaryActionBusy}
                      >
                        {primaryActionBusy ? <Loader2 size={16} className="animate-spin" /> : "Найти"}
                      </button>
                    </form>

                    {renderSectionMenu()}

                    {isAutocompleteOpen ? (
                      <SearchResults
                        results={searchResults}
                        highlightedIndex={highlightedResultIndex}
                        loading={isSearching && !isRouting}
                        query={query}
                        onPick={chooseSearchResult}
                      />
                    ) : null}
                  </motion.nav>
                ) : null}

                <motion.aside
                  layout
                  initial={{ opacity: 0, x: -24, scale: 0.985 }}
                  animate={{ opacity: 1, x: 0, scale: 1 }}
                  exit={{ opacity: 0, x: -18, scale: 0.99 }}
                  transition={SHEET_TRANSITION}
                  className={cn(
                    "planner-panel material-panel fixed left-4 top-[94px] z-40 flex h-[calc(100%-7.2rem)] w-[min(26rem,calc(100vw-2rem))] flex-col rounded-[1.5rem] px-6 py-6",
                    `mobile-sheet-${mobileSheetState}`,
                    panelOpen
                      ? "translate-y-0 opacity-100 pointer-events-auto"
                      : "-translate-y-[calc(100%+6rem)] opacity-0 pointer-events-none",
                    "transition-all duration-300 md:opacity-100",
                  )}
                >
                  <button
                    type="button"
                    className="sheet-handle"
                    aria-label="Свернуть панель"
                    onClick={() => setPanelOpen(false)}
                  >
                    <span />
                  </button>
                  <PanelHeader activeTab={activeTab} onClose={() => setPanelOpen(false)} />
                  <AnimatePresence mode="wait">
                    <motion.div
                      key={activeTab}
                      layout
                      initial={{ opacity: 0, y: 8, scale: 0.995 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, y: -6, scale: 0.995 }}
                      transition={PAGE_TRANSITION}
                      className="flex min-h-0 flex-1 flex-col"
                    >
                      {renderPanelContent()}
                    </motion.div>
                  </AnimatePresence>
                  {renderAttributionLinks("panel-attribution mt-3 rounded-full bg-white/54 px-3 py-2 text-center md:hidden")}
                </motion.aside>
              </>
            ) : null}
          </AnimatePresence>

          <AnimatePresence>
            {plannerStage === "navigating" && selectedRoute ? (
              <NavigationInstructionCard
                hint={navigationHint}
                gpsStatus={gpsStatus}
                rerouting={isRerouting}
                onOpenPlanner={handleShowPlanner}
              />
            ) : null}
          </AnimatePresence>

          <AnimatePresence>
            {plannerStage === "navigating" && selectedRoute ? (
              <TripSheet
                route={selectedRoute}
                livePosition={livePosition}
                activeInstructionIndex={activeInstructionIndex}
                onShowPlanner={handleShowPlanner}
                onReset={handleResetRoute}
              />
            ) : null}
          </AnimatePresence>

          {plannerStage !== "navigating" ? <WeatherChip route={selectedRoute} /> : null}
        </div>
      </LayoutGroup>
    </MotionConfig>
  );
}
