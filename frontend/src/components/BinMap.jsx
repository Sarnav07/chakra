import { useEffect, useRef, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Tooltip, useMap } from "react-leaflet";
import { cssVar, riskColor } from "../ui";

function resolveColor(varStr) {
  if (!varStr || !varStr.startsWith("var(")) return varStr || "#999";
  const name = varStr.slice(4, -1);
  return cssVar(name) || "#999";
}

function useSmallScreen() {
  const [small, setSmall] = useState(
    typeof window !== "undefined" && window.matchMedia("(max-width: 640px)").matches
  );
  useEffect(() => {
    const mql = window.matchMedia("(max-width: 640px)");
    const handler = (e) => setSmall(e.matches);
    mql.addEventListener("change", handler);
    return () => mql.removeEventListener("change", handler);
  }, []);
  return small;
}

function FitBounds({ items, nodes }) {
  const map = useMap();
  const fitted = useRef(false);
  useEffect(() => {
    if (fitted.current) return;
    const allPoints = [
      ...(items || []).map((d) => [d.lat, d.lon]),
      ...(nodes || []).map((n) => [n.lat, n.lon]),
    ];
    if (allPoints.length === 0) return;
    fitted.current = true;
    map.fitBounds(allPoints, { padding: [24, 24] });
  }, [items, nodes, map]);
  return null;
}

const NODE_COLORS = {
  depot: "--color-primary",
  compost: "--color-success",
};

export default function BinMap({ items, nodes, selectedId, onSelect }) {
  const small = useSmallScreen();
  const height = small ? "60vh" : "520px";

  const defaultCenter = [29.865, 77.896];
  const defaultZoom = 15;

  return (
    <MapContainer
      center={defaultCenter}
      zoom={defaultZoom}
      style={{ height, width: "100%", borderRadius: "var(--radius)" }}
      scrollWheelZoom={true}
    >
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      />
      <FitBounds items={items} nodes={nodes} />

      {(items || []).map((d) => {
        const selected = d.bin_id === selectedId;
        const color = resolveColor(riskColor(d));
        return (
          <CircleMarker
            key={d.bin_id}
            center={[d.lat, d.lon]}
            radius={d.capacity_l >= 600 ? 10 : 7}
            pathOptions={{
              fillColor: color,
              fillOpacity: 0.85,
              color: "#111",
              weight: selected ? 3 : 1,
              dashArray: d.reason_code === "needs_review" ? "4 3" : undefined,
            }}
            eventHandlers={{ click: () => onSelect(d.bin_id) }}
          >
            <Tooltip>
              {d.name}
              {d.p_overflow != null
                ? ` — P(overflow) ${(d.p_overflow * 100).toFixed(0)}%`
                : " — no reading"}
            </Tooltip>
          </CircleMarker>
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
  );
}
