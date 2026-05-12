const fs = require("fs");
const path = require("path");

const PptxGenJS = require("pptxgenjs");
const sharp = require("sharp");
const { imageSizingContain } = require("./pptxgenjs_helpers/image");
const {
  warnIfSlideHasOverlaps,
  warnIfSlideElementsOutOfBounds,
} = require("./pptxgenjs_helpers/layout");

const ROOT = path.resolve(__dirname, "../../..");
const REPORT_DIR = path.join(ROOT, "docs/report");
const ASSET_DIR = path.join(REPORT_DIR, "assets");
const OUT = path.join(REPORT_DIR, "presentation.pptx");

const W = 13.333;
const H = 7.5;
const COLORS = {
  navy: "1F4E79",
  blue: "2E75B6",
  green: "2F6F3E",
  amber: "A66A00",
  red: "9B1C1C",
  ink: "111827",
  muted: "5B6472",
  line: "D6DAE0",
  softBlue: "EAF2F8",
  softGreen: "E8F4EA",
  softAmber: "FFF3D6",
  softRed: "FDECEC",
  pale: "F7F9FB",
};

const diagrams = {
  application: "application_architecture",
  technical: "technical_architecture",
  langgraph: "langgraph_flow",
  guardrail: "llm_reviewer_guardrail",
  evidence: "evidence_to_report",
  gradio: "gradio_boundary",
};

async function ensurePngAssets() {
  for (const name of Object.values(diagrams)) {
    const svg = path.join(ASSET_DIR, `${name}.svg`);
    const png = path.join(ASSET_DIR, `${name}.png`);
    const cleanSvg = path.join(ASSET_DIR, `${name}_clean.svg`);
    if (!fs.existsSync(svg)) {
      throw new Error(`Missing Mermaid SVG: ${svg}`);
    }
    fs.writeFileSync(cleanSvg, sanitizeMermaidSvg(fs.readFileSync(svg, "utf8")));
    await sharp(cleanSvg, { density: 220 })
      .resize({ width: 2200, withoutEnlargement: true })
      .png()
      .toFile(png);
  }
}

function sanitizeMermaidSvg(svg) {
  return svg
    .replace(/var\(--_group-fill\)/g, "#FFFFFF")
    .replace(/var\(--_group-hdr\)/g, "#F7F9FB")
    .replace(/var\(--_node-fill\)/g, "#F7F9FB")
    .replace(/var\(--_node-stroke\)/g, "#D6DAE0")
    .replace(/var\(--_inner-stroke\)/g, "#D6DAE0")
    .replace(/var\(--_line\)/g, "#6B7280")
    .replace(/var\(--_arrow\)/g, "#2E75B6")
    .replace(/var\(--_text-sec\)/g, "#5B6472")
    .replace(/var\(--_text-muted\)/g, "#6B7280")
    .replace(/var\(--_text-faint\)/g, "#9CA3AF")
    .replace(/var\(--_text\)/g, "#111827")
    .replace(/color-mix\([^)]*\)/g, "#F7F9FB");
}

function addTitle(slide, title) {
  slide.addText(title, {
    x: 0.55,
    y: 0.28,
    w: 12.2,
    h: 0.48,
    fontFace: "Arial",
    fontSize: 22,
    bold: true,
    color: COLORS.ink,
    margin: 0,
    breakLine: false,
    fit: "shrink",
  });
  slide.addShape(pptx.ShapeType.line, {
    x: 0.55,
    y: 0.88,
    w: 12.2,
    h: 0,
    line: { color: COLORS.line, width: 0.8 },
  });
}

function addFooter(slide, n) {
  slide.addText("breeding-agent | 谷子多组学育种 workflow", {
    x: 0.55,
    y: 7.18,
    w: 5.2,
    h: 0.18,
    fontFace: "Arial",
    fontSize: 7.8,
    color: COLORS.muted,
    margin: 0,
  });
  slide.addText(String(n).padStart(2, "0"), {
    x: 12.25,
    y: 7.14,
    w: 0.5,
    h: 0.22,
    fontFace: "Arial",
    fontSize: 8.5,
    color: COLORS.muted,
    align: "right",
    margin: 0,
  });
}

