const fs = require('fs');
const path = require('path');
const {
  AlignmentType,
  BorderStyle,
  Document,
  Footer,
  HeadingLevel,
  ImageRun,
  PageBreak,
  PageNumber,
  Packer,
  Paragraph,
  ShadingType,
  Table,
  TableCell,
  TableRow,
  TextRun,
  WidthType,
} = require('docx');

const mdPath = path.resolve('research_tmp/us_ai_value_chain_report_ko.md');
const outPath = 'C:\\Users\\USER\\Downloads\\유로존\\US_AI_밸류체인_3개월_로테이션_분석_20260902.docx';
const md = fs.readFileSync(mdPath, 'utf8').replace(/\r/g, '');
const C = { navy: '0B2A4A', blue: '2F6BDE', teal: '09A7A9', gray: '667085', light: 'F3F6FA', white: 'FFFFFF', amber: 'F59E0B' };

function inlineRuns(text, base = {}) {
  const out = [];
  const re = /(\[(?:FACT|INFERENCE|ASSUMPTION|SPECULATION|RISK)\]|\*\*[^*]+\*\*|`[^`]+`)/g;
  let pos = 0;
  for (const m of text.matchAll(re)) {
    if (m.index > pos) out.push(new TextRun({ text: text.slice(pos, m.index), ...base }));
    const token = m[0];
    if (token.startsWith('**')) out.push(new TextRun({ text: token.slice(2, -2), bold: true, ...base }));
    else if (token.startsWith('`')) out.push(new TextRun({ text: token.slice(1, -1), font: 'Consolas', color: C.blue, ...base }));
    else {
      const fact = token === '[FACT]';
      const infer = token === '[INFERENCE]';
      out.push(new TextRun({ text: token + ' ', bold: true, color: fact ? C.teal : infer ? C.blue : C.amber, font: 'Aptos', size: 16 }));
    }
    pos = m.index + token.length;
  }
  if (pos < text.length) out.push(new TextRun({ text: text.slice(pos), ...base }));
  return out;
}

function para(text, opts = {}) {
  return new Paragraph({
    children: inlineRuns(text, { font: 'Malgun Gothic', size: opts.size || 20, color: opts.color || C.navy }),
    spacing: { after: opts.after ?? 105, line: opts.line || 285 },
    bullet: opts.bullet ? { level: 0 } : undefined,
    alignment: opts.alignment,
    indent: opts.indent,
    keepNext: opts.keepNext,
  });
}

function head(text, level) {
  return new Paragraph({
    heading: level === 1 ? HeadingLevel.HEADING_1 : level === 2 ? HeadingLevel.HEADING_2 : HeadingLevel.HEADING_3,
    children: [new TextRun({ text, font: 'Malgun Gothic', bold: true, color: level === 1 ? C.navy : level === 2 ? C.blue : C.teal })],
    spacing: { before: level === 1 ? 320 : 220, after: 120 },
    keepNext: true,
  });
}

function tableFrom(lines) {
  const rows = lines.map(x => x.trim().replace(/^\||\|$/g, '').split('|').map(y => y.trim()));
  if (rows.length > 1 && rows[1].every(x => /^:?-{3,}:?$/.test(x))) rows.splice(1, 1);
  const cols = Math.max(...rows.map(r => r.length));
  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    rows: rows.map((row, ri) => new TableRow({
      tableHeader: ri === 0,
      cantSplit: true,
      children: Array.from({ length: cols }, (_, ci) => new TableCell({
        width: { size: Math.floor(100 / cols), type: WidthType.PERCENTAGE },
        shading: ri === 0 ? { fill: C.navy, type: ShadingType.CLEAR } : (ri % 2 === 0 ? { fill: C.light, type: ShadingType.CLEAR } : undefined),
        margins: { top: 70, bottom: 70, left: 70, right: 70 },
        borders: {
          top: { style: BorderStyle.SINGLE, size: 2, color: 'D0D5DD' },
          bottom: { style: BorderStyle.SINGLE, size: 2, color: 'D0D5DD' },
          left: { style: BorderStyle.SINGLE, size: 2, color: 'D0D5DD' },
          right: { style: BorderStyle.SINGLE, size: 2, color: 'D0D5DD' },
        },
        children: [new Paragraph({
          children: inlineRuns(row[ci] || '', { font: 'Malgun Gothic', size: 14, color: ri === 0 ? C.white : C.navy, bold: ri === 0 }),
          spacing: { after: 0, line: 210 },
        })],
      })),
    })),
  });
}

