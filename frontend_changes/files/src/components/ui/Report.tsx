export const QUADRANTS = [
  {
    label: "Upper Outer Quadrant",
    abbr: "UOQ",
    clipX: "0%",
    clipY: "0%",
    desc: "Anterior · Superior-lateral view",
  },
  {
    label: "Upper Inner Quadrant",
    abbr: "UIQ",
    clipX: "50%",
    clipY: "0%",
    desc: "Anterior · Superior-medial view",
  },
  {
    label: "Lower Outer Quadrant",
    abbr: "LOQ",
    clipX: "0%",
    clipY: "50%",
    desc: "Anterior · Inferior-lateral view",
  },
  {
    label: "Lower Inner Quadrant",
    abbr: "LIQ",
    clipX: "50%",
    clipY: "50%",
    desc: "Anterior · Inferior-medial view",
  },
];

export const ANGLES = [
  { label: "Anterior (0°)", angle: "0deg" },
  { label: "Lateral (90°)", angle: "90deg" },
  { label: "Superior (Top)", angle: "top" },
  { label: "Medial (270°)", angle: "270deg" },
];

export function buildDomePanelGridHtml(
  side: "Left" | "Right",
  score: number,
  image: string,
) {
  return `
    <div class="dome-section">
      <div class="dome-section-header">
        <div class="dome-section-dot" style="background:${side === "Left" ? "#F0559E" : "#9B72E8"}"></div>
        <h2 class="dome-section-title">${side} Breast — Quadrant Analysis</h2>
        <span class="dome-section-score">Score: ${score}</span>
      </div>
      <div class="quadrant-grid">
        ${QUADRANTS.map(
          (q, i) => `
          <div class="quadrant-card">
            <div class="quadrant-header">
              <span class="quadrant-abbr" style="color:${side === "Left" ? "#F0559E" : "#9B72E8"}">${q.abbr}</span>
              <span class="quadrant-label">${q.label}</span>
            </div>
            <div class="quadrant-img-wrap">
              <img
                src="${image}"
                class="quadrant-img"
                style="object-position:${q.clipX} ${q.clipY}"
              />
              <div class="quadrant-overlay">
                <div class="quadrant-crosshair-h"></div>
                <div class="quadrant-crosshair-v"></div>
                <div class="quadrant-focus" style="
                  left:${q.clipX === "0%" ? "0" : "50%"};
                  top:${q.clipY === "0%" ? "0" : "50%"};
                "></div>
              </div>
            </div>
            <div class="quadrant-angle-label">${ANGLES[i].label}</div>
            <div class="quadrant-desc">${q.desc}</div>
          </div>
        `,
        ).join("")}
      </div>

      <div class="angle-strip">
        <div class="angle-strip-title">Multi-Angle Thermal Profile</div>
        <div class="angle-strip-row">
          ${ANGLES.map(
            (a, i) => `
            <div class="angle-panel">
              <div class="angle-panel-img-wrap">
                <img src="${image}" class="angle-panel-img" style="
                  transform: rotate(${a.angle === "top" ? "0deg" : a.angle === "0deg" ? "0deg" : a.angle === "90deg" ? "90deg" : "270deg"});
                  filter: hue-rotate(${i * 20}deg) saturate(1.1);
                "/>
              </div>
              <div class="angle-label">${a.label}</div>
            </div>
          `,
          ).join("")}
        </div>
      </div>
    </div>
  `;
}

export function buildReportHtml(r: any, leftImage: string, rightImage: string) {
  // Export the same location-only result shown in the app.
  const escape = (value: unknown) => String(value ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c] || c));
  return `<!doctype html><html><head><meta charset="utf-8"><style>
    body{font:14px Arial;color:#231b35;padding:24px}h1{color:#7c3aed}
    section{break-inside:avoid;margin:24px 0}img{width:260px;height:260px;object-fit:contain}
    </style></head><body><h1>DMAS-CF localization</h1>
    <p>${escape(r.label)} · ${escape(r.created_at)}</p>
    <p>Dots show reconstructed locations. Both views share one physical capture.</p>
    ${(["left", "right"] as const).filter(side => r[side]).map(side => {
      const result = r[side]; const peak = result.peak_location_cm;
      const image = side === "left" ? leftImage : rightImage;
      return `<section><h2>${side === "left" ? "Left" : "Right"} view</h2>
        <p>Status: ${escape(result.display_mode === "localization" ? result.status : "Legacy scan — capture a new DMAS-CF scan")}</p>
        <p>Displayed locations: ${escape(result.dot_count ?? 0)}</p>
        ${peak ? `<p>Peak (cm): x ${escape(peak.x)}, y ${escape(peak.y)}, z ${escape(peak.z)}</p>` : ""}
        ${image ? `<img src="${escape(image)}" />` : ""}</section>`;
    }).join("")}</body></html>`;
}