function bulletRuns(items) {
  return items.flatMap((text, idx) => [
    {
      text,
      options: {
        bullet: { type: "ul" },
        breakLine: idx < items.length - 1,
      },
    },
  ]);
}

function addBullets(slide, items, x, y, w, h, opts = {}) {
  slide.addText(bulletRuns(items), {
    x,
    y,
    w,
    h,
    fontFace: "Arial",
    fontSize: opts.fontSize || 15,
    color: COLORS.ink,
    breakLine: false,
    paraSpaceAfterPt: 8,
    valign: "top",
    fit: "shrink",
    margin: 0.02,
  });
}

function addSource(slide, text) {
  slide.addText(text, {
    x: 0.55,
    y: 6.88,
    w: 11.5,
    h: 0.16,
    fontFace: "Arial",
    fontSize: 7.5,
    color: COLORS.muted,
    margin: 0,
    fit: "shrink",
  });
}

function addImageContain(slide, file, x, y, w, h) {
  const imagePath = path.join(ASSET_DIR, file);
  slide.addImage({ path: imagePath, ...imageSizingContain(imagePath, x, y, w, h) });
}

function addTag(slide, text, x, y, color, fill) {
  slide.addShape(pptx.ShapeType.roundRect, {
    x,
    y,
    w: 1.75,
    h: 0.34,
    rectRadius: 0.04,
    fill: { color: fill },
    line: { color, width: 0.8 },
  });
  slide.addText(text, {
    x: x + 0.08,
    y: y + 0.08,
    w: 1.59,
    h: 0.13,
    fontFace: "Arial",
    fontSize: 8.5,
    bold: true,
    color,
    align: "center",
    margin: 0,
  });
}

function addMiniMetric(slide, label, value, detail, x, y, color) {
  slide.addShape(pptx.ShapeType.rect, {
    x,
    y,
    w: 3.85,
    h: 1.22,
    fill: { color: "FFFFFF" },
    line: { color: COLORS.line, width: 1 },
  });
  slide.addText(label, {
    x: x + 0.18,
    y: y + 0.16,
    w: 3.45,
    h: 0.18,
    fontFace: "Arial",
    fontSize: 9.5,
    bold: true,
    color,
    margin: 0,
  });
  slide.addText(value, {
    x: x + 0.18,
    y: y + 0.43,
    w: 3.45,
    h: 0.28,
    fontFace: "Arial",
    fontSize: 16,
    bold: true,
    color: COLORS.ink,
    margin: 0,
  });
  slide.addText(detail, {
    x: x + 0.18,
    y: y + 0.82,
    w: 3.45,
    h: 0.23,
    fontFace: "Arial",
    fontSize: 8.6,
    color: COLORS.muted,
    margin: 0,
    fit: "shrink",
  });
}

function addSimpleTable(slide, rows, x, y, colWs, rowH) {
  rows.forEach((row, r) => {
    let cx = x;
    row.forEach((cell, c) => {
      slide.addText(cell, {
        x: cx,
        y: y + r * rowH,
        w: colWs[c],
        h: rowH,
        fontFace: "Arial",
        fontSize: r === 0 ? 9.4 : 9.2,
        bold: r === 0 || c === 0,
        color: r === 0 ? COLORS.navy : COLORS.ink,
        fill: { color: r === 0 ? COLORS.softBlue : "FFFFFF" },
        line: { color: COLORS.line, width: 0.55 },
        margin: 0.06,
        valign: "mid",
        fit: "shrink",
      });
      cx += colWs[c];
    });
  });
}

