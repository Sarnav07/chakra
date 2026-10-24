export default function MapLegend({ items }) {
  return (
    <div className="ck-map-legend">
      {items.map((item) => (
        <div key={item.label} className="ck-map-legend__item">
          <span
            className="ck-map-legend__swatch"
            style={{
              backgroundColor: item.color,
              borderStyle: item.dashed ? "dashed" : "solid",
            }}
          />
          <span>{item.label}</span>
        </div>
      ))}
    </div>
  );
}
