/* chillcheck web UI. No build step, no dependencies. */

const CROPS = ["apple", "pear", "peach", "nectarine", "cherry", "plum", "apricot", "almond"];

const el = (id) => document.getElementById(id);

function setStatus(text, isError = false) {
  const node = el("status");
  node.textContent = text || "";
  node.classList.toggle("error", Boolean(isError));
}

function fmt(value, digits = 1) {
  if (value === null || value === undefined) return "-";
  const number = Number(value);
  if (!Number.isFinite(number)) return "-";
  return number.toFixed(digits);
}

function signed(value, digits = 1) {
  if (value === null || value === undefined) return "-";
  const number = Number(value);
  if (!Number.isFinite(number)) return "-";
  return (number > 0 ? "+" : "") + number.toFixed(digits);
}

function fillCrops() {
  const select = el("crops");
  for (const crop of CROPS) {
    const option = document.createElement("option");
    option.value = crop;
    option.textContent = crop.charAt(0).toUpperCase() + crop.slice(1);
    select.appendChild(option);
  }
}

async function geocode(query) {
  const response = await fetch(`/api/geocode?q=${encodeURIComponent(query)}&count=1`);
  if (!response.ok) throw new Error("Place lookup failed. Check the network.");
  const data = await response.json();
  const hits = data.results || [];
  if (!hits.length) throw new Error(`No place found for "${query}".`);
  const hit = hits[0];
  const label = [hit.name, hit.admin1, hit.country].filter(Boolean).join(", ");
  return { lat: hit.latitude, lon: hit.longitude, name: label };
}

async function loadAssessment(lat, lon, name, years, crops) {
  const params = new URLSearchParams({ lat: String(lat), lon: String(lon), years: String(years), name: name || "" });
  if (crops) params.set("crops", crops);
  const response = await fetch(`/api/assess?${params.toString()}`);
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error((data && data.detail) || "Assessment failed.");
  return data;
}

function pill(status) {
  const label = status.replace("_", " ");
  return `<span class="pill ${status}">${label}</span>`;
}

function drawChart(report) {
  const host = el("chart");
  const items = report.seasons.map((row) => ({
    label: String(row.season),
    value: row.chill_portions,
    kind: "obs",
  }));

  const projection = report.projection;
  if (projection && projection.chill_portions !== null) {
    items.push({ label: "2050", value: projection.chill_portions, kind: "proj" });
  }
  if (!items.length) {
    host.innerHTML = "<p class=\"meta\">No seasons to plot.</p>";
    return;
  }

  const W = 720;
  const H = 270;
  const padL = 46;
  const padR = 16;
  const padT = 16;
  const padB = 44;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;

  const peak = Math.max(...items.map((item) => item.value), 1);
  const top = Math.max(5, Math.ceil(peak / 5) * 5);
  const slot = plotW / items.length;
  const barW = Math.max(2, slot * 0.66);

  let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Chill portions by season">`;
  svg += `<rect x="0" y="0" width="${W}" height="${H}" fill="none"/>`;

  for (let tick = 0; tick <= 4; tick += 1) {
    const value = (top * tick) / 4;
    const y = padT + plotH - (value / top) * plotH;
    svg += `<line x1="${padL}" y1="${y.toFixed(1)}" x2="${W - padR}" y2="${y.toFixed(1)}" stroke="#e6e3d6" stroke-width="1"/>`;
    svg += `<text x="${padL - 8}" y="${(y + 4).toFixed(1)}" text-anchor="end" font-size="11" fill="#55655b">${value.toFixed(0)}</text>`;
  }

  const baseline = report.baseline && report.baseline.chill_portions;
  if (baseline) {
    const y = padT + plotH - (baseline / top) * plotH;
    svg += `<line x1="${padL}" y1="${y.toFixed(1)}" x2="${W - padR}" y2="${y.toFixed(1)}" stroke="#2f6b45" stroke-width="1.2" stroke-dasharray="5 4"/>`;
    svg += `<text x="${W - padR}" y="${(y - 6).toFixed(1)}" text-anchor="end" font-size="10.5" fill="#2f6b45">baseline ${fmt(baseline)}</text>`;
  }

  items.forEach((item, index) => {
    const height = Math.max(1, (item.value / top) * plotH);
    const x = padL + index * slot + (slot - barW) / 2;
    const y = padT + plotH - height;
    const fill = item.kind === "proj" ? "#a8620f" : "#2f6b45";
    svg += `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barW.toFixed(1)}" height="${height.toFixed(1)}" fill="${fill}" rx="1.5"><title>${item.label}: ${fmt(item.value)} portions</title></rect>`;

    const step = items.length > 22 ? Math.ceil(items.length / 12) : 1;
    const isProjection = item.kind === "proj";
    if (isProjection || index % step === 0) {
      const cx = x + barW / 2;
      svg += `<text x="${cx.toFixed(1)}" y="${H - padB + 16}" text-anchor="middle" font-size="10.5" fill="${isProjection ? "#a8620f" : "#55655b"}">${item.label}</text>`;
    }
  });

  svg += `<line x1="${padL}" y1="${padT + plotH}" x2="${W - padR}" y2="${padT + plotH}" stroke="#c9c6b6" stroke-width="1.2"/>`;
  svg += `<text x="${padL - 8}" y="${padT - 4}" text-anchor="end" font-size="10" fill="#55655b">portions</text>`;
  svg += "</svg>";
  host.innerHTML = svg;
}