function addMaturityRow(slide, y, item, status, boundary, color, fill) {
  slide.addText(item, {
    x: 0.75,
    y,
    w: 2.25,
    h: 0.26,
    fontFace: "Arial",
    fontSize: 13,
    bold: true,
    color: COLORS.ink,
    margin: 0,
  });
  addTag(slide, status, 3.08, y - 0.03, color, fill);
  slide.addText(boundary, {
    x: 5.1,
    y,
    w: 6.95,
    h: 0.28,
    fontFace: "Arial",
    fontSize: 12.2,
    color: COLORS.ink,
    margin: 0,
    fit: "shrink",
  });
}

const pptx = new PptxGenJS();
pptx.layout = "LAYOUT_WIDE";
pptx.author = "breeding-agent";
pptx.subject = "Reproducible crop multi-omics breeding workflow";
pptx.title = "breeding-agent 组会汇报";
pptx.company = "breeding-agent";
pptx.lang = "zh-CN";
pptx.theme = {
  headFontFace: "Arial",
  bodyFontFace: "Arial",
  lang: "zh-CN",
};
pptx.defineLayout({ name: "LAYOUT_WIDE", width: W, height: H });

function addSlide(title) {
  const slide = pptx.addSlide();
  slide.background = { color: "FFFFFF" };
  addTitle(slide, title);
  addFooter(slide, pptx._slides.length);
  return slide;
}

