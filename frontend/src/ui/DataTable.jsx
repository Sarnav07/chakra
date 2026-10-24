export default function DataTable({ columns, rows, emptyText }) {
  if (!rows || rows.length === 0) {
    return <div className="ck-datatable__empty">{emptyText || "No data"}</div>;
  }
  return (
    <div className="ck-datatable-wrap">
      <table className="ck-datatable">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key} scope="col">{col.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={row.id || row.bin_id || i}>
              {columns.map((col) => (
                <td key={col.key}>
                  {col.render ? col.render(row[col.key], row) : row[col.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
