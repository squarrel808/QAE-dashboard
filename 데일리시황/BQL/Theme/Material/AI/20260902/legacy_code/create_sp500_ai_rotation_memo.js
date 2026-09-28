const fs = require("fs");
const path = require("path");
const {
  AlignmentType,
  BorderStyle,
  Document,
  ExternalHyperlink,
  Footer,
  HeadingLevel,
  Packer,
  PageNumber,
  Paragraph,
  ShadingType,
  Table,
  TableCell,
  TableRow,
  TextRun,
  WidthType,
} = require("docx");

const input = process.argv[2] || path.join(__dirname, "SP500_AI_Value_Chain_Rotation.html");
const output = process.argv[3] || path.join(__dirname, "SP500_AI_Value_Chain_Rotation_PM_Memo_20260901.docx");
const source = fs.readFileSync(input, "utf8");
const match = source.match(/const DATA=(.*?);\r?\nconst S=/s);
if (!match) throw new Error("Embedded dashboard data not found");
const data = JSON.parse(match[1]);

const navy = "183B6B";
const blue = "2563EB";
const lightBlue = "EAF2FC";
const gray = "6B7280";
const lightGray = "F3F5F8";
const green = "15803D";
const red = "C62828";
const pct = (x) => x == null ? "—" : `${x >= 0 ? "+" : ""}${(x * 100).toFixed(1)}%`;
const stage = (key) => data.stages.find((x) => x.key === key);
const perf = (key, period, mode = "Core") => data.modes[mode][key].performance[period];
const text = (value, options = {}) => new TextRun({ text: value, font: "Aptos", size: options.size || 20, bold: !!options.bold, color: options.color, italics: !!options.italics });
const p = (value, options = {}) => new Paragraph({
  children: Array.isArray(value) ? value : [text(value, options)],
  spacing: { after: options.after ?? 120, line: options.line || 300 },
  alignment: options.alignment,
  heading: options.heading,
  pageBreakBefore: !!options.pageBreakBefore,
});
const bullet = (runs, level = 0) => new Paragraph({ children: Array.isArray(runs) ? runs : [text(runs)], bullet: { level }, spacing: { after: 90, line: 290 } });
const cell = (value, options = {}) => new TableCell({
  width: options.width ? { size: options.width, type: WidthType.PERCENTAGE } : undefined,
  shading: options.fill ? { fill: options.fill, type: ShadingType.CLEAR } : undefined,
  margins: { top: 90, bottom: 90, left: 100, right: 100 },
  children: [p(Array.isArray(value) ? value : [text(String(value), { bold: options.bold, color: options.color, size: options.size || 18 })], { after: 0, alignment: options.alignment })],
});
const headerRow = (items) => new TableRow({ children: items.map((x) => cell(x, { fill: navy, bold: true, color: "FFFFFF", alignment: AlignmentType.CENTER })) });
const linkPara = (label, url, note) => new Paragraph({
  children: [new ExternalHyperlink({ link: url, children: [text(label, { bold: true, color: blue })] }), text(` — ${note}`, { color: gray })],
  spacing: { after: 100, line: 280 },
});

const coreRows = [...data.stages]
  .map((s) => ({ s, m1: perf(s.key, "1M"), m3: perf(s.key, "3M"), m6: perf(s.key, "6M") }))
  .sort((a, b) => b.m1.return - a.m1.return);
const expandedRows = [...data.stages]
  .map((s) => ({ s, m1: perf(s.key, "1M", "Expanded"), m3: perf(s.key, "3M", "Expanded") }))
  .sort((a, b) => b.m1.return - a.m1.return);

