from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import pyqtSlot, pyqtSignal, QObject, QUrl
from enum import Enum
import json
import logging
import numpy as np

class MapMode(Enum):
    """Modos de interacción con el mapa"""
    PAN = "pan"                    # Navegar
    ADD_ANTENNA = "add_antenna"    # Colocar antena
    MOVE_ANTENNA = "move_antenna"  # Mover antena
    SELECT = "select"              # Seleccionar
    MEASURE = "measure"            # Medir distancia

class MapBridge(QObject):
    """Puente entre Python y JavaScript"""
    
    # Señales de Python a JS
    add_antenna_marker = pyqtSignal(str, float, float, str, str)  # id, lat, lon, name, color
    remove_antenna_marker = pyqtSignal(str)
    update_antenna_marker = pyqtSignal(str, float, float, float, str)  # id, lat, lon, azimuth, color
    #add_coverage_layer = pyqtSignal(str, str)  # antenna_id, geotiff_data_url
    add_coverage_layer = pyqtSignal(str, str, float, float, float, float) 
    remove_coverage_layer = pyqtSignal(str)
    set_map_mode = pyqtSignal(str)
    center_map = pyqtSignal(float, float, int)
    
    # Señales de JS a Python
    antenna_clicked_on_map = pyqtSignal(float, float)
    antenna_marker_moved = pyqtSignal(str, float, float)
    antenna_marker_selected = pyqtSignal(str)
    map_clicked = pyqtSignal(float, float)
    
    @pyqtSlot(float, float)
    def on_map_click(self, lat: float, lon: float):
        """Callback cuando se hace clic en el mapa"""
        self.map_clicked.emit(lat, lon)
    
    @pyqtSlot(str, float, float)
    def on_antenna_moved(self, antenna_id: str, lat: float, lon: float):
        """Callback cuando se mueve un marcador de antena"""
        self.antenna_marker_moved.emit(antenna_id, lat, lon)
    
    @pyqtSlot(str)
    def on_antenna_selected(self, antenna_id: str):
        """Callback cuando se selecciona una antena"""
        self.antenna_marker_selected.emit(antenna_id)

class MapWidget(QWidget):
    """Widget principal del mapa interactivo"""
    
    # Señales públicas
    antenna_placed = pyqtSignal(float, float)
    antenna_moved = pyqtSignal(str, float, float)
    antenna_selected = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger("MapWidget")
        self.current_mode = MapMode.PAN
        
        self._setup_ui()
        self._setup_bridge()
    
    def _setup_ui(self):
        """Configura la interfaz"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # WebView para Leaflet
        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view)
        
        # Cargar HTML del mapa
        map_html = self._load_map_html()
        self.web_view.setHtml(map_html)
    
    def _setup_bridge(self):
        """Configura el puente Python-JavaScript"""
        self.channel = QWebChannel()
        self.bridge = MapBridge()
        
        # Conectar señales del bridge a señales públicas
        self.bridge.map_clicked.connect(self._handle_map_click)
        self.bridge.antenna_marker_moved.connect(self.antenna_moved)
        self.bridge.antenna_marker_selected.connect(self.antenna_selected)
        
        # Registrar bridge en el canal
        self.channel.registerObject("bridge", self.bridge)
        self.web_view.page().setWebChannel(self.channel)
    
    def _load_map_html(self) -> str:
        """Carga plantilla HTML con Leaflet"""
        # En producción, cargar desde archivo
        return """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css" />
    <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js"></script>
    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
    <style>
        body { margin: 0; padding: 0; }
        #map { width: 100%; height: 100vh; }
        .antenna-marker {
            background: transparent;
            border: none;
        }
        .antenna-icon {
            width: 40px;
            height: 40px;
            margin-left: -20px;
            margin-top: -40px;
        }
        .coverage-layer {
            opacity: 0.6;
        }
    </style>
