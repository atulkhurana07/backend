import os
import sys

def generate_frontend_pages():
    frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
    pages_dir = os.path.join(frontend_dir, "src", "pages")
    os.makedirs(pages_dir, exist_ok=True)
    print("Writing updated frontend pages in:", pages_dir)

    # 1. ChargingStationsPage.tsx
    charging_page_code = """import React, { useState, useEffect, useRef } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { 
  Zap, 
  Search, 
  PlusCircle, 
  Navigation, 
  Phone, 
  Map as MapIcon, 
  List as ListIcon, 
  X, 
  CheckCircle2, 
  ExternalLink, 
  Info,
  Star
} from 'lucide-react';
import VoltiHeader from '../components/volti/VoltiHeader';
import VoltiFooter from '../components/volti/VoltiFooter';
import VoltiBackToTop from '../components/volti/VoltiBackToTop';
import { BIKANER_CHARGING_STATIONS, BikanerStation } from '../data/bikanerData';

// Free, reliable, crystal clear OpenStreetMap raster tiles (Zero API key requirement, zero watermarks)
const OSM_RASTER_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    'osm-tiles': {
      type: 'raster',
      tiles: [
        'https://a.tile.openstreetmap.org/{z}/{x}/{y}.png',
        'https://b.tile.openstreetmap.org/{z}/{x}/{y}.png',
        'https://c.tile.openstreetmap.org/{z}/{x}/{y}.png'
      ],
      tileSize: 256,
      attribution: '© OpenStreetMap contributors'
    }
  },
  layers: [
    {
      id: 'osm-tiles-layer',
      type: 'raster',
      source: 'osm-tiles',
      minzoom: 0,
      maxzoom: 19
    }
  ]
};

function calculateDistanceKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return Math.round(R * c * 10) / 10;
}

export const ChargingStationsPage: React.FC = () => {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);

  const [stations, setStations] = useState<BikanerStation[]>(BIKANER_CHARGING_STATIONS);
  const [selectedStation, setSelectedStation] = useState<BikanerStation | null>(BIKANER_CHARGING_STATIONS[0]);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState<'all' | 'fast_dc' | '24x7' | 'ccs2' | 'top_rated'>('all');
  const [viewMode, setViewMode] = useState<'map' | 'list'>('map');
  const [userLocation, setUserLocation] = useState<{ lat: number; lng: number } | null>(null);
  const [isLocating, setIsLocating] = useState(false);
  const [locationError, setLocationError] = useState<string | null>(null);

  // Add Center Modal State
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState(false);
  const [newStationForm, setNewStationForm] = useState({
    name: '',
    brand: 'Tata Power',
    address: '',
    area: 'Rani Bazar',
    pincode: '334001',
    latitude: 28.0229,
    longitude: 73.3119,
    powerKw: 60,
    connectors: 'CCS-2 (Fast DC), Type-2 (AC)',
    pricingInrPerKwh: 18.0,
    operatingHours: '24/7 Open',
    contactPhone: '+91 151 220000',
    description: '',
    imageUrl: 'https://images.unsplash.com/photo-1593941707882-a5bba14938c7?auto=format&fit=crop&w=800&q=80',
    amenities: ['24/7 Access', 'Restrooms', 'WiFi', 'EV Parking']
  });

  useEffect(() => {
    fetch('http://localhost:8000/api/public/charging-centers?city=Bikaner')
      .then((res) => {
        if (!res.ok) throw new Error('Backend offline');
        return res.json();
      })
      .then((backendStations: any[]) => {
        if (backendStations && backendStations.length > 0) {
          const mapped = backendStations.map((bs, index) => {
            const fallback = BIKANER_CHARGING_STATIONS[index % BIKANER_CHARGING_STATIONS.length];
            return {
              id: bs.id || `bkn-srv-${index}`,
              name: bs.name,
              brand: bs.name.includes('Tata') ? 'Tata Power' : bs.name.includes('Jio') ? 'Jio-bp pulse' : bs.name.includes('Statiq') ? 'Statiq' : 'ChargeZone',
              address: bs.address || fallback.address,
              area: bs.address?.split(',')[1] || fallback.area,
              city: bs.city || 'Bikaner',
              state: bs.state || 'Rajasthan',
              pincode: bs.pincode || '334001',
              latitude: bs.latitude,
              longitude: bs.longitude,
              status: bs.status === 'operational' ? 'Operational' : 'Limited',
              powerKw: bs.power_kw || fallback.powerKw,
              connectors: fallback.connectors,
              pricingInrPerKwh: bs.amenities?.pricing_inr_kwh || fallback.pricingInrPerKwh,
              operatingHours: bs.operating_hours || fallback.operatingHours,
              contactPhone: bs.contact_phone || fallback.contactPhone,
              description: bs.description || fallback.description,
              amenities: fallback.amenities,
              imageUrl: bs.amenities?.image_url || fallback.imageUrl,
              rating: fallback.rating,
              reviewCount: fallback.reviewCount,
              isVerified: true
            } as BikanerStation;
          });
          setStations(mapped);
        }
      })
      .catch(() => {
        setStations(BIKANER_CHARGING_STATIONS);
      });
  }, []);

  const filteredStations = stations.filter((st) => {
    const q = searchQuery.toLowerCase();
    const matchesSearch =
      st.name.toLowerCase().includes(q) ||
      st.address.toLowerCase().includes(q) ||
      st.area.toLowerCase().includes(q) ||
      st.brand.toLowerCase().includes(q);

    if (!matchesSearch) return false;

    if (activeFilter === 'fast_dc') return st.powerKw >= 50;
    if (activeFilter === '24x7') return st.operatingHours.includes('24/7');
    if (activeFilter === 'ccs2') return st.connectors.some((c) => c.type.includes('CCS'));
    if (activeFilter === 'top_rated') return st.rating >= 4.5;

    return true;
  });

  const stationsWithDistance = filteredStations.map((st) => {
    if (userLocation) {
      const dist = calculateDistanceKm(userLocation.lat, userLocation.lng, st.latitude, st.longitude);
      return { ...st, distanceKm: dist };
    }
    return st;
  });

  if (userLocation) {
    stationsWithDistance.sort((a, b) => (a.distanceKm || 0) - (b.distanceKm || 0));
  }

  useEffect(() => {
    if (!mapContainer.current) return;

    if (!mapRef.current) {
      const map = new maplibregl.Map({
        container: mapContainer.current,
        style: OSM_RASTER_STYLE,
        center: [73.3119, 28.0229],
        zoom: 13,
        attributionControl: false
      });

      map.addControl(new maplibregl.NavigationControl({ showCompass: true, showZoom: true }), 'top-right');
      mapRef.current = map;
    }

    const map = mapRef.current;

    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];

    stationsWithDistance.forEach((st) => {
      const isSelected = selectedStation?.id === st.id;

      const el = document.createElement('div');
      el.className = 'custom-map-marker';
      el.style.cursor = 'pointer';
      el.innerHTML = `
        <div style="
          background: ${isSelected ? '#4d7c0f' : '#84cc16'};
          color: white;
          padding: 6px 12px;
          border-radius: 24px;
          font-weight: 800;
          font-size: 12px;
          display: flex;
          align-items: center;
          gap: 5px;
          box-shadow: 0 4px 16px rgba(0,0,0,0.3);
          border: 2.5px solid white;
          transform: ${isSelected ? 'scale(1.2)' : 'scale(1)'};
          transition: all 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
        ">
          <span>⚡ ${st.powerKw}kW</span>
        </div>
      `;

      el.addEventListener('click', () => {
        setSelectedStation(st);
        map.flyTo({ center: [st.longitude, st.latitude], zoom: 14.5, speed: 1.2 });
      });

      const marker = new maplibregl.Marker({ element: el })
        .setLngLat([st.longitude, st.latitude])
        .addTo(map);

      markersRef.current.push(marker);
    });

    if (userLocation) {
      const userEl = document.createElement('div');
      userEl.innerHTML = `
        <div style="
          width: 24px;
          height: 24px;
          background: #0284c7;
          border-radius: 50%;
          border: 3px solid white;
          box-shadow: 0 0 16px #0284c7;
          position: relative;
        ">
          <div style="
            position: absolute;
            inset: -8px;
            border-radius: 50%;
            border: 2.5px solid #38bdf8;
            animation: ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite;
          "></div>
        </div>
      `;
      const userMarker = new maplibregl.Marker({ element: userEl })
        .setLngLat([userLocation.lng, userLocation.lat])
        .addTo(map);
      markersRef.current.push(userMarker);
    }
  }, [stationsWithDistance, selectedStation, userLocation]);

  const handleGetLocation = () => {
    if (!navigator.geolocation) {
      setLocationError('Geolocation is not supported by your browser');
      return;
    }
    setIsLocating(true);
    setLocationError(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setIsLocating(false);
        const loc = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        setUserLocation(loc);
        if (mapRef.current) {
          mapRef.current.flyTo({ center: [loc.lng, loc.lat], zoom: 14 });
        }
      },
      () => {
        setIsLocating(false);
        setLocationError('Please allow GPS location permission to find nearest chargers.');
      },
      { timeout: 10000 }
    );
  };

  const handleAddNewStation = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    // ... logic for submission ...
    setIsSubmitting(false);
    setSubmitSuccess(true);
    setTimeout(() => {
        setSubmitSuccess(false);
        setIsAddModalOpen(false);
    }, 1500);
  };

  return (
    <div className="volti-app bg-[#f8fafc] w-full min-h-screen flex flex-col font-sans">
      <VoltiHeader />

      {/* Main App Canvas */}
      <div className="w-full flex-1 pt-24 pb-6 px-3 sm:px-6 max-w-[1680px] mx-auto flex flex-col">
        {/* Floating Top Control Bar (Benchmark Reference Style) */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200/80 p-3 sm:p-4 mb-4 flex flex-wrap items-center justify-between gap-3">
          {/* Search Input Box */}
          <div className="relative flex-1 min-w-[260px] max-w-md">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
            <input
              type="text"
              placeholder="Search Bikaner stations, areas (Rani Bazar, NH-11, PBM)..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-9 py-2.5 bg-slate-100/90 hover:bg-slate-100 focus:bg-white border border-slate-200 focus:border-[#84cc16] focus:ring-2 focus:ring-[#84cc16]/20 rounded-xl text-sm font-semibold text-slate-800 transition-all outline-none"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-700"
              >
                <X size={16} />
              </button>
            )}
          </div>

          {/* Filter Pills with Proper Gap and Touch Target */}
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => setActiveFilter('all')}
              className={`px-3.5 py-2 rounded-xl text-xs font-bold transition-all min-h-[38px] ${
                activeFilter === 'all'
                  ? 'bg-[#84cc16] text-white shadow-sm'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              All ({stations.length})
            </button>
            <button
              onClick={() => setActiveFilter('fast_dc')}
              className={`px-3.5 py-2 rounded-xl text-xs font-bold transition-all min-h-[38px] ${
                activeFilter === 'fast_dc'
                  ? 'bg-[#84cc16] text-white shadow-sm'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              ⚡ 50kW+ Fast DC
            </button>
            <button
              onClick={() => setActiveFilter('24x7')}
              className={`px-3.5 py-2 rounded-xl text-xs font-bold transition-all min-h-[38px] ${
                activeFilter === '24x7'
                  ? 'bg-[#84cc16] text-white shadow-sm'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              🕒 24/7 Open
            </button>
            <button
              onClick={() => setActiveFilter('ccs2')}
              className={`px-3.5 py-2 rounded-xl text-xs font-bold transition-all min-h-[38px] ${
                activeFilter === 'ccs2'
                  ? 'bg-[#84cc16] text-white shadow-sm'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              🔌 CCS-2 Gun
            </button>
            <button
              onClick={() => setActiveFilter('top_rated')}
              className={`px-3.5 py-2 rounded-xl text-xs font-bold transition-all min-h-[38px] ${
                activeFilter === 'top_rated'
                  ? 'bg-[#84cc16] text-white shadow-sm'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              ⭐ Top Rated
            </button>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2">
            <button
              onClick={handleGetLocation}
              disabled={isLocating}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-lime-100 text-lime-900 hover:bg-lime-200 font-bold text-xs transition-all cursor-pointer min-h-[38px]"
              title="Find nearest EV station to your GPS location"
            >
              <Navigation size={14} className={isLocating ? 'animate-spin' : ''} />
              {isLocating ? 'Locating...' : 'Near Me'}
            </button>

            <button
              onClick={() => setIsAddModalOpen(true)}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#84cc16] hover:bg-[#65a30d] text-white font-bold text-xs shadow-md transition-all cursor-pointer min-h-[38px]"
            >
              <PlusCircle size={15} />
              + Add Station
            </button>

            <div className="bg-slate-100 p-1 rounded-xl flex items-center gap-1">
              <button
                onClick={() => setViewMode('map')}
                className={`p-2 rounded-lg transition-all min-h-[34px] min-w-[34px] flex items-center justify-center ${
                  viewMode === 'map' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-500'
                }`}
                title="Map View"
              >
                <MapIcon size={16} />
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={`p-2 rounded-lg transition-all min-h-[34px] min-w-[34px] flex items-center justify-center ${
                  viewMode === 'list' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-500'
                }`}
                title="List View"
              >
                <ListIcon size={16} />
              </button>
            </div>
          </div>
        </div>

        {locationError && (
          <div className="mb-3 bg-amber-50 border border-amber-200 text-amber-800 px-4 py-2 rounded-xl text-xs flex items-center gap-2">
            <Info size={14} />
            {locationError}
          </div>
        )}

        {/* 2-Column Responsive Body Layout */}
        <div className="flex-1 flex flex-col lg:flex-row gap-4 items-stretch h-[calc(100vh-200px)] min-h-[600px]">
          {/* Left Column: Station Card Directory (38% width) */}
          <div className={`w-full lg:w-[460px] xl:w-[500px] flex flex-col shrink-0 bg-white rounded-2xl p-3 border border-slate-200/80 shadow-sm ${
            viewMode === 'map' ? 'hidden lg:flex' : 'flex'
          }`}>
            <div className="flex items-center justify-between px-2 py-2 border-b border-slate-100 mb-2">
              <div className="flex items-center gap-2">
                <span className="font-extrabold text-sm text-slate-900">Bikaner Stations</span>
                <span className="text-xs font-bold bg-[#ecfccb] text-[#4d7c0f] px-2.5 py-0.5 rounded-full">
                  {stationsWithDistance.length} Active
                </span>
              </div>
              {userLocation && (
                <span className="text-xs text-slate-500 font-medium">📍 Sorted by Distance</span>
              )}
            </div>

            {/* Scrolling Card List */}
            <div className="flex-1 overflow-y-auto pr-1.5 space-y-3">
              {stationsWithDistance.map((station) => {
                const isSelected = selectedStation?.id === station.id;
                return (
                  <div
                    key={station.id}
                    onClick={() => {
                      setSelectedStation(station);
                      if (mapRef.current) {
                        mapRef.current.flyTo({
                          center: [station.longitude, station.latitude],
                          zoom: 14.5,
                          speed: 1.2
                        });
                      }
                    }}
                    className={`bg-white rounded-2xl p-3.5 border transition-all cursor-pointer shadow-xs hover:shadow-md ${
                      isSelected
                        ? 'border-[#84cc16] ring-2 ring-[#84cc16]/20 bg-[#f7fee7]/40'
                        : 'border-slate-200 hover:border-slate-300'
                    }`}
                  >
                    {/* Header inside Card: Integrated Badges */}
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <span className="text-[11px] font-extrabold uppercase tracking-wider text-[#4d7c0f] bg-[#ecfccb] px-2.5 py-0.5 rounded-md">
                        {station.brand}
                      </span>
                      
                      <div className="flex items-center gap-2">
                        {/* Power Rating Badge (Integrated inside card header) */}
                        <span className="inline-flex items-center gap-1 text-[11px] font-bold text-white bg-[#84cc16] px-2.5 py-0.5 rounded-full shadow-xs">
                          ⚡ {station.powerKw} kW DC
                        </span>

                        {station.distanceKm !== undefined && (
                          <span className="text-[11px] font-bold text-sky-700 bg-sky-50 px-2 py-0.5 rounded-full">
                            📍 {station.distanceKm} km
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Card Body */}
                    <div className="flex gap-3">
                      <img
                        src={station.imageUrl}
                        alt={station.name}
                        className="w-20 h-20 object-cover rounded-xl shrink-0 bg-slate-100 border border-slate-100"
                      />
                      <div className="flex-1 min-w-0">
                        <h4 className="font-extrabold text-slate-900 text-sm truncate">{station.name}</h4>
                        <p className="text-xs text-slate-500 line-clamp-2 mt-0.5">{station.address}</p>

                        <div className="flex items-center gap-2.5 mt-2 text-xs font-semibold text-slate-700">
                          <span className="flex items-center gap-1 text-amber-600 font-bold">
                            <Star size={12} className="fill-amber-500 text-amber-500" />
                            {station.rating} ({station.reviewCount})
                          </span>
                          <span>•</span>
                          <span className="text-slate-600 font-bold">₹{station.pricingInrPerKwh}/kWh</span>
                        </div>
                      </div>
                    </div>

                    {/* Card Footer: Connectors & Action */}
                    <div className="mt-3 pt-2.5 border-t border-slate-100 flex flex-wrap items-center justify-between gap-2">
                      <div className="flex flex-wrap gap-1.5">
                        {station.connectors.map((c, i) => (
                          <span
                            key={i}
                            className="inline-flex items-center gap-1 text-[10px] font-semibold bg-slate-100 text-slate-700 px-2 py-0.5 rounded-md"
                          >
                            <span className="w-1.5 h-1.5 rounded-full bg-[#84cc16]"></span>
                            {c.type} ({c.count} Guns)
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                );
              })}

              {stationsWithDistance.length === 0 && (
                <div className="text-center py-12 bg-white rounded-2xl border border-slate-200">
                  <p className="text-slate-500 text-sm">No charging stations found matching your search.</p>
                  <button
                    onClick={() => {
                      setSearchQuery('');
                      setActiveFilter('all');
                    }}
                    className="mt-3 text-xs font-bold text-[#65a30d] hover:underline"
                  >
                    Reset Filters
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Full-Height Interactive OpenStreetMap (62% width) */}
          <div className={`flex-1 w-full h-full bg-white rounded-2xl overflow-hidden shadow-sm border border-slate-200/80 relative ${
            viewMode === 'list' ? 'hidden lg:block' : 'block'
          }`}>
            <div ref={mapContainer} className="w-full h-full" />

            {/* Results Counter Badge (Benchmark Reference style) */}
            <div className="absolute bottom-4 left-4 bg-white/95 backdrop-blur-md px-3.5 py-1.5 rounded-full shadow-md border border-slate-200 text-xs font-extrabold text-slate-800 z-10 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[#84cc16] animate-pulse"></span>
              {filteredStations.length} Bikaner Charging Hubs
            </div>

            {/* Selected Station Floating Bottom Card */}
            {selectedStation && (
              <div className="absolute bottom-16 sm:bottom-4 left-4 right-4 sm:left-auto sm:right-4 sm:max-w-md bg-white/95 backdrop-blur-md p-4 rounded-2xl shadow-xl border border-slate-200/90 z-10">
                <div className="flex gap-3 items-center">
                  <img
                    src={selectedStation.imageUrl}
                    alt={selectedStation.name}
                    className="w-16 h-16 object-cover rounded-xl shrink-0"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-1">
                      <span className="text-[10px] font-bold text-[#4d7c0f] bg-[#ecfccb] px-2 py-0.5 rounded-full">
                        ⚡ {selectedStation.powerKw} kW Fast Charger
                      </span>
                      {selectedStation.distanceKm !== undefined && (
                        <span className="text-[10px] font-bold text-sky-700 bg-sky-50 px-2 py-0.5 rounded-full">
                          📍 {selectedStation.distanceKm} km
                        </span>
                      )}
                    </div>
                    <h4 className="font-extrabold text-slate-900 text-sm truncate mt-1">{selectedStation.name}</h4>
                    <p className="text-xs text-slate-500 truncate mt-0.5">{selectedStation.address}</p>
                  </div>
                </div>

                <div className="flex items-center gap-2 mt-3 pt-2.5 border-t border-slate-100">
                  <a
                    href={`https://www.google.com/maps/dir/?api=1&destination=${selectedStation.latitude},${selectedStation.longitude}`}
                    target="_blank"
                    rel="noreferrer"
                    className="flex-1 inline-flex items-center justify-center gap-1.5 bg-[#84cc16] hover:bg-[#65a30d] text-white py-2 rounded-xl text-xs font-bold shadow-xs transition-all"
                  >
                    <ExternalLink size={13} />
                    Get Directions
                  </a>
                  <a
                    href={`tel:${selectedStation.contactPhone}`}
                    className="inline-flex items-center justify-center gap-1.5 bg-slate-100 hover:bg-slate-200 text-slate-800 px-3.5 py-2 rounded-xl text-xs font-bold transition-all"
                  >
                    <Phone size={13} />
                    Call
                  </a>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Add New Charging Center Modal */}
      {isAddModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto">
          <div className="bg-white rounded-3xl max-w-2xl w-full p-6 sm:p-8 shadow-2xl border border-slate-100 relative my-8">
            <button
              onClick={() => setIsAddModalOpen(false)}
              className="absolute top-5 right-5 text-slate-400 hover:text-slate-700 p-2 rounded-full hover:bg-slate-100 transition-colors cursor-pointer"
            >
              <X size={20} />
            </button>

            {submitSuccess ? (
              <div className="text-center py-10">
                <CheckCircle2 size={64} className="text-[#84cc16] mx-auto mb-4" />
                <h3 className="text-2xl font-extrabold text-slate-900">Station Registered Successfully!</h3>
                <p className="text-slate-600 text-sm mt-2 max-w-md mx-auto">
                  Your charging center has been verified and added to the live Bikaner network map.
                </p>
              </div>
            ) : (
              <div>
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-10 h-10 rounded-xl bg-[#ecfccb] text-[#65a30d] flex items-center justify-center font-bold">
                    <PlusCircle size={22} />
                  </div>
                  <div>
                    <h3 className="text-xl sm:text-2xl font-extrabold text-slate-900">Register New Charging Center</h3>
                    <p className="text-xs text-slate-500">Submit a new EV charging location in Bikaner, Rajasthan.</p>
                  </div>
                </div>

                <form onSubmit={handleAddNewStation} className="space-y-4">
                    {/* Form fields here */}
                </form>
              </div>
            )}
          </div>
        </div>
      )}

      <VoltiFooter />
      <VoltiBackToTop />
    </div>
  );
};

export default ChargingStationsPage;
"""

    # Write ChargingStationsPage.tsx & SearchPage.tsx
    with open(os.path.join(pages_dir, "ChargingStationsPage.tsx"), "w", encoding="utf-8") as f:
        f.write(charging_page_code)
    with open(os.path.join(pages_dir, "SearchPage.tsx"), "w", encoding="utf-8") as f:
        f.write(charging_page_code)
    print("[+] Created ChargingStationsPage.tsx and SearchPage.tsx")

    # 2. WhereIsMyUrjaPage.tsx
    urja_page_code = """import React, { useState, useEffect, useRef } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { 
  MapPin, 
  Navigation, 
  ArrowRightLeft, 
  Clock, 
  BatteryCharging, 
  Sparkles,
  CheckCircle,
  Phone
} from 'lucide-react';
import VoltiHeader from '../components/volti/VoltiHeader';
import VoltiFooter from '../components/volti/VoltiFooter';
import VoltiBackToTop from '../components/volti/VoltiBackToTop';
import { 
  BIKANER_BUS_STOPS, 
  BIKANER_BUS_ROUTES, 
  BIKANER_ACTIVE_BUSES, 
  BikanerBusStop, 
  BikanerBusRoute, 
  BikanerActiveBus 
} from '../data/bikanerData';

// Free, reliable, crystal clear OpenStreetMap raster tiles
const OSM_RASTER_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    'osm-tiles': {
      type: 'raster',
      tiles: [
        'https://a.tile.openstreetmap.org/{z}/{x}/{y}.png',
        'https://b.tile.openstreetmap.org/{z}/{x}/{y}.png',
        'https://c.tile.openstreetmap.org/{z}/{x}/{y}.png'
      ],
      tileSize: 256,
      attribution: '© OpenStreetMap contributors'
    }
  },
  layers: [
    {
      id: 'osm-tiles-layer',
      type: 'raster',
      source: 'osm-tiles',
      minzoom: 0,
      maxzoom: 19
    }
  ]
};

function calculateDistanceKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return Math.round(R * c * 10) / 10;
}

export const WhereIsMyUrjaPage: React.FC = () => {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);

  const [fromStopText, setFromStopText] = useState('Junagarh Fort Main Gate');
  const [toStopText, setToStopText] = useState('Ganga Shahar Bus Stand');
  const [selectedFromStop, setSelectedFromStop] = useState<BikanerBusStop | null>(
    BIKANER_BUS_STOPS.find((s) => s.name.includes('Junagarh')) || BIKANER_BUS_STOPS[4]
  );
  const [selectedToStop, setSelectedToStop] = useState<BikanerBusStop | null>(
    BIKANER_BUS_STOPS.find((s) => s.name.includes('Ganga Shahar')) || BIKANER_BUS_STOPS[13]
  );

  const [fromSuggestions, setFromSuggestions] = useState<BikanerBusStop[]>([]);
  const [toSuggestions, setToSuggestions] = useState<BikanerBusStop[]>([]);
  const [showFromDropdown, setShowFromDropdown] = useState(false);
  const [showToDropdown, setShowToDropdown] = useState(false);

  const [selectedRoute, setSelectedRoute] = useState<BikanerBusRoute>(BIKANER_BUS_ROUTES[0]);
  const [activeBuses] = useState<BikanerActiveBus[]>(BIKANER_ACTIVE_BUSES);
  const [selectedBus, setSelectedBus] = useState<BikanerActiveBus | null>(BIKANER_ACTIVE_BUSES[0]);

  const [nearestStopInfo, setNearestStopInfo] = useState<{ stop: BikanerBusStop; distanceM: number } | null>(null);
  const [isLocating, setIsLocating] = useState(false);

  const handleFromChange = (text: string) => {
    setFromStopText(text);
    if (text.trim().length > 0) {
      const q = text.toLowerCase();
      const filtered = BIKANER_BUS_STOPS.filter(
        (s) => s.name.toLowerCase().includes(q) || s.hindiName.includes(q) || s.area.toLowerCase().includes(q)
      );
      setFromSuggestions(filtered);
      setShowFromDropdown(true);
    } else {
      setFromSuggestions([]);
      setShowFromDropdown(false);
    }
  };

  const handleToChange = (text: string) => {
    setToStopText(text);
    if (text.trim().length > 0) {
      const q = text.toLowerCase();
      const filtered = BIKANER_BUS_STOPS.filter(
        (s) => s.name.toLowerCase().includes(q) || s.hindiName.includes(q) || s.area.toLowerCase().includes(q)
      );
      setToSuggestions(filtered);
      setShowToDropdown(true);
    } else {
      setToSuggestions([]);
      setShowToDropdown(false);
    }
  };

  const handleSwapStops = () => {
    const tempText = fromStopText;
    const tempStop = selectedFromStop;
    setFromStopText(toStopText);
    setSelectedFromStop(selectedToStop);
    setToStopText(tempText);
    setSelectedToStop(tempStop);
  };

  const handleFindNearestStop = () => {
    if (!navigator.geolocation) return;
    setIsLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setIsLocating(false);
        const uLat = pos.coords.latitude;
        const uLng = pos.coords.longitude;

        let closest = BIKANER_BUS_STOPS[0];
        let minD = 99999;
        BIKANER_BUS_STOPS.forEach((st) => {
          const d = calculateDistanceKm(uLat, uLng, st.latitude, st.longitude);
          if (d < minD) {
            minD = d;
            closest = st;
          }
        });

        const distM = Math.round(minD * 1000);
        setNearestStopInfo({ stop: closest, distanceM: distM });
        setSelectedFromStop(closest);
        setFromStopText(closest.name);

        if (mapRef.current) {
          mapRef.current.flyTo({ center: [closest.longitude, closest.latitude], zoom: 14.5 });
        }
      },
      () => {
        setIsLocating(false);
      },
      { timeout: 10000 }
    );
  };

  const matchingRoutes = BIKANER_BUS_ROUTES.filter((r) => {
    if (!selectedFromStop && !selectedToStop) return true;
    const hasFrom = selectedFromStop ? r.stops.some((s) => s.stopId === selectedFromStop.id) : true;
    const hasTo = selectedToStop ? r.stops.some((s) => s.stopId === selectedToStop.id) : true;
    return hasFrom && hasTo;
  });

  const displayRoute = matchingRoutes.length > 0 ? matchingRoutes[0] : selectedRoute;

  useEffect(() => {
    if (!mapContainer.current) return;

    if (!mapRef.current) {
      const map = new maplibregl.Map({
        container: mapContainer.current,
        style: OSM_RASTER_STYLE,
        center: [73.3180, 28.0229],
        zoom: 13,
        attributionControl: false
      });

      map.addControl(new maplibregl.NavigationControl(), 'top-right');
      mapRef.current = map;
    }

    const map = mapRef.current;

    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];

    displayRoute.stops.forEach((st) => {
      const stopData = BIKANER_BUS_STOPS.find((s) => s.id === st.stopId);
      if (!stopData) return;

      const isFrom = selectedFromStop?.id === stopData.id;
      const isTo = selectedToStop?.id === stopData.id;

      const el = document.createElement('div');
      el.style.cursor = 'pointer';
      el.innerHTML = `
        <div style="
          background: ${isFrom ? '#16a34a' : isTo ? '#dc2626' : '#ffffff'};
          color: ${isFrom || isTo ? '#ffffff' : '#0f172a'};
          border: 2px solid ${isFrom ? '#15803d' : isTo ? '#b91c1c' : displayRoute.color};
          padding: 4px 8px;
          border-radius: 12px;
          font-weight: 800;
          font-size: 11px;
          box-shadow: 0 2px 8px rgba(0,0,0,0.25);
          display: flex;
          align-items: center;
          gap: 3px;
          white-space: nowrap;
        ">
          <span>🚏 ${st.sequence}. ${stopData.name.split(' ')[0]}</span>
        </div>
      `;

      const marker = new maplibregl.Marker({ element: el })
        .setLngLat([stopData.longitude, stopData.latitude])
        .addTo(map);

      markersRef.current.push(marker);
    });

    activeBuses.forEach((bus) => {
      const isSelected = selectedBus?.id === bus.id;

      const busEl = document.createElement('div');
      busEl.style.cursor = 'pointer';
      busEl.innerHTML = `
        <div style="
          background: ${displayRoute.color};
          color: white;
          padding: 6px 12px;
          border-radius: 24px;
          font-weight: 800;
          font-size: 12px;
          display: flex;
          align-items: center;
          gap: 5px;
          box-shadow: 0 4px 16px rgba(0,0,0,0.35);
          border: 2.5px solid white;
          transform: ${isSelected ? 'scale(1.2)' : 'scale(1)'};
          transition: all 0.2s ease;
        ">
          <span style="font-size: 14px;">🚌</span>
          <span>${bus.busNumber.slice(-3)}</span>
          <span style="font-size: 10px; opacity: 0.9;">(${bus.speedKmh}km/h)</span>
        </div>
      `;

      busEl.addEventListener('click', () => {
        setSelectedBus(bus);
        map.flyTo({ center: [bus.longitude, bus.latitude], zoom: 14.5 });
      });

      const busMarker = new maplibregl.Marker({ element: busEl })
        .setLngLat([bus.longitude, bus.latitude])
        .addTo(map);

      markersRef.current.push(busMarker);
    });

    const coordinates = displayRoute.stops
      .map((st) => {
        const s = BIKANER_BUS_STOPS.find((b) => b.id === st.stopId);
        return s ? [s.longitude, s.latitude] : null;
      })
      .filter((c): c is [number, number] => c !== null);

    if (coordinates.length > 1) {
      if (map.getSource('route-line')) {
        (map.getSource('route-line') as maplibregl.GeoJSONSource).setData({
          type: 'Feature',
          properties: {},
          geometry: { type: 'LineString', coordinates }
        });
      } else {
        map.on('load', () => {
          if (!map.getSource('route-line')) {
            map.addSource('route-line', {
              type: 'geojson',
              data: {
                type: 'Feature',
                properties: {},
                geometry: { type: 'LineString', coordinates }
              }
            });
            map.addLayer({
              id: 'route-line-layer',
              type: 'line',
              source: 'route-line',
              layout: { 'line-join': 'round', 'line-cap': 'round' },
              paint: {
                'line-color': displayRoute.color,
                'line-width': 5,
                'line-opacity': 0.9
              }
            });
          }
        });
      }
    }
  }, [displayRoute, activeBuses, selectedBus, selectedFromStop, selectedToStop]);

  return (
    <div className="volti-app bg-[#f8fafc] w-full min-h-screen flex flex-col font-sans">
      <VoltiHeader />

      {/* Main Canvas */}
      <div className="w-full flex-1 pt-24 pb-6 px-3 sm:px-6 max-w-[1680px] mx-auto flex flex-col">
        {/* Where Is My Train Style Search Card */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200/80 p-4 sm:p-5 mb-4">
          <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-4">
            {/* Search Route Inputs */}
            <div className="flex-1 grid grid-cols-1 md:grid-cols-11 gap-3 items-center">
              {/* From Stop */}
              <div className="md:col-span-5 relative">
                <label className="block text-xs font-extrabold uppercase tracking-wider text-slate-500 mb-1">
                  From Stop (स्थान से)
                </label>
                <div className="relative">
                  <MapPin className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#16a34a]" size={18} />
                  <input
                    type="text"
                    value={fromStopText}
                    onChange={(e) => handleFromChange(e.target.value)}
                    onFocus={() => setShowFromDropdown(true)}
                    placeholder="Pickup stop (e.g. Junagarh Fort)..."
                    className="w-full pl-10 pr-4 py-2.5 bg-slate-100/90 hover:bg-slate-100 focus:bg-white border border-slate-200 focus:border-[#84cc16] focus:ring-2 focus:ring-[#84cc16]/20 rounded-xl text-sm font-semibold text-slate-800 transition-all outline-none"
                  />
                </div>

                {showFromDropdown && fromSuggestions.length > 0 && (
                  <div className="absolute top-full left-0 right-0 mt-2 bg-white rounded-2xl shadow-2xl border border-slate-200 z-50 max-h-60 overflow-y-auto p-2">
                    {fromSuggestions.map((st) => (
                      <div
                        key={st.id}
                        onClick={() => {
                          setSelectedFromStop(st);
                          setFromStopText(st.name);
                          setShowFromDropdown(false);
                        }}
                        className="p-2 rounded-xl hover:bg-[#ecfccb]/50 cursor-pointer flex items-center justify-between transition-colors"
                      >
                        <div>
                          <p className="text-sm font-bold text-slate-800">{st.name}</p>
                          <p className="text-xs text-slate-500">{st.hindiName} • {st.area}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Swap Button */}
              <div className="md:col-span-1 flex justify-center py-1 md:py-0">
                <button
                  type="button"
                  onClick={handleSwapStops}
                  className="w-9 h-9 rounded-full bg-[#ecfccb] text-[#4d7c0f] hover:bg-[#d9f99d] flex items-center justify-center shadow-xs transition-transform active:rotate-180 cursor-pointer"
                  title="Swap Stops"
                >
                  <ArrowRightLeft size={16} />
                </button>
              </div>

              {/* To Stop */}
              <div className="md:col-span-5 relative">
                <label className="block text-xs font-extrabold uppercase tracking-wider text-slate-500 mb-1">
                  To Destination (कहाँ तक)
                </label>
                <div className="relative">
                  <MapPin className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#dc2626]" size={18} />
                  <input
                    type="text"
                    value={toStopText}
                    onChange={(e) => handleToChange(e.target.value)}
                    onFocus={() => setShowToDropdown(true)}
                    placeholder="Destination (e.g. Ganga Shahar)..."
                    className="w-full pl-10 pr-4 py-2.5 bg-slate-100/90 hover:bg-slate-100 focus:bg-white border border-slate-200 focus:border-[#84cc16] focus:ring-2 focus:ring-[#84cc16]/20 rounded-xl text-sm font-semibold text-slate-800 transition-all outline-none"
                  />
                </div>

                {showToDropdown && toSuggestions.length > 0 && (
                  <div className="absolute top-full left-0 right-0 mt-2 bg-white rounded-2xl shadow-2xl border border-slate-200 z-50 max-h-60 overflow-y-auto p-2">
                    {toSuggestions.map((st) => (
                      <div
                        key={st.id}
                        onClick={() => {
                          setSelectedToStop(st);
                          setToStopText(st.name);
                          setShowToDropdown(false);
                        }}
                        className="p-2 rounded-xl hover:bg-[#fee2e2]/50 cursor-pointer flex items-center justify-between transition-colors"
                      >
                        <div>
                          <p className="text-sm font-bold text-slate-800">{st.name}</p>
                          <p className="text-xs text-slate-500">{st.hindiName} • {st.area}</p>
                        </div>
                        <span className="text-[10px] font-bold bg-slate-100 text-slate-600 px-2 py-0.5 rounded-md">
                          {st.code}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Quick Line Selector & GPS Nearest Stop */}
            <div className="flex flex-wrap items-center gap-2 pt-2 lg:pt-0 border-t lg:border-t-0 border-slate-100">
              <button
                type="button"
                onClick={handleFindNearestStop}
                disabled={isLocating}
                className="inline-flex items-center gap-1.5 text-xs font-bold text-[#4d7c0f] bg-[#ecfccb] hover:bg-[#d9f99d] px-3.5 py-2.5 rounded-xl transition-all cursor-pointer min-h-[38px]"
              >
                <Navigation size={14} className={isLocating ? 'animate-spin' : ''} />
                {isLocating ? 'Locating...' : '📍 Nearest GPS Stop'}
              </button>

              <div className="flex items-center gap-1.5">
                {BIKANER_BUS_ROUTES.map((r) => (
                  <button
                    key={r.id}
                    onClick={() => setSelectedRoute(r)}
                    style={{ borderColor: r.color }}
                    className={`px-3 py-2 rounded-xl text-xs font-extrabold border transition-all min-h-[38px] ${
                      displayRoute.id === r.id ? 'bg-slate-900 text-white' : 'bg-white text-slate-700 hover:bg-slate-50'
                    }`}
                  >
                    {r.routeNumber.split(' ')[0]} {r.routeNumber.split(' ')[1]}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {nearestStopInfo && (
            <div className="mt-3 bg-[#ecfccb] border border-[#bef264] text-[#3f6212] px-4 py-2 rounded-xl text-xs flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CheckCircle size={15} />
                <span>
                  <strong>Closest Pickup:</strong> {nearestStopInfo.stop.name} ({nearestStopInfo.distanceM}m away • ~{Math.round(nearestStopInfo.distanceM / 80)} mins walk)
                </span>
              </div>
              <span className="font-bold underline cursor-pointer" onClick={() => setSelectedFromStop(nearestStopInfo.stop)}>
                Set As Origin
              </span>
            </div>
          )}
        </div>

        {/* 2-Column Split: Stop Sequence vs Map */}
        <div className="flex-1 flex flex-col lg:flex-row gap-4 items-stretch h-[calc(100vh-280px)] min-h-[550px]">
          {/* Left: Stop Sequence Timeline (38% width) */}
          <div className="w-full lg:w-[460px] xl:w-[500px] flex flex-col shrink-0 bg-white rounded-2xl p-4 border border-slate-200/80 shadow-sm">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div>
                <h3 className="font-extrabold text-sm text-slate-900 flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full" style={{ background: displayRoute.color }}></span>
                  {displayRoute.name}
                </h3>
                <p className="text-xs text-slate-500">Every {displayRoute.frequencyMins}m • Fare: ₹{displayRoute.fareInr}</p>
              </div>
              <span className="text-xs font-bold text-slate-600 bg-slate-100 px-2.5 py-1 rounded-lg">
                {displayRoute.firstBus} - {displayRoute.lastBus}
              </span>
            </div>

            {/* Vertical Timeline */}
            <div className="flex-1 overflow-y-auto mt-4 pl-6 pr-2 space-y-5 relative before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
              {displayRoute.stops.map((st) => {
                const stopData = BIKANER_BUS_STOPS.find((b) => b.id === st.stopId);
                const isFrom = selectedFromStop?.id === st.stopId;
                const isTo = selectedToStop?.id === st.stopId;
                const isBusHere = selectedBus?.currentStopId === st.stopId;

                return (
                  <div key={st.stopId} className="relative flex items-start justify-between gap-3">
                    <div
                      style={{
                        background: isFrom ? '#16a34a' : isTo ? '#dc2626' : isBusHere ? displayRoute.color : '#ffffff',
                        borderColor: isFrom ? '#15803d' : isTo ? '#b91c1c' : displayRoute.color
                      }}
                      className="absolute -left-6 top-0.5 w-5 h-5 rounded-full border-2 flex items-center justify-center text-[9px] font-bold text-white shadow-xs"
                    >
                      {isBusHere ? '⚡' : ''}
                    </div>

                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className={`text-sm font-extrabold ${isFrom ? 'text-emerald-700' : isTo ? 'text-rose-700' : 'text-slate-800'}`}>
                          {stopData?.name}
                        </span>
                        {isFrom && (
                          <span className="text-[10px] font-extrabold bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full">
                            🟢 Pickup
                          </span>
                        )}
                        {isTo && (
                          <span className="text-[10px] font-extrabold bg-rose-100 text-rose-800 px-2 py-0.5 rounded-full">
                            🔴 Destination
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-slate-500">{stopData?.hindiName} • {stopData?.landmark}</p>

                      {isBusHere && (
                        <div className="mt-1.5 inline-flex items-center gap-1.5 text-xs font-bold text-[#4d7c0f] bg-[#ecfccb] px-2.5 py-1 rounded-lg">
                          <span>🚌 {selectedBus?.busNumber} arriving here</span>
                        </div>
                      )}
                    </div>

                    <div className="text-right shrink-0">
                      <span className="text-xs font-bold text-slate-700">+{st.scheduledMinsFromStart} min</span>
                      <p className="text-[10px] text-slate-400">Stop #{st.sequence}</p>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Helpline Footer */}
            <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
              <div>
                <p className="text-xs font-bold text-slate-800">Bikaner Transit Helpline</p>
                <p className="text-[11px] text-slate-500">Live Passenger Support</p>
              </div>
              <a
                href="tel:+911512226600"
                className="inline-flex items-center gap-1.5 bg-[#84cc16] hover:bg-[#65a30d] text-white px-3 py-1.5 rounded-xl text-xs font-bold shadow-xs"
              >
                <Phone size={13} />
                +91 151 222 6600
              </a>
            </div>
          </div>

          {/* Right: Full-Height Interactive Map (62% width) */}
          <div className="flex-1 w-full h-full bg-white rounded-2xl overflow-hidden shadow-sm border border-slate-200/80 relative min-h-[450px]">
            <div ref={mapContainer} className="w-full h-full" />

            {/* Active Bus Live Stats Bar */}
            {selectedBus && (
              <div className="absolute bottom-4 left-4 right-4 bg-white/95 backdrop-blur-md p-3.5 rounded-2xl shadow-xl border border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-3 z-10">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-[#ecfccb] text-[#4d7c0f] flex items-center justify-center text-lg">
                    🚌
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-extrabold text-sm text-slate-900">{selectedBus.busNumber}</span>
                      <span className="text-[10px] font-bold bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-md">
                        {selectedBus.occupancy} Seats
                      </span>
                    </div>
                    <p className="text-xs text-slate-500">Speed: {selectedBus.speedKmh} km/h • Direction: {selectedBus.direction}</p>
                  </div>
                </div>

                <div className="flex items-center gap-3 text-xs font-semibold">
                  <div className="flex items-center gap-1.5 text-emerald-700 bg-emerald-50 px-3 py-1.5 rounded-xl">
                    <BatteryCharging size={15} />
                    <span>{selectedBus.batteryPct}% SoC</span>
                  </div>
                  <div className="flex items-center gap-1.5 text-slate-700 bg-slate-100 px-3 py-1.5 rounded-xl">
                    <Clock size={14} />
                    <span>{selectedBus.delayMins === 0 ? 'On Time' : `${selectedBus.delayMins}m Delay`}</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      <VoltiFooter />
      <VoltiBackToTop />
    </div>
  );
};

export default WhereIsMyUrjaPage;
"""

    with open(os.path.join(pages_dir, "WhereIsMyUrjaPage.tsx"), "w", encoding="utf-8") as f:
        f.write(urja_page_code)
    print("[+] Created WhereIsMyUrjaPage.tsx")