const children = [];
children.push(new Paragraph({
  children: [text("S&P 500 AI VALUE-CHAIN ROTATION", { bold: true, color: navy, size: 34 })],
  spacing: { after: 70 },
}));
children.push(p("Hardware leadership is correcting; application-layer breadth has improved", { bold: true, size: 27, color: blue, after: 130 }));
children.push(p(`PM research note · Data through ${data.meta.asOf} · ${data.meta.spxMembers} S&P 500 securities`, { color: gray, after: 240 }));
children.push(new Table({
  width: { size: 10100, type: WidthType.DXA },
  rows: [new TableRow({ children: [
    cell("1M leader", { fill: lightBlue, bold: true, color: navy }),
    cell(`AI Software ${pct(perf("software", "1M").return)}`, { fill: lightBlue, bold: true, color: green }),
    cell("3M signal", { fill: lightBlue, bold: true, color: navy }),
    cell("Hardware unwind / software resilience", { fill: lightBlue, bold: true, color: navy }),
  ] })],
}));

children.push(p("Executive Summary", { heading: HeadingLevel.HEADING_1, pageBreakBefore: false }));
children.push(bullet([text("[FACT] ", { bold: true, color: green }), text(`Over the latest month, the Core AI Software basket rose ${pct(perf("software", "1M").return)} versus ${pct(data.benchmark.returns["1M"])} for the equal-weight S&P 500. Four of five Core software names were positive.`)]));
children.push(bullet([text("[FACT] ", { bold: true, color: green }), text(`The prior hardware leaders reversed: Core Compute/Memory returned ${pct(perf("compute", "3M").return)}, Systems/Networking ${pct(perf("systems", "3M").return)} and Semicap/EDA ${pct(perf("semicap", "3M").return)} over three months.`)]));
children.push(bullet([text("[FACT] ", { bold: true, color: green }), text(`This is occurring after a very large six-month run: Compute/Memory ${pct(perf("compute", "6M").return)} and Systems/Networking ${pct(perf("systems", "6M").return)}. The recent weakness therefore looks like a de-rating/position unwind from extreme winners, not proof that AI infrastructure demand has disappeared.`)]));
children.push(bullet([text("[INFERENCE] ", { bold: true, color: blue }), text("The rotation is currently inside the AI complex—from capital-intensive infrastructure toward software and selected edge applications—more than a clean move from AI into non-AI equities.")]));
children.push(bullet([text("[INFERENCE] ", { bold: true, color: blue }), text("For a PM, the key confirmation is whether software relative strength survives beyond a short squeeze and becomes broader EPS revision leadership, while hardware earnings remain solid despite price consolidation.")]));

children.push(p("Key Findings", { heading: HeadingLevel.HEADING_1 }));
children.push(new Table({
  width: { size: 10100, type: WidthType.DXA },
  rows: [headerRow(["Core value-chain stage", "1M", "vs SPX EW", "3M", "6M", "1M breadth"]), ...coreRows.map((x, i) => new TableRow({ children: [
    cell(x.s.short, { fill: i % 2 ? "FFFFFF" : lightGray, bold: true }),
    cell(pct(x.m1.return), { fill: i % 2 ? "FFFFFF" : lightGray, color: x.m1.return >= 0 ? green : red, alignment: AlignmentType.RIGHT }),
    cell(pct(x.m1.relative), { fill: i % 2 ? "FFFFFF" : lightGray, color: x.m1.relative >= 0 ? green : red, alignment: AlignmentType.RIGHT }),
    cell(pct(x.m3.return), { fill: i % 2 ? "FFFFFF" : lightGray, color: x.m3.return >= 0 ? green : red, alignment: AlignmentType.RIGHT }),
    cell(pct(x.m6.return), { fill: i % 2 ? "FFFFFF" : lightGray, color: x.m6.return >= 0 ? green : red, alignment: AlignmentType.RIGHT }),
    cell(pct(x.m1.breadth), { fill: i % 2 ? "FFFFFF" : lightGray, alignment: AlignmentType.RIGHT }),
  ] }))],
}));
children.push(p("Interpretation: the 1M winner is the application layer, while every Core infrastructure stage is negative over 3M. Yet the 6M ranking remains dominated by compute and systems. This is a sharp timing rotation, not yet a change in the structural capex regime.", { after: 180 }));

