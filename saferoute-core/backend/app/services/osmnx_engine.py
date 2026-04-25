import osmnx as ox
import networkx as nx

# Примечание: Для старта мы берем Центральный АО Москвы, 
# так как загрузка всей Москвы займет много времени и оперативной памяти.
print("⏳ Загрузка графа дорог ЦАО Москвы. Это займет около 1-2 минут...")
try:
    # Тип 'bike' отлично подходит для самокатов (велодорожки + дороги)
    moscow_graph = ox.graph_from_place('Central Administrative Okrug, Moscow, Russia', network_type='bike')
    print("✅ Граф успешно загружен!")
except Exception as e:
    print(f"⚠️ Ошибка загрузки графа: {e}")
    moscow_graph = None

def get_safe_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float):
    if moscow_graph is None:
        raise ValueError("Граф дорог не инициализирован")

    # Находим ближайшие к координатам узлы на графе
    start_node = ox.distance.nearest_nodes(moscow_graph, start_lon, start_lat)
    end_node = ox.distance.nearest_nodes(moscow_graph, end_lon, end_lat)

    # Строим кратчайший путь с помощью алгоритма Дейкстры (по длине ребра)
    try:
        route = nx.shortest_path(moscow_graph, start_node, end_node, weight='length')
    except nx.NetworkXNoPath:
        raise ValueError("Безопасный путь между точками не найден")

    # Преобразуем узлы графа обратно в координаты для фронтенда
    route_coords = [[moscow_graph.nodes[node]['x'], moscow_graph.nodes[node]['y']] for node in route]
    
    # Считаем длину в метрах
    distance_meters = int(sum(ox.utils_graph.get_route_edge_attributes(moscow_graph, route, 'length')))
    
    return {
        "distance": distance_meters,
        "calories": int(distance_meters * 0.04), # Примерный расход
        "coordinates": route_coords
    }
