from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="SafeRoute Engine API")

# Разрешаем CORS, чтобы React (localhost:5173) мог стучаться к FastAPI (localhost:8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/route")
def get_safe_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float):
    # В реальном проекте здесь будет SQL-запрос к PostGIS и алгоритм Дейкстры (pgRouting).
    # Пока отдаем тестовые варианты маршрутов в формате routes[].
    routes = [
        {
            "id": "safe",
            "label": "SafeRoute",
            "subtitle": "Максимально безопасный путь",
            "type": "Feature",
            "properties": {
                "safety_index": 98.5,
                "calories_burn": 320,
                "estimated_mins": 14,
                "distance_m": 4200
            },
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [start_lon, start_lat],
                    [37.6050, 55.7520],
                    [37.5950, 55.7500],
                    [end_lon, end_lat]
                ]
            }
        },
        {
            "id": "alt",
            "label": "Alternative",
            "subtitle": "Более свободные улицы",
            "type": "Feature",
            "properties": {
                "safety_index": 93.0,
                "calories_burn": 350,
                "estimated_mins": 17,
                "distance_m": 4700
            },
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [start_lon, start_lat],
                    [37.6110, 55.7510],
                    [37.6010, 55.7485],
                    [end_lon, end_lat]
                ]
            }
        },
        {
            "id": "scenic",
            "label": "Scenic Route",
            "subtitle": "Более комфортный путь",
            "type": "Feature",
            "properties": {
                "safety_index": 95.0,
                "calories_burn": 390,
                "estimated_mins": 19,
                "distance_m": 5100
            },
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [start_lon, start_lat],
                    [37.6140, 55.7540],
                    [37.6020, 55.7560],
                    [end_lon, end_lat]
                ]
            }
        }
    ]

    # Оставляем обратную совместимость со старым форматом.
    primary_route = routes[0]
    return {
        "routes": routes,
        "type": primary_route["type"],
        "properties": primary_route["properties"],
        "geometry": primary_route["geometry"]
    }

if __name__ == "__main__":
    print("🚀 SafeRoute Backend is running on http://localhost:8000")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
