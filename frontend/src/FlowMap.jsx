import { useMemo, useState } from "react";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "./FlowMap.css";

// Default example location only; set the actual CCTV camera coordinates before operational use.
const DEFAULT_CAMERA = { lat: 12.9716, lng: 77.5946 };

function makeIcon(kind) {
  const colors = kind === "collision" ? "#e24e59" : kind === "stopped_vehicle" ? "#e6a23c" : "#4986e7";
  const label = kind === "collision" ? "!" : kind === "stopped_vehicle" ? "Ⅱ" : "•";
  return L.divIcon({
    className: "flow-leaflet-icon-wrap",
    html: `<span class="flow-leaflet-pin" style="background:${colors}">${label}</span>`,
    iconSize: [32, 32],
    iconAnchor: [16, 16],
    popupAnchor: [0, -15],
  });
}

function CameraMarker({ position }) {
  const map = useMap();
  // Keep the map centered on the selected camera when the user applies a new location.
  map.setView([position.lat, position.lng], map.getZoom(), { animate: false });
  return <Marker position={[position.lat, position.lng]} icon={L.divIcon({ className: "flow-leaflet-icon-wrap", html: '<span class="flow-camera-pin">CAM</span>', iconSize: [42, 30], iconAnchor: [21, 15] })}>
    <Popup>Configured CCTV camera location (verify these coordinates).</Popup>
  </Marker>;
}

export default function FlowMap({ incidents = [] }) {
  const [lat, setLat] = useState(String(DEFAULT_CAMERA.lat));
  const [lng, setLng] = useState(String(DEFAULT_CAMERA.lng));
  const [appliedCamera, setAppliedCamera] = useState(DEFAULT_CAMERA);
  const camera = { lat: Number(lat), lng: Number(lng) };
  const valid = Number.isFinite(camera.lat) && Number.isFinite(camera.lng) && Math.abs(camera.lat) <= 90 && Math.abs(camera.lng) <= 180;
  const mappable = useMemo(() => incidents.map((incident) => {
    const hasCoordinates = incident.latitude !== undefined && incident.longitude !== undefined && Number.isFinite(Number(incident.latitude)) && Number.isFinite(Number(incident.longitude)) && incident.latitude !== null && incident.longitude !== null;
    return { ...incident, position: hasCoordinates ? { lat: Number(incident.latitude), lng: Number(incident.longitude) } : appliedCamera, isDemoLocation: !hasCoordinates };
  }), [incidents, appliedCamera]);

  return <div className="flow-map-layout">
    <div className="flow-map-controls">
      <label>Camera latitude<input value={lat} onChange={(e) => setLat(e.target.value)} inputMode="decimal" /></label>
      <label>Camera longitude<input value={lng} onChange={(e) => setLng(e.target.value)} inputMode="decimal" /></label>
      <button disabled={!valid} onClick={() => setAppliedCamera(camera)}>Set camera location</button>
      <div className="map-key"><span className="key-dot danger" /> Suspected collision <span className="key-dot warning" /> Stopped vehicle</div>
      <p>OpenStreetMap tiles are used. Incidents without GPS coordinates appear at the configured camera location as placeholders, not verified incident locations.</p>
      <strong>{incidents.length} incident(s) from FlowGuard</strong>
      <small className="map-attribution-note">Map data © OpenStreetMap contributors.</small>
    </div>
    <div className="flow-map-canvas">
      <MapContainer center={[appliedCamera.lat, appliedCamera.lng]} zoom={12} scrollWheelZoom className="flow-leaflet-map">
        <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap contributors</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        <CameraMarker position={appliedCamera} />
        {mappable.map((incident) => <Marker key={incident.id} position={[incident.position.lat, incident.position.lng]} icon={makeIcon(incident.type)}>
          <Popup>
            <div className="map-info">
              <strong>{String(incident.type || "Traffic incident").replaceAll("_", " ")}</strong>
              <div>Status: {incident.status || "Unknown"}</div>
              <div>Severity: {incident.severity || "Not specified"}</div>
              {incident.isDemoLocation && <small>Placeholder location: this incident has no GPS coordinates. Set the actual camera location before using operational alerts.</small>}
            </div>
          </Popup>
        </Marker>)}
      </MapContainer>
    </div>
  </div>;
}
