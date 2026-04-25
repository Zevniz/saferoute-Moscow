import React, { startTransition, useDeferredValue, useEffect, useRef, useState } from "react";
import { AnimatePresence, LayoutGroup, MotionConfig, animate, motion } from "framer-motion";
import Map, { Layer, Marker, NavigationControl, Source } from "react-map-gl/maplibre";
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
  SlidersHorizontal,
  User,
} from "lucide-react";
import {
  CURRENT_LOCATION,
  DEFAULT_LAYER_OPTIONS,
  INITIAL_VIEW_STATE,
  MAP_STYLE,
  PANEL_TRANSITION,
  PROFILE_OPTIONS,
  SCORING_MODE_OPTIONS,
} from "./config/safeRoute";
import {
  AppTabRail,
  EmptyState,
  EndpointStack,
  ModeButton,
  NavigationInstructionCard,
  PanelHeader,
  RouteCard,
  SearchResults,
  ServiceHealthList,
  StatusBanner,
  ToggleRow,
  TripSheet,
  WeatherChip,
} from "./components/AppPanels";
import { useHealth } from "./hooks/useHealth";
import { useSidewalkCells } from "./hooks/useSidewalkCells";
import {
  formatDistance,
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
  const requestIdRef = useRef(0);

  const [query, setQuery] = useState("");
  const [origin, setOrigin] = useState(CURRENT_LOCATION);
  const [destination, setDestination] = useState(null);
  const [profile, setProfile] = useState("walk");
  const [routeMode, setRouteMode] = useState("safest");
  const [plannerStage, setPlannerStage] = useState("idle");
  const [activeTab, setActiveTab] = useState("search");
  const [routes, setRoutes] = useState([]);
  const [selectedRouteId, setSelectedRouteId] = useState(null);
  const [feedback, setFeedback] = useState(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const [layerOptions, setLayerOptions] = useState(DEFAULT_LAYER_OPTIONS);
  const [routeProgress, setRouteProgress] = useState(0);
  const [searchResults, setSearchResults] = useState([]);
  const [highlightedResultIndex, setHighlightedResultIndex] = useState(0);
  const [isAutocompleteOpen, setIsAutocompleteOpen] = useState(false);
  const { health, loading: isHealthLoading, loadHealth } = useHealth();
  const {
    cells: sidewalkCells,
    loading: sidewalkCellsLoading,
    error: sidewalkCellsError,
  } = useSidewalkCells({ enabled: layerOptions.sidewalkQuality, mapRef });
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

  useEffect(() => {
    loadHealth();
  }, []);

  useEffect(() => {
    if (!selectedRoute) {
      setRouteProgress(0);
      return undefined;
    }

    setRouteProgress(0);
    const controls = animate(0, 1, {
      duration: 0.82,
      ease: [0.22, 1, 0.36, 1],
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
        duration: 1600,
        maxZoom: plannerStage === "navigating" ? 14.8 : 14.2,
      });
    }, 120);

    return () => window.clearTimeout(timeoutId);
  }, [plannerStage, selectedRoute?.id]);

  useEffect(() => {
    const trimmedQuery = deferredQuery.trim();
    if (!plannerVisible || trimmedQuery.length < 2 || trimmedQuery === destination?.label) {
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
  }, [deferredQuery, destination?.label, plannerVisible, search]);

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
        setActiveTab(successStage === "navigating" ? "navigation" : "routes");
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

  async function chooseDestination(result) {
    const nextDestination = {
      lat: Number(result.lat),
      lon: Number(result.lon),
      label: buildDestinationLabel(result, query.trim()),
      kind: result.kind,
    };

    startTransition(() => {
      setDestination(nextDestination);
      setQuery(nextDestination.label);
      setSearchResults([]);
      setIsAutocompleteOpen(false);
      setPanelOpen(true);
      setActiveTab("routes");
      setFeedback(null);
    });

    mapRef.current?.flyTo({
      center: [nextDestination.lon, nextDestination.lat],
      zoom: 14.2,
      duration: 1450,
    });

    await requestRoutes({
      nextProfile: profile,
      nextOrigin: origin,
      nextDestination,
    });
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
      setActiveTab("search");
      setFeedback(null);
    });

    try {
      const result = searchResults[highlightedResultIndex] ?? searchResults[0];
      if (result) {
        await chooseDestination(result);
        return;
      }

      const results = await search(trimmedQuery, 5);
      if (!results.length) {
        throw new Error("Ничего не найдено. Попробуйте другой адрес или ориентир.");
      }
      await chooseDestination(results[0]);
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
      setActiveTab("routes");
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
      setActiveTab("routes");
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
      setActiveTab("navigation");
      setPanelOpen(false);
      setFeedback(null);
      setActiveInstructionIndex(0);
    });
  }

  function handleResetRoute() {
    startTransition(() => {
      setRoutes([]);
      setSelectedRouteId(null);
      setPlannerStage("idle");
      setActiveTab("search");
      setFeedback(null);
    });
  }

  function handleShowPlanner() {
    startTransition(() => {
      setActiveTab("routes");
      setPanelOpen(true);
    });
  }

  function handleTabSelect(tabId) {
    startTransition(() => {
      setActiveTab(tabId);
      setPanelOpen(true);
      if (tabId === "navigation" && selectedRoute && plannerStage === "idle") {
        setPlannerStage("planned");
      }
    });

    if (tabId === "settings") {
      loadHealth();
    }
  }

  function toggleLayerOption(optionId) {
    setLayerOptions((current) => ({
      ...current,
      [optionId]: !current[optionId],
    }));
  }

  function renderPanelContent() {
    if (activeTab === "search") {
      return (
        <div className="flex min-h-0 flex-1 flex-col">
          <div className="mb-5">
            <EndpointStack origin={origin} destination={destination} onSwap={handleSwap} />
          </div>

          <AnimatePresence mode="wait">
            <StatusBanner feedback={feedback} loading={isRouting} />
          </AnimatePresence>

          <div className="min-h-0 flex-1 overflow-y-auto pr-2">
            <EmptyState title="Начните с поиска" icon={Search}>
              Введите адрес или ориентир в верхней строке. Результаты приходят из локального SafeRoute API, а не из публичного Nominatim.
            </EmptyState>

            {destination ? (
              <motion.button
                type="button"
                layout
                onClick={() => handleTabSelect("routes")}
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

    if (activeTab === "navigation") {
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
                          {formatDistance(instruction.distance_m)} • {Math.round((instruction.time_s ?? 0) / 60) || 1} мин
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
              Сначала выберите точку назначения и реальную альтернативу. Здесь появятся манёвры из Valhalla без эвристических подсказок.
            </EmptyState>
          )}
        </div>
      );
    }

    if (activeTab === "layers") {
      return (
        <div className="min-h-0 flex-1 overflow-y-auto pr-2">
          <div className="space-y-2">
            <ToggleRow
              icon={layerOptions.route ? Eye : EyeOff}
              title="Линия маршрута"
              subtitle="Показывает или скрывает текущий GeoJSON route source."
              enabled={layerOptions.route}
              onToggle={() => toggleLayerOption("route")}
            />
            <ToggleRow
              icon={Compass}
              title="Акцент маршрута"
              subtitle="Усиливает тень и толщину линии, не меняя геометрию."
              enabled={layerOptions.routeEmphasis}
              onToggle={() => toggleLayerOption("routeEmphasis")}
            />
            <ToggleRow
              icon={Radio}
              title="Пульс GPS"
              subtitle="Визуальный индикатор точности вокруг текущей точки."
              enabled={layerOptions.gpsAccuracy}
              onToggle={() => toggleLayerOption("gpsAccuracy")}
            />
            <ToggleRow
              icon={LayersIcon}
              title="Пины поиска"
              subtitle="Показывает origin и destination markers на карте."
              enabled={layerOptions.pins}
              onToggle={() => toggleLayerOption("pins")}
            />
            <ToggleRow
              icon={ShieldCheck}
              title="Качество тротуаров"
              subtitle={
                sidewalkCellsLoading
                  ? "Загружаем реальные H3-агрегаты telemetry API..."
                  : sidewalkCellsError
                    ? sidewalkCellsError
                    : sidewalkCells?.features?.length
                      ? `Показано ${sidewalkCells.features.length} H3-ячеек качества и свежести.`
                      : "Показывает реальные telemetry H3-ячейки; пусто, пока данных нет."
              }
              enabled={layerOptions.sidewalkQuality}
              onToggle={() => toggleLayerOption("sidewalkQuality")}
            />
          </div>
        </div>
      );
    }

    if (activeTab === "settings") {
      return (
        <div className="min-h-0 flex-1 overflow-y-auto pr-2">
          <ServiceHealthList health={health} loading={isHealthLoading} onRefresh={loadHealth} />

          <div className="mt-4 space-y-2">
            <div className="service-row rounded-[1.2rem] px-4 py-3">
              <div className="flex items-center gap-2 text-sm font-bold text-on-surface">
                <CheckCircle2 size={16} className="text-primary" />
                Motion policy
              </div>
              <div className="mt-1 text-xs font-medium leading-5 text-outline">
                Framer Motion работает через MotionConfig с reducedMotion=&quot;user&quot;.
              </div>
            </div>
            <div className="service-row rounded-[1.2rem] px-4 py-3">
              <div className="flex items-center gap-2 text-sm font-bold text-on-surface">
                <ShieldCheck size={16} className="text-primary" />
                Источник маршрутов
              </div>
              <div className="mt-1 text-xs font-medium leading-5 text-outline">
                {selectedRoute?.properties?.source || "Маршрут ещё не построен"}
              </div>
            </div>
            <a
              href={FIGMA_DESIGN_URL}
              target="_blank"
              rel="noreferrer"
              className="service-row block rounded-[1.2rem] px-4 py-3 transition-all hover:bg-white/58 active:scale-[0.99]"
            >
              <div className="flex items-center gap-2 text-sm font-bold text-on-surface">
                <ExternalLink size={16} className="text-primary" />
                Figma design source
              </div>
              <div className="mt-1 text-xs font-medium leading-5 text-outline">
                SafeRoute Apple Minimal board: вкладки, glass-токены, motion notes и route-card система.
              </div>
            </a>
          </div>
        </div>
      );
    }

    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="mb-5 flex items-center gap-2 rounded-full bg-white/40 p-1.5">
          {PROFILE_OPTIONS.map((option) => (
            <ModeButton
              key={option.id}
              option={option}
              active={profile === option.id}
              onSelect={handleProfileChange}
            />
          ))}
        </div>

        <div className="mb-5 grid grid-cols-4 gap-2 rounded-full bg-white/40 p-1.5">
          {SCORING_MODE_OPTIONS.map((option) => (
            <ModeButton
              key={option.id}
              option={option}
              active={routeMode === option.id}
              onSelect={handleRouteModeChange}
            />
          ))}
        </div>

        <div className="mb-5">
          <EndpointStack origin={origin} destination={destination} onSwap={handleSwap} />
        </div>

        <AnimatePresence mode="wait">
          <StatusBanner feedback={feedback} loading={isRouting} />
        </AnimatePresence>

        <div className="min-h-0 flex-1 overflow-y-auto pr-2">
          {routes.length > 0 ? (
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
            </div>
          ) : (
            <EmptyState title="Маршруты появятся здесь" icon={Route}>
              Выберите место из autocomplete. SafeRoute покажет только реальные маршруты Valhalla/PostGIS без transit-заглушек.
            </EmptyState>
          )}
        </div>

        <div className="mt-5 space-y-3">
          <div className="flex items-center gap-2 text-xs font-medium text-on-surface-variant">
            <ShieldCheck size={14} className="text-primary" />
            <span>
              {selectedRoute
                ? `Индекс безопасности: ${selectedRoute.properties?.safety_index ?? "--"}%`
                : "Постройте маршрут, чтобы оценить безопасность пути"}
            </span>
          </div>

          <button
            type="button"
            onClick={handleStartNavigation}
            disabled={primaryActionBusy || !destination}
            className="soul-gradient inline-flex w-full items-center justify-center gap-2 rounded-full px-5 py-4 text-sm font-bold tracking-[0.14em] text-on-primary shadow-[0_18px_36px_rgba(0,88,188,0.22)] transition-all hover:opacity-92 active:scale-[0.985] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {primaryActionBusy ? <Loader2 size={16} className="animate-spin" /> : <Navigation2 size={16} />}
            <span>{primaryActionLabel}</span>
          </button>

          {selectedRoute ? (
            <button
              type="button"
              onClick={handleResetRoute}
              className="inline-flex w-full items-center justify-center gap-2 rounded-full bg-white/58 px-5 py-3 text-sm font-semibold text-on-surface-variant transition-all hover:bg-white/72 active:scale-[0.985]"
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

              <div className="absolute bottom-10 right-4 z-10">
                <NavigationControl showCompass={false} />
              </div>
            </Map>
            <div className="map-atmosphere pointer-events-none absolute inset-0" />
          </div>

          <AnimatePresence>
            {plannerVisible ? (
              <>
                {commandBarVisible ? (
                  <motion.nav
                    layout
                    initial={{ opacity: 0, y: -18 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    transition={PANEL_TRANSITION}
                    className="fixed left-0 top-0 z-50 w-full px-4 pt-4 md:w-auto"
                  >
                    <form
                      onSubmit={handleSearch}
                      className="command-bar glass-panel mx-auto flex w-full max-w-2xl items-center gap-1 rounded-[1.8rem] px-3 py-3 md:mx-0 md:max-w-xl"
                    >
                      <button
                        type="button"
                        aria-label="Показать панель маршрутов"
                        onClick={() => setPanelOpen((previous) => !previous)}
                        className="inline-flex h-11 w-11 items-center justify-center rounded-full text-on-surface-variant transition-all hover:bg-white/55 active:scale-95"
                      >
                        <Menu size={18} />
                      </button>

                      <Search size={17} className="ml-1 text-outline" />

                      <input
                        value={query}
                        onChange={(event) => {
                          setQuery(event.target.value);
                          setActiveTab("search");
                        }}
                        onFocus={() => {
                          setActiveTab("search");
                          if (searchResults.length) {
                            setIsAutocompleteOpen(true);
                          }
                        }}
                        onKeyDown={handleSearchKeyDown}
                        className="w-full border-none bg-transparent px-2 py-2 text-sm font-medium text-on-surface placeholder:text-outline focus:outline-none"
                        placeholder="Куда едем по Москве?"
                        aria-autocomplete="list"
                        aria-expanded={isAutocompleteOpen}
                      />

                      <div className="ml-2 flex items-center gap-1 pl-2">
                        <button
                          type="button"
                          onClick={() => handleTabSelect("settings")}
                          className="inline-flex h-10 w-10 items-center justify-center rounded-full text-on-surface-variant transition-all hover:bg-white/55"
                          aria-label="Профиль и настройки"
                        >
                          <User size={17} />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleTabSelect("layers")}
                          className="inline-flex h-10 w-10 items-center justify-center rounded-full text-on-surface-variant transition-all hover:bg-white/55"
                          aria-label="Слои"
                        >
                          <SlidersHorizontal size={17} />
                        </button>
                      </div>
                    </form>

                    {isAutocompleteOpen ? (
                      <SearchResults
                        results={searchResults}
                        highlightedIndex={highlightedResultIndex}
                        loading={isSearching && !isRouting}
                        query={query}
                        onPick={chooseDestination}
                      />
                    ) : null}
                  </motion.nav>
                ) : null}

                <motion.aside
                  layout
                  initial={{ opacity: 0, x: -24 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -18 }}
                  transition={PANEL_TRANSITION}
                  className={cn(
                    "planner-panel glass-panel fixed left-4 top-[94px] z-40 flex h-[calc(100%-7.2rem)] w-[min(26rem,calc(100vw-2rem))] flex-col rounded-[2rem] px-6 py-6",
                    panelOpen
                      ? "translate-y-0 opacity-100"
                      : "-translate-y-[calc(100%+6rem)] opacity-0 md:translate-y-0 md:opacity-100",
                    "transition-all duration-300 md:opacity-100",
                  )}
                >
                  <PanelHeader activeTab={activeTab} onClose={() => setPanelOpen(false)} />
                  <AppTabRail activeTab={activeTab} hasRoute={Boolean(selectedRoute)} onSelect={handleTabSelect} />
                  <AnimatePresence mode="wait">
                    <motion.div
                      key={activeTab}
                      layout
                      initial={{ opacity: 0, y: 10, filter: "blur(6px)" }}
                      animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                      exit={{ opacity: 0, y: -8, filter: "blur(4px)" }}
                      transition={PANEL_TRANSITION}
                      className="flex min-h-0 flex-1 flex-col"
                    >
                      {renderPanelContent()}
                    </motion.div>
                  </AnimatePresence>
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

          {plannerStage !== "navigating" ? <WeatherChip /> : null}
        </div>
      </LayoutGroup>
    </MotionConfig>
  );
}
