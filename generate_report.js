const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  HeadingLevel, AlignmentType, BorderStyle, WidthType, ShadingType,
  LevelFormat, PageNumber, Footer, PageBreak, TabStopType, TabStopPosition
} = require('docx');
const fs = require('fs');

const PAGE_W = 9360; // content width in DXA (8.5" page - 1" margins each side)

// ── Color palette ──────────────────────────────────────────────────────
const C = {
  navy:      "1B3A6B",
  navyLight: "2E5FA3",
  red:       "C0392B",
  redLight:  "FADBD8",
  amber:     "B7770D",
  amberLight:"FEF9E7",
  green:     "1E7A45",
  greenLight:"EAFAF1",
  purple:    "6C3483",
  purpleLight:"F5EEF8",
  blue:      "1565C0",
  blueLight: "EBF5FB",
  gray:      "5D6D7E",
  grayLight: "F2F3F4",
  grayBorder:"CCCCCC",
  white:     "FFFFFF",
  lightBlue: "D6EAF8",
  darkText:  "1A1A2E",
};

// ── Border helpers ─────────────────────────────────────────────────────
const border = (color = C.grayBorder, sz = 4) => ({
  style: BorderStyle.SINGLE, size: sz, color
});
const allBorders = (color, sz) => ({
  top: border(color, sz), bottom: border(color, sz),
  left: border(color, sz), right: border(color, sz)
});
const noBorder = () => ({ style: BorderStyle.NONE, size: 0, color: "FFFFFF" });
const noBorders = () => ({ top: noBorder(), bottom: noBorder(), left: noBorder(), right: noBorder() });

// ── Text helpers ───────────────────────────────────────────────────────
const run = (text, opts = {}) => new TextRun({ text, font: "Arial", ...opts });
const mono = (text, opts = {}) => new TextRun({ text, font: "Courier New", size: 18, ...opts });
const para = (children, opts = {}) => new Paragraph({ children: Array.isArray(children) ? children : [children], ...opts });
const emptyPara = (spacing = 80) => para([run("")], { spacing: { before: spacing, after: spacing } });

// ── Severity badge cell ────────────────────────────────────────────────
const severityColors = {
  "Critical": { bg: "C0392B", fg: "FFFFFF" },
  "Medium":   { bg: "E67E22", fg: "FFFFFF" },
  "Low":      { bg: "27AE60", fg: "FFFFFF" },
};

const badgeCell = (label, width = 1100) => {
  const c = severityColors[label] || { bg: C.gray, fg: C.white };
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    borders: noBorders(),
    shading: { fill: c.bg, type: ShadingType.CLEAR },
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [para([run(label, { color: c.fg, bold: true, size: 17 })], {
      alignment: AlignmentType.CENTER
    })]
  });
};

const typeCell = (label, bg, fg, width = 1200) => new TableCell({
  width: { size: width, type: WidthType.DXA },
  borders: noBorders(),
  shading: { fill: bg, type: ShadingType.CLEAR },
  margins: { top: 60, bottom: 60, left: 100, right: 100 },
  children: [para([run(label, { color: fg, bold: true, size: 17 })], {
    alignment: AlignmentType.CENTER
  })]
});

// ── Section header ─────────────────────────────────────────────────────
const sectionHeader = (emoji, title, subtitle) => [
  emptyPara(160),
  new Table({
    width: { size: PAGE_W, type: WidthType.DXA },
    columnWidths: [PAGE_W],
    rows: [new TableRow({
      children: [new TableCell({
        width: { size: PAGE_W, type: WidthType.DXA },
        borders: { ...noBorders(), left: { style: BorderStyle.SINGLE, size: 20, color: C.navy } },
        shading: { fill: C.grayLight, type: ShadingType.CLEAR },
        margins: { top: 120, bottom: 120, left: 200, right: 120 },
        children: [
          para([run(`${emoji}  ${title}`, { bold: true, size: 28, color: C.navy })]),
          para([run(subtitle, { size: 20, color: C.gray })])
        ]
      })]
    })]
  }),
  emptyPara(120),
];

// ── Issue card ─────────────────────────────────────────────────────────
const labelRow = (label, text, labelColor = C.gray) => new TableRow({
  children: [
    new TableCell({
      width: { size: 1400, type: WidthType.DXA },
      borders: noBorders(),
      shading: { fill: C.grayLight, type: ShadingType.CLEAR },
      margins: { top: 60, bottom: 60, left: 120, right: 80 },
      children: [para([run(label, { bold: true, size: 18, color: labelColor })])]
    }),
    new TableCell({
      width: { size: PAGE_W - 1400, type: WidthType.DXA },
      borders: noBorders(),
      shading: { fill: C.white, type: ShadingType.CLEAR },
      margins: { top: 60, bottom: 60, left: 120, right: 120 },
      children: [para([run(text, { size: 18, color: C.darkText })])]
    }),
  ]
});

const codeBlock = (lines) => new Table({
  width: { size: PAGE_W - 240, type: WidthType.DXA },
  columnWidths: [PAGE_W - 240],
  rows: [new TableRow({
    children: [new TableCell({
      width: { size: PAGE_W - 240, type: WidthType.DXA },
      borders: { ...noBorders(), left: { style: BorderStyle.SINGLE, size: 12, color: C.navy } },
      shading: { fill: "1E1E1E", type: ShadingType.CLEAR },
      margins: { top: 100, bottom: 100, left: 160, right: 120 },
      children: lines.map(l => para([mono(l, { color: l.startsWith('#') || l.startsWith('//') ? "6A9955" : l.startsWith('# ✅') || l.startsWith('# ❌') ? "6A9955" : "D4D4D4" })], {
        spacing: { before: 20, after: 20 }
      }))
    })]
  })]
});

