# Объяснимость маршрута: Визуализация переходов

## Обзор

Добавлена визуализация пешеходных переходов на маршруте для улучшения объяснимости оценки безопасности.

## Что добавлено

### Backend

#### Модели данных (app/schemas/routing.py)

**CrossingPoint** - точка перехода на маршруте:
- `lat`, `lon` - координаты
- `type` - тип перехода (traffic_signal, marked, unmarked, underpass, overpass, unknown)
- `controlled` - регулируемый (True/False/None)
- `confidence` - уверенность определения (0.0-1.0)

**CrossingSummary** - сводка переходов:
- `total` - общее количество
- `traffic_signals` - переходы со светофором
- `marked` - размеченные (зебры)
- `unmarked` - нерегулируемые
- `underpass` - подземные
- `overpass` - надземные
- `unknown` - неизвестного типа

**RouteProperties** - добавлены поля:
- `crossings: List[CrossingPoint]` - список переходов
- `crossing_summary: Optional[CrossingSummary]` - сводка

#### Функции (app/services/routing.py)

**extract_crossings_from_route(route_data)** - извлечение переходов:
- Анализирует инструкции маршрута
- Определяет тип по ключевым словам (светофор, зебра, переход, подземный, надземный)
- Извлекает координаты из geometry
- Возвращает список CrossingPoint

**build_crossing_summary(crossings)** - построение сводки:
- Подсчитывает переходы по типам
- Возвращает CrossingSummary

**enrich_route_with_crossings(route_data)** - обогащение маршрута:
- Вызывает extract_crossings_from_route()
- Вызывает build_crossing_summary()
- Добавляет данные в route_data

### Frontend

#### Утилиты (src/lib/crossing-utils.js)

- `getCrossingIcon(type)` - эмодзи для типа (🚦, 🚶, ⚠️, ⬇️, ⬆️)
- `getCrossingLabel(type)` - человекочитаемое название
- `getCrossingColor(type)` - цвет маркера
- `formatCrossingSummary(summary)` - форматирование сводки
- `getCrossingSafetyDescription(summary)` - описание безопасности

#### Компоненты

**RouteInsight.jsx** - добавлена секция "Переходы на маршруте":
- Сводка: "Переходы: X всего · Y со светофором · Z зебра"
- Описание безопасности
- Иконки первых 5 переходов
- Счетчик "+N ещё"

**App.jsx** - маркеры переходов на карте:
- Цветные круглые маркеры с иконками
- Цвет зависит от типа перехода
- Tooltip при наведении
- Показываются только для активного маршрута

## Использование

### API Response

```json
{
  "routes": [
    {
      "properties": {
        "crossings": [
          {
            "lat": 55.7520,
            "lon": 37.6175,
            "type": "traffic_signal",
            "controlled": true,
            "confidence": 0.8
          }
        ],
        "crossing_summary": {
          "total": 5,
          "traffic_signals": 3,
          "marked": 1,
          "unmarked": 0,
          "underpass": 0,
          "overpass": 0,
          "unknown": 1
        }
      }
    }
  ]
}
```

### Frontend

Маркеры переходов автоматически отображаются на карте при построении маршрута.
Сводка переходов показывается в панели RouteInsight.

## Ограничения текущей реализации

1. **Определение типа перехода** - используется эвристика по ключевым словам в инструкциях
   - TODO: интеграция с OSM данными из moscow_network
   - TODO: использование crossing_count, controlled_crossing_count из БД

2. **Точность координат** - берутся из begin_shape_index инструкции
   - TODO: более точное определение координат перехода

3. **Confidence** - фиксированные значения для эвристики
   - TODO: динамический расчет на основе качества данных

## Следующие шаги

1. Интеграция с реальными OSM данными из moscow_network
2. Добавить переключатель "Детали безопасности" для скрытия/показа маркеров
3. Улучшить блок "Почему такая оценка" с использованием score.reasons
4. Добавить Popup при клике на маркер с детальной информацией
5. Раскраска сегментов маршрута по уровню безопасности

## Тестирование

```bash
# Backend typecheck
npm run typecheck:backend

# Frontend lint
npm run lint

# Тест API
curl "http://localhost:8000/api/route?lat1=55.7558&lon1=37.6173&lat2=55.7496724&lon2=37.6210752&profile=walk&alternatives=3&mode=safest"
```

## Коммиты

- b3e52ad - Add crossing points and summary to route response
- d0600e8 - Add crossing visualization to map and route insight
