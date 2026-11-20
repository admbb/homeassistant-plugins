/**
 * Sirivision SR-S25G3412F Pro Switch Card (custom:sirivision-switch-pro-card)
 * Unified AN Pro Visual Language (Frosted Port Pills + Mobile-First Bottom Sheet)
 * Read-Only SNMP Telemetry · No credentials ever stored or exposed in frontend.
 */

const DEFAULT_CONFIG = {
  type: "custom:sirivision-switch-pro-card",
  entity: "sensor.xi_li_wei_shi_sr_s25g3412f_zhuang_tai",
  name: "",
  layout_mode: "front_panel", // "front_panel" | "grid"
  rj45_order: "dual_row",     // "dual_row" (1,3,5,7 / 2,4,6,8) | "linear" (1..8)
  hide_unused: false,
  show_traffic: true,
  theme: "dark",              // "dark" | "light"
  port_aliases: {},
};

function fmtRate(bps) {
  const v = Number(bps);
  if (!Number.isFinite(v) || v <= 0) return "0 bps";
  if (v >= 1e9) return `${(v / 1e9).toFixed(2).replace(/\.?0+$/, "")}G`;
  if (v >= 1e6) return `${(v / 1e6).toFixed(2).replace(/\.?0+$/, "")}M`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(1).replace(/\.0$/, "")}K`;
  return `${Math.round(v)}b`;
}

function fmtRateFull(bps) {
  const v = Number(bps);
  if (!Number.isFinite(v) || v <= 0) return "0 bps";
  if (v >= 1e9) return `${(v / 1e9).toFixed(2).replace(/\.?0+$/, "")} Gbps`;
  if (v >= 1e6) return `${(v / 1e6).toFixed(2).replace(/\.?0+$/, "")} Mbps`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(1).replace(/\.0$/, "")} Kbps`;
  return `${Math.round(v)} bps`;
}

function fmtRateMbpsVal(bps) {
  const v = Number(bps);
  if (!Number.isFinite(v) || v <= 0) return "0.00";
  const mbps = v / 1e6;
  if (mbps >= 100) return mbps.toFixed(1).replace(/\.0$/, "");
  if (mbps >= 0.01) return mbps.toFixed(2);
  return mbps.toFixed(3);
}

