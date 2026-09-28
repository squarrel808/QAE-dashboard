const fs = require('fs');
const path = require('path');
const {
  AlignmentType,
  BorderStyle,
  Document,
  Footer,
  HeadingLevel,
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

const mdPath = path.resolve('research_tmp/bloomberg_translation_ko.md');
const srcPath = 'C:\\Users\\USER\\.codex\\attachments\\30d97098-3bf7-4d43-becd-6e5e5d0501ef\\pasted-text.txt';
const outPath = 'C:\\Users\\USER\\Downloads\\유로존\\Bloomberg_AI_브리핑_전체번역_20260902.docx';

const md = fs.readFileSync(mdPath, 'utf8').replace(/\r/g, '');
const source = fs.readFileSync(srcPath, 'utf8').replace(/\r/g, '');

const COLORS = { navy: '0B2A4A', blue: '2F6BDE', teal: '09A7A9', gray: '667085', light: 'F3F6FA', white: 'FFFFFF' };

function runsFromInline(text, opts = {}) {
  const runs = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let pos = 0;
  for (const m of text.matchAll(re)) {
    if (m.index > pos) runs.push(new TextRun({ text: text.slice(pos, m.index), ...opts }));
    const token = m[0];
    if (token.startsWith('**')) runs.push(new TextRun({ text: token.slice(2, -2), bold: true, ...opts }));
    else runs.push(new TextRun({ text: token.slice(1, -1), font: 'Consolas', color: COLORS.blue, ...opts }));
    pos = m.index + token.length;
  }
  if (pos < text.length) runs.push(new TextRun({ text: text.slice(pos), ...opts }));
  return runs;
}

function p(text, options = {}) {
  return new Paragraph({
    children: runsFromInline(text, { font: 'Malgun Gothic', size: options.size || 20, color: options.color || COLORS.navy }),
    spacing: { after: options.after ?? 120, line: options.line || 300 },
    alignment: options.alignment,
    bullet: options.bullet ? { level: 0 } : undefined,
    indent: options.indent,
  });
}

function heading(text, level) {
  const h = level === 1 ? HeadingLevel.HEADING_1 : level === 2 ? HeadingLevel.HEADING_2 : HeadingLevel.HEADING_3;
  return new Paragraph({
    heading: h,
    children: [new TextRun({ text, font: 'Malgun Gothic', bold: true, color: level === 1 ? COLORS.navy : COLORS.blue })],
    spacing: { before: level === 1 ? 320 : 220, after: 130 },
    keepNext: true,
  });
}

function parseTable(lines) {
  const rows = lines.filter(x => x.trim()).map(line => line.trim().replace(/^\||\|$/g, '').split('|').map(x => x.trim()));
  if (rows.length >= 2 && rows[1].every(x => /^:?-{3,}:?$/.test(x))) rows.splice(1, 1);
  const maxCols = Math.max(...rows.map(r => r.length));
  const widths = Array(maxCols).fill(Math.floor(100 / maxCols));
  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    rows: rows.map((row, ri) => new TableRow({
      tableHeader: ri === 0,
      cantSplit: true,
      children: Array.from({ length: maxCols }, (_, ci) => new TableCell({
        width: { size: widths[ci], type: WidthType.PERCENTAGE },
        shading: ri === 0 ? { fill: COLORS.navy, type: ShadingType.CLEAR } : (ri % 2 === 0 ? { fill: COLORS.light, type: ShadingType.CLEAR } : undefined),
        margins: { top: 80, bottom: 80, left: 75, right: 75 },
        borders: {
          top: { style: BorderStyle.SINGLE, size: 2, color: 'D0D5DD' },
          bottom: { style: BorderStyle.SINGLE, size: 2, color: 'D0D5DD' },
          left: { style: BorderStyle.SINGLE, size: 2, color: 'D0D5DD' },
          right: { style: BorderStyle.SINGLE, size: 2, color: 'D0D5DD' },
        },
        children: [new Paragraph({
          children: [new TextRun({ text: row[ci] || '', font: 'Malgun Gothic', size: 15, bold: ri === 0, color: ri === 0 ? COLORS.white : COLORS.navy })],
          spacing: { after: 0, line: 220 },
        })],
      })),
    })),
  });
}

function parseMarkdown(text) {
  const out = [];
  const lines = text.split('\n');
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trimEnd();
    if (!line.trim()) continue;
    if (line.startsWith('|')) {
      const tbl = [];
      while (i < lines.length && lines[i].trim().startsWith('|')) tbl.push(lines[i++]);
      i--;
      out.push(parseTable(tbl));
      out.push(new Paragraph({ spacing: { after: 120 } }));
    } else if (line.startsWith('# ')) {
      if (out.length) out.push(new Paragraph({ children: [new PageBreak()] }));
      out.push(heading(line.slice(2), 1));
    } else if (line.startsWith('## ')) {
      out.push(heading(line.slice(3), 2));
    } else if (line.startsWith('### ')) {
      out.push(heading(line.slice(4), 3));
    } else if (line.startsWith('- ')) {
      out.push(p(line.slice(2), { bullet: true, after: 70 }));
    } else {
      out.push(p(line));
    }
  }
  return out;
}

