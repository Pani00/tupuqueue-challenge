// SOLOBOOM LAS — lee data.json (generado por fetch_data.py vía GitHub Actions)
// y dibuja la escalera + las tarjetas. No necesita build ni dependencias.

const TIERS = [
  { key: "IRON", label: "Hierro", varName: "--tier-iron", start: 0, end: 10 },
  { key: "BRONZE", label: "Bronce", varName: "--tier-bronze", start: 10, end: 20 },
  { key: "SILVER", label: "Plata", varName: "--tier-silver", start: 20, end: 30 },
  { key: "GOLD", label: "Oro", varName: "--tier-gold", start: 30, end: 40 },
  { key: "PLATINUM", label: "Platino", varName: "--tier-platinum", start: 40, end: 50 },
  { key: "EMERALD", label: "Esmeralda", varName: "--tier-emerald", start: 50, end: 60 },
  { key: "DIAMOND", label: "Diamante", varName: "--tier-diamond", start: 60, end: 75 },
  { key: "MASTER", label: "Maestro", varName: "--tier-master", start: 75, end: 85 },
  { key: "GRANDMASTER", label: "Gran Maestro", varName: "--tier-grandmaster", start: 85, end: 93 },
  { key: "CHALLENGER", label: "Aspirante", varName: "--tier-challenger", start: 93, end: 100 },
];
const APEX = new Set(["MASTER", "GRANDMASTER", "CHALLENGER"]);
const RANK_ORDER = { IV: 0, III: 1, II: 2, I: 3 };
const UPDATE_MINUTES = 30;

let countdownTimer = null;