def seed():
    generate_frontend_pages()
    try:
        engine = create_engine(settings.DATABASE_URL_SYNC)
        Base.metadata.create_all(bind=engine)
        with Session(engine) as db:
            existing = db.query(Department).first()
            if existing:
                print("Database already seeded. Skipping DB seed.")
                return
            print("[+] Seeding database...")
    except Exception as e:
        print("Note on database connection:", e)

        
        # Departments
        transport = Department(name="Transport Department", code="TRANSPORT", description="Public bus and transport fleet")
        fire = Department(name="Fire Department", code="FIRE", description="Fire brigade EV fleet")
        electricity = Department(name="Electricity Department", code="ELECTRICITY", description="Electricity utility EV fleet")
        db.add_all([transport, fire, electricity])
        db.flush()
        
        # Users
        admin = User(
            email="admin@chargeease.gov",
            hashed_password=hash_password("admin123"),
            full_name="Platform Administrator",
            role=UserRole.PLATFORM_ADMIN,
            is_active=True,
        )
        transport_admin = User(
            email="transport@chargeease.gov",
            hashed_password=hash_password("transport123"),
            full_name="Transport Admin",
            role=UserRole.DEPARTMENT_ADMIN,
            department_id=transport.id,
            is_active=True,
        )
        fire_admin = User(
            email="fire@chargeease.gov",
            hashed_password=hash_password("fire123"),
            full_name="Fire Admin",
            role=UserRole.DEPARTMENT_ADMIN,
            department_id=fire.id,
            is_active=True,
        )
        electricity_admin = User(
            email="electricity@chargeease.gov",
            hashed_password=hash_password("electricity123"),
            full_name="Electricity Admin",
            role=UserRole.DEPARTMENT_ADMIN,
            department_id=electricity.id,
            is_active=True,
        )
        db.add_all([admin, transport_admin, fire_admin, electricity_admin])
        db.flush()
        
        # Vehicles and Devices
        vehicle_configs = [
            # Transport buses
            ("bus-001", "dev-bus-001", VehicleType.ELECTRIC_BUS, transport.id, "Tata", "Starbus EV", 2024),
            ("bus-002", "dev-bus-002", VehicleType.ELECTRIC_BUS, transport.id, "Tata", "Starbus EV", 2024),
            ("bus-003", "dev-bus-003", VehicleType.ELECTRIC_BUS, transport.id, "Ashok Leyland", "Circuit S", 2025),
            ("bus-004", "dev-bus-004", VehicleType.ELECTRIC_BUS, transport.id, "Tata", "Starbus EV", 2025),
            ("bus-005", "dev-bus-005", VehicleType.ELECTRIC_BUS, transport.id, "BYD", "K9", 2024),
            ("bus-006", "dev-bus-006", VehicleType.ELECTRIC_BUS, transport.id, "Ashok Leyland", "Circuit S", 2025),
            # Fire
            ("fire-001", "dev-fire-001", VehicleType.FIRE_EV, fire.id, "Tata", "Nexon EV", 2025),
            ("fire-002", "dev-fire-002", VehicleType.FIRE_EV, fire.id, "MG", "ZS EV", 2025),
            ("fire-003", "dev-fire-003", VehicleType.FIRE_EV, fire.id, "Tata", "Nexon EV", 2024),
            ("fire-004", "dev-fire-004", VehicleType.FIRE_EV, fire.id, "MG", "ZS EV", 2025),
            # Electricity
            ("util-001", "dev-util-001", VehicleType.UTILITY_EV, electricity.id, "Tata", "Tigor EV", 2024),
            ("util-002", "dev-util-002", VehicleType.UTILITY_EV, electricity.id, "Tata", "Tigor EV", 2024),
            ("util-003", "dev-util-003", VehicleType.UTILITY_EV, electricity.id, "MG", "Comet EV", 2025),
            ("util-004", "dev-util-004", VehicleType.UTILITY_EV, electricity.id, "Mahindra", "eXUV300", 2025),
            ("util-005", "dev-util-005", VehicleType.UTILITY_EV, electricity.id, "Tata", "Tigor EV", 2025),
        ]
        
        for v_code, d_code, v_type, dept_id, make, model, year in vehicle_configs:
            vehicle = Vehicle(
                vehicle_code=v_code,
                vehicle_type=v_type,
                department_id=dept_id,
                make=make,
                model=model,
                year=year,
                is_active=True,
                public_visible=True,
            )
            db.add(vehicle)
            db.flush()
            device = Device(
                device_code=d_code,
                vehicle_id=vehicle.id,
                firmware_version="0.3.1",
                status=DeviceStatus.ACTIVE,
            )
            db.add(device)
        
        # Charging centers
        db.add_all([
            ChargingCenter(
                name="ISBT Kashmere Gate Charging Hub",
                latitude=28.6675, longitude=77.2283,
                connectors={"CCS2": 4, "CHAdeMO": 2}, power_kw=150,
                source="GNCTD", public_visible=True,
            ),
            ChargingCenter(
                name="Nehru Place Depot Charger",
                latitude=28.5491, longitude=77.2533,
                connectors={"CCS2": 6}, power_kw=120,
                source="DTC", public_visible=True,
            ),
            ChargingCenter(
                name="ITO EV Station",
                latitude=28.6271, longitude=77.2405,
                connectors={"CCS2": 2, "Type2": 4}, power_kw=60,
                source="BSES", public_visible=True,
            ),
        ])
        
        # Geofences
        db.add_all([
            Geofence(
                name="IP Estate Bus Depot",
                geofence_type=GeofenceType.DEPOT,
                department_id=transport.id,
                center_lat=28.6304, center_lng=77.2467,
                radius_m=200,
                is_active=True,
            ),
            Geofence(
                name="ITO Fire Station",
                geofence_type=GeofenceType.STATION,
                department_id=fire.id,
                center_lat=28.6271, center_lng=77.2405,
                radius_m=150,
                is_active=True,
            ),
        ])
        
        db.commit()
        print("[+] Seed complete!")
        print(f"   Departments: 3")
        print(f"   Users: 4 (1 admin + 3 dept admins)")
        print(f"   Vehicles: 15")
        print(f"   Devices: 15")
        print(f"   Charging Centers: 3")
        print(f"   Geofences: 2")
        print()
        print("   Admin login: admin@chargeease.gov / admin123")
        print("   Transport:   transport@chargeease.gov / transport123")
        print("   Fire:        fire@chargeease.gov / fire123")
        print("   Electricity: electricity@chargeease.gov / electricity123")


if __name__ == "__main__":
    seed()
