from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.osmnx_engine import get_safe_route

router = APIRouter()

@router.get("/route")
def calculate_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float):
    try:
        data = get_safe_route(start_lat, start_lon, end_lat, end_lon)
        
        # Упаковываем ответ в стандартный GeoJSON
        return {
            "type": "Feature",
            "properties": {
                "distance_m": data["distance"],
                "calories_burn": data["calories"],
                "safety_index": 95 # Заглушка, здесь будет логика оценки безопасности
            },
            "geometry": {
                "type": "LineString",
                "coordinates": data["coordinates"]
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