function esc(str) {
  return String(str).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function tierInfo(tierKey) {
  return TIERS.find((t) => t.key === tierKey) || null;
}

function score(tier, rank, lp) {
  const idx = TIERS.findIndex((t) => t.key === tier);
  if (idx === -1) return -1;
  if (APEX.has(tier)) return idx * 10000 + (lp || 0);
  const rIdx = RANK_ORDER[rank] ?? 0;
  return idx * 10000 + rIdx * 100 + (lp || 0);
}

function ladderPercent(tier, rank, lp) {
  const t = tierInfo(tier);
  if (!t) return 0;
  const span = t.end - t.start;
  if (APEX.has(tier)) {
    const frac = Math.min((lp || 0) / 1000, 1);
    return t.start + span * frac;
  }
  const rIdx = RANK_ORDER[rank] ?? 0;
  const withinRank = Math.min((lp || 0) / 100, 1);
  return t.start + span * ((rIdx + withinRank) / 4);
}

function progressLabel(current, baseline) {
  if (!current || !current.tier || !baseline || !baseline.tier) return null;
  if (current.tier === baseline.tier && current.rank === baseline.rank) {
    const diff = (current.leaguePoints || 0) - (baseline.leaguePoints || 0);
    if (diff === 0) return { cls: "flat", text: "sin cambios" };
    return { cls: diff > 0 ? "up" : "down", text: `${diff > 0 ? "+" : ""}${diff} LP` };
  }
  const curScore = score(current.tier, current.rank, current.leaguePoints);
  const baseScore = score(baseline.tier, baseline.rank, baseline.leaguePoints);
  if (curScore > baseScore) return { cls: "up", text: "subió de rango ▲" };
  if (curScore < baseScore) return { cls: "down", text: "bajó de rango ▼" };
  return { cls: "flat", text: "sin cambios" };
}

function profileIconUrl(player, ddragonVersion) {
  if (!player.profileIconId || !ddragonVersion) return null;
  return `https://ddragon.leagueoflegends.com/cdn/${ddragonVersion}/img/profileicon/${player.profileIconId}.png`;
}

function tierEmblemUrl(tier) {
  if (!tier) return null;
  return `https://raw.communitydragon.org/latest/plugins/rcp-fe-lol-static-assets/global/default/images/ranked-emblem/emblem-${tier.toLowerCase()}.png`;
}

function formatLastUpdated(iso) {
  if (!iso) return "esperando primera actualización";
  const d = new Date(iso);
  return d.toLocaleString("es-AR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false });
}

async function loadData() {
  try {
    const res = await fetch(`data.json?t=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) throw new Error("data.json no disponible todavía");
    const data = await res.json();
    render(data);
  } catch (err) {
    showEmptyState();
  }
}

function showEmptyState() {
  const board = document.getElementById("board");
  board.innerHTML = `<p class="board-empty">Todavía no hay datos. En cuanto corra la primera actualización automática (o la dispares a mano desde GitHub Actions) va a aparecer el ranking acá.</p>`;
  document.getElementById("last-updated").textContent = "—";
  document.getElementById("countdown").textContent = "--:--";
}

function render(data) {
  const players = data.players || [];
  const sorted = [...players].sort(
    (a, b) => score(b.tier, b.rank, b.leaguePoints) - score(a.tier, a.rank, a.leaguePoints)
  );

  renderLadder(sorted, data.ddragonVersion);
  renderBoard(sorted, data.ddragonVersion);

  const anyStale = players.some((p) => p.stale);
  const pill = document.getElementById("live-pill");
  pill.classList.toggle("is-stale", anyStale || !data.generatedAt);
  pill.innerHTML = anyStale
    ? `<span class="dot"></span> DATO PARCIAL`
    : `<span class="dot"></span> EN VIVO`;

  document.getElementById("last-updated").textContent = formatLastUpdated(data.generatedAt);
  scheduleCountdown(data.generatedAt);
}

function renderLadder(players, ddragonVersion) {
  const track = document.getElementById("ladder-track");
  const ticks = TIERS.map((t) => {
    const mid = t.start + (t.end - t.start) / 2;
    return `<span class="ladder-tick" style="left:${mid}%">${esc(t.label)}</span>`;
  }).join("");

  const markers = players
    .filter((p) => p.tier)
    .map((p) => {
      const pct = ladderPercent(p.tier, p.rank, p.leaguePoints);
      const icon = profileIconUrl(p, ddragonVersion);
      const style = `left:${pct}%;${icon ? `background-image:url('${icon}')` : ""}`;
      return `<div class="ladder-marker" style="${style}" title="${esc(p.gameName)}#${esc(p.tagLine)} · ${esc(tierInfo(p.tier)?.label || p.tier)} ${esc(p.rank || "")} ${p.leaguePoints ?? 0} LP"></div>`;
    })
    .join("");

  track.innerHTML = ticks + markers;
}

function renderBoard(players, ddragonVersion) {
  const board = document.getElementById("board");
  if (!players.length) {
    board.innerHTML = `<p class="board-empty">No hay jugadores configurados en players.json.</p>`;
    return;
  }

  board.innerHTML = players
    .map((p, i) => {
      const t = tierInfo(p.tier);
      const tierVar = t ? `var(${t.varName})` : "var(--line)";
      const icon = profileIconUrl(p, ddragonVersion);
      const emblem = tierEmblemUrl(p.tier);
      const progress = progressLabel(p, p.baseline);
      const games = (p.wins || 0) + (p.losses || 0);
      const wr = games > 0 ? Math.round(((p.wins || 0) / games) * 100) : null;

      let gamesSinceBaseline = null;
      if (p.baseline && p.tier) {
        gamesSinceBaseline =
          (p.wins || 0) + (p.losses || 0) - ((p.baseline.wins || 0) + (p.baseline.losses || 0));
      }

      return `
      <article class="card" style="--tier-color:${tierVar}">
        <div class="card-top">
          <span class="rank-position ${i === 0 ? "is-first" : ""}">#${i + 1}</span>
          <div class="avatar" style="${icon ? `background-image:url('${icon}')` : ""}"></div>
          <div class="identity">
            <div class="riot-id">${esc(p.gameName)}<span class="tag">#${esc(p.tagLine)}</span></div>
            <a class="opgg-link" href="${esc(p.opggUrl)}" target="_blank" rel="noopener">Ver en op.gg ↗</a>
          </div>
        </div>

        ${
          p.tier
            ? `
        <div class="rank-row">
          ${emblem ? `<img class="tier-emblem" src="${emblem}" alt="${esc(t.label)}" loading="lazy">` : ""}
          <div class="tier-text">
            <span class="tier-name">${esc(t ? t.label : p.tier)}${APEX.has(p.tier) ? "" : " " + esc(p.rank || "")}</span>
            <span class="lp-value">${p.leaguePoints ?? 0} LP</span>
          </div>
          ${progress ? `<span class="progress-pill ${progress.cls}">${esc(progress.text)}</span>` : ""}
        </div>
        <div class="stats-row">
          <span><b>${p.wins ?? 0}</b>V &middot; <b>${p.losses ?? 0}</b>D${wr !== null ? ` &middot; ${wr}% WR` : ""}</span>
          ${gamesSinceBaseline !== null ? `<span>${gamesSinceBaseline} jugadas en el challenge</span>` : ""}
        </div>
        ${
          p.baseline && p.baseline.tier
            ? `<div class="baseline-note">Arrancó en ${esc(tierInfo(p.baseline.tier)?.label || p.baseline.tier)}${APEX.has(p.baseline.tier) ? "" : " " + esc(p.baseline.rank || "")} · ${p.baseline.leaguePoints ?? 0} LP</div>`
            : ""
        }
        `
            : `<div class="rank-row"><span class="tier-name" style="color:var(--muted)">Sin clasificar todavía</span></div>`
        }

        ${p.stale ? `<span class="stale-tag">⚠ No se pudo actualizar en la última corrida — mostrando el último dato bueno</span>` : ""}
      </article>`;
    })
    .join("");
}

function scheduleCountdown(generatedAt) {
  clearInterval(countdownTimer);
  const el = document.getElementById("countdown");
  if (!generatedAt) {
    el.textContent = "--:--";
    return;
  }
  const next = new Date(generatedAt).getTime() + UPDATE_MINUTES * 60 * 1000;

  function tick() {
    const diff = next - Date.now();
    if (diff <= 0) {
      el.textContent = "00:00";
      return;
    }
    const m = Math.floor(diff / 60000);
    const s = Math.floor((diff % 60000) / 1000);
    el.textContent = `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }

  tick();
  countdownTimer = setInterval(tick, 1000);
}

loadData();
setInterval(loadData, 45000); // vuelve a leer data.json cada 45s por si ya se actualizó