function buildLegacyReportHtml(r: any, leftImage: string, rightImage: string) {
  const m = r.metrics;
  const cfg = r.config_snapshot;
  const now = new Date(r.created_at);

  const hasLeft = r.left != null;
  const hasRight = r.right != null;

  if (!hasLeft || !hasRight) {
    const sideImage = hasLeft ? leftImage : rightImage;
    return buildSingleSideReportHtml(r, sideImage);
  }

  // --- Both sides present — generate full bilateral report ---

  const dateStr = now.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  });
  const timeStr = now.toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
  });

  const verdictColor =
    m.verdict === "healthy"
      ? "#57CDB2"
      : m.verdict === "monitor"
        ? "#FFB65C"
        : "#FF7B93";

  const metricRow = (label: string, left: any, right: any, unit = "") =>
    `<tr>
      <td class="metric-label">${label}</td>
      <td class="metric-val">${left}${unit}</td>
      <td class="metric-val">${right}${unit}</td>
    </tr>`;

  const riskRow = (level: string, color: string, left: any, right: any) =>
    `<tr>
      <td><span class="risk-badge" style="background:${color}20;color:${color};border:1px solid ${color}40">${level}</span></td>
      <td class="metric-val">${left}</td>
      <td class="metric-val">${right}</td>
    </tr>`;

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Ovula ✿ Breast Health Report — ${dateStr}</title>
  <style>
    @page { size: A4; margin: 14mm 16mm; }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    html { width: 210mm; font-family: -apple-system, Helvetica Neue, Arial, sans-serif; }
    body { color: #1A1028; background: #ffffff; padding: 0; font-size: 12px; }

    /* ── Cover Header ── */
    .cover-header {
      display: flex; justify-content: space-between; align-items: flex-start;
      padding: 20px 0 16px; border-bottom: 2.5px solid #F0559E; margin-bottom: 20px;
    }
    .brand { display: flex; flex-direction: column; gap: 3px; }
    .brand-logo { font-size: 26px; font-weight: 900; color: #F0559E; letter-spacing: -0.5px; }
    .brand-sub { font-size: 11px; color: #9B72E8; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase; }
    .report-meta { text-align: right; color: #7A6B85; font-size: 11px; line-height: 1.7; }
    .report-meta strong { color: #2B1E33; }

    /* ── Score Hero ── */
    .score-hero {
      display: flex; gap: 20px; align-items: stretch;
      background: linear-gradient(135deg, #FFF3F8, #F3ECFF);
      border-radius: 16px; padding: 20px 24px; margin-bottom: 20px;
      border: 1px solid #F6E2ED;
    }
    .score-block { display: flex; flex-direction: column; align-items: center; justify-content: center; min-width: 110px; }
    .score-label { font-size: 10px; font-weight: 700; color: #7A6B85; letter-spacing: 1.2px; text-transform: uppercase; margin-bottom: 4px; }
    .score-num { font-size: 64px; font-weight: 900; color: #2B1E33; line-height: 1; }
    .score-denom { font-size: 14px; color: #7A6B85; font-weight: 600; margin-top: 4px; }
    .verdict-pill {
      display: inline-block; padding: 8px 20px; border-radius: 999px;
      font-weight: 800; font-size: 14px; color: #fff; margin-top: 10px;
      background: ${verdictColor};
    }
    .score-divider { width: 1px; background: #F6E2ED; margin: 0 4px; }
    .score-side-metrics { flex: 1; display: flex; flex-direction: column; justify-content: center; gap: 8px; }
    .side-row { display: flex; align-items: center; gap: 12px; padding: 10px 14px; border-radius: 12px; background: rgba(255,255,255,0.7); }
    .side-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
    .side-name { font-size: 11px; font-weight: 700; color: #7A6B85; width: 50px; }
    .side-score { font-size: 22px; font-weight: 900; color: #2B1E33; }
    .side-deviation { font-size: 11px; color: #7A6B85; margin-left: 4px; }
    .asym-row { display: flex; align-items: center; gap: 8px; padding: 8px 14px; border-radius: 12px; background: rgba(255,255,255,0.7); margin-top: 4px; }
    .asym-label { font-size: 11px; color: #7A6B85; font-weight: 600; }
    .asym-val { font-size: 16px; font-weight: 800; color: ${m.left_right?.asymmetry > 15 ? "#ba1a1a" : m.left_right?.asymmetry > 8 ? "#FFB65C" : "#57CDB2"}; }

    /* ── Section Titles ── */
    .section-title {
      font-size: 15px; font-weight: 800; color: #2B1E33;
      letter-spacing: -0.3px; margin: 22px 0 12px;
      padding-bottom: 6px; border-bottom: 1.5px solid #F6E2ED;
      display: flex; align-items: center; gap: 8px;
    }
    .section-pill { display: inline-block; background: #F0559E1A; color: #F0559E; font-size: 9px; font-weight: 800; letter-spacing: 1.2px; text-transform: uppercase; padding: 2px 10px; border-radius: 999px; }

    /* ── Dome Section ── */
    .dome-section { margin-bottom: 28px; page-break-inside: avoid; }
    .simple-image-container { display: flex; justify-content: center; align-items: center; margin: 20px 0; }
    .simple-image-wrap { max-width: 500px; width: 100%; border: 2px solid #F6E2ED; border-radius: 16px; overflow: hidden; background: #ffffff; padding: 10px; }
    .simple-image-img { width: 100%; height: auto; display: block; border-radius: 8px; }
    .dome-section-header { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
    .dome-section-dot { width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; }
    .dome-section-title { font-size: 14px; font-weight: 800; color: #2B1E33; flex: 1; }
    .dome-section-score { font-size: 12px; font-weight: 700; color: #7A6B85; background: #FFF3F8; padding: 4px 12px; border-radius: 999px; border: 1px solid #F6E2ED; }

    /* ── Quadrant Grid ── */
    .quadrant-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 14px; }
    .quadrant-card { border: 1px solid #F6E2ED; border-radius: 14px; overflow: hidden; background: #fff; }
    .quadrant-header { display: flex; align-items: center; gap: 8px; padding: 8px 12px; background: #FFF3F8; border-bottom: 1px solid #F6E2ED; }
    .quadrant-abbr { font-size: 11px; font-weight: 900; letter-spacing: 0.5px; }
    .quadrant-label { font-size: 10px; font-weight: 700; color: #2B1E33; }
    .quadrant-img-wrap { position: relative; width: 100%; height: 140px; overflow: hidden; background: #0D111A; }
    .quadrant-img { width: 200%; height: 200%; object-fit: contain; position: absolute; }
    .quadrant-overlay { position: absolute; inset: 0; pointer-events: none; }
    .quadrant-crosshair-h { position: absolute; top: 50%; left: 0; right: 0; height: 1px; background: rgba(240,85,158,0.3); }
    .quadrant-crosshair-v { position: absolute; left: 50%; top: 0; bottom: 0; width: 1px; background: rgba(240,85,158,0.3); }
    .quadrant-focus { position: absolute; width: 24px; height: 24px; border: 2px solid #F0559E; border-radius: 50%; transform: translate(-50%,-50%); }
    .quadrant-angle-label { font-size: 9px; font-weight: 700; color: #F0559E; text-transform: uppercase; letter-spacing: 0.8px; padding: 4px 10px 0; }
    .quadrant-desc { font-size: 9px; color: #9B8FA5; padding: 2px 10px 8px; }

    /* ── Angle Strip ── */
    .angle-strip { background: #0D111A; border-radius: 14px; padding: 12px 14px; }
    .angle-strip-title { color: #FF9FCB; font-size: 10px; font-weight: 800; letter-spacing: 1.5px; text-transform: uppercase; margin-bottom: 10px; }
    .angle-strip-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
    .angle-panel { display: flex; flex-direction: column; align-items: center; gap: 6px; }
    .angle-panel-img-wrap { width: 70px; height: 70px; border-radius: 10px; overflow: hidden; border: 1px solid rgba(240,85,158,0.25); background: #1e2536; display: flex; align-items: center; justify-content: center; }
    .angle-panel-img { width: 90px; height: 90px; object-fit: contain; }
    .angle-label { font-size: 8px; color: #B3A3BE; font-weight: 700; text-align: center; letter-spacing: 0.4px; }

    /* ── Tables ── */
    .data-table { width: 100%; border-collapse: collapse; margin-bottom: 16px; border-radius: 12px; overflow: hidden; }
    .data-table thead tr { background: linear-gradient(90deg, #F0559E08, #9B72E808); }
    .data-table th { padding: 10px 12px; font-size: 10px; font-weight: 800; color: #F0559E; text-align: left; letter-spacing: 0.8px; text-transform: uppercase; border-bottom: 1.5px solid #F6E2ED; }
    .data-table td { padding: 9px 12px; font-size: 12px; border-bottom: 1px solid #F6E2ED; }
    .data-table tr:last-child td { border-bottom: none; }
    .data-table tr:nth-child(even) td { background: #FFF3F808; }
    .metric-label { color: #5A4B6A; font-weight: 600; }
    .metric-val { color: #2B1E33; font-weight: 700; font-size: 13px; }
    .risk-badge { display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 10px; font-weight: 800; letter-spacing: 0.5px; }

    /* ── Config Card ── */
    .config-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 20px; }
    .config-card { background: #FFF3F8; border: 1px solid #F6E2ED; border-radius: 12px; padding: 12px 14px; }
    .config-card-label { font-size: 9px; font-weight: 700; color: #7A6B85; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 4px; }
    .config-card-val { font-size: 14px; font-weight: 800; color: #2B1E33; }

    /* ── Recommendations ── */
    .rec-list { display: flex; flex-direction: column; gap: 8px; margin-bottom: 20px; }
    .rec-item { display: flex; gap: 10px; align-items: flex-start; background: #FFF3F8; border: 1px solid #F6E2ED; border-radius: 12px; padding: 10px 14px; }
    .rec-icon { color: #F0559E; font-size: 14px; flex-shrink: 0; margin-top: 1px; }
    .rec-text { font-size: 12px; color: #2B1E33; line-height: 1.6; }

    /* ── Footer ── */
    .report-footer { border-top: 1.5px solid #F6E2ED; padding-top: 14px; margin-top: 28px; }
    .footer-brand { font-size: 11px; font-weight: 800; color: #F0559E; margin-bottom: 4px; }
    .footer-disclaimer { font-size: 9.5px; color: #B3A3BE; line-height: 1.6; }
    .footer-row { display: flex; justify-content: space-between; align-items: flex-start; gap: 20px; }
    .footer-qr { width: 48px; height: 48px; background: #F6E2ED; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 8px; color: #9B8FA5; text-align: center; flex-shrink: 0; }

    /* ── Page Break ── */
    .page-break { page-break-before: always; padding-top: 10px; }
  </style>
</head>
<body>

  <!-- ═══ COVER HEADER ═══ -->
  <div class="cover-header">
    <div class="brand">
      <div class="brand-logo">ovula ✿</div>
      <div class="brand-sub">Breast Health Report · Naibra Thermal Patch</div>
    </div>
    <div class="report-meta">
      <strong>Scan ID:</strong> ${r.id ?? "SC-" + Math.floor(Math.random() * 90000 + 10000)}<br/>
      <strong>Date:</strong> ${dateStr}<br/>
      <strong>Time:</strong> ${timeStr}<br/>
      <strong>Label:</strong> ${r.label ?? "Routine Scan"}<br/>
      <strong>Session:</strong> ${m.past_vs_current ? "Follow-up" : "Baseline"}
    </div>
  </div>

  <!-- ═══ SCORE HERO ═══ -->
  <div class="score-hero">
    <div class="score-block">
      <div class="score-label">Overall Score</div>
      <div class="score-num">${m.overall_score}</div>
      <div class="score-denom">out of 100</div>
      <div class="verdict-pill">${m.verdict_label}</div>
    </div>
    <div class="score-divider"></div>
    <div class="score-side-metrics">
      <div class="side-row">
        <div class="side-dot" style="background:#F0559E"></div>
        <div class="side-name">Left</div>
        <div class="side-score">${r.left.score}</div>
        <div class="side-deviation">Dev: ${m.standard_vs_current.left_deviation_pct}% from std</div>
      </div>
      <div class="side-row">
        <div class="side-dot" style="background:#9B72E8"></div>
        <div class="side-name">Right</div>
        <div class="side-score">${r.right.score}</div>
        <div class="side-deviation">Dev: ${m.standard_vs_current.right_deviation_pct}% from std</div>
      </div>
      <div class="asym-row">
        <div class="asym-label">Left–Right Asymmetry Index</div>
        <div class="asym-val">Δ ${m.left_right.asymmetry} pts</div>
      </div>
      <div class="asym-row">
        <div class="asym-label">Standard Profile Ref</div>
        <div class="asym-val" style="color:#9B72E8; font-size:13px">${m.standard_vs_current.standard}</div>
      </div>
    </div>
  </div>

  <!-- ═══ BREAST DOME ANALYSIS ═══ -->
  <div class="section-title">
    <span class="section-pill">Bilateral View</span>
    Bilateral Thermal Maps — Left & Right Breasts
  </div>

  <!--
  ${buildDomePanelGridHtml("Left", r.left.score, leftImage)}
  ${buildDomePanelGridHtml("Right", r.right.score, rightImage)}
  -->
  <div class="simple-image-container" style="display: flex; gap: 20px; justify-content: center; align-items: center;">
    <div class="simple-image-wrap" style="flex: 1; max-width: 320px;">
      <div style="font-size: 11px; font-weight: 700; color: #FFF; background: #F0559E; padding: 4px 8px; text-align: center; border-radius: 6px; margin-bottom: 8px; letter-spacing: 0.5px;">LEFT BREAST</div>
      <img src="${leftImage}" class="simple-image-img" />
    </div>
    <div class="simple-image-wrap" style="flex: 1; max-width: 320px;">
      <div style="font-size: 11px; font-weight: 700; color: #FFF; background: #9B72E8; padding: 4px 8px; text-align: center; border-radius: 6px; margin-bottom: 8px; letter-spacing: 0.5px;">RIGHT BREAST</div>
      <img src="${rightImage}" class="simple-image-img" />
    </div>
  </div>

  <!-- ═══ METRICS TABLE ═══ -->
  <div class="page-break">
    <div class="section-title"><span class="section-pill">Metrics</span> Detailed Scan Metrics</div>
    <table class="data-table">
      <thead><tr><th>Metric</th><th>Left Breast</th><th>Right Breast</th></tr></thead>
      <tbody>
        ${metricRow("Thermal Score", r.left.score, r.right.score)}
        ${metricRow("Deviation from Standard Profile (" + m.standard_vs_current.standard + ")", m.standard_vs_current.left_deviation_pct, m.standard_vs_current.right_deviation_pct, "%")}
      </tbody>
    </table>

    <div class="section-title" style="margin-top:16px"><span class="section-pill">Risk</span> Risk Point Distribution</div>
    <table class="data-table">
      <thead><tr><th>Severity</th><th>Left Breast</th><th>Right Breast</th></tr></thead>
      <tbody>
        ${riskRow("HIGH RISK", "#FF3D64", r.left.dot_counts.high, r.right.dot_counts.high)}
        ${riskRow("MEDIUM", "#FFA531", r.left.dot_counts.medium, r.right.dot_counts.medium)}
        ${riskRow("LOW", "#3FC98A", r.left.dot_counts.low, r.right.dot_counts.low)}
        ${riskRow("BASELINE", "#7FA9F0", r.left.dot_counts.baseline, r.right.dot_counts.baseline)}
      </tbody>
    </table>

    <div class="section-title" style="margin-top:16px"><span class="section-pill">Comparison</span> Temporal & Bilateral Comparison</div>
    <table class="data-table">
      <thead><tr><th>Comparison Type</th><th>Result</th></tr></thead>
      <tbody>
        <tr>
          <td class="metric-label">Left vs Right Asymmetry</td>
          <td class="metric-val">Δ ${m.left_right.asymmetry} pts${m.left_right.asymmetry > 15 ? " ⚠️ Elevated" : m.left_right.asymmetry > 8 ? " · Monitor" : " · Within range"}</td>
        </tr>
        <tr>
          <td class="metric-label">Past vs Current Score</td>
          <td class="metric-val">${
            m.past_vs_current
              ? `${m.past_vs_current.prev_overall} → ${m.overall_score} (${m.past_vs_current.delta >= 0 ? "+" : ""}${m.past_vs_current.delta} pts)`
              : "Baseline scan — no prior data"
          }</td>
        </tr>
        <tr>
          <td class="metric-label">Standard Profile Reference</td>
          <td class="metric-val">${m.standard_vs_current.standard}</td>
        </tr>
      </tbody>
    </table>

    <!-- ═══ PATCH CONFIGURATION ═══ -->
    <div class="section-title" style="margin-top:16px"><span class="section-pill">Hardware</span> Naibra Patch Configuration</div>
    <div class="config-grid">
      <div class="config-card">
        <div class="config-card-label">Prong Count</div>
        <div class="config-card-val">${cfg.num_prongs} prongs</div>
      </div>
      <div class="config-card">
        <div class="config-card-label">Antennas / Prong</div>
        <div class="config-card-val">${cfg.antennas_per_prong} antennas</div>
      </div>
      <div class="config-card">
        <div class="config-card-label">Total Channels</div>
        <div class="config-card-val">${cfg.num_prongs * cfg.antennas_per_prong} total</div>
      </div>
      <div class="config-card">
        <div class="config-card-label">Frequency Range</div>
        <div class="config-card-val">${cfg.freq_start_mhz / 1000}–${cfg.freq_stop_mhz / 1000} GHz</div>
      </div>
      <div class="config-card">
        <div class="config-card-label">Sweep Points</div>
        <div class="config-card-val">${cfg.sweep_points} pts</div>
      </div>
      <div class="config-card">
        <div class="config-card-label">Scan Duration</div>
        <div class="config-card-val">60 seconds</div>
      </div>
    </div>

    <!-- ═══ RECOMMENDATIONS ═══ -->
    <div class="section-title"><span class="section-pill">Actions</span> Recommended Clinical Actions</div>
    <div class="rec-list">
      ${m.recommendations
        .map(
          (rec: string) => `
        <div class="rec-item">
          <div class="rec-icon">✿</div>
          <div class="rec-text">${rec}</div>
        </div>
      `,
        )
        .join("")}
    </div>

    <!-- ═══ FOOTER ═══ -->
    <div class="report-footer">
      <div class="footer-row">
        <div>
          <div class="footer-brand">ovula ✿ · Brela Innovations</div>
          <div class="footer-disclaimer">
            This report is generated by Ovula for use with the Naibra Breast Thermal Patch.<br/>
            <strong>It is a screening companion tool, NOT a clinical diagnosis.</strong>
            Any abnormal findings should be reviewed by a qualified healthcare professional.<br/>
            Report generated: ${dateStr} at ${timeStr} · Ovula v2.0 · Naibra Patch ${cfg.num_prongs}P/${cfg.antennas_per_prong}A
          </div>
        </div>
        <div class="footer-qr">QR<br/>Code</div>
      </div>
    </div>
  </div>

</body>
</html>`;
}

export function buildSimpleImagesReportHtml(
  leftImage: string,
  rightImage: string,
) {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Simple Breast Dome Images</title>
  <style>
    @page { size: A4; margin: 10mm; }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, sans-serif; text-align: center; background: #ffffff; color: #1A1028; }
    .page { page-break-after: always; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; padding: 20px; }
    .page:last-child { page-break-after: avoid; }
    h1 { font-size: 24px; font-weight: 700; margin-bottom: 20px; color: #F0559E; }
    .img-container { width: 100%; max-width: 500px; border: 2px solid #F6E2ED; border-radius: 16px; overflow: hidden; background: #ffffff; padding: 10px; }
    img { width: 100%; height: auto; display: block; border-radius: 8px; }
  </style>
</head>
<body>
  <div class="page">
    <h1>Left Breast Dome View</h1>
    <div class="img-container">
      <img src="${leftImage}" />
    </div>
  </div>
  <div class="page">
    <h1>Right Breast Dome View</h1>
    <div class="img-container">
      <img src="${rightImage}" />
    </div>
  </div>
</body>
</html>`;
}

export function buildSingleSideReportHtml(r: any, sideImage: string) {
  const side = r.scanned_side === "right" ? "Right" : "Left";
  const sideData = r.scanned_side === "right" ? r.right : r.left;
  const sideColor = side === "Left" ? "#F0559E" : "#9B72E8";
  const cfg = r.config_snapshot;
  const now = new Date(r.created_at);
  const dateStr = now.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  });
  const timeStr = now.toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
  });

  const verdict =
    sideData.score >= 75
      ? { label: "Healthy Range", color: "#57CDB2" }
      : sideData.score >= 50
        ? { label: "Monitor", color: "#FFB65C" }
        : { label: "Needs Review", color: "#FF7B93" };

  const metricRow = (label: string, val: any, unit = "") =>
    `<tr><td class="metric-label">${label}</td><td class="metric-val">${val}${unit}</td></tr>`;

  const riskRow = (level: string, color: string, val: any) =>
    `<tr>
      <td><span class="risk-badge" style="background:${color}20;color:${color};border:1px solid ${color}40">${level}</span></td>
      <td class="metric-val">${val}</td>
    </tr>`;

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Ovula ✿ Breast Health Report — ${dateStr}</title>
  <style>
    @page { size: A4; margin: 14mm 16mm; }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    html { width: 210mm; font-family: -apple-system, Helvetica Neue, Arial, sans-serif; }
    body { color: #1A1028; background: #ffffff; padding: 0; font-size: 12px; }

    .cover-header { display: flex; justify-content: space-between; align-items: flex-start; padding: 20px 0 16px; border-bottom: 2.5px solid ${sideColor}; margin-bottom: 20px; }
    .brand { display: flex; flex-direction: column; gap: 3px; }
    .brand-logo { font-size: 26px; font-weight: 900; color: #F0559E; letter-spacing: -0.5px; }
    .brand-sub { font-size: 11px; color: #9B72E8; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase; }
    .report-meta { text-align: right; color: #7A6B85; font-size: 11px; line-height: 1.7; }
    .report-meta strong { color: #2B1E33; }

    .single-side-banner { display: flex; align-items: center; gap: 8px; background: ${sideColor}12; border: 1px solid ${sideColor}30; border-radius: 10px; padding: 8px 14px; margin-bottom: 16px; font-size: 11px; font-weight: 700; color: ${sideColor}; }

    .score-hero { display: flex; gap: 20px; align-items: stretch; background: linear-gradient(135deg, #FFF3F8, #F3ECFF); border-radius: 16px; padding: 20px 24px; margin-bottom: 20px; border: 1px solid #F6E2ED; }
    .score-block { display: flex; flex-direction: column; align-items: center; justify-content: center; min-width: 110px; }
    .score-label { font-size: 10px; font-weight: 700; color: #7A6B85; letter-spacing: 1.2px; text-transform: uppercase; margin-bottom: 4px; }
    .score-num { font-size: 64px; font-weight: 900; color: #2B1E33; line-height: 1; }
    .score-denom { font-size: 14px; color: #7A6B85; font-weight: 600; margin-top: 4px; }
    .verdict-pill { display: inline-block; padding: 8px 20px; border-radius: 999px; font-weight: 800; font-size: 14px; color: #fff; margin-top: 10px; background: ${verdict.color}; }
    .score-divider { width: 1px; background: #F6E2ED; margin: 0 4px; }
    .score-side-metrics { flex: 1; display: flex; flex-direction: column; justify-content: center; gap: 8px; }
    .side-row { display: flex; align-items: center; gap: 12px; padding: 10px 14px; border-radius: 12px; background: rgba(255,255,255,0.7); }
    .side-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
    .side-name { font-size: 11px; font-weight: 700; color: #7A6B85; width: 90px; }
    .side-score { font-size: 22px; font-weight: 900; color: #2B1E33; }
    .info-note { font-size: 10.5px; color: #9B72E8; font-weight: 600; padding: 8px 14px; background: rgba(255,255,255,0.6); border-radius: 10px; }

    .section-title { font-size: 15px; font-weight: 800; color: #2B1E33; letter-spacing: -0.3px; margin: 22px 0 12px; padding-bottom: 6px; border-bottom: 1.5px solid #F6E2ED; display: flex; align-items: center; gap: 8px; }
    .section-pill { display: inline-block; background: #F0559E1A; color: #F0559E; font-size: 9px; font-weight: 800; letter-spacing: 1.2px; text-transform: uppercase; padding: 2px 10px; border-radius: 999px; }

    .simple-image-container { display: flex; justify-content: center; align-items: center; margin: 20px 0; }
    .simple-image-wrap { max-width: 380px; width: 100%; border: 2px solid #F6E2ED; border-radius: 16px; overflow: hidden; background: #ffffff; padding: 10px; }
    .simple-image-img { width: 100%; height: auto; display: block; border-radius: 8px; }

    .data-table { width: 100%; border-collapse: collapse; margin-bottom: 16px; border-radius: 12px; overflow: hidden; }
    .data-table thead tr { background: linear-gradient(90deg, #F0559E08, #9B72E808); }
    .data-table th { padding: 10px 12px; font-size: 10px; font-weight: 800; color: #F0559E; text-align: left; letter-spacing: 0.8px; text-transform: uppercase; border-bottom: 1.5px solid #F6E2ED; }
    .data-table td { padding: 9px 12px; font-size: 12px; border-bottom: 1px solid #F6E2ED; }
    .data-table tr:last-child td { border-bottom: none; }
    .metric-label { color: #5A4B6A; font-weight: 600; }
    .metric-val { color: #2B1E33; font-weight: 700; font-size: 13px; }
    .risk-badge { display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 10px; font-weight: 800; letter-spacing: 0.5px; }

    .config-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 20px; }
    .config-card { background: #FFF3F8; border: 1px solid #F6E2ED; border-radius: 12px; padding: 12px 14px; }
    .config-card-label { font-size: 9px; font-weight: 700; color: #7A6B85; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 4px; }
    .config-card-val { font-size: 14px; font-weight: 800; color: #2B1E33; }

    .rec-list { display: flex; flex-direction: column; gap: 8px; margin-bottom: 20px; }
    .rec-item { display: flex; gap: 10px; align-items: flex-start; background: #FFF3F8; border: 1px solid #F6E2ED; border-radius: 12px; padding: 10px 14px; }
    .rec-icon { color: #F0559E; font-size: 14px; flex-shrink: 0; margin-top: 1px; }
    .rec-text { font-size: 12px; color: #2B1E33; line-height: 1.6; }

    .report-footer { border-top: 1.5px solid #F6E2ED; padding-top: 14px; margin-top: 28px; }
    .footer-brand { font-size: 11px; font-weight: 800; color: #F0559E; margin-bottom: 4px; }
    .footer-disclaimer { font-size: 9.5px; color: #B3A3BE; line-height: 1.6; }
    .footer-row { display: flex; justify-content: space-between; align-items: flex-start; gap: 20px; }
    .footer-qr { width: 48px; height: 48px; background: #F6E2ED; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 8px; color: #9B8FA5; text-align: center; flex-shrink: 0; }
  </style>
</head>
<body>

  <div class="cover-header">
    <div class="brand">
      <div class="brand-logo">ovula ✿</div>
      <div class="brand-sub">Breast Health Report · Naibra Thermal Patch</div>
    </div>
    <div class="report-meta">
      <strong>Scan ID:</strong> ${r.id ?? "SC-" + Math.floor(Math.random() * 90000 + 10000)}<br/>
      <strong>Date:</strong> ${dateStr}<br/>
      <strong>Time:</strong> ${timeStr}<br/>
      <strong>Label:</strong> ${r.label ?? "Routine Scan"}<br/>
      <strong>Scan Type:</strong> Single-side
    </div>
  </div>

  <div class="single-side-banner">
    ⚠ Only the ${side.toUpperCase()} side was scanned in this session — no bilateral comparison available.
  </div>

  <div class="score-hero">
    <div class="score-block">
      <div class="score-label">${side} Score</div>
      <div class="score-num">${sideData.score}</div>
      <div class="score-denom">out of 100</div>
      <div class="verdict-pill">${verdict.label}</div>
    </div>
    <div class="score-divider"></div>
    <div class="score-side-metrics">
      <div class="side-row">
        <div class="side-dot" style="background:${sideColor}"></div>
        <div class="side-name">${side} Breast</div>
        <div class="side-score">${sideData.score}</div>
      </div>
      <div class="info-note">Mean severity: ${sideData.mean_severity} · Max severity: ${sideData.max_severity} · Anomalies: ${sideData.anomaly_count}</div>
    </div>
  </div>

  <div class="section-title">
    <span class="section-pill">Single View</span>
    ${side} Breast — Thermal Map
  </div>
  <div class="simple-image-container">
    <div class="simple-image-wrap">
      <div style="font-size: 11px; font-weight: 700; color: #FFF; background: ${sideColor}; padding: 4px 8px; text-align: center; border-radius: 6px; margin-bottom: 8px; letter-spacing: 0.5px;">${side.toUpperCase()} BREAST</div>
      <img src="${sideImage}" class="simple-image-img" />
    </div>
  </div>

  <div class="section-title"><span class="section-pill">Metrics</span> Scan Metrics</div>
  <table class="data-table">
    <thead><tr><th>Metric</th><th>${side} Breast</th></tr></thead>
    <tbody>
      ${metricRow("Thermal Score", sideData.score)}
      ${metricRow("Mean Severity", sideData.mean_severity)}
      ${metricRow("Max Severity", sideData.max_severity)}
      ${metricRow("Anomaly Count", sideData.anomaly_count)}
    </tbody>
  </table>

  <div class="section-title" style="margin-top:16px"><span class="section-pill">Risk</span> Risk Point Distribution</div>
  <table class="data-table">
    <thead><tr><th>Severity</th><th>${side} Breast</th></tr></thead>
    <tbody>
      ${riskRow("HIGH RISK", "#FF3D64", sideData.dot_counts.high)}
      ${riskRow("MEDIUM", "#FFA531", sideData.dot_counts.medium)}
      ${riskRow("LOW", "#3FC98A", sideData.dot_counts.low)}
      ${riskRow("BASELINE", "#7FA9F0", sideData.dot_counts.baseline)}
    </tbody>
  </table>

  <div class="section-title" style="margin-top:16px"><span class="section-pill">Hardware</span> Naibra Patch Configuration</div>
  <div class="config-grid">
    <div class="config-card">
      <div class="config-card-label">Prong Count</div>
      <div class="config-card-val">${cfg.num_prongs} prongs</div>
    </div>
    <div class="config-card">
      <div class="config-card-label">Antennas / Prong</div>
      <div class="config-card-val">${cfg.antennas_per_prong} antennas</div>
    </div>
    <div class="config-card">
      <div class="config-card-label">Total Channels</div>
      <div class="config-card-val">${cfg.num_prongs * cfg.antennas_per_prong} total</div>
    </div>
    <div class="config-card">
      <div class="config-card-label">Frequency Range</div>
      <div class="config-card-val">${cfg.freq_start_mhz / 1000}–${cfg.freq_stop_mhz / 1000} GHz</div>
    </div>
    <div class="config-card">
      <div class="config-card-label">Sweep Points</div>
      <div class="config-card-val">${cfg.sweep_points} pts</div>
    </div>
    <div class="config-card">
      <div class="config-card-label">Connection Mode</div>
      <div class="config-card-val">${cfg.connection_mode}</div>
    </div>
  </div>

  <div class="section-title"><span class="section-pill">Note</span> Recommendation</div>
  <div class="rec-list">
    <div class="rec-item">
      <div class="rec-icon">✿</div>
      <div class="rec-text">This session only scanned the ${side.toLowerCase()} side. For a complete bilateral asymmetry comparison, run a full scan of both sides in your next session.</div>
    </div>
  </div>

  <div class="report-footer">
    <div class="footer-row">
      <div>
        <div class="footer-brand">ovula ✿ · Brela Innovations</div>
        <div class="footer-disclaimer">
          This report is generated by Ovula for use with the Naibra Breast Thermal Patch.<br/>
          <strong>It is a screening companion tool, NOT a clinical diagnosis.</strong>
          Any abnormal findings should be reviewed by a qualified healthcare professional.<br/>
          Report generated: ${dateStr} at ${timeStr} · Ovula v2.0 · Naibra Patch ${cfg.num_prongs}P/${cfg.antennas_per_prong}A
        </div>
      </div>
      <div class="footer-qr">QR<br/>Code</div>
    </div>
  </div>

</body>
</html>`;
}
