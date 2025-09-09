import React, { useState, useEffect, useCallback } from 'react';
import './App.css';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from './components/ui/card';
import { Badge } from './components/ui/badge';
import { Button } from './components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './components/ui/select';
import { MapPin, Wifi, WifiOff, Filter, RefreshCw } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const WS_URL = BACKEND_URL.replace('https://', 'wss://').replace('http://', 'ws://');

const DrainMonitoring = () => {
  const [drains, setDrains] = useState([]);
  const [filteredDrains, setFilteredDrains] = useState([]);
  const [filter, setFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [connected, setConnected] = useState(false);
  const [map, setMap] = useState(null);
  const [markers, setMarkers] = useState([]);
  const [socket, setSocket] = useState(null);

  // Status mapping
  const statusConfig = {
    livre: { color: '#10B981', label: 'Livre', bgColor: 'bg-green-100', textColor: 'text-green-800' },
    parcialmente_obstruido: { color: '#F59E0B', label: 'Parcialmente Obstruído', bgColor: 'bg-yellow-100', textColor: 'text-yellow-800' },
    entupido: { color: '#EF4444', label: 'Entupido', bgColor: 'bg-red-100', textColor: 'text-red-800' }
  };

  // Initialize Google Maps
  const initMap = useCallback(() => {
    if (window.google && !map) {
      const mapInstance = new window.google.maps.Map(document.getElementById('map'), {
        center: { lat: -23.5505, lng: -46.6333 }, // São Paulo center
        zoom: 14,
        styles: [
          {
            featureType: 'water',
            elementType: 'geometry',
            stylers: [{ color: '#193341' }]
          },
          {
            featureType: 'landscape',
            elementType: 'geometry',
            stylers: [{ color: '#2c5a64' }]
          },
          {
            featureType: 'road',
            elementType: 'geometry',
            stylers: [{ color: '#29768a' }, { lightness: -37 }]
          }
        ]
      });
      setMap(mapInstance);
    }
  }, [map]);

  // Create marker for drain
  const createMarker = useCallback((drain, mapInstance) => {
    if (!mapInstance || !window.google) return null;

    const marker = new window.google.maps.Marker({
      position: { lat: drain.latitude, lng: drain.longitude },
      map: mapInstance,
      title: drain.location_name,
      icon: {
        path: window.google.maps.SymbolPath.CIRCLE,
        scale: 8,
        fillColor: statusConfig[drain.status].color,
        fillOpacity: 1,
        strokeColor: '#ffffff',
        strokeWeight: 2
      }
    });

    const infoWindow = new window.google.maps.InfoWindow({
      content: `
        <div class="p-2">
          <h3 class="font-bold text-sm">${drain.location_name}</h3>
          <p class="text-xs text-gray-600">Status: ${statusConfig[drain.status].label}</p>
          <p class="text-xs text-gray-500">Última atualização: ${new Date(drain.last_updated).toLocaleString('pt-BR')}</p>
        </div>
      `
    });

    marker.addListener('click', () => {
      infoWindow.open(mapInstance, marker);
    });

    return marker;
  }, []);

  // Load Google Maps API
  useEffect(() => {
    const loadGoogleMaps = () => {
      if (window.google) {
        initMap();
        return;
      }

      const script = document.createElement('script');
      script.src = `https://maps.googleapis.com/maps/api/js?key=AIzaSyD0YaJUwr1zrXL9135WC9LTjkLwCZfHPpg&libraries=places`;
      script.async = true;
      script.defer = true;
      script.onload = initMap;
      document.head.appendChild(script);
    };

    loadGoogleMaps();
  }, [initMap]);

  // Update markers on map
  useEffect(() => {
    if (map && filteredDrains.length >= 0) {
      // Clear existing markers
      markers.forEach(marker => marker.setMap(null));
      
      // Create new markers
      const newMarkers = filteredDrains.map(drain => createMarker(drain, map));
      setMarkers(newMarkers.filter(marker => marker !== null));
    }
  }, [map, filteredDrains]);

  // WebSocket connection
  useEffect(() => {
    const connectWebSocket = () => {
      const ws = new WebSocket(`${WS_URL}/ws`);
      
      ws.onopen = () => {
        console.log('WebSocket connected');
        setConnected(true);
      };
      
      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          console.log('WebSocket message:', message);
          
          if (message.type === 'sensor_update' || message.type === 'drain_updated') {
            setDrains(prevDrains => {
              const updatedDrains = prevDrains.map(drain => 
                drain.id === message.data.id ? message.data : drain
              );
              return updatedDrains;
            });
          } else if (message.type === 'drain_created') {
            setDrains(prevDrains => [...prevDrains, message.data]);
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };
      
      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setConnected(false);
        // Reconnect after 3 seconds
        setTimeout(connectWebSocket, 3000);
      };
      
      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setConnected(false);
      };
      
      setSocket(ws);
    };

    connectWebSocket();

    return () => {
      if (socket) {
        socket.close();
      }
    };
  }, [WS_URL]);

  // Fetch drains data
  const fetchDrains = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/drains`);
      setDrains(response.data);
    } catch (error) {
      console.error('Error fetching drains:', error);
    } finally {
      setLoading(false);
    }
  };

  // Initialize sample data
  const initSampleData = async () => {
    try {
      await axios.post(`${API}/init-sample-data`);
      await fetchDrains();
    } catch (error) {
      console.error('Error initializing sample data:', error);
    }
  };

  // Filter drains based on status
  useEffect(() => {
    if (filter === 'all') {
      setFilteredDrains(drains);
    } else {
      setFilteredDrains(drains.filter(drain => drain.status === filter));
    }
  }, [drains, filter]);

  // Load initial data
  useEffect(() => {
    fetchDrains();
  }, []);

  const getStatusCounts = () => {
    return {
      total: drains.length,
      livre: drains.filter(d => d.status === 'livre').length,
      parcialmente_obstruido: drains.filter(d => d.status === 'parcialmente_obstruido').length,
      entupido: drains.filter(d => d.status === 'entupido').length
    };
  };

  const counts = getStatusCounts();

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <div className="flex items-center space-x-3">
              <MapPin className="h-8 w-8 text-blue-600" />
              <div>
                <h1 className="text-2xl font-bold text-gray-900">Monitoramento de Bueiros</h1>
                <p className="text-sm text-gray-500">Sistema em tempo real - São Paulo</p>
              </div>
            </div>
            
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2">
                {connected ? (
                  <Wifi className="h-5 w-5 text-green-500" />
                ) : (
                  <WifiOff className="h-5 w-5 text-red-500" />
                )}
                <span className={`text-sm ${connected ? 'text-green-600' : 'text-red-600'}`}>
                  {connected ? 'Conectado' : 'Desconectado'}
                </span>
              </div>
              
              <Button onClick={fetchDrains} variant="outline" size="sm">
                <RefreshCw className="h-4 w-4 mr-2" />
                Atualizar
              </Button>
              
              <Button onClick={initSampleData} variant="outline" size="sm">
                Dados de Exemplo
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Total</p>
                  <p className="text-2xl font-bold">{counts.total}</p>
                </div>
                <MapPin className="h-8 w-8 text-gray-400" />
              </div>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-green-600">Livres</p>
                  <p className="text-2xl font-bold text-green-600">{counts.livre}</p>
                </div>
                <div className="h-8 w-8 rounded-full bg-green-500"></div>
              </div>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-yellow-600">Parcialmente</p>
                  <p className="text-2xl font-bold text-yellow-600">{counts.parcialmente_obstruido}</p>
                </div>
                <div className="h-8 w-8 rounded-full bg-yellow-500"></div>
              </div>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-red-600">Entupidos</p>
                  <p className="text-2xl font-bold text-red-600">{counts.entupido}</p>
                </div>
                <div className="h-8 w-8 rounded-full bg-red-500"></div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Main Content */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Map */}
          <div className="lg:col-span-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span>Mapa de Bueiros</span>
                  <div className="flex items-center space-x-2">
                    <Filter className="h-4 w-4" />
                    <Select value={filter} onValueChange={setFilter}>
                      <SelectTrigger className="w-48">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">Todos os status</SelectItem>
                        <SelectItem value="livre">Apenas livres</SelectItem>
                        <SelectItem value="parcialmente_obstruido">Parcialmente obstruídos</SelectItem>
                        <SelectItem value="entupido">Apenas entupidos</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div id="map" className="w-full h-96 rounded-lg"></div>
              </CardContent>
            </Card>
          </div>

          {/* Sidebar - Drain List */}
          <div>
            <Card>
              <CardHeader>
                <CardTitle>Lista de Bueiros ({filteredDrains.length})</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3 max-h-96 overflow-y-auto">
                  {loading ? (
                    <div className="text-center py-4">Carregando...</div>
                  ) : filteredDrains.length === 0 ? (
                    <div className="text-center py-4 text-gray-500">
                      Nenhum bueiro encontrado
                    </div>
                  ) : (
                    filteredDrains.map((drain) => (
                      <div key={drain.id} className="border rounded-lg p-3 hover:bg-gray-50">
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <h4 className="font-medium text-sm">{drain.location_name}</h4>
                            <p className="text-xs text-gray-500 mt-1">
                              {drain.latitude.toFixed(6)}, {drain.longitude.toFixed(6)}
                            </p>
                            <p className="text-xs text-gray-400 mt-1">
                              {new Date(drain.last_updated).toLocaleString('pt-BR')}
                            </p>
                          </div>
                          <Badge className={`${statusConfig[drain.status].bgColor} ${statusConfig[drain.status].textColor} border-0`}>
                            {statusConfig[drain.status].label}
                          </Badge>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DrainMonitoring;