children.push(p("Detailed Analysis", { heading: HeadingLevel.HEADING_1, pageBreakBefore: true }));
children.push(p("1. What has rotated?", { heading: HeadingLevel.HEADING_2 }));
children.push(p(`The strongest short-window move is software. Core AI Software gained ${pct(perf("software", "1W").return)} in one week and ${pct(perf("software", "1M").return)} in one month. CRM and NOW were the largest one-month contributors at +34.8% and +25.3%; PLTR and ADBE also rose. APP fell sharply, which is why the basket's breadth and median are more informative than its mean alone.`));
children.push(p(`By contrast, Core Semicap/EDA fell ${pct(perf("semicap", "1M").return)}, Power/Data Center ${pct(perf("power", "1M").return)} and Compute/Memory ${pct(perf("compute", "1M").return)}. Their 1M positive breadth was 17%, 12% and 40%, respectively. The weakness is therefore broad within those stages, not only a single-stock event.`));
children.push(p("2. Why this does not yet equal an AI-exodus call", { heading: HeadingLevel.HEADING_2 }));
children.push(p(`The six-month return gap is still enormous: Core Compute/Memory ${pct(perf("compute", "6M").return)}, Systems/Networking ${pct(perf("systems", "6M").return)} and Semicap/EDA ${pct(perf("semicap", "6M").return)}, compared with ${pct(data.benchmark.returns["6M"])} for the equal-weight S&P 500. A three-month drawdown after that run can be explained by crowded-position unwinding and multiple compression even if end demand remains intact.`));
children.push(p("[FACT] The infrastructure demand backdrop remains strong in primary disclosures. The IEA expects data-center electricity use to more than double toward 2030, and recent company reports from NVIDIA, Broadcom, Arista, Vertiv and Eaton continue to describe strong AI compute, networking, power and cooling demand. [INFERENCE] Price leadership can therefore migrate away from hardware before the earnings cycle turns down."));
children.push(p("3. Core versus Expanded universe", { heading: HeadingLevel.HEADING_2 }));
children.push(p(`The Expanded AI Software basket returned ${pct(perf("software", "1M", "Expanded").return)} in one month with ${pct(perf("software", "1M", "Expanded").breadth)} positive breadth and ${pct(perf("software", "3M", "Expanded").return)} over three months. That is stronger and broader than the Core-only message, which supports genuine application-layer participation rather than a move confined to one flagship name.`));
children.push(new Table({
  width: { size: 10100, type: WidthType.DXA },
  rows: [headerRow(["Expanded stage", "Names", "1M", "1M breadth", "3M"]), ...expandedRows.map((x, i) => new TableRow({ children: [
    cell(x.s.short, { fill: i % 2 ? "FFFFFF" : lightGray, bold: true }),
    cell(String(x.m1.members), { fill: i % 2 ? "FFFFFF" : lightGray, alignment: AlignmentType.RIGHT }),
    cell(pct(x.m1.return), { fill: i % 2 ? "FFFFFF" : lightGray, color: x.m1.return >= 0 ? green : red, alignment: AlignmentType.RIGHT }),
    cell(pct(x.m1.breadth), { fill: i % 2 ? "FFFFFF" : lightGray, alignment: AlignmentType.RIGHT }),
    cell(pct(x.m3.return), { fill: i % 2 ? "FFFFFF" : lightGray, color: x.m3.return >= 0 ? green : red, alignment: AlignmentType.RIGHT }),
  ] }))],
}));