function renderCards(report) {
  const base = report.baseline;
  const recent = report.recent;
  const future = report.projection;
  const trend = report.trend;

  el("card-base").textContent = fmt(base.chill_portions);
  el("card-base-foot").textContent = `${base.from} to ${base.to} · ${base.count} seasons · range ${fmt(base.min_portions)} to ${fmt(base.max_portions)}`;

  el("card-recent").textContent = fmt(recent.chill_portions);
  el("card-recent-foot").textContent = `${recent.from} to ${recent.to} · ${recent.count} seasons`;

  if (future && future.chill_portions !== null) {
    el("card-future").textContent = fmt(future.chill_portions);
    const change = base.chill_portions ? ((future.chill_portions - base.chill_portions) / base.chill_portions) * 100 : null;
    el("card-future-foot").textContent = `${future.window[0]} to ${future.window[1]} · ${change === null ? "" : signed(change, 0) + "% against baseline"}`;
  } else {
    el("card-future").textContent = "-";
    el("card-future-foot").textContent = "Projection unavailable";
  }

  const perDecade = trend.portions_per_decade;
  el("card-trend").textContent = signed(perDecade, 2);
  el("card-trend-foot").textContent = `${base.count} seasons, least squares fit`;
}

function renderTable(report) {
  const body = el("varieties").querySelector("tbody");
  body.innerHTML = "";
  const nowHours = report.baseline.chill_hours;

  for (const row of report.varieties) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${row.name}</td>
      <td>${row.crop}</td>
      <td class="num">${row.chill_low.toFixed(0)}-${row.chill_high.toFixed(0)}</td>
      <td class="num">${fmt(nowHours, 0)}</td>
      <td>${pill(row.status_now)}</td>
      <td>${pill(row.status_2050)}</td>`;
    tr.title = row.note || "";
    body.appendChild(tr);
  }

  const summary = report.variety_summary || {};
  const now = summary.now || {};
  const future = summary.y2050 || {};
  el("table-meta").textContent =
    `Now: ${now.safe || 0} safe, ${now.marginal || 0} marginal, ${now.at_risk || 0} at risk. ` +
    `2050: ${future.safe || 0} safe, ${future.marginal || 0} marginal, ${future.at_risk || 0} at risk.`;
}

function render(report) {
  el("results").hidden = false;
  const location = report.location;
  el("place-name").textContent = location.name;
  el("place-meta").textContent =
    `${location.latitude}, ${location.longitude} · ${location.elevation_m} m · ` +
    `${location.season_window} (${location.hemisphere} hemisphere)`;

  renderCards(report);
  el("chart-meta").textContent = `${report.seasons.length} seasons${report.projection ? " plus the 2050 mean" : ""}`;
  drawChart(report);
  renderTable(report);

  const notes = el("notes");
  notes.innerHTML = "";
  for (const note of report.notes || []) {
    const item = document.createElement("li");
    item.textContent = note;
    notes.appendChild(item);
  }
}

async function run(event) {
  if (event) event.preventDefault();
  const button = el("run");
  const place = el("place").value.trim();
  const years = el("years").value;
  const crops = el("crops").value;

  button.disabled = true;
  try {
    let lat = null;
    let lon = null;
    let name = null;

    if (place) {
      setStatus("Looking up the place...");
      const hit = await geocode(place);
      lat = hit.lat;
      lon = hit.lon;
      name = hit.name;
    } else if (stateFromUrl.lat !== null) {
      lat = stateFromUrl.lat;
      lon = stateFromUrl.lon;
      name = stateFromUrl.name;
    } else {
      throw new Error("Enter a place name or postcode.");
    }

    setStatus("Counting chill from daily weather records. This can take a few seconds...");
    const report = await loadAssessment(lat, lon, name, years, crops);
    render(report);
    setStatus("");

    const params = new URLSearchParams({ lat: String(lat), lon: String(lon), years: String(years) });
    if (name) params.set("place", name);
    if (crops) params.set("crops", crops);
    history.replaceState(null, "", `?${params.toString()}`);
  } catch (error) {
    setStatus(error.message || "Something failed.", true);
  } finally {
    button.disabled = false;
  }
}

const stateFromUrl = { lat: null, lon: null, name: null };

function readUrl() {
  const params = new URLSearchParams(window.location.search);
  const lat = params.get("lat");
  const lon = params.get("lon");
  if (lat !== null && lon !== null) {
    stateFromUrl.lat = Number(lat);
    stateFromUrl.lon = Number(lon);
    stateFromUrl.name = params.get("place");
  }
  if (params.get("years")) el("years").value = params.get("years");
  if (params.get("crops")) el("crops").value = params.get("crops");
  if (params.get("place")) el("place").value = params.get("place");
}

function boot() {
  fillCrops();
  readUrl();
  el("query").addEventListener("submit", run);
  if (stateFromUrl.lat !== null) run();
}

document.addEventListener("DOMContentLoaded", boot);