const issueCard = (num, severity, type, typeBg, typeFg, title, file, description, badCode, goodCode, fix) => {
  const headerRow = new TableRow({
    children: [new TableCell({
      width: { size: PAGE_W, type: WidthType.DXA },
      columnSpan: 1,
      borders: noBorders(),
      shading: { fill: C.navy, type: ShadingType.CLEAR },
      margins: { top: 120, bottom: 120, left: 160, right: 120 },
      children: [
        new Table({
          width: { size: PAGE_W - 280, type: WidthType.DXA },
          columnWidths: [400, 1200, 1100, PAGE_W - 280 - 400 - 1200 - 1100],
          rows: [new TableRow({
            children: [
              new TableCell({
                width: { size: 400, type: WidthType.DXA },
                borders: noBorders(),
                shading: { fill: C.navy, type: ShadingType.CLEAR },
                margins: { top: 0, bottom: 0, left: 0, right: 120 },
                children: [para([run(`#${num}`, { bold: true, size: 24, color: "7FB3F5" })])]
              }),
              typeCell(type, typeBg, typeFg, 1200),
              badgeCell(severity, 1100),
              new TableCell({
                width: { size: PAGE_W - 280 - 400 - 1200 - 1100, type: WidthType.DXA },
                borders: noBorders(),
                shading: { fill: C.navy, type: ShadingType.CLEAR },
                margins: { top: 0, bottom: 0, left: 120, right: 0 },
                children: [para([run(title, { bold: true, size: 20, color: C.white })])]
              }),
            ]
          })]
        })
      ]
    })]
  });

  const metaRows = [
    labelRow("File", file, C.navyLight),
    labelRow("Description", description),
  ];

  const rows = [headerRow, ...metaRows];

  const sections = [];

  if (badCode) {
    sections.push(
      emptyPara(60),
      para([run("❌  Current code (problem)", { bold: true, size: 19, color: C.red })],
        { spacing: { before: 40, after: 60 } }),
      codeBlock(badCode),
    );
  }

  if (goodCode) {
    sections.push(
      emptyPara(60),
      para([run("✅  Fixed code", { bold: true, size: 19, color: C.green })],
        { spacing: { before: 40, after: 60 } }),
      codeBlock(goodCode),
    );
  }

  sections.push(
    emptyPara(60),
    new Table({
      width: { size: PAGE_W - 240, type: WidthType.DXA },
      columnWidths: [PAGE_W - 240],
      rows: [new TableRow({
        children: [new TableCell({
          width: { size: PAGE_W - 240, type: WidthType.DXA },
          borders: { ...noBorders(), left: { style: BorderStyle.SINGLE, size: 12, color: C.green } },
          shading: { fill: C.greenLight, type: ShadingType.CLEAR },
          margins: { top: 100, bottom: 100, left: 160, right: 120 },
          children: [para([
            run("How to fix:  ", { bold: true, size: 18, color: C.green }),
            run(fix, { size: 18, color: C.darkText })
          ])]
        })]
      })]
    }),
    emptyPara(120),
  );

  const bodyCell = new TableRow({
    children: [new TableCell({
      width: { size: PAGE_W, type: WidthType.DXA },
      borders: { top: noBorder(), bottom: border(C.grayBorder, 4), left: border(C.navy, 8), right: border(C.grayBorder, 4) },
      shading: { fill: C.white, type: ShadingType.CLEAR },
      margins: { top: 80, bottom: 80, left: 160, right: 120 },
      children: [...metaRows.map(() => null).filter(x => x !== null), ...sections].filter(x => x !== null)
    })]
  });

  // Outer card table
  return [
    new Table({
      width: { size: PAGE_W, type: WidthType.DXA },
      columnWidths: [PAGE_W],
      rows: [
        headerRow,
        new TableRow({
          children: [new TableCell({
            width: { size: PAGE_W, type: WidthType.DXA },
            borders: { top: noBorder(), bottom: border(C.grayBorder, 4), left: border(C.navy, 16), right: border(C.grayBorder, 4) },
            shading: { fill: C.white, type: ShadingType.CLEAR },
            margins: { top: 80, bottom: 80, left: 160, right: 120 },
            children: [
              para([run(description, { size: 19, color: C.darkText })], { spacing: { before: 40, after: 40 } }),
              ...(badCode ? [
                para([run("❌  Current code (problem)", { bold: true, size: 19, color: C.red })], { spacing: { before: 80, after: 60 } }),
                codeBlock(badCode),
              ] : []),
              ...(goodCode ? [
                para([run("✅  Fixed code", { bold: true, size: 19, color: C.green })], { spacing: { before: 120, after: 60 } }),
                codeBlock(goodCode),
              ] : []),
              para([run("")], { spacing: { before: 80, after: 0 } }),
              new Table({
                width: { size: PAGE_W - 400, type: WidthType.DXA },
                columnWidths: [PAGE_W - 400],
                rows: [new TableRow({
                  children: [new TableCell({
                    width: { size: PAGE_W - 400, type: WidthType.DXA },
                    borders: { ...noBorders(), left: { style: BorderStyle.SINGLE, size: 16, color: C.green } },
                    shading: { fill: C.greenLight, type: ShadingType.CLEAR },
                    margins: { top: 100, bottom: 100, left: 160, right: 120 },
                    children: [para([
                      run("Fix:  ", { bold: true, size: 18, color: C.green }),
                      run(fix, { size: 18, color: C.darkText })
                    ])]
                  })]
                })]
              }),
              para([run("")], { spacing: { before: 60, after: 0 } }),
              new Table({
                width: { size: PAGE_W - 400, type: WidthType.DXA },
                columnWidths: [400, PAGE_W - 400 - 400],
                rows: [new TableRow({
                  children: [
                    new TableCell({
                      width: { size: 400, type: WidthType.DXA },
                      borders: noBorders(),
                      shading: { fill: C.grayLight, type: ShadingType.CLEAR },
                      margins: { top: 60, bottom: 60, left: 80, right: 80 },
                      children: [para([run("File", { bold: true, size: 18, color: C.gray })])]
                    }),
                    new TableCell({
                      width: { size: PAGE_W - 400 - 400, type: WidthType.DXA },
                      borders: noBorders(),
                      shading: { fill: C.grayLight, type: ShadingType.CLEAR },
                      margins: { top: 60, bottom: 60, left: 80, right: 80 },
                      children: [para([mono(file, { size: 18, color: C.navyLight })])]
                    }),
                  ]
                })]
              }),
              para([run("")], { spacing: { before: 80, after: 0 } }),
            ]
          })]
        })
      ]
    }),
    emptyPara(160),
  ];
};