children.push(p("Portfolio Implications", { heading: HeadingLevel.HEADING_1, pageBreakBefore: true }));
children.push(bullet([text("Tactical: ", { bold: true, color: navy }), text("Do not describe the latest move as broad AI capitulation. The cleanest observation is long application-layer relative strength versus short crowded infrastructure leaders over the latest one to three months.")]));
children.push(bullet([text("Confirmation: ", { bold: true, color: navy }), text("Track FY1/FY2 EPS revisions, order/backlog growth and earnings breadth by value-chain stage. Software price leadership without improving revisions is vulnerable to reversal.")]));
children.push(bullet([text("Risk control: ", { bold: true, color: navy }), text("Use Core and Expanded baskets together. Core shows purer theme beta; Expanded breadth reveals whether the move has spread to adjacent beneficiaries.")]));
children.push(bullet([text("Implementation: ", { bold: true, color: navy }), text("Equal weighting is useful for diagnosing breadth but is not the same as investable capital weighting. Any trade should be stress-tested under market-cap, risk-parity and beta-neutral weights.")]));

children.push(p("Risks and Limitations", { heading: HeadingLevel.HEADING_1 }));
children.push(bullet("[RISK] Current S&P 500 membership is carried backward. The history therefore contains survivorship and index-reconstitution bias."));
children.push(bullet("[RISK] The source is the Bloomberg Price field from the user's raw constituent workbook. Returns exclude dividends; corporate-action adjustment settings should be independently audited before trading use."));
children.push(bullet("[RISK] Daily equal weighting gives a small beneficiary the same return weight as a mega-cap platform. It is intentionally a breadth monitor, not an estimate of S&P 500 contribution."));
children.push(bullet("[RISK] Value-chain membership is a research taxonomy. Core versus Adjacent is a judgement about economic exposure, not a Bloomberg or S&P industry classification."));
children.push(bullet("[RISK] Several six-month constituent returns are extreme. Median return, breadth and capped-return versions should be reviewed alongside the headline average."));

children.push(p("Open Questions", { heading: HeadingLevel.HEADING_1 }));
children.push(bullet("Do FY1/FY2 EPS revision breadth and earnings contribution confirm the one-month software rotation?"));
children.push(bullet("Is the hardware correction driven by multiple compression, estimate cuts, or both?"));
children.push(bullet("Would beta-neutral or sector-neutral value-chain portfolios show the same ranking?"));
children.push(bullet("How much of the power/data-center basket is a direct AI demand signal versus rates, power prices and utility regulation?"));
children.push(bullet("Does the application-layer strength persist after the next earnings season and beyond a four-week window?"));

children.push(p("Sources", { heading: HeadingLevel.HEADING_1, pageBreakBefore: true }));
children.push(p("Market data", { heading: HeadingLevel.HEADING_2 }));
children.push(p(`User-supplied Bloomberg raw workbook merged with the prior panel. Current panel: ${data.meta.startDate} to ${data.meta.endDate}; ${data.meta.spxMembers} S&P 500 securities. Dashboard methodology and constituent list are embedded in the accompanying HTML.`));
children.push(p("External research and primary disclosures", { heading: HeadingLevel.HEADING_2 }));
for (const [label, url, note] of data.sources) children.push(linkPara(label, url, note));

const doc = new Document({
  styles: {
    default: { document: { run: { font: "Aptos", size: 20, color: "172033" }, paragraph: { spacing: { line: 300 } } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: "Aptos Display", size: 28, bold: true, color: navy }, paragraph: { spacing: { before: 260, after: 120 }, keepNext: true } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: "Aptos Display", size: 23, bold: true, color: blue }, paragraph: { spacing: { before: 180, after: 80 }, keepNext: true } },
    ],
  },
  sections: [{
    properties: { page: { margin: { top: 900, right: 850, bottom: 850, left: 850 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [text("S&P 500 AI Value-Chain Rotation · Page ", { color: gray, size: 16 }), new TextRun({ children: [PageNumber.CURRENT], font: "Aptos", size: 16, color: gray })] })] }) },
    children,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.mkdirSync(path.dirname(output), { recursive: true });
  fs.writeFileSync(output, buf);
  console.log(`output=${output}`);
});