</head>
<body>
    <div id="map"></div>
    
    <script>
        // Variables globales
        let map;
        let bridge;
        let currentMode = 'pan';
        let antennaMarkers = {};
        let coverageLayers = {};
        let selectedMarker = null;
        
        // Inicializar mapa
        function initMap() {
            map = L.map('map').setView([-2.9001, -79.0059], 13);
            
            // Capas base
            const osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap contributors',
                maxZoom: 19
            });
            
            const satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
                attribution: 'Esri',
                maxZoom: 19
            });
            
            osmLayer.addTo(map);
            
            // Control de capas
            L.control.layers({
                'OpenStreetMap': osmLayer,
                'Satellite': satelliteLayer
            }).addTo(map);
            
            // Escala
            L.control.scale({imperial: false}).addTo(map);
            
            // Eventos del mapa
            map.on('click', handleMapClick);
            
            console.log('Map initialized');
        }
        
        // Manejar clic en el mapa
        function handleMapClick(e) {
            if (currentMode === 'add_antenna') {
                bridge.on_map_click(e.latlng.lat, e.latlng.lng);
            }
        }
        
        // Agregar marcador de antena
        function addAntennaMarker(id, lat, lon, name, color) {
            console.log('Adding antenna marker:', id, lat, lon);
            
            // Crear icono personalizado
            const icon = L.divIcon({
                className: 'antenna-marker',
                html: `
                    <svg class="antenna-icon" viewBox="0 0 40 40">
                        <circle cx="20" cy="20" r="8" fill="${color}" stroke="white" stroke-width="2"/>
                        <path d="M20,20 L20,5" stroke="${color}" stroke-width="3" stroke-linecap="round"/>
                        <circle cx="20" cy="5" r="3" fill="${color}"/>
                    </svg>
                `
            });
            
            // Crear marcador
            const marker = L.marker([lat, lon], {
                icon: icon,
                draggable: currentMode === 'move_antenna',
                title: name
            });
            
            // Popup
            marker.bindPopup(`<b>${name}</b><br>Lat: ${lat.toFixed(6)}<br>Lon: ${lon.toFixed(6)}`);
            
            // Eventos
            marker.on('click', () => {
                bridge.on_antenna_selected(id);
                selectMarker(id);
            });
            
            marker.on('dragend', (e) => {
                const pos = e.target.getLatLng();
                bridge.on_antenna_moved(id, pos.lat, pos.lng);
            });
            
            marker.addTo(map);
            antennaMarkers[id] = marker;
        }
        
        // Remover marcador de antena
        function removeAntennaMarker(id) {
            if (antennaMarkers[id]) {
                map.removeLayer(antennaMarkers[id]);
                delete antennaMarkers[id];
            }
        }
        
        // Actualizar marcador de antena
        function updateAntennaMarker(id, lat, lon, azimuth, color) {
            if (antennaMarkers[id]) {
                const marker = antennaMarkers[id];
                marker.setLatLng([lat, lon]);
                
                // Actualizar icono con azimuth
                const icon = L.divIcon({
                    className: 'antenna-marker',
                    html: `
                        <svg class="antenna-icon" viewBox="0 0 40 40" style="transform: rotate(${azimuth}deg)">
                            <circle cx="20" cy="20" r="8" fill="${color}" stroke="white" stroke-width="2"/>
                            <path d="M20,20 L20,5" stroke="${color}" stroke-width="3" stroke-linecap="round"/>
                            <circle cx="20" cy="5" r="3" fill="${color}"/>
                            <!-- Sector beam -->
                            <path d="M20,20 L10,5 L30,5 Z" fill="${color}" opacity="0.3"/>
                        </svg>
                    `
                });
                marker.setIcon(icon);
            }
        }
        
        // Seleccionar marcador
        function selectMarker(id) {
            // Deseleccionar anterior
            if (selectedMarker && antennaMarkers[selectedMarker]) {
                // Restaurar estilo normal
            }
            
            selectedMarker = id;
            
            // Resaltar nuevo
            if (antennaMarkers[id]) {
                antennaMarkers[id].openPopup();
            }
        }
        
        // Agregar capa de cobertura
        function addCoverageLayer(antennaId, imageUrl, latMin, lonMin, latMax, lonMax) {
            console.log('Adding coverage layer for:', antennaId);
            
            // Bounds del overlay
            var bounds = [[latMin, lonMin], [latMax, lonMax]];
            
            // Crear overlay de imagen
            var imageOverlay = L.imageOverlay(imageUrl, bounds, {
                opacity: 0.6,
                interactive: false
            });
            
            imageOverlay.addTo(map);
            coverageLayers[antennaId] = imageOverlay;
        }
        
        // Remover capa de cobertura
        function removeCoverageLayer(antennaId) {
            if (coverageLayers[antennaId]) {
                map.removeLayer(coverageLayers[antennaId]);
                delete coverageLayers[antennaId];
            }
        }
        
        // Cambiar modo del mapa
        function setMapMode(mode) {
            console.log('Map mode changed to:', mode);
            currentMode = mode;
            
            // Actualizar cursor
            const mapContainer = document.getElementById('map');
            if (mode === 'add_antenna') {
                mapContainer.style.cursor = 'crosshair';
            } else if (mode === 'move_antenna') {
                mapContainer.style.cursor = 'move';
            } else {
                mapContainer.style.cursor = '';
            }
            
            // Actualizar draggable de marcadores
            Object.values(antennaMarkers).forEach(marker => {
                marker.dragging[mode === 'move_antenna' ? 'enable' : 'disable']();
            });
        }
        
        // Centrar mapa
        function centerMap(lat, lon, zoom) {
            map.setView([lat, lon], zoom);
        }
        
        // Inicializar QWebChannel
        new QWebChannel(qt.webChannelTransport, function(channel) {
            bridge = channel.objects.bridge;
            
            // Conectar señales de Python a funciones JS
            bridge.add_antenna_marker.connect(addAntennaMarker);
            bridge.remove_antenna_marker.connect(removeAntennaMarker);
            bridge.update_antenna_marker.connect(updateAntennaMarker);
            bridge.add_coverage_layer.connect(addCoverageLayer);
            bridge.remove_coverage_layer.connect(removeCoverageLayer);
            bridge.set_map_mode.connect(setMapMode);
            bridge.center_map.connect(centerMap);
            
            console.log('Bridge connected');
            initMap();
        });
    </script>