async function build() {
  await ensurePngAssets();

  let slide = addSlide("项目当前能本地生成候选标记建议，但不输出最终实验标记");
  addImageContain(slide, "application_architecture.png", 0.55, 1.05, 8.5, 5.55);
  addBullets(
    slide,
    [
      "研究对象固定为谷子黄酮相关候选标记推荐。",
      "默认读取本地文件，不调用外部 API。",
      "输出是候选建议、报告和验证计划，不是最终 KASP/CAPS 标记。",
    ],
    9.25,
    1.25,
    3.35,
    2.2,
    { fontSize: 14 }
  );
  addTag(slide, "Local inputs", 9.25, 3.95, COLORS.navy, COLORS.softBlue);
  addTag(slide, "Candidate output", 9.25, 4.4, COLORS.green, COLORS.softGreen);
  addSource(slide, "Source: docs/architecture_overview.md, AGENTS.md");

  slide = addSlide("代码层把数据处理、Agent 编排、QA 和展示分开实现");
  addImageContain(slide, "technical_architecture.png", 0.68, 1.0, 7.65, 5.6);
  addBullets(
    slide,
    [
      "integration/ 聚合 evidence 并生成候选表。",
      "graphs/ 承载 LangGraph 主线多 Agent 编排。",
      "llm/ 只服务 ReviewerAgent 的可选审阅增强。",
      "FinalQAAgent 和 output_guard 负责发布前检查。",
    ],
    8.65,
    1.18,
    3.85,
    3.35,
    { fontSize: 13.4 }
  );
  addTag(slide, "Backend modules", 8.65, 4.9, COLORS.navy, COLORS.softBlue);
  addTag(slide, "Display only UI", 10.62, 4.9, COLORS.red, COLORS.softRed);
  addSource(slide, "Source: docs/code_reading_guide.md, docs/architecture_overview.md");

  slide = addSlide("学长 mini 数据包先转换为标准 evidence，再进入报告生成");
  addImageContain(slide, "evidence_to_report.png", 0.72, 1.02, 7.55, 5.74);
  addBullets(
    slide,
    [
      "转录组：bam/ 中所有文件；代谢组：metabolome_raw_3372.tsv。",
      "基因组：genome.fa + genome.gff；注释：local_region_emapper_annotations.tsv。",
      "文献证据只读取已验证 DOI，不新增 DOI。",
      "variant_status=not_called 时不写具体 SNP/InDel 位置。",
    ],
    8.55,
    1.25,
    3.9,
    3.1,
    { fontSize: 13.6 }
  );
  addSource(slide, "Source: scripts/demo/create_flavonoid_marker_evidence_from_package.py, docs/flavonoid_marker_aggregation_usage.md");

  slide = addSlide("三个高优先基因已有统计证据，但还不是育种验证结论");
  const tableRows = [
    ["gene_id", "log2FC", "padj", "Direction", "top metabolite r"],
    ["Si9g04210.1", "-6.5426", "5.62e-158", "Green higher", "-0.9958"],
    ["Si5g31340.1", "1.5744", "4.71e-07", "Golden higher", "0.9888"],
    ["Si9g34380.1", "3.2050", "8.95e-14", "Golden higher", "0.9955"],
  ];
  addSimpleTable(slide, tableRows, 0.72, 1.18, [1.72, 1.12, 1.32, 1.78, 1.36], 0.45);
  addMiniMetric(slide, "Si9g04210.1", "baseMean 3234.58", "Green_mean 6401.01 vs Golden_mean 68.15", 0.72, 3.45, COLORS.navy);
  addMiniMetric(slide, "Si5g31340.1", "baseMean 173.00", "Green_mean 86.85 vs Golden_mean 259.16", 4.72, 3.45, COLORS.green);
  addMiniMetric(slide, "Si9g34380.1", "baseMean 73.05", "Green_mean 14.38 vs Golden_mean 131.71", 8.72, 3.45, COLORS.amber);
  addBullets(
    slide,
    ["这些值是 package-derived evidence。", "仍需更大群体的基因型和黄酮含量数据验证关联。"],
    8.72,
    1.25,
    3.55,
    1.25,
    { fontSize: 13.4 }
  );
  addSource(slide, "Source: AGENTS.md fixed mini-evidence statistics");

  slide = addSlide("规则化 aggregation 只给候选标记类型建议，不写最终标记结论");
  addImageContain(slide, "evidence_to_report.png", 0.72, 1.05, 6.4, 5.45);
  addBullets(
    slide,
    [
      "聚合 transcriptomics、metabolomics、annotation、literature 和 variant evidence。",
      "SNP/InDel/KASP/CAPS 是候选类型建议；KASP/CAPS 表只是 preliminary screening。",
      "核心建议必须保留“群体”：围绕三个基因开发候选 SNP/InDel/KASP 标记，再用更大群体数据验证关联。",
    ],
    7.52,
    1.24,
    4.85,
    3.15,
    { fontSize: 13.6 }
  );
  addTag(slide, "No fabricated DOI", 7.52, 4.85, COLORS.red, COLORS.softRed);
  addTag(slide, "No fabricated variants", 9.5, 4.85, COLORS.red, COLORS.softRed);
  addSource(slide, "Source: src/breeding_agent/integration/flavonoid_marker_qa.py, docs/flavonoid_marker_aggregation_usage.md");

  slide = addSlide("LangGraph 是主线多 Agent 编排层，默认仍运行规则 Agent");
  addImageContain(slide, "langgraph_flow.png", 0.62, 1.0, 11.95, 4.6);
  addBullets(
    slide,
    [
      "LangGraph 负责 workflow / agent graph 编排，不承担模型推理。",
      "每个 node 记录 trace、warnings、limitations 和 passed 状态。",
      "Deep Agents 是并行 POC，不替代 LangGraph。",
    ],
    0.78,
    5.82,
    11.5,
    0.82,
    { fontSize: 12.6 }
  );
  addSource(slide, "Source: docs/langgraph_flavonoid_marker_workflow.md, src/breeding_agent/graphs/flavonoid_marker_graph.py");

  slide = addSlide("LLM 目前只增强 ReviewerAgent，OutputGuard 和 FinalQAAgent 拦截风险");
  addImageContain(slide, "llm_reviewer_guardrail.png", 0.6, 1.0, 7.85, 5.55);
  addBullets(
    slide,
    [
      "只有 reviewer_agent_node 可选调用本地 OpenAI-compatible LLM。",
      "模型只增强 reviewer notes，不直接生成 SNP/InDel/KASP/CAPS 结论。",
      "OutputGuard 拦截伪造 DOI、伪造位点、LowQual 优先化和过度 KASP/CAPS 表述。",
      "失败、空输出或 guard 不通过时回退到规则 ReviewerAgent，再进入 FinalQAAgent。",
    ],
    8.75,
    1.2,
    3.75,
    3.65,
    { fontSize: 13.3 }
  );
  addTag(slide, "enable_thinking=false", 8.75, 5.15, COLORS.navy, COLORS.softBlue);
  addSource(slide, "Source: docs/local_llm_reviewer_agent.md, src/breeding_agent/llm/output_guard.py");

  slide = addSlide("候选区域 variant calling 提供初筛证据，不能替代 WGS/GBS 群体验证");
  addShapeColumn(slide, 0.78, 1.22, "Candidate region calling", ["samtools / bcftools", "真实 VCF 位点进入候选表", "PASS / LowQual 分层"], COLORS.navy, COLORS.softBlue);
  addShapeColumn(slide, 4.8, 1.22, "Marker screening", ["PASS SNP 可复核 KASP 潜力", "CAPS 仍需酶切位点筛查", "LowQual 只保留可追溯记录"], COLORS.green, COLORS.softGreen);
  addShapeColumn(slide, 8.82, 1.22, "Validation still needed", ["WGS/GBS 群体变异 calling", "基因型-黄酮含量关联", "qRT-PCR / LC-MS/MS / Sanger"], COLORS.amber, COLORS.softAmber);
  slide.addText("当前边界：候选区域 MVP 输出是初筛证据，不是群体验证结果。", {
    x: 1.0,
    y: 5.64,
    w: 11.2,
    h: 0.34,
    fontFace: "Arial",
    fontSize: 14,
    bold: true,
    color: COLORS.red,
    align: "center",
    margin: 0,
  });
  addSource(slide, "Source: docs/genomics_variant_calling_usage.md");

  slide = addSlide("Gradio 只负责展示和触发，不承载核心 evidence 逻辑");
  addImageContain(slide, "gradio_boundary.png", 0.72, 1.05, 7.15, 5.45);
  addBullets(
    slide,
    [
      "Gradio 展示 RNA-seq、代谢组、基因组、integration 和黄酮推荐结果。",
      "核心逻辑留在 workflows、integration、agents 和 graphs。",
      "可展示 LLM reviewer 状态，但不展示本地配置文件内容。",
    ],
    8.2,
    1.35,
    4.05,
    2.6,
    { fontSize: 13.6 }
  );
  addTag(slide, "Display layer", 8.2, 4.55, COLORS.navy, COLORS.softBlue);
  addTag(slide, "Workflow trigger", 10.18, 4.55, COLORS.green, COLORS.softGreen);
  addSource(slide, "Source: docs/gradio_demo_usage.md, src/breeding_agent/web/gradio_app.py");

  slide = addSlide("Deep Agents、Lobster-style benchmark 和 Promoter Design 都保持 POC / scaffold 边界");
  addMaturityRow(slide, 1.34, "Deep Agents", "POC", "复用规则 agents；不调用真实 LLM；不替代 LangGraph。", COLORS.amber, COLORS.softAmber);
  addMaturityRow(slide, 2.25, "Lobster-style", "Reference", "不是真实 Lobster AI run；只做外部范式对照。", COLORS.red, COLORS.softRed);
  addMaturityRow(slide, 3.16, "Promoter Design", "Scaffold", "只定义 schema、数据盘点和占位输出；不生成真实 promoter sequence。", COLORS.red, COLORS.softRed);
  addMaturityRow(slide, 4.07, "Final reports", "Guarded", "manifest、QA 和 reviewer notes 保留边界说明。", COLORS.green, COLORS.softGreen);
  addBullets(
    slide,
    ["这些模块可作为后续扩展入口，但当前组会不能写成真实集成或实验验证已经完成。"],
    1.0,
    5.45,
    11.2,
    0.5,
    { fontSize: 13 }
  );
  addSource(slide, "Source: docs/deepagents_flavonoid_marker_poc.md, docs/lobster_external_agent_benchmark.md, docs/promoter_design_task.md");

  slide = addSlide("下一阶段应优先补候选位点复核和群体验证证据");
  addRoadmap(slide);
  addBullets(
    slide,
    [
      "先复核 PASS SNP/InDel 的 coverage、flanking sequence 和转化潜力。",
      "再扩展 WGS/GBS 群体变异 calling，与黄酮含量做关联验证。",
      "报告发布前继续保留 OutputGuard、FinalQAAgent 和人工 review。",
    ],
    1.0,
    5.58,
    11.2,
    0.85,
    { fontSize: 12.8 }
  );
  addSource(slide, "Source: AGENTS.md required boundaries and current workflow docs");

  for (const s of pptx._slides) {
    warnIfSlideHasOverlaps(s, pptx);
    warnIfSlideElementsOutOfBounds(s, pptx);
  }
  await pptx.writeFile({ fileName: OUT });
  console.log(`Wrote ${OUT}`);
}

