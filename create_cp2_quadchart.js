const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const {
  FaCheckCircle, FaExclamationTriangle, FaBrain,
  FaArrowRight, FaCalendarAlt
} = require("react-icons/fa");

// ── Icon helpers ─────────────────────────────────────────────────────────
function renderIconSvg(IconComponent, color, size = 256) {
  return ReactDOMServer.renderToStaticMarkup(
    React.createElement(IconComponent, { color, size: String(size) })
  );
}

async function iconToBase64Png(IconComponent, color, size = 256) {
  const svg = renderIconSvg(IconComponent, color, size);
  const pngBuffer = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + pngBuffer.toString("base64");
}

// ── ASU / Synapse palette ────────────────────────────────────────────────
const MAROON = "8C1D40";
const GOLD = "FFC627";
const DARK_BG = "2D2D2D";
const WHITE = "FFFFFF";
const LIGHT_BG = "F8F8F8";
const GREEN = "2E7D32";
const RED = "C62828";
const ORANGE = "E65100";
const BLUE = "1565C0";
const GRAY = "666666";
const LIGHT_GRAY = "E0E0E0";
const TEXT_DARK = "212121";

async function main() {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE"; // 13.3" x 7.5"
  pres.author = "Team Alabama";
  pres.title = "Synapse AI - Checkpoint 2 Quad Chart";

  const slide = pres.addSlide();
  slide.background = { color: LIGHT_BG };

  // Pre-render icons
  const checkIcon = await iconToBase64Png(FaCheckCircle, "#2E7D32", 256);
  const warnIcon = await iconToBase64Png(FaExclamationTriangle, "#C62828", 256);
  const brainIcon = await iconToBase64Png(FaBrain, "#FFC627", 256);
  const arrowIcon = await iconToBase64Png(FaArrowRight, "#FFFFFF", 256);
  const calIcon = await iconToBase64Png(FaCalendarAlt, "#FFFFFF", 256);

  // ═══════════════════════════════════════════════════════════════════════
  // HEADER BAR
  // ═══════════════════════════════════════════════════════════════════════
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 13.3, h: 0.95,
    fill: { color: MAROON }
  });

  // Brain icon
  slide.addImage({ data: brainIcon, x: 0.4, y: 0.17, w: 0.6, h: 0.6 });

  // Synapse AI title
  slide.addText([
    { text: "Synapse AI", options: { bold: true, color: GOLD, fontSize: 28, fontFace: "Arial Black" } }
  ], { x: 1.1, y: 0.15, w: 3, h: 0.65, margin: 0 });

  // Checkpoint title
  slide.addText("Checkpoint 2 Quad Chart", {
    x: 4.2, y: 0.15, w: 4.5, h: 0.65,
    color: WHITE, fontSize: 22, fontFace: "Arial", bold: false, margin: 0
  });

  // Subtitle
  slide.addText("Neuro-Symbolic Clinical Decision Support", {
    x: 8.8, y: 0.15, w: 4.2, h: 0.65,
    color: GOLD, fontSize: 13, fontFace: "Arial", italic: true, align: "right", margin: 0
  });

  // ═══════════════════════════════════════════════════════════════════════
  // QUADRANT LAYOUT  (2x2 grid)
  // ═══════════════════════════════════════════════════════════════════════
  const Q_TOP = 1.15;
  const Q_MID = 4.1;
  const Q_LEFT = 0.3;
  const Q_RIGHT = 6.85;
  const Q_W = 6.25;
  const Q_H_TOP = 2.75;
  const Q_H_BOT = 2.95;

  // Vertical divider
  slide.addShape(pres.shapes.LINE, {
    x: 6.65, y: 1.05, w: 0, h: 5.95,
    line: { color: BLUE, width: 2.5 }
  });

  // Horizontal divider
  slide.addShape(pres.shapes.LINE, {
    x: 0.3, y: 3.98, w: 12.7, h: 0,
    line: { color: BLUE, width: 2.5 }
  });

  // ═══════════════════════════════════════════════════════════════════════
  // Q1: ACCOMPLISHMENTS (top-left)
  // ═══════════════════════════════════════════════════════════════════════

  // Green accent bar
  slide.addShape(pres.shapes.RECTANGLE, {
    x: Q_LEFT, y: Q_TOP, w: 0.06, h: Q_H_TOP,
    fill: { color: GREEN }
  });

  // Section icon + title
  slide.addImage({ data: checkIcon, x: Q_LEFT + 0.2, y: Q_TOP + 0.05, w: 0.3, h: 0.3 });
  slide.addText("ACCOMPLISHMENTS (KPIs)", {
    x: Q_LEFT + 0.6, y: Q_TOP, w: 5, h: 0.4,
    color: GREEN, fontSize: 18, fontFace: "Arial", bold: true, margin: 0
  });

  const accomplishments = [
    { title: "MIMIC + Neo4j Validation Complete", desc: "MIMIC-IV schema aligned with Neo4j graph nodes; patient context retrieval verified" },
    { title: "Vision-Text Integration Complete", desc: "MedGemma 27B on Vertex AI + BiomedCLIP; image captions fused with clinical text context" },
    { title: "SOAP Note Generator Deployed", desc: "Patient context + vitals history → structured SOAP notes via streaming LLM pipeline" },
    { title: "Drug Safety Pipeline Operational", desc: "Neo4j graph traversal: interactions, contraindications, QT prolongation, Beers criteria" },
    { title: "Full-Stack Application Deployed", desc: "Next.js App Router + FastAPI; clinician dashboard, patient portal, SSE streaming" },
  ];

  let accY = Q_TOP + 0.48;
  for (const item of accomplishments) {
    slide.addImage({ data: checkIcon, x: Q_LEFT + 0.2, y: accY + 0.02, w: 0.2, h: 0.2 });
    slide.addText([
      { text: item.title, options: { bold: true, fontSize: 11, color: TEXT_DARK, breakLine: true } },
      { text: item.desc, options: { fontSize: 9, color: GRAY } }
    ], { x: Q_LEFT + 0.5, y: accY - 0.03, w: 5.3, h: 0.38, margin: 0, valign: "top" });
    accY += 0.37;
  }

  // ═══════════════════════════════════════════════════════════════════════
  // Q2: ROLLING ACTION ITEMS (top-right)
  // ═══════════════════════════════════════════════════════════════════════

  // Blue accent bar
  slide.addShape(pres.shapes.RECTANGLE, {
    x: Q_RIGHT, y: Q_TOP, w: 0.06, h: Q_H_TOP,
    fill: { color: BLUE }
  });

  // Title with arrow icon
  slide.addShape(pres.shapes.OVAL, {
    x: Q_RIGHT + 0.2, y: Q_TOP + 0.05, w: 0.3, h: 0.3,
    fill: { color: BLUE }
  });
  slide.addImage({ data: arrowIcon, x: Q_RIGHT + 0.24, y: Q_TOP + 0.09, w: 0.22, h: 0.22 });
  slide.addText("ROLLING ACTION ITEM LIST", {
    x: Q_RIGHT + 0.6, y: Q_TOP, w: 5, h: 0.4,
    color: BLUE, fontSize: 18, fontFace: "Arial", bold: true, margin: 0
  });

  // Table header
  const tblHeaderOpts = { fill: { color: "F0F0F0" }, color: TEXT_DARK, bold: true, fontSize: 10, fontFace: "Arial", align: "left", valign: "middle" };
  const tblCellOpts = { color: TEXT_DARK, fontSize: 9.5, fontFace: "Arial", align: "left", valign: "middle" };
  const tblOwnerOpts = { color: GRAY, fontSize: 9, fontFace: "Arial", align: "left", valign: "middle" };
  const tblDueOpts = { color: GRAY, fontSize: 9, fontFace: "Arial", align: "center", valign: "middle" };

  const actionItems = [
    ["1", "Safety critic layer refinement & edge cases", "Pranav, Pragyan", "Apr 10"],
    ["2", "Performance testing within system architecture", "Pritish, Mansi", "Apr 10"],
    ["3", "Scale-to-zero MedGemma for cost optimization", "Pragyan", "Apr 12"],
    ["4", "Improve vision model accuracy (target >50% F1)", "Pragyan, Mansi", "Apr 14"],
    ["5", "Final evaluation report & demo preparation", "Pranav, Chandana", "Apr 18"],
  ];

  const tableRows = [
    [
      { text: "#", options: { ...tblHeaderOpts, align: "center" } },
      { text: "Action Item", options: tblHeaderOpts },
      { text: "Owner", options: tblHeaderOpts },
      { text: "Due", options: { ...tblHeaderOpts, align: "center" } }
    ],
    ...actionItems.map((row, i) => [
      { text: row[0], options: { ...tblCellOpts, align: "center", color: BLUE, bold: true } },
      { text: row[1], options: tblCellOpts },
      { text: row[2], options: tblOwnerOpts },
      { text: row[3], options: tblDueOpts }
    ])
  ];

  slide.addTable(tableRows, {
    x: Q_RIGHT + 0.15, y: Q_TOP + 0.5, w: 5.95,
    colW: [0.35, 3.4, 1.3, 0.7],
    border: { pt: 0.5, color: LIGHT_GRAY },
    rowH: [0.3, 0.35, 0.35, 0.35, 0.35, 0.35],
    margin: [0.05, 0.1, 0.05, 0.1]
  });

  // ═══════════════════════════════════════════════════════════════════════
  // Q3: RISKS & BARRIERS (bottom-left)
  // ═══════════════════════════════════════════════════════════════════════

  // Red accent bar
  slide.addShape(pres.shapes.RECTANGLE, {
    x: Q_LEFT, y: Q_MID + 0.15, w: 0.06, h: Q_H_BOT,
    fill: { color: RED }
  });

  slide.addImage({ data: warnIcon, x: Q_LEFT + 0.2, y: Q_MID + 0.2, w: 0.3, h: 0.3 });
  slide.addText("RISKS & BARRIERS", {
    x: Q_LEFT + 0.6, y: Q_MID + 0.15, w: 5, h: 0.4,
    color: RED, fontSize: 18, fontFace: "Arial", bold: true, margin: 0
  });

  const risks = [
    { level: "HIGH", color: RED, title: "Vision Model Accuracy Gap", desc: "34.7% Macro F1 on MIMIC-CXR; 62.3% hallucination rate on non-CheXpert findings" },
    { level: "HIGH", color: RED, title: "MedGemma Inference Cost", desc: "$5/hr GPU cost without scale-to-zero; cold start latency ~180s after idle" },
    { level: "HIGH", color: RED, title: "Drug Alert Signal Filtering", desc: "Raw Neo4j output mixes treatment text with safety alerts; requires deterministic filtering" },
    { level: "MED", color: ORANGE, title: "Free Model Rate Limiting", desc: "OpenRouter free-tier models (GPT-OSS, Nemotron) hit 429 rate limits under load" },
    { level: "MED", color: ORANGE, title: "Dev Tooling Sandbox Constraints", desc: "macOS sandbox blocks backend preview; limits real-time verification workflow" },
  ];

  let riskY = Q_MID + 0.65;
  for (const risk of risks) {
    // Badge
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: Q_LEFT + 0.2, y: riskY + 0.02, w: 0.55, h: 0.22,
      fill: { color: risk.color }, rectRadius: 0.04
    });
    slide.addText(risk.level, {
      x: Q_LEFT + 0.2, y: riskY + 0.02, w: 0.55, h: 0.22,
      color: WHITE, fontSize: 7.5, fontFace: "Arial", bold: true, align: "center", valign: "middle", margin: 0
    });

    slide.addText([
      { text: risk.title, options: { bold: true, fontSize: 11, color: TEXT_DARK, breakLine: true } },
      { text: risk.desc, options: { fontSize: 8.5, color: GRAY } }
    ], { x: Q_LEFT + 0.85, y: riskY - 0.03, w: 5, h: 0.42, margin: 0, valign: "top" });

    riskY += 0.44;
  }

  // ═══════════════════════════════════════════════════════════════════════
  // Q4: SCHEDULE TO FINAL (bottom-right)
  // ═══════════════════════════════════════════════════════════════════════

  // Gold accent bar
  slide.addShape(pres.shapes.RECTANGLE, {
    x: Q_RIGHT, y: Q_MID + 0.15, w: 0.06, h: Q_H_BOT,
    fill: { color: GOLD }
  });

  slide.addShape(pres.shapes.OVAL, {
    x: Q_RIGHT + 0.2, y: Q_MID + 0.2, w: 0.3, h: 0.3,
    fill: { color: GOLD }
  });
  slide.addImage({ data: calIcon, x: Q_RIGHT + 0.24, y: Q_MID + 0.24, w: 0.22, h: 0.22 });
  slide.addText("SCHEDULE TO FINAL (Apr 20)", {
    x: Q_RIGHT + 0.6, y: Q_MID + 0.15, w: 5, h: 0.4,
    color: "B8860B", fontSize: 18, fontFace: "Arial", bold: true, margin: 0
  });

  // Gantt chart area — compact layout matching CP1 style
  const ganttX = Q_RIGHT + 0.15;
  const ganttW = 5.95;
  const ganttTop = Q_MID + 0.65;
  const barH = 0.24;
  const barGap = 0.04;

  // Timeline: Feb 19 → Apr 20 (same range as CP1 for consistency)
  const startDate = new Date(2026, 1, 19); // Feb 19
  const endDate = new Date(2026, 3, 20);   // Apr 20
  const totalDays = (endDate - startDate) / (1000 * 60 * 60 * 24);

  function dateToX(d) {
    const days = (d - startDate) / (1000 * 60 * 60 * 24);
    return ganttX + (days / totalDays) * ganttW;
  }

  function dateToW(d1, d2) {
    const days = (d2 - d1) / (1000 * 60 * 60 * 24);
    return (days / totalDays) * ganttW;
  }

  // TODAY marker (Mar 26)
  const today = new Date(2026, 2, 26);
  const todayX = dateToX(today);
  slide.addText("TODAY", {
    x: todayX - 0.3, y: ganttTop - 0.2, w: 0.6, h: 0.16,
    color: RED, fontSize: 7, fontFace: "Arial", bold: true, align: "center", margin: 0
  });
  slide.addShape(pres.shapes.LINE, {
    x: todayX, y: ganttTop - 0.04, w: 0, h: 1.95,
    line: { color: RED, width: 1.5, dashType: "dash" }
  });

  // Gantt bars — overlapping timeline like CP1
  const ganttItems = [
    { label: "Scale-to-Zero Deploy", start: new Date(2026, 2, 20), end: new Date(2026, 3, 2), color: "1E88E5" },
    { label: "Vision Model Tuning", start: new Date(2026, 2, 22), end: new Date(2026, 3, 8), color: "43A047" },
    { label: "Integration Testing", start: new Date(2026, 3, 1), end: new Date(2026, 3, 12), color: GOLD },
    { label: "Safety Critic Refinement", start: new Date(2026, 3, 3), end: new Date(2026, 3, 14), color: "FF7043" },
    { label: "Performance & Load Testing", start: new Date(2026, 3, 8), end: new Date(2026, 3, 16), color: "AB47BC" },
    { label: "Final Eval & Report", start: new Date(2026, 3, 14), end: new Date(2026, 3, 20), color: DARK_BG },
  ];

  ganttItems.forEach((item, i) => {
    const y = ganttTop + i * (barH + barGap);
    const x = dateToX(item.start);
    const w = dateToW(item.start, item.end);

    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x, y, w, h: barH,
      fill: { color: item.color }, rectRadius: 0.03
    });
    slide.addText(item.label, {
      x, y, w, h: barH,
      color: WHITE, fontSize: 7.5, fontFace: "Arial", bold: true,
      align: "left", valign: "middle", margin: [0, 0.08, 0, 0.08]
    });
  });

  // Milestone markers row
  const markerY = ganttTop + ganttItems.length * (barH + barGap) + 0.08;

  // CP2 diamond (Apr 2)
  const cp2Date = new Date(2026, 3, 2);
  const cp2X = dateToX(cp2Date);
  slide.addShape(pres.shapes.DIAMOND, {
    x: cp2X - 0.1, y: markerY, w: 0.18, h: 0.18,
    fill: { color: GOLD }
  });
  slide.addText("CP2", {
    x: cp2X - 0.25, y: markerY + 0.2, w: 0.5, h: 0.15,
    color: GOLD, fontSize: 7.5, fontFace: "Arial", bold: true, align: "center", margin: 0
  });

  // FINAL diamond (Apr 20)
  const finalDate = new Date(2026, 3, 20);
  const finalX = dateToX(finalDate);
  slide.addShape(pres.shapes.DIAMOND, {
    x: finalX - 0.1, y: markerY, w: 0.18, h: 0.18,
    fill: { color: GOLD }
  });
  slide.addText("FINAL", {
    x: finalX - 0.3, y: markerY + 0.2, w: 0.6, h: 0.15,
    color: GOLD, fontSize: 7.5, fontFace: "Arial", bold: true, align: "center", margin: 0
  });

  // Date labels along the bottom axis
  const dateLabelsY = markerY + 0.38;
  const dateTicks = [
    { date: new Date(2026, 1, 19), label: "Feb 19" },
    { date: new Date(2026, 2, 5), label: "Mar 5" },
    { date: new Date(2026, 2, 20), label: "Mar 20" },
    { date: new Date(2026, 3, 2), label: "Apr 2" },
    { date: new Date(2026, 3, 20), label: "Apr 20" },
  ];

  dateTicks.forEach(tick => {
    const x = dateToX(tick.date);
    slide.addText(tick.label, {
      x: x - 0.35, y: dateLabelsY, w: 0.7, h: 0.16,
      color: GRAY, fontSize: 7.5, fontFace: "Arial", align: "center", margin: 0
    });
  });

  // ═══════════════════════════════════════════════════════════════════════
  // FOOTER
  // ═══════════════════════════════════════════════════════════════════════
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 7.1, w: 13.3, h: 0.4,
    fill: { color: MAROON }
  });
  slide.addText("Team Alabama  |  Arizona State University  |  Capstone Project", {
    x: 0.4, y: 7.1, w: 7, h: 0.4,
    color: WHITE, fontSize: 10, fontFace: "Arial", valign: "middle", margin: 0
  });
  slide.addText([
    { text: "Checkpoint 2  |  ", options: { color: WHITE, fontSize: 10 } },
    { text: "April 2026", options: { color: GOLD, fontSize: 10, bold: true } }
  ], {
    x: 9, y: 7.1, w: 4, h: 0.4,
    fontFace: "Arial", align: "right", valign: "middle", margin: [0, 0.3, 0, 0]
  });

  // ═══════════════════════════════════════════════════════════════════════
  // SAVE
  // ═══════════════════════════════════════════════════════════════════════
  const outPath = "/Users/pragyan/Desktop/personal projects/capstone/TrustMed-AI/SynapseAI_CP2_QuadChart.pptx";
  await pres.writeFile({ fileName: outPath });
  console.log("✅ Created: " + outPath);
}

main().catch(err => { console.error(err); process.exit(1); });