function imageBlock(line) {
  const m = line.match(/^\[\[IMAGE:(.+?)\|(.+?)\|(\d+)\]\]$/);
  if (!m) return null;
  const imgPath = m[1], caption = m[2], width = Number(m[3]);
  const dims = imgPath.includes('Monthly') ? [1552, 1458] : imgPath.includes('Normalized') ? [2683, 1514] : [2227, 1335];
  const height = Math.round(width * dims[1] / dims[0]);
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, children: [new ImageRun({ data: fs.readFileSync(imgPath), transformation: { width, height }, type: 'png' })], spacing: { before: 100, after: 80 } }),
    new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: caption, font: 'Malgun Gothic', size: 16, italics: true, color: C.gray })], spacing: { after: 170 } }),
  ];
}

function parse(text) {
  const out = [];
  const lines = text.split('\n');
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trimEnd();
    if (!line.trim()) continue;
    const img = imageBlock(line.trim());
    if (img) { out.push(...img); continue; }
    if (line.trim().startsWith('|')) {
      const ls = [];
      while (i < lines.length && lines[i].trim().startsWith('|')) ls.push(lines[i++]);
      i--; out.push(tableFrom(ls)); out.push(new Paragraph({ spacing: { after: 130 } }));
    } else if (line.startsWith('# ')) {
      if (out.length) out.push(new Paragraph({ children: [new PageBreak()] }));
      out.push(head(line.slice(2), 1));
    } else if (line.startsWith('## ')) out.push(head(line.slice(3), 2));
    else if (line.startsWith('### ')) out.push(head(line.slice(4), 3));
    else if (line.startsWith('- ')) out.push(para(line.slice(2), { bullet: true, after: 65 }));
    else out.push(para(line));
  }
  return out;
}

const body = [
  new Paragraph({ children: [new TextRun({ text: '미국 AI 밸류체인', font: 'Malgun Gothic', size: 46, bold: true, color: C.navy })], spacing: { after: 100 } }),
  new Paragraph({ children: [new TextRun({ text: '최근 3개월 로테이션과 시장 내러티브', font: 'Malgun Gothic', size: 30, color: C.blue })], spacing: { after: 260 } }),
  para('2026-06-01~2026-08-31 · 동일가중 가격수익률 · 공식 기업 실적 교차검증', { color: C.gray, after: 80 }),
  para('BQuant 신규 원자료 통합본과 별도로, 3개월 미국 개별종목 가격은 Yahoo Finance 일별 비조정 종가로 보완했다.', { color: C.gray }),
  new Paragraph({ children: [new PageBreak()] }),
  ...parse(md),
];

const doc = new Document({
  creator: 'OpenAI Codex',
  title: '미국 AI 밸류체인 최근 3개월 로테이션',
  description: '밸류체인별 동일가중 성과와 공식 기업 실적을 결합한 투자 리서치',
  styles: {
    default: { document: { run: { font: 'Malgun Gothic', size: 20, color: C.navy }, paragraph: { spacing: { line: 285 } } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: 'Malgun Gothic', size: 32, bold: true, color: C.navy }, paragraph: { spacing: { before: 320, after: 180 }, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: 'Malgun Gothic', size: 25, bold: true, color: C.blue }, paragraph: { spacing: { before: 250, after: 140 }, outlineLevel: 1 } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: 'Malgun Gothic', size: 22, bold: true, color: C.teal }, paragraph: { spacing: { before: 210, after: 110 }, outlineLevel: 2 } },
    ],
  },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 850, right: 720, bottom: 780, left: 720 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: 'US AI Value Chain  |  ', font: 'Aptos', size: 15, color: C.gray }), new TextRun({ children: [PageNumber.CURRENT], size: 15, color: C.gray })] })] }) },
    children: body,
  }],
});

Packer.toBuffer(doc).then(buf => { fs.writeFileSync(outPath, buf); console.log(outPath); });