// ── Summary table ──────────────────────────────────────────────────────
const summaryTable = () => {
  const headerCells = ["#", "Category", "Severity", "Title", "File"].map((h, i) => {
    const widths = [400, 1200, 900, 4460, 2400];
    return new TableCell({
      width: { size: widths[i], type: WidthType.DXA },
      borders: allBorders(C.navy, 4),
      shading: { fill: C.navy, type: ShadingType.CLEAR },
      margins: { top: 80, bottom: 80, left: 100, right: 100 },
      children: [para([run(h, { bold: true, size: 18, color: C.white })], { alignment: AlignmentType.CENTER })]
    });
  });

  const issues = [
    // [num, type, typeBg, typeFg, severity, title, file]
    ["1", "Bug", "C0392B", "FFFFFF", "Critical", "Ref counter race condition", "operations.py"],
    ["2", "Bug", "C0392B", "FFFFFF", "Critical", "Stale lru_cache for lookups", "models.py"],
    ["3", "Bug", "C0392B", "FFFFFF", "Medium",   "Bulk ref pre-allocation too small", "bulk.py"],
    ["4", "Bug", "C0392B", "FFFFFF", "Medium",   "internal_note exposed in Excel download", "statement.py"],
    ["5", "Bug", "C0392B", "FFFFFF", "Medium",   "Batch listing endpoints have no auth", "batches.py"],
    ["6", "Bug", "C0392B", "FFFFFF", "Low",      "Batch export endpoint has no auth", "batches.py"],
    ["7", "Security", "6C3483", "FFFFFF", "Critical", "JWT_SECRET KeyError crashes server", "auth.py"],
    ["8", "Security", "6C3483", "FFFFFF", "Critical", "Deactivated user keeps token access", "auth.py"],
    ["9", "Security", "6C3483", "FFFFFF", "Medium",   "Hardcoded seed passwords", "models.py"],
    ["10","Security", "6C3483", "FFFFFF", "Medium",   "finance.db committed to the repo", ".gitignore"],
    ["11","Security", "6C3483", "FFFFFF", "Low",      "No rate limiting on login", "auth.py"],
    ["12","Performance","1565C0","FFFFFF","Medium",   "Correlated subqueries per report row", "reports.py / dashboard.py"],
    ["13","Performance","1565C0","FFFFFF","Low",      "Reconciliation loads all rows into RAM", "reconciliation.py"],
    ["14","Refactor", "1E7A45", "FFFFFF", "Low",      "Inconsistent transaction type names", "operations.py / bulk.py"],
    ["15","UX",       "B7770D", "FFFFFF", "Medium",   "Password change doesn't revoke tokens", "auth.py"],
    ["16","UX",       "B7770D", "FFFFFF", "Low",      "Audit log limited to 500 rows / no pagination", "admin.py"],
    ["17","Refactor", "1E7A45", "FFFFFF", "Low",      "Config format mismatch (CSV vs JSON)", "config.py / lookups.py"],
    ["18","Refactor", "1E7A45", "FFFFFF", "Low",      "Audit log path is relative / breaks on Render", "models.py"],
  ];

  const severityBg = { "Critical": "FADBD8", "Medium": "FEF9E7", "Low": "EAFAF1" };
  const severityFg = { "Critical": "C0392B", "Medium": "E67E22", "Low": "27AE60" };

  const dataRows = issues.map(([num, type, typeBg, typeFg, sev, title, file], i) =>
    new TableRow({
      children: [
        new TableCell({
          width: { size: 400, type: WidthType.DXA },
          borders: allBorders(C.grayBorder, 4),
          shading: { fill: i % 2 === 0 ? C.white : C.grayLight, type: ShadingType.CLEAR },
          margins: { top: 60, bottom: 60, left: 80, right: 80 },
          children: [para([run(num, { bold: true, size: 18, color: C.navy })], { alignment: AlignmentType.CENTER })]
        }),
        new TableCell({
          width: { size: 1200, type: WidthType.DXA },
          borders: allBorders(C.grayBorder, 4),
          shading: { fill: typeBg + "22", type: ShadingType.CLEAR },
          margins: { top: 60, bottom: 60, left: 80, right: 80 },
          children: [para([run(type, { bold: true, size: 17, color: typeBg })], { alignment: AlignmentType.CENTER })]
        }),
        new TableCell({
          width: { size: 900, type: WidthType.DXA },
          borders: allBorders(C.grayBorder, 4),
          shading: { fill: severityBg[sev], type: ShadingType.CLEAR },
          margins: { top: 60, bottom: 60, left: 80, right: 80 },
          children: [para([run(sev, { bold: true, size: 17, color: severityFg[sev] })], { alignment: AlignmentType.CENTER })]
        }),
        new TableCell({
          width: { size: 4460, type: WidthType.DXA },
          borders: allBorders(C.grayBorder, 4),
          shading: { fill: i % 2 === 0 ? C.white : C.grayLight, type: ShadingType.CLEAR },
          margins: { top: 60, bottom: 60, left: 100, right: 80 },
          children: [para([run(title, { size: 18, color: C.darkText })])]
        }),
        new TableCell({
          width: { size: 2400, type: WidthType.DXA },
          borders: allBorders(C.grayBorder, 4),
          shading: { fill: i % 2 === 0 ? C.white : C.grayLight, type: ShadingType.CLEAR },
          margins: { top: 60, bottom: 60, left: 100, right: 80 },
          children: [para([mono(file, { size: 17, color: C.navyLight })])]
        }),
      ]
    })
  );

  return new Table({
    width: { size: PAGE_W, type: WidthType.DXA },
    columnWidths: [400, 1200, 900, 4460, 2400],
    rows: [new TableRow({ children: headerCells }), ...dataRows]
  });
};

