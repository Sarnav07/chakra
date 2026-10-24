import { useEffect, useRef } from "react";
import { MapContainer, TileLayer, Polyline, CircleMarker, Tooltip, useMap } from "react-leaflet";
import { CHART, cssVar } from "../ui";

function FitBounds({ alternative, nodes }) {
  const map = useMap();
  const lastFleet = useRef(null);
  useEffect(() => {
    if (!alternative) return;
    if (lastFleet.current === alternative.fleet_size) return;
    lastFleet.current = alternative.fleet_size;
    const pts = [];
    for (const r of alternative.routes || []) {
      for (const p of r.polyline || []) pts.push(p);
      for (const s of r.stops || []) pts.push([s.lat, s.lon]);
    }
    for (const n of nodes || []) pts.push([n.lat, n.lon]);
    if (pts.length === 0) return;
    // fit after layout: during the page fade-in the container can still have
    // its initial size, and Leaflet then zooms out to the whole city
    const fit = () => {
      map.invalidateSize();
      map.fitBounds(pts, { padding: [24, 24], maxZoom: 17 });
    };
    fit();
    const timer = setTimeout(fit, 350);
    return () => clearTimeout(timer);
  }, [alternative, nodes, map]);
  return null;
}

const NODE_COLORS = { depot: "--color-primary", compost: "--color-success" };

export default function RouteMap({ alternative, nodes }) {
  const defaultCenter = [29.865, 77.896];

  if (!alternative) return null;

  const legend = (alternative.routes || []).map((r, i) => ({
    vehicleId: r.vehicle_id,
    color: CHART.series[i % CHART.series.length],
    stream: r.stream,
  }));

  return (
    <div>
      <MapContainer
        center={defaultCenter}
        zoom={15}
        style={{ height: "480px", width: "100%", borderRadius: "var(--radius)" }}
        scrollWheelZoom={true}
        key={alternative.fleet_size}
      >
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        />
        <FitBounds alternative={alternative} nodes={nodes} />

        {(alternative.routes || []).map((route, i) => {
          const color = CHART.series[i % CHART.series.length];
          return (
            <span key={route.vehicle_id}>
              {route.polyline && route.polyline.length > 1 && (
                <Polyline
                  positions={route.polyline}
                  pathOptions={{ color, weight: 3, opacity: 0.8 }}
                />
              )}
              {(route.stops || []).map((stop) => (
                <CircleMarker
                  key={stop.bin_id}
                  center={[stop.lat, stop.lon]}
                  radius={6}
                  pathOptions={{ fillColor: color, fillOpacity: 0.9, color: "#111", weight: 1 }}
                >
                  <Tooltip permanent>
                    <span style={{ fontSize: 11 }}>{stop.seq}</span>
                  </Tooltip>
                </CircleMarker>
              ))}
            </span>
          );
        })}

        {(nodes || []).map((n) => (
          <CircleMarker
            key={n.node_id}
            center={[n.lat, n.lon]}
            radius={9}
            pathOptions={{
              fillColor: cssVar(NODE_COLORS[n.kind] || "--color-muted"),
              fillOpacity: 0.9,
              color: "#111",
              weight: 2,
            }}
          >
            <Tooltip permanent>{n.name}</Tooltip>
          </CircleMarker>
        ))}
      </MapContainer>

      <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-3)", padding: "var(--space-2) 0", fontSize: "0.8125rem" }}>
        {legend.map((l) => (
          <span key={l.vehicleId} style={{ display: "inline-flex", alignItems: "center", gap: "var(--space-1)" }}>
            <span style={{ width: 14, height: 4, background: l.color, borderRadius: 2, display: "inline-block" }} />
            {l.vehicleId} ({l.stream})
          </span>
        ))}
        <span style={{ color: "var(--color-muted)" }}>Food route ends at the compost stop</span>
      </div>
    </div>
  );
}