</body>
</html>
        """
    
    # ===== Métodos públicos =====
    
    def set_mode(self, mode: MapMode):
        """Cambia el modo de interacción del mapa"""
        self.current_mode = mode
        self.bridge.set_map_mode.emit(mode.value)
        self.logger.info(f"Map mode set to: {mode.value}")
    
    def add_antenna(self, antenna_id: str, lat: float, lon: float, 
                    name: str, color: str = "#FF0000"):
        """Agrega marcador de antena al mapa"""
        self.bridge.add_antenna_marker.emit(antenna_id, lat, lon, name, color)
    
    def remove_antenna(self, antenna_id: str):
        """Remueve marcador de antena del mapa"""
        self.bridge.remove_antenna_marker.emit(antenna_id)
    
    def update_antenna(self, antenna_id: str, lat: float, lon: float, 
                      azimuth: float = 0.0, color: str = "#FF0000"):
        """Actualiza marcador de antena"""
        self.bridge.update_antenna_marker.emit(antenna_id, lat, lon, azimuth, color)
    def show_coverage(self, antenna_id: str, coverage_data: dict):
        """
        Muestra capa de cobertura como overlay
        
        Args:
            coverage_data: dict con 'lats', 'lons', 'rsrp', 'image_url'
        """
        if not self.bridge:
            return
        
        # Si viene con image_url (data URL de la imagen), usarlo
        if 'image_url' in coverage_data:
            bounds = coverage_data['bounds']  # [[lat_min, lon_min], [lat_max, lon_max]]
            self.bridge.add_coverage_layer.emit(
                antenna_id, 
                coverage_data['image_url'],
                bounds[0][0], bounds[0][1],  # lat_min, lon_min
                bounds[1][0], bounds[1][1]   # lat_max, lon_max
            )

    def show_coverage1(self, antenna_id: str, coverage_data: np.ndarray):
        """Muestra capa de cobertura para una antena"""
        # Convertir array numpy a formato compatible con Leaflet
        # En implementación real: convertir a GeoTIFF o formato raster
        geotiff_url = self._convert_to_geotiff(coverage_data)
        self.bridge.add_coverage_layer.emit(antenna_id, geotiff_url)
    
    def hide_coverage(self, antenna_id: str):
        """Oculta capa de cobertura"""
        self.bridge.remove_coverage_layer.emit(antenna_id)
    
    def center_on_location(self, lat: float, lon: float, zoom: int = 15):
        """Centra el mapa en una ubicación"""
        self.bridge.center_map.emit(lat, lon, zoom)
    
    def _handle_map_click(self, lat: float, lon: float):
        """Maneja clics en el mapa según el modo actual"""
        if self.current_mode == MapMode.ADD_ANTENNA:
            self.antenna_placed.emit(lat, lon)
            # Volver a modo navegación después de colocar
            self.set_mode(MapMode.PAN)
        elif self.current_mode == MapMode.SELECT:
            # Lógica de selección
            pass
    
    def _convert_to_geotiff(self, data: np.ndarray) -> str:
        """Convierte array numpy a GeoTIFF (implementación simplificada)"""
        # TODO: Implementar conversión real usando rasterio o GDAL
        return "data:image/geotiff;base64,..."