function extractBql(raw) {
  const lines = raw.split('\n');
  const queries = [];
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].trim() === 'Data Query') {
      let j = i + 1;
      while (j < lines.length && !lines[j].trim()) j++;
      if (j < lines.length && lines[j].trim().startsWith('for ')) queries.push(lines[j].trim());
    }
  }
  return [...new Set(queries)];
}

function extractSourceLists(raw) {
  const lines = raw.split('\n');
  const result = [];
  let inList = false;
  for (const lineRaw of lines) {
    const line = lineRaw.trim();
    if (line === 'Responses are generated by') { inList = true; result.push('Bloomberg AI 응답 경고: 정확성과 완전성을 반드시 확인할 것.'); continue; }
    if (inList && line === 'Workflow') { inList = false; result.push(''); continue; }
    if (!inList || !line || /^\d+\.$/.test(line) || line === 'Bloomberg AI' || line === '. Check to make sure they are correct and complete.') continue;
    if (line === 'Copy' || line === 'Save to' || line === 'Workflows') continue;
    if (/^(Bloomberg|Benzinga|Dow Jones|Financial|Globe|MNI|Associated|Business Insider|Avalon|Ion|NightVision|Zacks|The Deal|Third Party)/.test(line) || /^NEWS\s/.test(line)) result.push(line);
  }
  return result;
}

const body = [];
body.push(new Paragraph({
  children: [new TextRun({ text: 'Bloomberg AI 브리핑', font: 'Malgun Gothic', size: 42, bold: true, color: COLORS.navy })],
  spacing: { after: 120 },
}));
body.push(new Paragraph({
  children: [new TextRun({ text: '미국 · 비미국 · 팩터/테마/포지셔닝 전체 번역', font: 'Malgun Gothic', size: 28, color: COLORS.blue })],
  spacing: { after: 260 },
}));
body.push(p('원문 생성일 2026-09-01 · 번역본 작성일 2026-09-02', { color: COLORS.gray, after: 80 }));
body.push(p('사용자 제공 Bloomberg AI 출력물의 한국어 번역. 투자판단 전 원문 수치와 1차 자료를 재확인해야 한다.', { color: COLORS.gray }));
body.push(new Paragraph({ children: [new PageBreak()] }));
body.push(...parseMarkdown(md));

body.push(new Paragraph({ children: [new PageBreak()] }));
body.push(heading('부록 A. 원문 BQL(Data Query) 코드', 1));
body.push(p('아래 코드는 원문에 반복된 Bloomberg Query Language 표현을 중복 제거해 그대로 보존한 것이다.', { color: COLORS.gray }));
for (const [i, q] of extractBql(source).entries()) {
  body.push(new Paragraph({
    children: [new TextRun({ text: `${i + 1}. ${q}`, font: 'Consolas', size: 13, color: '344054' })],
    spacing: { after: 75, line: 210 },
  }));
}

body.push(new Paragraph({ children: [new PageBreak()] }));
body.push(heading('부록 B. 원문 뉴스 제공자·날짜 목록', 1));
body.push(p('뉴스 제공자와 날짜는 번역 대상이라기보다 출처 식별자이므로 원문 표기를 유지했다.', { color: COLORS.gray }));
for (const line of extractSourceLists(source)) {
  if (!line) body.push(new Paragraph({ spacing: { after: 80 } }));
  else body.push(new Paragraph({ children: [new TextRun({ text: line, font: 'Malgun Gothic', size: 15, color: '344054' })], spacing: { after: 40 } }));
}

const doc = new Document({
  creator: 'OpenAI Codex',
  title: 'Bloomberg AI 브리핑 전체 번역',
  description: '사용자 제공 Bloomberg AI 미국·비미국·팩터/테마 보고서의 한국어 번역',
  styles: {
    default: { document: { run: { font: 'Malgun Gothic', size: 20, color: COLORS.navy }, paragraph: { spacing: { line: 300 } } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: 'Malgun Gothic', size: 32, bold: true, color: COLORS.navy }, paragraph: { spacing: { before: 320, after: 180 }, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: 'Malgun Gothic', size: 25, bold: true, color: COLORS.blue }, paragraph: { spacing: { before: 260, after: 140 }, outlineLevel: 1 } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: 'Malgun Gothic', size: 21, bold: true, color: COLORS.teal }, paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 2 } },
    ],
  },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 850, right: 720, bottom: 780, left: 720 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: 'Bloomberg AI 번역  |  ', font: 'Malgun Gothic', size: 15, color: COLORS.gray }), new TextRun({ children: [PageNumber.CURRENT], size: 15, color: COLORS.gray })] })] }) },
    children: body,
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(outPath, buf);
  console.log(outPath);
  console.log('BQL', extractBql(source).length, 'source lines', extractSourceLists(source).length);
});

