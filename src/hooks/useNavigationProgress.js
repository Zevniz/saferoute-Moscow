import { useEffect, useRef, useState } from "react";

import { OFF_ROUTE_SAMPLE_LIMIT, OFF_ROUTE_THRESHOLD_METERS } from "../config/safeRoute";
import { getInstructionIndexForShape, getRouteProgressForPosition } from "../lib/route-utils";

export function useNavigationProgress({ enabled, selectedRoute, destination, profile, onReroute }) {
  const onRerouteRef = useRef(onReroute);
  const selectedRouteRef = useRef(null);
  const destinationRef = useRef(null);
  const profileRef = useRef(profile);
  const offRouteSamplesRef = useRef(0);
  const rerouteLockRef = useRef(false);
  const [livePosition, setLivePosition] = useState(null);
  const [activeInstructionIndex, setActiveInstructionIndex] = useState(0);
  const [gpsStatus, setGpsStatus] = useState("");
  const [rerouting, setRerouting] = useState(false);

  useEffect(() => {
    selectedRouteRef.current = selectedRoute;
  }, [selectedRoute]);

  useEffect(() => {
    destinationRef.current = destination;
  }, [destination]);

  useEffect(() => {
    profileRef.current = profile;
  }, [profile]);

  useEffect(() => {
    onRerouteRef.current = onReroute;
  }, [onReroute]);

  useEffect(() => {
    if (!enabled || !selectedRoute) {
      setLivePosition(null);
      setGpsStatus("");
      setActiveInstructionIndex(0);
      offRouteSamplesRef.current = 0;
      return undefined;
    }

    if (!navigator.geolocation) {
      setGpsStatus("GPS недоступен в этом браузере. Показываем первый реальный манёвр.");
      return undefined;
    }

    setGpsStatus("Ожидаем GPS-позицию...");
    const watchId = navigator.geolocation.watchPosition(
      (position) => {
        const nextPosition = {
          lat: position.coords.latitude,
          lon: position.coords.longitude,
          accuracy: position.coords.accuracy,
          timestamp: position.timestamp,
          label: "Текущая позиция",
        };
        const route = selectedRouteRef.current;
        const nextDestination = destinationRef.current;

        setLivePosition(nextPosition);
        if (!route) {
          return;
        }

        const progress = getRouteProgressForPosition(route.geometry, nextPosition);
        setActiveInstructionIndex(getInstructionIndexForShape(route.properties?.instructions, progress.nearestShapeIndex));

        if (
          Number.isFinite(progress.distanceToRouteMeters) &&
          progress.distanceToRouteMeters <= OFF_ROUTE_THRESHOLD_METERS
        ) {
          offRouteSamplesRef.current = 0;
          setGpsStatus(`На маршруте • ${Math.round(progress.distanceToRouteMeters)} м от линии`);
          return;
        }

        offRouteSamplesRef.current += 1;
        setGpsStatus(`Отклонение ${Math.round(progress.distanceToRouteMeters)} м от маршрута`);
        if (offRouteSamplesRef.current >= OFF_ROUTE_SAMPLE_LIMIT && nextDestination && !rerouteLockRef.current) {
          rerouteLockRef.current = true;
          setRerouting(true);
          Promise.resolve(
            onRerouteRef.current?.({
              origin: nextPosition,
              destination: nextDestination,
              profile: profileRef.current,
            }),
          ).finally(() => {
            offRouteSamplesRef.current = 0;
            rerouteLockRef.current = false;
            setRerouting(false);
          });
        }
      },
      () => setGpsStatus("Нет доступа к GPS. Разрешите геолокацию, чтобы манёвры переключались автоматически."),
      { enableHighAccuracy: true, maximumAge: 1500, timeout: 10000 },
    );

    return () => navigator.geolocation.clearWatch(watchId);
  }, [enabled, selectedRoute]);

  return {
    activeInstructionIndex,
    gpsStatus,
    livePosition,
    rerouting,
    setActiveInstructionIndex,
  };
}