function addShapeColumn(slide, x, y, title, items, color, fill) {
  slide.addShape(pptx.ShapeType.rect, {
    x,
    y,
    w: 3.45,
    h: 3.75,
    fill: { color: fill },
    line: { color, width: 1 },
  });
  slide.addText(title, {
    x: x + 0.22,
    y: y + 0.24,
    w: 3.0,
    h: 0.3,
    fontFace: "Arial",
    fontSize: 14.5,
    bold: true,
    color,
    margin: 0,
    fit: "shrink",
  });
  addBullets(slide, items, x + 0.38, y + 0.9, 2.8, 2.15, { fontSize: 12.6 });
}

function addRoadmap(slide) {
  const steps = [
    ["1", "Candidate region review", "Coverage, quality, flanking sequence"],
    ["2", "Marker conversion check", "KASP/CAPS feasibility, still preliminary"],
    ["3", "Population evidence", "WGS/GBS + genotype-phenotype association"],
    ["4", "Wet-lab validation", "qRT-PCR, LC-MS/MS, Sanger / target region"],
  ];
  const y = 2.0;
  steps.forEach((step, idx) => {
    const x = 0.9 + idx * 3.05;
    const color = idx < 2 ? COLORS.navy : idx === 2 ? COLORS.green : COLORS.amber;
    const fill = idx < 2 ? COLORS.softBlue : idx === 2 ? COLORS.softGreen : COLORS.softAmber;
    slide.addShape(pptx.ShapeType.ellipse, {
      x,
      y,
      w: 0.62,
      h: 0.62,
      fill: { color },
      line: { color },
    });
    slide.addText(step[0], {
      x,
      y: y + 0.14,
      w: 0.62,
      h: 0.18,
      fontFace: "Arial",
      fontSize: 12,
      bold: true,
      color: "FFFFFF",
      align: "center",
      margin: 0,
    });
    if (idx < steps.length - 1) {
      slide.addShape(pptx.ShapeType.line, {
        x: x + 0.72,
        y: y + 0.31,
        w: 2.08,
        h: 0,
        line: { color: COLORS.line, width: 1.2, beginArrowType: "none", endArrowType: "triangle" },
      });
    }
    slide.addShape(pptx.ShapeType.rect, {
      x: x - 0.28,
      y: y + 0.92,
      w: 2.38,
      h: 1.22,
      fill: { color: fill },
      line: { color, width: 0.9 },
    });
    slide.addText(step[1], {
      x: x - 0.12,
      y: y + 1.1,
      w: 2.08,
      h: 0.24,
      fontFace: "Arial",
      fontSize: 11,
      bold: true,
      color,
      align: "center",
      margin: 0,
      fit: "shrink",
    });
    slide.addText(step[2], {
      x: x - 0.08,
      y: y + 1.52,
      w: 2.0,
      h: 0.32,
      fontFace: "Arial",
      fontSize: 8.8,
      color: COLORS.ink,
      align: "center",
      margin: 0,
      fit: "shrink",
    });
  });
}

build().catch((err) => {
  console.error(err);
  process.exit(1);
});
