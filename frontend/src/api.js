async function request(path, options = {}) {
  const res = await fetch("/api" + path, options);
  const contentType = res.headers.get("content-type") || "";
  let data;
  if (contentType.includes("application/json")) {
    data = await res.json();
  } else {
    data = await res.text();
  }
  if (!res.ok) {
    const detail =
      data && typeof data === "object" && data.detail !== undefined
        ? typeof data.detail === "string"
          ? data.detail
          : JSON.stringify(data.detail)
        : `HTTP ${res.status}`;
    throw new Error(detail);
  }
  return data;
}

function jsonBody(body) {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

export function getScenario() {
  return request("/scenario");
}

export function resetDemo() {
  return request("/demo/reset", { method: "POST" });
}

export function getBins() {
  return request("/bins");
}

export function getBinHistory(binId, days = 14) {
  const params = new URLSearchParams({ days: String(days) });
  return request(`/bins/${encodeURIComponent(binId)}/history?${params}`);
}

export function postObservation(body) {
  return request("/observations", jsonBody(body));
}

export function runForecasts() {
  return request("/forecasts", jsonBody({}));
}

export function getLatestForecasts() {
  return request("/forecasts/latest");
}

export function getForecastEval() {
  return request("/forecasts/eval");
}

export function postDecisions(tau) {
  return request("/decisions", jsonBody({ tau }));
}

export function postRoutes({ tau, fleet_sizes = [1, 2, 3], fast = false }) {
  return request("/routes", jsonBody({ tau, fleet_sizes, fast }));
}

export function getPlan(planId) {
  return request(`/routes/${encodeURIComponent(planId)}`);
}

export function choosePlan(planId, fleetSize) {
  return request(
    `/routes/${encodeURIComponent(planId)}/choose`,
    jsonBody({ fleet_size: fleetSize })
  );
}

export function getWorkerRoutes() {
  return request("/worker/routes");
}

export function confirmPickup(body) {
  return request("/pickups", jsonBody(body));
}

export function arriveCompost(routeId) {
  return request("/pickups/arrive-compost", jsonBody({ route_id: routeId }));
}

export function getBatches(status = "all") {
  const params = new URLSearchParams({ status });
  return request(`/batches?${params}`);
}

export function postReport(formData) {
  return request("/reports", { method: "POST", body: formData });
}

export function getReports(status = "open") {
  const params = new URLSearchParams({ status });
  return request(`/reports?${params}`);
}

export function rejectReport(reportId) {
  return request(`/reports/${encodeURIComponent(reportId)}/reject`, {
    method: "POST",
  });
}

export function getClassifierStatus() {
  return request("/classify/status");
}

export function classifyItem(formData) {
  return request("/classify", { method: "POST", body: formData });
}

export function postMessLog(body) {
  return request("/mess-logs", jsonBody(body));
}

export function getMessLogs(days = 14, messId = "") {
  const params = new URLSearchParams({ days: String(days) });
  if (messId) params.set("mess_id", messId);
  return request(`/mess-logs?${params}`);
}

export function getDashboard() {
  return request("/dashboard");
}

export function getTwin() {
  return request("/twin");
}

export function runTwin() {
  return request("/twin/run", { method: "POST" });
}

export function getScaleLab() {
  return request("/scale-lab");
}

export function runScaleLab() {
  return request("/scale-lab/run", { method: "POST" });
}