// ── Cover page ─────────────────────────────────────────────────────────
const coverPage = () => [
  emptyPara(1200),
  new Table({
    width: { size: PAGE_W, type: WidthType.DXA },
    columnWidths: [PAGE_W],
    rows: [new TableRow({
      children: [new TableCell({
        width: { size: PAGE_W, type: WidthType.DXA },
        borders: { ...noBorders(), bottom: { style: BorderStyle.SINGLE, size: 24, color: C.navy } },
        shading: { fill: C.white, type: ShadingType.CLEAR },
        margins: { top: 0, bottom: 240, left: 0, right: 0 },
        children: [
          para([run("Finance A/R System", { bold: true, size: 56, color: C.navy })]),
          para([run("Code Review & Bug Report", { size: 36, color: C.navyLight })]),
        ]
      })]
    })]
  }),
  emptyPara(200),
  para([run("Prepared for: Abdulrahman", { size: 22, color: C.gray })]),
  para([run("Date: " + new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' }), { size: 22, color: C.gray })]),
  para([run("Repository: abdo326c/Finance---A-R", { size: 22, color: C.gray })]),
  emptyPara(400),
  new Table({
    width: { size: PAGE_W, type: WidthType.DXA },
    columnWidths: [PAGE_W / 3, PAGE_W / 3, PAGE_W / 3],
    rows: [new TableRow({
      children: [
        ["6", "Bugs", C.red, C.redLight],
        ["5", "Security Issues", C.purple, C.purpleLight],
        ["7", "Improvements", C.blue, C.blueLight],
      ].map(([num, label, fg, bg]) => new TableCell({
        width: { size: PAGE_W / 3, type: WidthType.DXA },
        borders: allBorders(fg, 6),
        shading: { fill: bg, type: ShadingType.CLEAR },
        margins: { top: 160, bottom: 160, left: 120, right: 120 },
        children: [
          para([run(num, { bold: true, size: 72, color: fg })], { alignment: AlignmentType.CENTER }),
          para([run(label, { size: 22, color: fg })], { alignment: AlignmentType.CENTER }),
        ]
      }))
    })]
  }),
  para([new PageBreak()]),
];

// ── MAIN ───────────────────────────────────────────────────────────────
const doc = new Document({
  numbering: { config: [] },
  styles: {
    default: {
      document: { run: { font: "Arial", size: 22, color: C.darkText } }
    },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 36, bold: true, font: "Arial", color: C.navy },
        paragraph: { spacing: { before: 320, after: 160 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: "Arial", color: C.navyLight },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
    ]
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
      }
    },
    footers: {
      default: new Footer({
        children: [
          new Table({
            width: { size: PAGE_W, type: WidthType.DXA },
            columnWidths: [PAGE_W / 2, PAGE_W / 2],
            rows: [new TableRow({
              children: [
                new TableCell({
                  width: { size: PAGE_W / 2, type: WidthType.DXA },
                  borders: { ...noBorders(), top: border(C.grayBorder, 4) },
                  shading: { fill: C.white, type: ShadingType.CLEAR },
                  margins: { top: 80, bottom: 0, left: 0, right: 0 },
                  children: [para([run("Finance A/R — Code Review Report", { size: 16, color: C.gray })])]
                }),
                new TableCell({
                  width: { size: PAGE_W / 2, type: WidthType.DXA },
                  borders: { ...noBorders(), top: border(C.grayBorder, 4) },
                  shading: { fill: C.white, type: ShadingType.CLEAR },
                  margins: { top: 80, bottom: 0, left: 0, right: 0 },
                  children: [para([
                    run("Page ", { size: 16, color: C.gray }),
                  ], { alignment: AlignmentType.RIGHT })]
                }),
              ]
            })]
          })
        ]
      })
    },
    children: [
      ...coverPage(),

      // ── EXECUTIVE SUMMARY ────────────────────────────────────────────
      para(["Executive Summary"], { heading: HeadingLevel.HEADING_1 }),
      para([run("A full review of the Finance A/R codebase (repository: abdo326c/Finance---A-R) was conducted by reading every backend Python file and frontend TypeScript file. The system is a university Accounts Receivable platform built with FastAPI + SQLAlchemy (backend) and React + TypeScript (frontend), deployed on Vercel (frontend) and Render.com (backend) with a Supabase PostgreSQL database.", { size: 20 })],
        { spacing: { before: 0, after: 160 } }),
      para([run("The review identified 18 issues across four categories: bugs, security vulnerabilities, performance problems, and code quality improvements. Six issues are rated Critical and require immediate attention before the system handles sensitive student financial data in production.", { size: 20 })],
        { spacing: { before: 0, after: 200 } }),

      para(["Issue Summary Table"], { heading: HeadingLevel.HEADING_2 }),
      summaryTable(),
      para([new PageBreak()]),

      // ── SECTION 1: BUGS ──────────────────────────────────────────────
      ...sectionHeader("🐛", "Section 1 — Bugs", "Logic errors that cause incorrect behaviour, data loss, or crashes"),

      ...issueCard(
        1, "Critical", "Bug", "C0392B", "FFFFFF",
        "Ref counter race condition causes duplicate reference numbers",
        "backend/api/operations.py",
        "Inside process_transaction(), a ref counter sync runs before next_ref_block() is called. Under concurrent requests, two transactions can be assigned the same reference number, causing a unique constraint violation and a 500 Internal Server Error.",
        [
          "# Inside process_transaction() — runs every request:",
          "max_tx_id = db.query(func.max(Transaction.id)).scalar() or 0",
          "ref_row = db.get(RefCounter, 1)",
          "if ref_row and ref_row.seq <= max_tx_id:",
          "    ref_row.seq = max_tx_id + 500  # bumped here",
          "    db.flush()",
          "# Then next_ref_block() is called again — gap window exists",
        ],
        [
          "# In backend/models.py — run ONCE at startup:",
          "def sync_ref_counter(db):",
          '    """Called once at startup to align counter with actual max ID."""',
          "    max_id = db.query(func.max(Transaction.id)).scalar() or 0",
          "    row = db.get(RefCounter, 1)",
          "    if row and row.seq < max_id:",
          "        row.seq = max_id + 100",
          "        db.commit()",
          "",
          "# In backend/main.py startup_event — remove inline sync from operations.py",
          "@app.on_event('startup')",
          "def startup_event():",
          "    seed_default_users()",
          "    with SessionLocal() as db:",
          "        sync_ref_counter(db)  # add this",
        ],
        "Remove the inline ref-counter sync from process_transaction(). Move it to a startup-only function called once in main.py startup_event()."
      ),

      ...issueCard(
        2, "Critical", "Bug", "C0392B", "FFFFFF",
        "Stale lru_cache on get_static_lookups — new data never appears",
        "backend/models.py",
        "get_static_lookups() is decorated with @lru_cache(maxsize=1). It reads scholarship types, colleges, and years once at startup and caches forever. Adding a new scholarship type, college, or academic year via the Admin UI has no effect until the server is restarted.",
        [
          "@lru_cache(maxsize=1)",
          "def get_static_lookups():",
          "    # Reads DB once, then never refreshes",
          "    sch_map = {sch.name: sch.id for sch in s.query(ScholarshipType).all()}",
          "    colleges = [c[0] for c in s.query(Student.college).distinct()]",
          "    years    = [y[0] for y in s.query(Transaction.academic_year).distinct()]",
          "    return sch_map, colleges, years",
          "",
          "# Missing cache_clear() in:",
          "# - registration.py (after registering new students -> new colleges/years)",
          "# - bulk.py (after bulk invoices -> new years appear)",
        ],
        [
          "# In backend/api/registration.py — after db.commit():",
          "from models import get_static_lookups",
          "get_static_lookups.cache_clear()  # new college may have been added",
          "",
          "# In backend/api/bulk.py — after successful bulk upload commit:",
          "get_static_lookups.cache_clear()  # new years may appear from bulk invoices",
          "",
          "# In backend/api/lookups.py add_scholarship_type — already done correctly!",
          "# Confirm it exists:",
          "get_static_lookups.cache_clear()",
        ],
        "Add get_static_lookups.cache_clear() after every write that could create new colleges, years, or scholarship types: registration.py, bulk.py (on invoice upload success)."
      ),

      ...issueCard(
        3, "Medium", "Bug", "C0392B", "FFFFFF",
        "Bulk upload ref counter pre-allocation may be too small",
        "backend/api/bulk.py",
        "The bulk upload path pre-allocates total * 2 + 100 reference numbers. For students with multiple active scholarships, build_auto_discount_transactions() generates one SCH- ref per scholarship. A student with 4 scholarships produces 5 refs (1 INV + 4 SCH), not 2. For large files this causes the counter to run out mid-batch, producing reference number collisions and 500 errors.",
        [
          "# Pre-allocation assumes at most 1 discount per student:",
          "start = next_ref_block(db, total * 2 + 100)",
          "# Reality: a student with 4 active scholarships produces 5 refs",
          "# For 1000 students this may allocate ~2100 but need ~6000",
        ],
        [
          "# Query the actual maximum scholarship count per student for the term:",
          "from sqlalchemy import func",
          "max_schs = db.query(func.count(StudentScholarship.id)).filter(",
          "    StudentScholarship.term == term_v,",
          "    StudentScholarship.academic_year == year_v,",
          "    StudentScholarship.is_active == True",
          ").group_by(StudentScholarship.student_id).order_by(",
          "    func.count(StudentScholarship.id).desc()",
          ").limit(1).scalar() or 1",
          "",
          "# Use it in the pre-allocation:",
          "start = next_ref_block(db, total * (1 + max_schs) + 100)",
        ],
        "Before the main upload loop, query the maximum number of active scholarships any single student has for the given term/year. Use that to set the correct pre-allocation multiplier."
      ),

      ...issueCard(
        4, "Medium", "Bug", "C0392B", "FFFFFF",
        "internal_note exposed in statement Excel and JSON downloads",
        "backend/api/statement.py",
        "The internal_note field is intentionally excluded from the PDF statement (correct behaviour). However, the /statement/search JSON response and the /statement/excel download both include \"Internal Note\" in every row. If a staff member shares the Excel file with a student, private internal notes become visible.",
        [
          "# Both /search and /excel return internal_note unconditionally:",
          "results.append({",
          "    ...",
          '    "Internal Note": t.internal_note,  # exposed to all roles',
          "})",
        ],
        [
          "# Gate internal_note on user role in both endpoints:",
          "is_staff = current_user.role in ['Admin', 'Editor']",
          "",
          "row = {",
          '    "Student ID": s.id, "Name": s.name, ...',
          "    # Only include sensitive field for staff roles:",
          '    **( {"Internal Note": t.internal_note} if is_staff else {} )',
          "}",
          "results.append(row)",
        ],
        "Wrap internal_note in a role check. Only include it in search/Excel responses when current_user.role is Admin or Editor. Viewers see the field omitted entirely."
      ),

      ...issueCard(
        5, "Medium", "Bug", "C0392B", "FFFFFF",
        "Batch listing endpoints have no authentication guard",
        "backend/api/batches.py",
        "GET /api/batches/active and GET /api/batches/deleted both return full batch summaries including batch IDs, transaction types, record counts, and total debits/credits. Neither endpoint requires authentication. Any unauthenticated HTTP caller can enumerate all financial batch history.",
        [
          "# No current_user dependency — publicly accessible:",
          "@router.get('/active')",
          "async def get_active_batches(db: Session = Depends(get_db)):",
          "    ...",
          "",
          "@router.get('/deleted')",
          "async def get_deleted_batches(db: Session = Depends(get_db)):",
          "    ...",
        ],
        [
          "from api.auth import get_current_user",
          "",
          "@router.get('/active')",
          "async def get_active_batches(",
          "    current_user = Depends(get_current_user),  # add this",
          "    db: Session = Depends(get_db)",
          "):",
          "    ...",
          "",
          "@router.get('/deleted')",
          "async def get_deleted_batches(",
          "    current_user = Depends(get_current_user),  # add this",
          "    db: Session = Depends(get_db)",
          "):",
          "    ...",
        ],
        "Add current_user = Depends(get_current_user) to both get_active_batches and get_deleted_batches in batches.py."
      ),

      ...issueCard(
        6, "Low", "Bug", "C0392B", "FFFFFF",
        "Batch export endpoint has no authentication",
        "backend/api/batches.py",
        "GET /api/batches/export/{batch_id} returns a full Excel file of all transactions in a batch without requiring authentication. Batch IDs follow the predictable pattern BCH-YYMMDD-HHMMSS, making them guessable. Any external caller can download complete student financial records for any batch.",
        [
          "@router.get('/export/{batch_id}')",
          "async def export_batch(batch_id: str, db: Session = Depends(get_db)):",
          "    # No authentication — open to the public",
          "    ...",
        ],
        [
          "@router.get('/export/{batch_id}')",
          "async def export_batch(",
          "    batch_id: str,",
          "    current_user = Depends(get_current_user),  # add this",
          "    db: Session = Depends(get_db)",
          "):",
          "    ...",
        ],
        "Add current_user = Depends(get_current_user) to the export_batch endpoint. Consider also requiring Admin or Editor role for exports."
      ),

      para([new PageBreak()]),

      // ── SECTION 2: SECURITY ──────────────────────────────────────────
      ...sectionHeader("🔒", "Section 2 — Security Issues", "Vulnerabilities that expose data or allow unauthorised access"),

      ...issueCard(
        7, "Critical", "Security", "6C3483", "FFFFFF",
        "JWT_SECRET crashes server at startup if env var is missing",
        "backend/api/auth.py",
        "SECRET_KEY = os.environ[\"JWT_SECRET\"] raises a KeyError at import time if the environment variable is not set. This crashes the entire FastAPI server on boot with an unreadable traceback rather than a clear configuration error — making it hard to diagnose in a Render.com deployment.",
        [
          '# Raises KeyError at import time — server will not start:',
          'SECRET_KEY = os.environ["JWT_SECRET"]',
        ],
        [
          "import os",
          "",
          "SECRET_KEY = os.environ.get('JWT_SECRET')",
          "if not SECRET_KEY:",
          "    raise RuntimeError(",
          "        'JWT_SECRET environment variable is not set. '",
          "        'Add it to your Render environment variables before starting.'",
          "    )",
        ],
        "Use os.environ.get() and raise a RuntimeError with a clear human-readable message so deployment failures are immediately diagnosable."
      ),

      ...issueCard(
        8, "Critical", "Security", "6C3483", "FFFFFF",
        "Deactivated users retain valid token access for up to 7 days",
        "backend/api/auth.py",
        "Tokens have a 7-day lifetime (ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7). The get_current_user function verifies the token signature but does not check is_active. If an admin deactivates a user account, that user's existing token continues to grant full access for up to 7 days.",
        [
          "# get_current_user — only checks token validity, not is_active:",
          "user = db.query(SystemUser).filter(SystemUser.username == token_data.username).first()",
          "if user is None:",
          "    raise credentials_exception",
          "return user  # returns even if user.is_active is False",
        ],
        [
          "# Step 1 — check is_active on every request:",
          "user = db.query(SystemUser).filter(",
          "    SystemUser.username == token_data.username",
          ").first()",
          "if user is None or not user.is_active:  # add is_active check",
          "    raise credentials_exception",
          "",
          "# Step 2 — shorten token lifetime for production:",
          "ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8 hours, not 7 days",
        ],
        "Add not user.is_active to the check in get_current_user. This is a one-line fix. Also reduce token lifetime from 7 days to 8-24 hours for a production system handling financial data."
      ),

      ...issueCard(
        9, "Medium", "Security", "6C3483", "FFFFFF",
        "Default seed passwords are hardcoded — risky in production",
        "backend/models.py",
        "The seed_default_users() function falls back to the hardcoded password \"ChangeMe123!\" if SEED_ADMIN_PW or SEED_EDITOR_PW environment variables are not configured. If these env vars are accidentally omitted from the Render.com deployment, the admin account is created with a known public password with no warning.",
        [
          "def seed_default_users():",
          '    admin_pw = os.getenv("SEED_ADMIN_PW", "ChangeMe123!")  # dangerous fallback',
          '    editor_pw = os.getenv("SEED_EDITOR_PW", "ChangeMe123!")  # dangerous fallback',
          "    ...",
        ],
        [
          "def seed_default_users():",
          "    admin_pw = os.getenv('SEED_ADMIN_PW')",
          "    if not admin_pw:",
          "        print('WARNING: SEED_ADMIN_PW not set — skipping user seed.')",
          "        print('Set this env var on first deploy, then restart the service.')",
          "        return",
          "",
          "    editor_pw = os.getenv('SEED_EDITOR_PW')",
          "    if not editor_pw:",
          "        print('WARNING: SEED_EDITOR_PW not set — skipping user seed.')",
          "        return",
          "    # proceed with seeding...",
        ],
        "Remove hardcoded fallback passwords. If env vars are missing, skip seeding and print a clear warning. Document the required env vars in DEPLOYMENT_GUIDE.md."
      ),

      ...issueCard(
        10, "Medium", "Security", "6C3483", "FFFFFF",
        "finance.db database file committed to the GitHub repository",
        "backend/finance.db  /  .gitignore",
        "The file backend/finance.db (a SQLite database) and backend/finance_audit.log are present in the repository and are likely tracked by git. This exposes student names, IDs, transaction history, and bcrypt password hashes to anyone with repository access — even in a private repo, this is a serious data protection violation.",
        [
          "# finance.db and finance_audit.log are NOT in .gitignore",
          "# Anyone with repo access can run:",
          "#   sqlite3 backend/finance.db .dump",
          "# ... and read all student financial records and password hashes",
        ],
        [
          "# Step 1 — add to .gitignore:",
          "backend/finance.db",
          "backend/finance_audit.log",
          "backend/__pycache__/",
          "",
          "# Step 2 — remove from git tracking:",
          "git rm --cached backend/finance.db",
          "git rm --cached backend/finance_audit.log",
          'git commit -m "Remove sensitive database files from tracking"',
          "git push",
          "",
          "# Step 3 — if repo is public or was ever public:",
          "# Use BFG Repo Cleaner to purge from full git history:",
          "# https://rtyley.github.io/bfg-repo-cleaner/",
          "# bfg --delete-files finance.db",
        ],
        "Immediately add finance.db and finance_audit.log to .gitignore and remove them from git tracking. If the repo was ever public, use BFG Repo Cleaner to purge from full history. Rotate all credentials stored in the database."
      ),

      ...issueCard(
        11, "Low", "Security", "6C3483", "FFFFFF",
        "No rate limiting on the login endpoint — brute force possible",
        "backend/api/auth.py",
        "POST /api/auth/token accepts unlimited password attempts with no delay, lockout, or IP-based throttling. An attacker can systematically try passwords against any known username without restriction.",
        [
          "# No rate limiting — unlimited login attempts:",
          "@router.post('/token', response_model=Token)",
          "async def login_for_access_token(",
          "    form_data: OAuth2PasswordRequestForm = Depends(),",
          "    db: Session = Depends(get_db)",
          "):",
          "    ...",
        ],
        [
          "# Add slowapi to requirements.txt:",
          "# slowapi",
          "",
          "# In backend/main.py:",
          "from slowapi import Limiter, _rate_limit_exceeded_handler",
          "from slowapi.util import get_remote_address",
          "from slowapi.errors import RateLimitExceeded",
          "limiter = Limiter(key_func=get_remote_address)",
          "app.state.limiter = limiter",
          "app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)",
          "",
          "# In backend/api/auth.py:",
          "from main import limiter",
          "@router.post('/token')",
          "@limiter.limit('10/minute')",
          "async def login_for_access_token(request: Request, ...):",
          "    ...",
        ],
        "Install slowapi and apply a rate limit of 10 requests/minute per IP on the login endpoint. This is a small addition (two lines) that prevents automated brute-force attacks."
      ),

      para([new PageBreak()]),

      // ── SECTION 3: PERFORMANCE ───────────────────────────────────────
      ...sectionHeader("⚡", "Section 3 — Performance Issues", "Queries and patterns that will degrade significantly as data grows"),

      ...issueCard(
        12, "Medium", "Performance", "1565C0", "FFFFFF",
        "Correlated subqueries on student_statuses run once per student row",
        "backend/api/reports.py  /  backend/api/dashboard.py",
        "Multiple SQL queries use a correlated subquery pattern: (SELECT status FROM student_statuses WHERE student_id=s.id ORDER BY id DESC LIMIT 1). This nested SELECT executes once for every student row in the outer query. For 1,000 students this means 1,000 extra database round-trips inside a single report generation call — making reports increasingly slow as enrolment grows.",
        [
          "-- Runs once per student in the outer query (N+1 problem):",
          "SELECT s.id, s.name,",
          "    COALESCE(",
          "        (SELECT status FROM student_statuses",
          "         WHERE student_id=s.id ORDER BY id DESC LIMIT 1),",
          "        'Not Set'",
          "    ) AS status",
          "FROM students s",
          "-- For 1000 students: 1000 extra sub-SELECTs",
        ],
        [
          "-- Replace with a CTE that computes latest status once:",
          "WITH latest_status AS (",
          "    SELECT student_id,",
          "           status,",
          "           ROW_NUMBER() OVER (",
          "               PARTITION BY student_id ORDER BY id DESC",
          "           ) AS rn",
          "    FROM student_statuses",
          ")",
          "SELECT s.id, s.name,",
          "    COALESCE(ls.status, 'Not Set') AS status",
          "FROM students s",
          "LEFT JOIN latest_status ls",
          "    ON ls.student_id = s.id AND ls.rn = 1",
          "-- One scan of student_statuses — no per-row subqueries",
        ],
        "Refactor the correlated subquery into a CTE using ROW_NUMBER() OVER (PARTITION BY student_id ORDER BY id DESC). Apply this change in reports.py (3 occurrences) and dashboard.py (1 occurrence). Create a reusable latest_status CTE string constant."
      ),

      ...issueCard(
        13, "Low", "Performance", "1565C0", "FFFFFF",
        "Reconciliation analysis loads all transactions into Python memory",
        "backend/api/reconciliation.py",
        "The /reconciliation/analyze endpoint loads every Transaction and Student row for a given term/year into SQLAlchemy objects, then iterates them in Python to compute per-student charge/discount/payment totals. For a term with 2,000 students and 10 transactions each, this loads 20,000 ORM objects into RAM. The aggregation should be pushed to SQL.",
        [
          "# Loads all rows into Python memory:",
          "db_txs = (",
          "    db.query(Transaction, Student)",
          "    .join(Student, Transaction.student_id == Student.id)",
          "    .filter(Transaction.term == target_term,",
          "            Transaction.academic_year == target_year)",
          "    .all()  # N objects in RAM",
          ")",
          "for tx, student in db_txs:",
          "    local_students[sid]['charges'] += float(tx.debit)",
          "    ...",
        ],
        [
          "# Push grouping to SQL — returns one row per student:",
          "sql = text('''",
          "    SELECT s.id AS student_id, s.name,",
          "        COALESCE(SUM(CASE",
          "            WHEN t.transaction_type IN ('Invoice','Bulk Invoices (Tuition)')",
          "            THEN t.debit ELSE 0 END), 0) AS charges,",
          "        COALESCE(SUM(CASE",
          "            WHEN t.transaction_type IN ('Discount','Bulk Scholarships')",
          "            THEN t.credit - t.debit ELSE 0 END), 0) AS discounts,",
          "        COALESCE(SUM(CASE",
          "            WHEN t.transaction_type IN ('Payment Receipt','Bulk Payments')",
          "            THEN t.credit - t.debit ELSE 0 END), 0) AS payments",
          "    FROM students s",
          "    LEFT JOIN transactions t ON t.student_id = s.id",
          "        AND t.term = :term AND t.academic_year = :year",
          "    GROUP BY s.id, s.name",
          "''')",
          "rows = db.execute(sql, {'term': target_term, 'year': target_year}).fetchall()",
        ],
        "Replace the in-Python aggregation loop with a single GROUP BY SQL query. This reduces memory usage from O(N transactions) to O(N students) and is typically 10x faster."
      ),

      para([new PageBreak()]),

      // ── SECTION 4: CODE QUALITY ──────────────────────────────────────
      ...sectionHeader("🔧", "Section 4 — Code Quality & Refactoring", "Issues that cause subtle bugs or make maintenance harder"),

      ...issueCard(
        14, "Low", "Refactor", "1E7A45", "FFFFFF",
        "Inconsistent transaction type names cause missed records in reports",
        "backend/api/operations.py  /  backend/api/bulk.py  /  backend/api/reports.py",
        "The same transaction category is stored under different string values in different parts of the codebase. Reports filter for both names, but any future code that forgets the variant will silently miss records. This is a latent data integrity bug.",
        [
          "# operations.py stores:       'Credit Hours Adjustment'",
          "# bulk.py stores:             'Credit Hours Adjustments'  (plural)",
          "# reports.py filters for both (workaround):",
          "transaction_type.in_(['Credit Hours Adjustment','Credit Hours Adjustments',",
          "                       'General Adjustment','General Adjustments'])",
          "",
          "# reconciliation.py uses yet another variant: 'Adjustment'",
          "# d365.py checks for: 'Adjustment', 'Bulk Adjustments'",
        ],
        [
          "# Create backend/constants.py:",
          "TX_INVOICE         = 'Invoice'",
          "TX_BULK_INVOICE    = 'Bulk Invoices (Tuition)'",
          "TX_PAYMENT         = 'Payment Receipt'",
          "TX_BULK_PAYMENT    = 'Bulk Payments'",
          "TX_DISCOUNT        = 'Discount'",
          "TX_BULK_DISCOUNT   = 'Bulk Scholarships'",
          "TX_ADJ_HOURS       = 'Credit Hours Adjustment'",
          "TX_BULK_ADJ_HOURS  = 'Credit Hours Adjustments'",
          "TX_OTHER_FEE       = 'Other Fees'",
          "TX_BULK_OTHER_FEE  = 'Bulk Other Fees'",
          "TX_GENERAL_ADJ     = 'General Adjustment'",
          "",
          "# Import and use everywhere instead of raw strings",
          "from constants import TX_INVOICE, TX_PAYMENT, ...",
        ],
        "Create backend/constants.py with all canonical transaction type names. Import and use these constants everywhere. Run a one-time migration to normalise any plural variants already stored in the database."
      ),

      ...issueCard(
        15, "Medium", "UX", "B7770D", "FFFFFF",
        "Password change does not invalidate existing sessions",
        "backend/api/auth.py",
        "When a user changes their password via POST /api/auth/change-password, all existing JWT tokens for that user remain valid for up to 7 days. An admin resetting a compromised account's password cannot immediately revoke that user's active sessions — the attacker retains access.",
        [
          "# change_password() updates the hash but tokens stay valid:",
          "user.password_hash = hash_pw(req.new_password)",
          "db.commit()",
          "# Existing tokens are still accepted by get_current_user()",
          "# because they have a valid signature and non-expired exp",
        ],
        [
          "# Step 1 — add password_changed_at to SystemUser in models.py:",
          "from sqlalchemy import DateTime",
          "from sqlalchemy.sql import func",
          "password_changed_at = Column(DateTime, server_default=func.now())",
          "",
          "# Step 2 — stamp it on password change in auth.py:",
          "user.password_hash = hash_pw(req.new_password)",
          "user.password_changed_at = datetime.now(timezone.utc)",
          "db.commit()",
          "",
          "# Step 3 — check in get_current_user:",
          "payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])",
          "iat = datetime.fromtimestamp(payload.get('iat', 0), tz=timezone.utc)",
          "if user.password_changed_at and iat < user.password_changed_at:",
          "    raise credentials_exception  # token predates password change",
        ],
        "Add a password_changed_at DateTime column to SystemUser. Update it on every password change. In get_current_user, compare the token's iat claim against this timestamp and reject tokens issued before the password was changed."
      ),

      ...issueCard(
        16, "Low", "UX", "B7770D", "FFFFFF",
        "Audit log capped at 500 rows with no pagination or filtering",
        "backend/api/admin.py",
        "The GET /api/admin/audit-logs endpoint returns only the most recent 500 entries using .limit(500). On an active system, entries older than the most recent 500 are permanently inaccessible through the Admin UI. There is no pagination, date range filter, or action type filter.",
        [
          "@router.get('/audit-logs')",
          "async def get_audit_logs(current_user, db):",
          "    logs = db.query(AuditLog)",
          "        .order_by(AuditLog.created_at.desc())",
          "        .limit(500)  # hard cap — older entries invisible",
          "        .all()",
          "    return [...]",
        ],
        [
          "from typing import Optional",
          "",
          "@router.get('/audit-logs')",
          "async def get_audit_logs(",
          "    page: int = 1,",
          "    limit: int = 100,",
          "    action: Optional[str] = None,",
          "    username: Optional[str] = None,",
          "    current_user = Depends(get_current_user),",
          "    db: Session = Depends(get_db)",
          "):",
          "    if current_user.role != 'Admin':",
          "        raise HTTPException(status_code=403, ...)",
          "    q = db.query(AuditLog).order_by(AuditLog.created_at.desc())",
          "    if action:   q = q.filter(AuditLog.action == action)",
          "    if username: q = q.filter(AuditLog.username == username)",
          "    total = q.count()",
          "    logs = q.offset((page - 1) * limit).limit(limit).all()",
          "    return {'total': total, 'page': page, 'limit': limit, 'data': [...]}",
        ],
        "Replace the hard .limit(500) with proper pagination (page + limit query params). Add optional filters for action and username. Return total count so the frontend can show page navigation."
      ),

      ...issueCard(
        17, "Low", "Refactor", "1E7A45", "FFFFFF",
        "Config format mismatch between config.py and lookups.py",
        "backend/config.py  /  backend/api/lookups.py",
        "get_dynamic_configs() in config.py reads stored config values and parses them with .split(',') (comma-separated). The update_lookup() endpoint in lookups.py writes config values using json.dumps() (JSON array format). If you update any config value through the Admin UI, get_dynamic_configs() will misparse it — for example '[\"Fall\",\"Spring\"]' split by comma becomes ['[\"Fall\"', '\"Spring\"]'] instead of ['Fall', 'Spring'].",
        [
          "# config.py reads with comma-split:",
          "VALID_TERMS = [t.strip() for t in configs['VALID_TERMS'].split(',')]",
          "# Result if stored as JSON: ['[\"Fall\"', '\"Spring\"', '\"Summer\"]']  -- WRONG",
          "",
          "# lookups.py writes as JSON:",
          "new_value = json.dumps(data.values)  # stores '[\"Fall\",\"Spring\",\"Summer\"]'",
        ],
        [
          "# config.py — parse as JSON first, fall back to comma-split for legacy:",
          "import json",
          "",
          "def _parse_list(raw: str) -> list:",
          "    try:",
          "        val = json.loads(raw)",
          "        if isinstance(val, list):",
          "            return val",
          "    except (json.JSONDecodeError, TypeError):",
          "        pass",
          "    return [v.strip() for v in raw.split(',') if v.strip()]",
          "",
          "# Use in get_dynamic_configs():",
          "VALID_TERMS    = _parse_list(configs['VALID_TERMS'])",
          "VALID_STATUSES = _parse_list(configs['VALID_STATUSES'])",
          "VALID_COLLEGES = _parse_list(configs['VALID_COLLEGES'])",
        ],
        "Add a _parse_list() helper in config.py that tries JSON parsing first and falls back to comma-split for legacy seed data. This makes both old and new stored formats work correctly."
      ),

      ...issueCard(
        18, "Low", "Refactor", "1E7A45", "FFFFFF",
        "Audit log file path is relative — silent failure on Render.com",
        "backend/models.py",
        "The audit log is written to \"finance_audit.log\" (a relative path). On Render.com's free tier the working directory may not be writable, and the file will not persist across deploys (Render uses ephemeral disk). The log handler will fail silently or fill up temporary storage.",
        [
          "# Relative path — breaks in cloud deployments:",
          "logHandler = logging.FileHandler('finance_audit.log')",
          "# On Render: file written to /tmp or fails silently",
          "# File lost on every redeploy",
        ],
        [
          "import os, logging",
          "",
          "# Make path configurable via env var; default to stdout for cloud:",
          "AUDIT_LOG_PATH = os.getenv('AUDIT_LOG_PATH', None)",
          "",
          "if AUDIT_LOG_PATH:",
          "    log_handler = logging.FileHandler(AUDIT_LOG_PATH)",
          "else:",
          "    # On Render: logs go to stdout and are captured by the dashboard",
          "    log_handler = logging.StreamHandler()",
          "",
          "formatter = jsonlogger.JsonFormatter(",
          "    '%(asctime)s %(levelname)s %(name)s %(message)s'",
          ")",
          "log_handler.setFormatter(formatter)",
          "audit_logger.addHandler(log_handler)",
        ],
        "Make the audit log destination configurable via the AUDIT_LOG_PATH environment variable. When the variable is not set, default to stdout so logs are captured by Render's log stream. Document this in DEPLOYMENT_GUIDE.md."
      ),

      // ── CLOSING ──────────────────────────────────────────────────────
      para([new PageBreak()]),
      para(["Remediation Priority"], { heading: HeadingLevel.HEADING_1 }),
      para([run("Address issues in the following order:", { size: 20 })], { spacing: { before: 0, after: 160 } }),

      new Table({
        width: { size: PAGE_W, type: WidthType.DXA },
        columnWidths: [700, 1600, PAGE_W - 700 - 1600],
        rows: [
          new TableRow({
            children: [
              new TableCell({ width: { size: 700, type: WidthType.DXA }, borders: allBorders(C.navy, 4), shading: { fill: C.navy, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, children: [para([run("Priority", { bold: true, size: 18, color: C.white })], { alignment: AlignmentType.CENTER })] }),
              new TableCell({ width: { size: 1600, type: WidthType.DXA }, borders: allBorders(C.navy, 4), shading: { fill: C.navy, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, children: [para([run("Issues", { bold: true, size: 18, color: C.white })], { alignment: AlignmentType.CENTER })] }),
              new TableCell({ width: { size: PAGE_W - 700 - 1600, type: WidthType.DXA }, borders: allBorders(C.navy, 4), shading: { fill: C.navy, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, children: [para([run("Reason", { bold: true, size: 18, color: C.white })], { alignment: AlignmentType.CENTER })] }),
            ]
          }),
          ...[
            ["1 — Do now", "#10: Remove finance.db from git\n#7: Fix JWT_SECRET startup crash\n#8: Add is_active token check\n#5 & #6: Add batch auth guards", "Data exposure and complete service outage risk"],
            ["2 — This week", "#1: Fix ref counter race\n#2: Fix stale cache\n#4: Gate internal_note by role\n#9: Remove hardcoded passwords\n#15: Invalidate tokens on password change", "Data integrity and access control"],
            ["3 — Next sprint", "#11: Add login rate limiting\n#3: Fix bulk ref allocation\n#12: Fix correlated subqueries\n#17: Fix config format mismatch", "Security hardening and performance at scale"],
            ["4 — Backlog", "#13: Reconciliation SQL refactor\n#14: Create constants.py\n#16: Audit log pagination\n#18: Fix audit log path", "Code quality and operational stability"],
          ].map(([priority, issues, reason], i) => new TableRow({
            children: [
              new TableCell({ width: { size: 700, type: WidthType.DXA }, borders: allBorders(C.grayBorder, 4), shading: { fill: i % 2 === 0 ? C.white : C.grayLight, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, children: [para([run(priority, { bold: true, size: 18, color: C.navy })])] }),
              new TableCell({ width: { size: 1600, type: WidthType.DXA }, borders: allBorders(C.grayBorder, 4), shading: { fill: i % 2 === 0 ? C.white : C.grayLight, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, children: issues.split('\n').map(line => para([mono(line, { size: 17, color: C.navyLight })], { spacing: { before: 20, after: 20 } })) }),
              new TableCell({ width: { size: PAGE_W - 700 - 1600, type: WidthType.DXA }, borders: allBorders(C.grayBorder, 4), shading: { fill: i % 2 === 0 ? C.white : C.grayLight, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, children: [para([run(reason, { size: 18, color: C.darkText })])] }),
            ]
          }))
        ]
      }),

      emptyPara(200),
      para([run("End of Report", { bold: true, size: 20, color: C.gray })], { alignment: AlignmentType.CENTER }),
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("/mnt/user-data/outputs/Finance_AR_Bug_Report.docx", buffer);
  console.log("Done.");
});