function fmtBytes(bytes) {
  const b = Number(bytes);
  if (!Number.isFinite(b) || b < 0) return "不支持";
  if (b === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB", "PB"];
  const idx = Math.min(units.length - 1, Math.floor(Math.log(b) / Math.log(1024)));
  const val = b / Math.pow(1024, idx);
  return `${val >= 100 ? val.toFixed(0) : val >= 10 ? val.toFixed(1) : val.toFixed(2)} ${units[idx]}`;
}

function fmtUptime(seconds) {
  const s = Number(seconds);
  if (!Number.isFinite(s) || s < 0) return "不支持";
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (d > 0) return `${d}天 ${h}小时`;
  if (h > 0) return `${h}小时 ${m}分`;
  return `${m}分`;
}

function fmtSpeedShort(mbps) {
  const n = Number(mbps);
  if (!Number.isFinite(n) || n <= 0) return "";
  if (n >= 1000) return `${(n / 1000).toFixed(1).replace(/\.0$/, "")}G`;
  return `${n}M`;
}

function escHtml(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function buildTrendSvg(points, unitLabel = "Mbps") {
  const W = 320;
  const H = 96;
  const padL = 6;
  const padR = 6;
  const padT = 8;
  const padB = 14;
  if (!Array.isArray(points) || points.length < 2) {
    return `<div class="chart-empty">等待采集足够的历史样本（约 10 秒后生成曲线）</div>`;
  }
  const rxVals = points.map((p) => Number(p[1]) || 0);
  const txVals = points.map((p) => Number(p[2]) || 0);
  const maxVal = Math.max(0.05, ...rxVals, ...txVals);

  const toCoords = (arr) =>
    arr
      .map((val, idx) => {
        const x = padL + (idx / Math.max(1, arr.length - 1)) * (W - padL - padR);
        const y = H - padB - (val / maxVal) * (H - padT - padB);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");

  const firstTime = new Date((Number(points[0][0]) || 0) * 1000);
  const lastTime = new Date((Number(points[points.length - 1][0]) || 0) * 1000);
  const fmtT = (d) =>
    `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;

  return `
    <svg viewBox="0 0 ${W} ${H}" class="trend-svg" preserveAspectRatio="none">
      <line x1="${padL}" y1="${padT}" x2="${W - padR}" y2="${padT}" stroke="rgba(148,163,184,0.12)" stroke-dasharray="3 3" />
      <line x1="${padL}" y1="${(H - padB + padT) / 2}" x2="${W - padR}" y2="${(H - padB + padT) / 2}" stroke="rgba(148,163,184,0.10)" stroke-dasharray="3 3" />
      <line x1="${padL}" y1="${H - padB}" x2="${W - padR}" y2="${H - padB}" stroke="rgba(148,163,184,0.18)" />
      <polyline fill="none" stroke="#22c55e" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" points="${toCoords(rxVals)}" />
      <polyline fill="none" stroke="#60a5fa" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" points="${toCoords(txVals)}" />
    </svg>
    <div class="chart-axis">
      <span>${fmtT(firstTime)}</span>
      <span>峰值 ${maxVal.toFixed(2)} ${unitLabel}</span>
      <span>${fmtT(lastTime)}</span>
    </div>
  `;
}

class SirivisionSwitchProCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = { ...DEFAULT_CONFIG };
    this._hass = null;
    this._selectedPort = null;
    this._chartWindow = "5m";
    this._drawer = null;
    this._macFilter = "";
    this._macPortFilter = "all";
    this._localPrefs = {};
    this._built = false;
    this._lastSig = "";
    this._lastScrollTs = 0;
  }

  static getStubConfig() {
    return { ...DEFAULT_CONFIG };
  }

  setConfig(config) {
    this._config = { ...DEFAULT_CONFIG, ...(config || {}) };
    try {
      const saved = localStorage.getItem(`siri_prefs_${this._config.entity}`);
      if (saved) this._localPrefs = JSON.parse(saved);
    } catch {
      this._localPrefs = {};
    }
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._built) this._build();
    const ent = this._resolveEntity();
    const sig = this._computeSig(ent);
    if (sig === this._lastSig) return;
    this._lastSig = sig;
    this._render();
  }

  _computeSig(ent) {
    const attr = ent?.attributes || {};
    return [
      ent?.entity_id || "",
      ent?.state || "",
      ent?.last_updated || "",
      attr.uptime_seconds || "",
      attr.ports_up ?? "",
      attr.mac_total ?? "",
      this._drawer || "",
      this._selectedPort || "",
      this._chartWindow || "",
      this._macFilter || "",
      this._macPortFilter || "",
      JSON.stringify(this._localPrefs || {}),
    ].join("|");
  }

  getCardSize() {
    return 5;
  }

  _pref(key, fallback) {
    if (key in this._localPrefs) return this._localPrefs[key];
    if (key in this._config && this._config[key] !== "" && this._config[key] !== undefined) {
      return this._config[key];
    }
    return fallback;
  }

  _savePref(key, val) {
    this._localPrefs = { ...this._localPrefs, [key]: val };
    try {
      localStorage.setItem(`siri_prefs_${this._config.entity}`, JSON.stringify(this._localPrefs));
    } catch {
      // ignore storage quota errors
    }
    this._render();
  }

  _resolveEntity() {
    if (!this._hass) return null;
    if (this._config.entity && this._hass.states[this._config.entity]) {
      return this._hass.states[this._config.entity];
    }
    const states = Object.entries(this._hass.states);
    const byAttr = states.find(([, st]) => {
      const a = st?.attributes;
      return a && Array.isArray(a.ports) && (a.sys_object_id === "1.3.6.1.4.1.27282.3.2.10" || String(a.model || "").includes("SR-S25G"));
    });
    if (byAttr) return byAttr[1];
    const byId = states.find(([id]) =>
      id.startsWith("sensor.") && (id.includes("sirivision") || id.includes("sr_s25g3412f")) && (id.endsWith("_status") || id.endsWith("_zhuang_tai"))
    );
    return byId ? byId[1] : null;
  }

  _build() {
    this._built = true;
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          --an-accent: #3b82f6;
          --an-bg: var(--ha-card-background, var(--card-background-color, rgba(22, 30, 46, 0.82)));
          --an-text: var(--primary-text-color, #f1f5f9);
          --an-sub: var(--secondary-text-color, #94a3b8);
          --an-border: var(--ha-card-border-color, rgba(255, 255, 255, 0.08));
          --an-pill: rgba(148, 163, 184, 0.07);
          --an-pill-hover: rgba(148, 163, 184, 0.14);
          --an-pill-border: rgba(255, 255, 255, 0.04);
          --an-green: #22c55e;
          --an-blue: #60a5fa;
          --an-gray: #64748b;
          --an-orange: #f59e0b;
          --an-yellow: #facc15;
        }
        :host([data-theme="light"]) {
          --an-bg: #f8fafc;
          --an-text: #0f172a;
          --an-sub: #475569;
          --an-border: #cbd5e1;
          --an-pill: rgba(15, 23, 42, 0.045);
          --an-pill-hover: rgba(15, 23, 42, 0.09);
          --an-pill-border: rgba(15, 23, 42, 0.08);
          --an-green: #16a34a;
          --an-blue: #2563eb;
        }
        ha-card {
          background: var(--an-bg);
          border-radius: var(--ha-card-border-radius, 18px);
          border: 1px solid var(--an-border);
          box-shadow: var(--ha-card-box-shadow, 0 8px 24px rgba(0, 0, 0, 0.22));
          padding: 16px;
          color: var(--an-text);
          overflow: hidden;
          position: relative;
        }
        .hdr {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 8px;
          margin-bottom: 12px;
        }
        .hdr-left {
          display: flex;
          align-items: center;
          gap: 10px;
          min-width: 0;
        }
        .title-wrap {
          display: flex;
          flex-direction: column;
          min-width: 0;
        }
        .title {
          font-size: 15px;
          font-weight: 700;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          line-height: 1.2;
        }
        .subtitle {
          font-size: 11.5px;
          color: var(--an-sub);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          margin-top: 2px;
        }
        .hdr-actions {
          display: flex;
          align-items: center;
          gap: 6px;
          flex-shrink: 0;
        }
        .status-pill {
          display: inline-flex;
          align-items: center;
          gap: 5px;
          padding: 3px 9px;
          border-radius: 999px;
          font-size: 11px;
          font-weight: 600;
          background: rgba(148, 163, 184, 0.14);
          border: 1px solid rgba(255, 255, 255, 0.06);
          white-space: nowrap;
        }
        .status-dot {
          width: 7px;
          height: 7px;
          border-radius: 50%;
          background: var(--an-green);
        }
        .status-pill.err { color: var(--an-orange); }
        .status-pill.err .status-dot { background: var(--an-orange); }
        .icon-btn {
          width: 33px;
          height: 33px;
          border-radius: 50%;
          border: 1px solid rgba(148, 163, 184, 0.16);
          background: rgba(148, 163, 184, 0.08);
          color: var(--an-sub);
          display: inline-flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          padding: 0;
          transition: all 0.2s ease;
        }
        .icon-btn:hover, .icon-btn.active {
          background: rgba(59, 130, 246, 0.18);
          border-color: rgba(59, 130, 246, 0.45);
          color: var(--an-blue);
        }
        .icon-btn ha-icon { --mdc-icon-size: 17px; }
        .offline-banner {
          background: rgba(245, 158, 11, 0.12);
          border: 1px solid rgba(245, 158, 11, 0.35);
          color: var(--an-orange);
          border-radius: 12px;
          padding: 8px 11px;
          font-size: 12px;
          margin-bottom: 10px;
          line-height: 1.4;
        }

        /* Traffic & Stats Strip matching MikrotikRouterProCard */
        .tf-grid {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 6px;
          margin-bottom: 8px;
        }
        .tf-box {
          background: var(--an-pill);
          border: 1px solid var(--an-pill-border);
          border-radius: 11px;
          padding: 7px 9px;
          min-width: 0;
        }
        .tf-lbl {
          font-size: 10px;
          color: var(--an-sub);
          margin-bottom: 3px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .tf-row {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 4px;
        }
        .tf-metric {
          display: flex;
          flex-direction: column;
          align-items: flex-start;
          line-height: 1.25;
          min-width: 0;
        }
        .tf-num {
          font-size: 12px;
          font-weight: 700;
          font-variant-numeric: tabular-nums;
          white-space: nowrap;
        }
        .tf-unit {
          font-size: 10px;
          font-weight: 600;
          opacity: 0.9;
          white-space: nowrap;
        }
        .rx-c { color: var(--an-green); }
        .tx-c { color: var(--an-blue); }

        .sec-lbl {
          display: flex;
          justify-content: space-between;
          align-items: center;
          font-size: 10.5px;
          color: var(--an-sub);
          margin: 8px 2px 5px;
        }

        /* Frosted Port Pills — Identical style to MikrotikRouterProCard */
        .ports-strip {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 6px;
          margin-bottom: 6px;
        }
        .port-pill {
          background: var(--an-pill);
          border: 1px solid var(--an-pill-border);
          border-radius: 11px;
          padding: 8px 4px;
          text-align: center;
          cursor: pointer;
          transition: background 0.2s ease, border-color 0.2s ease;
          min-width: 0;
          -webkit-tap-highlight-color: transparent;
        }
        .port-pill:hover {
          background: var(--an-pill-hover);
          border-color: rgba(148, 163, 184, 0.18);
        }
        .port-lbl {
          font-size: 10.5px;
          color: var(--an-sub);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          margin-bottom: 3px;
          padding: 0 2px;
        }
        .port-st {
          font-size: 11.5px;
          font-weight: 700;
          color: var(--an-text);
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 4px;
          white-space: nowrap;
        }
        .p-dot {
          width: 6.5px;
          height: 6.5px;
          border-radius: 50%;
          background: var(--an-gray);
          display: inline-block;
          flex-shrink: 0;
        }
        .p-dot.green { background: var(--an-green); box-shadow: 0 0 6px rgba(34, 197, 94, 0.55); }
        .p-dot.gray { background: var(--an-gray); }
        .p-dot.yellow { background: var(--an-yellow); }
        .p-dot.blue { background: var(--an-blue); }
        .p-dot.orange { background: var(--an-orange); }
        .port-rate {
          font-size: 9.5px;
          color: var(--an-sub);
          font-variant-numeric: tabular-nums;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          margin-top: 2px;
        }

        .stats-strip {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 6px;
          margin-top: 8px;
        }
        .stat-pill {
          background: var(--an-pill);
          border: 1px solid var(--an-pill-border);
          border-radius: 10px;
          padding: 6px 8px;
          text-align: center;
          min-width: 0;
        }
        .stat-lbl { font-size: 10px; color: var(--an-sub); white-space: nowrap; }
        .stat-val {
          font-size: 12px;
          font-weight: 700;
          margin-top: 2px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .tabs-bar {
          display: flex;
          gap: 6px;
          margin-top: 10px;
        }
        .tab-btn {
          flex: 1;
          background: var(--an-pill);
          border: 1px solid var(--an-pill-border);
          color: var(--an-sub);
          border-radius: 11px;
          padding: 7px 10px;
          font-size: 11.5px;
          font-weight: 600;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 5px;
          cursor: pointer;
        }
        .tab-btn.active {
          color: var(--an-blue);
          border-color: rgba(96, 165, 250, 0.35);
          background: rgba(59, 130, 246, 0.14);
        }
        .tab-btn ha-icon { --mdc-icon-size: 15px; }

        .drawer {
          margin-top: 8px;
          background: var(--an-pill);
          border: 1px solid var(--an-pill-border);
          border-radius: 12px;
          padding: 12px;
        }
        .drawer-title {
          font-size: 12px;
          font-weight: 700;
          margin-bottom: 8px;
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .vlan-row { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
        .vlan-chip {
          font-size: 11px;
          padding: 3px 8px;
          border-radius: 8px;
          background: rgba(59, 130, 246, 0.12);
          border: 1px solid rgba(59, 130, 246, 0.25);
          color: var(--an-blue);
        }
        .filter-row { display: flex; gap: 6px; margin-bottom: 8px; }
        .inp, .sel {
          background: rgba(15, 23, 42, 0.55);
          border: 1px solid rgba(148, 163, 184, 0.22);
          color: var(--an-text);
          border-radius: 8px;
          padding: 6px 9px;
          font-size: 12px;
          min-width: 0;
        }
        :host([data-theme="light"]) .inp, :host([data-theme="light"]) .sel { background: #fff; }
        .inp { flex: 1; }
        .mac-list {
          max-height: 240px;
          overflow-y: auto;
          overflow-x: hidden;
          -webkit-overflow-scrolling: touch;
          overscroll-behavior: contain;
          touch-action: pan-y;
          scrollbar-width: thin;
          scrollbar-color: rgba(148, 163, 184, 0.35) transparent;
          display: flex;
          flex-direction: column;
          gap: 5px;
          padding-right: 4px;
        }
        .mac-list::-webkit-scrollbar { width: 5px; }
        .mac-list::-webkit-scrollbar-thumb { background: rgba(148, 163, 184, 0.32); border-radius: 999px; }
        .mac-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          font-size: 11.5px;
          padding: 6px 10px;
          border-radius: 999px;
          background: rgba(148, 163, 184, 0.08);
          border: 1px solid rgba(255, 255, 255, 0.04);
          font-variant-numeric: tabular-nums;
          flex-shrink: 0;
        }
        .set-row {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 10px;
          padding: 6px 0;
          border-bottom: 1px solid var(--an-pill-border);
          font-size: 12px;
        }
        .set-row:last-child { border-bottom: none; }
        .alias-grid {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 6px;
          margin-top: 8px;
        }
        .alias-item { display: flex; align-items: center; gap: 5px; font-size: 11px; }
        .alias-item span { width: 52px; color: var(--an-sub); flex-shrink: 0; }
        .save-btn {
          margin-top: 8px;
          width: 100%;
          padding: 8px;
          border-radius: 10px;
          border: 1px solid rgba(59, 130, 246, 0.45);
          background: rgba(59, 130, 246, 0.16);
          color: var(--an-blue);
          font-weight: 700;
          cursor: pointer;
          font-size: 12px;
        }

        /* Mobile-First Bottom Sheet Modal */
        .modal-backdrop {
          position: fixed;
          inset: 0;
          background: rgba(0, 0, 0, 0.65);
          backdrop-filter: blur(4px);
          z-index: 9999;
          display: flex;
          align-items: flex-end;
          justify-content: center;
          padding: 0;
        }
        .modal-sheet {
          width: 100%;
          max-width: 540px;
          max-height: 86vh;
          overflow-y: auto;
          background: rgba(15, 23, 42, 0.97);
          border: 1px solid rgba(148, 163, 184, 0.22);
          border-radius: 20px 20px 0 0;
          padding: 16px;
          color: var(--an-text);
          box-shadow: 0 -10px 36px rgba(0, 0, 0, 0.45);
        }
        :host([data-theme="light"]) .modal-sheet { background: #fff; }
        @media (min-width: 640px) {
          .modal-backdrop { align-items: center; padding: 16px; }
          .modal-sheet { border-radius: 20px; }
        }
        .sheet-hdr { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .sheet-title { font-size: 16px; font-weight: 700; display: flex; align-items: center; gap: 8px; }
        .kv-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-bottom: 12px; }
        .kv-box {
          background: var(--an-pill);
          border: 1px solid var(--an-pill-border);
          border-radius: 12px;
          padding: 8px 10px;
        }
        .kv-k { font-size: 10.5px; color: var(--an-sub); }
        .kv-v { font-size: 13px; font-weight: 700; margin-top: 2px; word-break: break-word; }
        .chart-card {
          background: var(--an-pill);
          border: 1px solid var(--an-pill-border);
          border-radius: 12px;
          padding: 10px;
          margin-bottom: 12px;
        }
        .chart-hdr { display: flex; justify-content: space-between; align-items: center; font-size: 11.5px; margin-bottom: 6px; }
        .seg { display: inline-flex; border-radius: 8px; overflow: hidden; border: 1px solid var(--an-pill-border); }
        .seg button {
          background: transparent;
          border: none;
          color: var(--an-sub);
          font-size: 11px;
          padding: 3px 8px;
          cursor: pointer;
        }
        .seg button.active { background: rgba(59, 130, 246, 0.2); color: var(--an-blue); font-weight: 700; }
        .trend-svg { width: 100%; height: 96px; display: block; }
        .chart-axis { display: flex; justify-content: space-between; font-size: 10px; color: var(--an-sub); margin-top: 2px; }
        .chart-empty { text-align: center; font-size: 11.5px; color: var(--an-sub); padding: 18px 8px; }

        @media (max-width: 560px) {
          .tf-grid { grid-template-columns: 1fr; }
          .stats-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
          .alias-grid { grid-template-columns: 1fr; }
        }
        @media (max-width: 440px) {
          .ports-strip { gap: 4px; }
          .port-lbl { font-size: 9.5px; }
          .port-st { font-size: 10.5px; }
          .port-rate { font-size: 9px; }
        }
      </style>
      <ha-card id="cardRoot"></ha-card>
      <div id="modalHost"></div>
    `;
  }

  _orderRj45(ports) {
    const mode = this._pref("rj45_order", "dual_row");
    const sorted = [...ports].sort((a, b) => a.slot - b.slot);
    if (mode !== "dual_row" || sorted.length !== 8) return sorted;
    return [sorted[0], sorted[2], sorted[4], sorted[6], sorted[1], sorted[3], sorted[5], sorted[7]];
  }

  _renderPortPill(p, showTraffic) {
    const aliases = this._config.port_aliases || {};
    const displayAlias = p.alias || aliases[p.physical_port] || "";
    const baseNum = p.type === "sfp_plus" ? `SFP+ ${p.slot - 8}` : `口${p.slot}`;
    const labelText = displayAlias ? `${baseNum}·${displayAlias}` : `${baseNum} (${p.type === "sfp_plus" ? "10G" : "2.5G"})`;

    const spdShort = fmtSpeedShort(p.speed_mbps);
    let stText = "断开";
    if (p.admin_status === "down") stText = "禁用";
    else if (p.connected) stText = spdShort ? `已连·${spdShort}` : "已连";
    else if (p.summary_label && p.summary_label !== "未连接") stText = p.summary_label;

    const rateHtml =
      showTraffic && p.connected
        ? `<div class="port-rate">↓${fmtRate(p.rx_bps)} ↑${fmtRate(p.tx_bps)}</div>`
        : "";

    return `
      <div class="port-pill ${p.connected ? "up" : ""}" data-port="${escHtml(p.physical_port)}">
        <div class="port-lbl">${escHtml(labelText)}</div>
        <div class="port-st"><span class="p-dot ${escHtml(p.led_color || "gray")}"></span><span>${escHtml(stText)}</span></div>
        ${rateHtml}
      </div>
    `;
  }

  _renderMacRows(attr, ports) {
    const macs = Array.isArray(attr.mac_entries) ? attr.mac_entries : [];
    const portMap = new Map(ports.map((p) => [p.if_index, p]));
    const q = this._macFilter.trim().toLowerCase();
    const filtered = macs.filter((m) => {
      if (this._macPortFilter !== "all" && String(m.if_index) !== this._macPortFilter) return false;
      if (!q) return true;
      const p = portMap.get(m.if_index);
      const hay = `${m.mac} vlan${m.vlan_id} ${p?.physical_port || ""} ${p?.alias || ""}`.toLowerCase();
      return hay.includes(q);
    });
    const html = filtered.length
      ? filtered.map((m) => {
          const p = portMap.get(m.if_index);
          return `<div class="mac-item"><span>${escHtml(m.mac)}</span><span>VLAN ${m.vlan_id} · ${escHtml(p ? (p.alias ? `${p.physical_port} (${p.alias})` : p.physical_port) : `ifIndex ${m.if_index}`)}</span></div>`;
        }).join("")
      : `<div style="font-size:11.5px;color:var(--an-sub);padding:8px">无匹配 MAC 记录</div>`;
    return { count: filtered.length, html };
  }

  _render() {
    if (!this._built) return;
    const theme = this._pref("theme", "dark");
    this.setAttribute("data-theme", theme);

    const root = this.shadowRoot.getElementById("cardRoot");
    const prevMacList = root.querySelector(".mac-list");
    const prevMacScroll = prevMacList ? prevMacList.scrollTop : 0;
    const activeElId = this.shadowRoot.activeElement?.id || null;
    const selStart = activeElId === "macSearchInp" ? this.shadowRoot.activeElement.selectionStart : null;
    const selEnd = activeElId === "macSearchInp" ? this.shadowRoot.activeElement.selectionEnd : null;

    const ent = this._resolveEntity();
    if (!ent) {
      root.innerHTML = `<div class="offline-banner">未找到 Sirivision 交换机实体 (${escHtml(this._config.entity)})。</div>`;
      return;
    }

    const attr = ent.attributes || {};
    const online = Boolean(attr.snmp_connected) && ent.state === "online";
    const devName = this._pref("name", "") || attr.device_name || "希力威视 SR-S25G3412F";
    const host = attr.host || "地址未知";
    const ports = Array.isArray(attr.ports) ? attr.ports : [];
    const layoutMode = this._pref("layout_mode", "front_panel");
    const hideUnused = Boolean(this._pref("hide_unused", false));
    const showTraffic = this._pref("show_traffic", true) !== false;

    const visiblePorts = hideUnused ? ports.filter((p) => p.connected) : ports;
    const rj45Ports = this._orderRj45(visiblePorts.filter((p) => p.type === "rj45"));
    const sfpPorts = [...visiblePorts.filter((p) => p.type === "sfp_plus")].sort((a, b) => a.slot - b.slot);

    let portsHtml = "";
    if (layoutMode === "grid") {
      portsHtml = `
        <div class="sec-lbl"><span>物理端口（标准网格 · 12 口）</span><span>在线 ${attr.ports_up ?? 0} / ${attr.ports_total ?? 12}</span></div>
        <div class="ports-strip">
          ${visiblePorts.map((p) => this._renderPortPill(p, showTraffic)).join("")}
        </div>
      `;
    } else {
      portsHtml = `
        <div class="sec-lbl"><span>2.5G RJ45 电口 (${attr.ports_rj45_up ?? 0}/8 在线)</span><span>${this._pref("rj45_order", "dual_row") === "dual_row" ? "物理双排" : "顺序 1–8"}</span></div>
        <div class="ports-strip">
          ${rj45Ports.map((p) => this._renderPortPill(p, showTraffic)).join("")}
        </div>
        <div class="sec-lbl"><span>10G SFP+ 光口 (${attr.ports_sfp_up ?? 0}/4 在线)</span><span>端口 9–12</span></div>
        <div class="ports-strip">
          ${sfpPorts.map((p) => this._renderPortPill(p, showTraffic)).join("")}
        </div>
      `;
    }

    const renderTfBox = (title, rxBps, txBps) => `
      <div class="tf-box">
        <div class="tf-lbl">${title}</div>
        <div class="tf-row">
          <div class="tf-metric rx-c"><span class="tf-num">↓ ${fmtRateMbpsVal(rxBps)}</span><span class="tf-unit">Mbps</span></div>
          <div class="tf-metric tx-c"><span class="tf-num">↑ ${fmtRateMbpsVal(txBps)}</span><span class="tf-unit">Mbps</span></div>
        </div>
      </div>
    `;

    root.innerHTML = `
      <div class="hdr">
        <div class="hdr-left">
          <div class="title-wrap">
            <div class="title">${escHtml(devName)}</div>
            <div class="subtitle">${escHtml(host)} · ${escHtml(attr.model || "SR-S25G3412F")} · 在线 ${fmtUptime(attr.uptime_seconds)}</div>
          </div>
          <div class="status-pill ${online ? "" : "err"}">
            <span class="status-dot"></span>
            <span>${online ? `运行正常 (${attr.ports_up ?? 0}/12)` : "SNMP 异常"}</span>
          </div>
        </div>
        <div class="hdr-actions">
          <button class="icon-btn" id="btnLayout" title="切换前面板/网格">
            <ha-icon icon="${layoutMode === "front_panel" ? "mdi:view-grid-outline" : "mdi:ethernet"}"></ha-icon>
          </button>
          <button class="icon-btn ${this._drawer === "settings" ? "active" : ""}" id="btnSettings" title="设置与端口命名">
            <ha-icon icon="mdi:cog-outline"></ha-icon>
          </button>
        </div>
      </div>

      ${!online ? `
        <div class="offline-banner">
          <strong>SNMP 连接异常</strong>${attr.last_error ? `：${escHtml(attr.last_error)}` : ""} · 最后成功：${escHtml(attr.last_success_at || "尚未连接")}
        </div>
      ` : ""}

      ${showTraffic ? `
        <div class="tf-grid">
          ${renderTfBox("全部端口聚合 (非出口带宽)", attr.total_rx_bps, attr.total_tx_bps)}
          ${renderTfBox("2.5G RJ45 汇总", attr.rj45_rx_bps, attr.rj45_tx_bps)}
          ${renderTfBox("10G SFP+ 汇总", attr.sfp_rx_bps, attr.sfp_tx_bps)}
        </div>
      ` : ""}

      ${portsHtml}

      <div class="stats-strip">
        <div class="stat-pill"><div class="stat-lbl">物理端口</div><div class="stat-val">${attr.ports_up ?? 0} / ${attr.ports_total ?? 12}</div></div>
        <div class="stat-pill"><div class="stat-lbl">MAC 转发表</div><div class="stat-val">${attr.mac_total ?? 0} 条</div></div>
        <div class="stat-pill"><div class="stat-lbl">CPU / 内存</div><div class="stat-val" style="color:var(--an-sub)">不支持</div></div>
        <div class="stat-pill"><div class="stat-lbl">最后更新</div><div class="stat-val">${escHtml((attr.last_success_at || "--").split(" ").pop())}</div></div>
      </div>

      <div class="tabs-bar">
        <button class="tab-btn ${this._drawer === "mac" ? "active" : ""}" id="btnMacDrawer">
          <ha-icon icon="mdi:table-network"></ha-icon>
          <span>VLAN & MAC (${attr.mac_total ?? 0})</span>
        </button>
        <button class="tab-btn ${this._drawer === "settings" ? "active" : ""}" id="btnSetDrawer">
          <ha-icon icon="mdi:tune-variant"></ha-icon>
          <span>端口命名 & 显示</span>
        </button>
      </div>

      ${this._renderDrawer(attr, ports)}
    `;

    this._bindCardEvents(attr, ports);
    this._renderModal(ports);

    const newMacList = root.querySelector(".mac-list");
    if (newMacList && prevMacScroll > 0) {
      newMacList.scrollTop = prevMacScroll;
    }
    if (activeElId === "macSearchInp") {
      const inp = this.shadowRoot.getElementById("macSearchInp");
      if (inp) {
        inp.focus();
        if (selStart !== null && selEnd !== null) inp.setSelectionRange(selStart, selEnd);
      }
    }
  }

  _renderDrawer(attr, ports) {
    if (this._drawer === "mac") {
      const vlans = Array.isArray(attr.vlans) ? attr.vlans : [];
      const macInfo = this._renderMacRows(attr, ports);
      return `
        <div class="drawer">
          <div class="drawer-title"><span>VLAN 列表 (Q-BRIDGE-MIB)</span><span>共 ${vlans.length} 个</span></div>
          <div class="vlan-row">
            ${vlans.length ? vlans.map((v) => `<span class="vlan-chip">VLAN ${v.vlan_id} · ${escHtml(v.name)}</span>`).join("") : `<span style="font-size:11px;color:var(--an-sub)">设备未返回 VLAN 数据</span>`}
          </div>
          <div class="drawer-title" style="margin-top:8px"><span>MAC 地址转发表</span><span id="macMatchCount">匹配 ${macInfo.count} 条</span></div>
          <div class="filter-row">
            <input class="inp" id="macSearchInp" placeholder="搜索 MAC / 端口 / 别名..." value="${escHtml(this._macFilter)}" />
            <select class="sel" id="macPortSel">
              <option value="all">全部端口</option>
              ${ports.map((p) => `<option value="${p.if_index}" ${this._macPortFilter === String(p.if_index) ? "selected" : ""}>${escHtml(p.physical_port)}${p.alias ? ` (${escHtml(p.alias)})` : ""}</option>`).join("")}
            </select>
          </div>
          <div class="mac-list" id="macListContainer">
            ${macInfo.html}
          </div>
        </div>
      `;
    }

    if (this._drawer === "settings") {
      const layoutMode = this._pref("layout_mode", "front_panel");
      const rjOrder = this._pref("rj45_order", "dual_row");
      const hideUnused = Boolean(this._pref("hide_unused", false));
      const showTraffic = this._pref("show_traffic", true) !== false;
      const theme = this._pref("theme", "dark");
      return `
        <div class="drawer">
          <div class="drawer-title"><span>显示与交互设置</span><span style="font-size:10.5px;color:var(--an-sub)">SNMP 凭证仅由 HA 后端保管</span></div>
          <div class="set-row">
            <span>设备名称</span>
            <input class="inp" style="max-width:210px" id="inpDevName" value="${escHtml(this._pref("name", attr.device_name || "希力威视 SR-S25G3412F"))}" />
          </div>
          <div class="set-row">
            <span>端口布局方式</span>
            <select class="sel" id="selLayout">
              <option value="front_panel" ${layoutMode === "front_panel" ? "selected" : ""}>真实前面板 (8×RJ45 + 4×SFP+)</option>
              <option value="grid" ${layoutMode === "grid" ? "selected" : ""}>标准统一网格</option>
            </select>
          </div>
          <div class="set-row">
            <span>2.5G RJ45 排列</span>
            <select class="sel" id="selRjOrder">
              <option value="dual_row" ${rjOrder === "dual_row" ? "selected" : ""}>双排交错 (1/3/5/7 上, 2/4/6/8 下)</option>
              <option value="linear" ${rjOrder === "linear" ? "selected" : ""}>顺序排列 (1–8)</option>
            </select>
          </div>
          <div class="set-row">
            <span>隐藏未连接端口</span>
            <input type="checkbox" id="chkHideUnused" ${hideUnused ? "checked" : ""} />
          </div>
          <div class="set-row">
            <span>显示实时 RX / TX 流量</span>
            <input type="checkbox" id="chkShowTraffic" ${showTraffic ? "checked" : ""} />
          </div>
          <div class="set-row">
            <span>主题外观</span>
            <select class="sel" id="selTheme">
              <option value="dark" ${theme === "dark" ? "selected" : ""}>深色模式</option>
              <option value="light" ${theme === "light" ? "selected" : ""}>浅色模式</option>
            </select>
          </div>
          <div style="margin-top:10px;font-size:11.5px;font-weight:700">端口自定义名称（保存至 HA 后端配置）</div>
          <div class="alias-grid">
            ${ports.map((p) => `
              <div class="alias-item">
                <span>${escHtml(p.physical_port)}</span>
                <input class="inp port-alias-inp" data-port="${escHtml(p.physical_port)}" placeholder="${escHtml(p.interface_name)}" value="${escHtml(p.alias || "")}" />
              </div>
            `).join("")}
          </div>
          <button class="save-btn" id="btnSaveAliases">保存端口名称到 Home Assistant</button>
        </div>
      `;
    }
    return "";
  }

  _bindCardEvents(attr, ports) {
    const r = this.shadowRoot;
    r.getElementById("btnLayout")?.addEventListener("click", () => {
      const cur = this._pref("layout_mode", "front_panel");
      this._savePref("layout_mode", cur === "front_panel" ? "grid" : "front_panel");
    });
    r.getElementById("btnSettings")?.addEventListener("click", () => {
      this._drawer = this._drawer === "settings" ? null : "settings";
      this._render();
    });
    r.getElementById("btnSetDrawer")?.addEventListener("click", () => {
      this._drawer = this._drawer === "settings" ? null : "settings";
      this._render();
    });
    r.getElementById("btnMacDrawer")?.addEventListener("click", () => {
      this._drawer = this._drawer === "mac" ? null : "mac";
      this._render();
    });
    r.querySelectorAll(".port-pill").forEach((el) => {
      el.addEventListener("click", (ev) => {
        ev.stopPropagation();
        this._selectedPort = el.getAttribute("data-port");
        this._lastSig = this._computeSig(this._resolveEntity());
        this._renderModal(ports);
      });
    });

    r.getElementById("macSearchInp")?.addEventListener("input", (e) => {
      this._macFilter = e.target.value || "";
      const info = this._renderMacRows(attr, ports);
      const listEl = r.getElementById("macListContainer");
      const cntEl = r.getElementById("macMatchCount");
      if (listEl) listEl.innerHTML = info.html;
      if (cntEl) cntEl.textContent = `匹配 ${info.count} 条`;
    });
    r.getElementById("macPortSel")?.addEventListener("change", (e) => {
      this._macPortFilter = e.target.value || "all";
      const info = this._renderMacRows(attr, ports);
      const listEl = r.getElementById("macListContainer");
      const cntEl = r.getElementById("macMatchCount");
      if (listEl) { listEl.innerHTML = info.html; listEl.scrollTop = 0; }
      if (cntEl) cntEl.textContent = `匹配 ${info.count} 条`;
    });
    r.getElementById("inpDevName")?.addEventListener("change", (e) => {
      this._savePref("name", e.target.value.trim());
    });
    r.getElementById("selLayout")?.addEventListener("change", (e) => {
      this._savePref("layout_mode", e.target.value);
    });
    r.getElementById("selRjOrder")?.addEventListener("change", (e) => {
      this._savePref("rj45_order", e.target.value);
    });
    r.getElementById("chkHideUnused")?.addEventListener("change", (e) => {
      this._savePref("hide_unused", Boolean(e.target.checked));
    });
    r.getElementById("chkShowTraffic")?.addEventListener("change", (e) => {
      this._savePref("show_traffic", Boolean(e.target.checked));
    });
    r.getElementById("selTheme")?.addEventListener("change", (e) => {
      this._savePref("theme", e.target.value);
    });
    r.getElementById("btnSaveAliases")?.addEventListener("click", async () => {
      const entryId = attr.entry_id;
      if (!entryId || !this._hass) return;
      const inputs = [...r.querySelectorAll(".port-alias-inp")];
      for (const inp of inputs) {
        const phys = inp.getAttribute("data-port");
        const val = inp.value.trim();
        const orig = ports.find((p) => p.physical_port === phys)?.alias || "";
        if (val !== orig) {
          await this._hass.callService("sirivision_switch", "set_port_config", {
            entry_id: entryId,
            physical_port: phys,
            alias: val,
          });
        }
      }
      this._drawer = null;
      this._render();
    });
  }

  _renderModal(ports) {
    const host = this.shadowRoot.getElementById("modalHost");
    if (!this._selectedPort) {
      host.innerHTML = "";
      return;
    }
    const p = ports.find((x) => x.physical_port === this._selectedPort);
    if (!p) {
      host.innerHTML = "";
      return;
    }
    const pts = this._chartWindow === "1h" ? (p.history_1h || []) : (p.history_5m || []);
    const macs = Array.isArray(p.mac_list) ? p.mac_list : [];
    const speedDisplay = p.connected
      ? (p.speed_mbps ? `${p.speed_mbps >= 1000 ? `${p.speed_mbps / 1000} Gbps` : `${p.speed_mbps} Mbps`}` : "固件未上报（已连接）")
      : "未连接";

    host.innerHTML = `
      <div class="modal-backdrop" id="modalBackdrop">
        <div class="modal-sheet">
          <div class="sheet-hdr">
            <div class="sheet-title">
              <span class="p-dot ${escHtml(p.led_color || "gray")}" style="width:9px;height:9px"></span>
              <span>端口 ${escHtml(p.physical_port)}${p.alias ? ` · ${escHtml(p.alias)}` : ""}</span>
            </div>
            <button class="icon-btn" id="btnCloseModal"><ha-icon icon="mdi:close"></ha-icon></button>
          </div>
          <div class="kv-grid">
            <div class="kv-box">
              <div class="kv-k">运行状态 / 管理状态</div>
              <div class="kv-v">${escHtml(p.oper_label || "未知")} / ${escHtml(p.admin_label || "启用")}</div>
            </div>
            <div class="kv-box">
              <div class="kv-k">端口类型 & SNMP 接口</div>
              <div class="kv-v">${p.type === "sfp_plus" ? "10G SFP+" : "2.5G RJ45"} · ${escHtml(p.interface_name)} (ifIndex=${p.if_index ?? "--"})</div>
            </div>
            <div class="kv-box">
              <div class="kv-k">当前协商速率</div>
              <div class="kv-v">${escHtml(speedDisplay)}</div>
            </div>
            <div class="kv-box">
              <div class="kv-k">双工模式 / PVID</div>
              <div class="kv-v">${escHtml(p.duplex || "不支持")} · VLAN ${p.pvid ?? "不支持"}</div>
            </div>
            <div class="kv-box">
              <div class="kv-k">实时接收 (RX)</div>
              <div class="kv-v rx-c">${fmtRateFull(p.rx_bps)}</div>
            </div>
            <div class="kv-box">
              <div class="kv-k">实时发送 (TX)</div>
              <div class="kv-v tx-c">${fmtRateFull(p.tx_bps)}</div>
            </div>
            <div class="kv-box">
              <div class="kv-k">累计接收 / 发送字节</div>
              <div class="kv-v">${fmtBytes(p.rx_bytes)} / ${fmtBytes(p.tx_bytes)}</div>
            </div>
            <div class="kv-box">
              <div class="kv-k">错误包 / 丢弃包</div>
              <div class="kv-v">错包 ${p.in_errors ?? 0}/${p.out_errors ?? 0} · 丢包 ${p.in_discards ?? 0}/${p.out_discards ?? 0}</div>
            </div>
          </div>

          <div class="chart-card">
            <div class="chart-hdr">
              <span><strong>流量趋势</strong> (<span class="rx-c">● RX</span> <span class="tx-c">● TX</span>)</span>
              <div class="seg">
                <button class="${this._chartWindow === "5m" ? "active" : ""}" id="btnWin5m">5分钟</button>
                <button class="${this._chartWindow === "1h" ? "active" : ""}" id="btnWin1h">1小时</button>
              </div>
            </div>
            ${buildTrendSvg(pts, "Mbps")}
          </div>

          <div class="chart-card" style="margin-bottom:0">
            <div class="chart-hdr">
              <span><strong>关联 MAC 地址</strong></span>
              <span>${macs.length} 条</span>
            </div>
            <div class="mac-list" style="max-height:110px">
              ${macs.length ? macs.map((m) => `<div class="mac-item"><span>${escHtml(m.mac)}</span><span>VLAN ${m.vlan_id}</span></div>`).join("") : `<div style="font-size:11px;color:var(--an-sub)">当前无学习到的 MAC 记录</div>`}
            </div>
          </div>
        </div>
      </div>
    `;

    this.shadowRoot.getElementById("modalBackdrop")?.addEventListener("click", (e) => {
      if (e.target.id === "modalBackdrop") {
        this._selectedPort = null;
        this._renderModal(ports);
      }
    });
    this.shadowRoot.getElementById("btnCloseModal")?.addEventListener("click", () => {
      this._selectedPort = null;
      this._renderModal(ports);
    });
    this.shadowRoot.getElementById("btnWin5m")?.addEventListener("click", () => {
      this._chartWindow = "5m";
      this._renderModal(ports);
    });
    this.shadowRoot.getElementById("btnWin1h")?.addEventListener("click", () => {
      this._chartWindow = "1h";
      this._renderModal(ports);
    });
  }
}

if (!customElements.get("sirivision-switch-pro-card")) {
  customElements.define("sirivision-switch-pro-card", SirivisionSwitchProCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "sirivision-switch-pro-card")) {
  window.customCards.push({
    type: "sirivision-switch-pro-card",
    name: "Sirivision SR-S25G3412F Pro Switch Card",
    description: "希力威视 12 口 2.5G/10G 交换机 SNMP 实时监控卡片",
    preview: true,
  });
}
