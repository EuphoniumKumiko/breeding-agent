# breeding-agent 架构图 Mermaid Source

本文件先用 Mermaid 固化组会 PPT 中的架构图，再导出 SVG/PNG 放入 `presentation.pptx`。所有图均按当前仓库真实状态绘制：LangGraph 是主线多 Agent 编排层，Gradio 是展示层，LLM 只增强 ReviewerAgent，Deep Agents / Lobster-style / Promoter Design 不写成真实完成能力。

## Diagram 1: Application Architecture

```mermaid
%%{init: {"theme": "base", "themeVariables": {"background": "#FFFFFF", "mainBkg": "#F7F9FB", "clusterBkg": "#F7F9FB", "clusterBorder": "#D6DAE0", "primaryBorderColor": "#6B7280", "primaryTextColor": "#111827", "lineColor": "#6B7280"}}}%%
flowchart LR
  classDef input fill:#EAF2F8,stroke:#1F4E79,color:#0B1F33
  classDef workflow fill:#F7F9FB,stroke:#6B7280,color:#111827
  classDef output fill:#E8F4EA,stroke:#2F6F3E,color:#102A19
  classDef limit fill:#FDECEC,stroke:#9B1C1C,color:#3B0A0A

  subgraph Inputs["Local data and evidence"]
    BAM["bam/ all files"]
    MET["metabolome_raw_3372.tsv"]
    GEN["genome.fa + genome.gff"]
    ANN["local_region_emapper_annotations.tsv"]
    DOI["verified literature DOI"]
  end

  subgraph Tasks["Runnable project tasks"]
    DEG["RNA-seq DEG reproduction"]
    EVI["Flavonoid evidence package"]
    VAR["Candidate-region variant calling MVP"]
    MARKER["Flavonoid candidate marker recommendation"]
    GRAPH["LangGraph run"]
  end

  subgraph Outputs["Human-facing outputs"]
    CAND["candidate gene / marker type table"]
    REPORT["Markdown report"]
    TRACE["graph trace + QA JSON + manifest"]
    UI["Gradio display"]
  end

  subgraph Boundaries["Current limits"]
    B1["No final KASP/CAPS marker"]
    B2["No WGS/GBS population validation"]
    B3["No wet-lab validation claim"]
  end

  BAM --> DEG --> EVI
  MET --> EVI
  GEN --> EVI
  ANN --> EVI
  DOI --> EVI
  GEN --> VAR
  BAM --> VAR
  EVI --> MARKER
  VAR --> MARKER
  MARKER --> GRAPH
  MARKER --> CAND
  MARKER --> REPORT
  GRAPH --> TRACE
  CAND --> UI
  REPORT --> UI
  TRACE --> UI
  MARKER -.current limit.-> B1
  VAR -.current limit.-> B2
  REPORT -.current limit.-> B3

  class BAM,MET,GEN,ANN,DOI input
  class DEG,EVI,VAR,MARKER,GRAPH workflow
  class CAND,REPORT,TRACE,UI output
  class B1,B2,B3 limit
```

## Diagram 2: Technical Architecture

```mermaid
%%{init: {"theme": "base", "themeVariables": {"background": "#FFFFFF", "mainBkg": "#F7F9FB", "clusterBkg": "#F7F9FB", "clusterBorder": "#D6DAE0", "primaryBorderColor": "#6B7280", "primaryTextColor": "#111827", "lineColor": "#6B7280"}}}%%
flowchart TB
  classDef cli fill:#EAF2F8,stroke:#1F4E79,color:#0B1F33
  classDef core fill:#F7F9FB,stroke:#6B7280,color:#111827
  classDef agent fill:#E8F4EA,stroke:#2F6F3E,color:#102A19
  classDef guard fill:#FFF3D6,stroke:#A66A00,color:#3B2700
  classDef display fill:#FDECEC,stroke:#9B1C1C,color:#3B0A0A

  subgraph Entry["Entry points"]
    CLI1["cli/deg.py"]
    CLI2["cli/flavonoid_markers.py"]
    CLI3["cli/flavonoid_markers_graph.py"]
    CLI4["cli/genomics_variants.py"]
    WEB["web/gradio_app.py"]
  end

  subgraph Backend["Workflow and evidence modules"]
    WF["workflows/"]
    INT["integration/"]
    REP["reports/"]
    VAL["validators/"]
    MOD["modules/genomics + modules/metabolomics + modules/promoter"]
  end

  subgraph AgentLayer["Agent and graph layer"]
    AG["agents/"]
    GR["graphs/"]
    LLM["llm/"]
  end

  subgraph QA["Risk controls"]
    OG["output_guard.py"]
    FQA["FinalQAAgent"]
    MAN["manifest + qa_check.json"]
  end

  CLI1 --> WF
  CLI2 --> WF
  CLI3 --> GR
  CLI4 --> WF
  WEB --> WF
  WEB --> GR
  WF --> VAL
  WF --> MOD
  WF --> INT
  INT --> REP
  GR --> AG
  AG --> REP
  LLM --> OG
  GR --> LLM
  REP --> FQA
  OG --> FQA
  FQA --> MAN
  WEB -.display only.-> MAN

  class CLI1,CLI2,CLI3,CLI4 cli
  class WF,INT,REP,VAL,MOD core
  class AG,GR,LLM agent
  class OG,FQA,MAN guard
  class WEB display
```

## Diagram 3: LangGraph Node Flow

```mermaid
%%{init: {"theme": "base", "themeVariables": {"background": "#FFFFFF", "mainBkg": "#F7F9FB", "clusterBkg": "#F7F9FB", "clusterBorder": "#D6DAE0", "primaryBorderColor": "#6B7280", "primaryTextColor": "#111827", "lineColor": "#6B7280"}}}%%
flowchart TB
  classDef node fill:#F7F9FB,stroke:#4B5563,color:#111827
  classDef agent fill:#E8F4EA,stroke:#2F6F3E,color:#102A19
  classDef guard fill:#FFF3D6,stroke:#A66A00,color:#3B2700
  classDef output fill:#EAF2F8,stroke:#1F4E79,color:#0B1F33

  subgraph Prepare["Prepare evidence and context"]
    direction LR
    START((START)) --> LOAD["load_evidence_node"] --> AGG["aggregate_candidates_node"] --> CTX["build_agent_context_node"]
  end

  subgraph Agents["Rule-agent chain"]
    direction LR
    LIT["literature_agent_node"] --> MARKER["marker_recommendation_agent_node"] --> VAL["validation_agent_node"] --> REV["reviewer_agent_node"] --> FQA["final_qa_agent_node"]
  end

  subgraph Outputs["Report and trace outputs"]
    direction LR
    REPORT["report_node"] --> WRITE["write_outputs_node"] --> TRACE["graph_trace.json\nnode_decision_table.tsv\nqa_check.json"] --> END((END))
  end

  CTX --> LIT
  FQA --> REPORT

  LIT -.uses.-> LA["LiteratureAgent"]
  MARKER -.uses.-> MA["MarkerRecommendationAgent"]
  VAL -.uses.-> VA["ValidationAgent"]
  REV -.uses.-> RA["ReviewerAgent"]
  FQA -.uses.-> QA["FinalQAAgent"]

  class LOAD,AGG,CTX,REPORT,WRITE node
  class LIT,MARKER,VAL,REV agent
  class FQA,QA guard
  class TRACE output
```

## Diagram 4: LLM Reviewer Guardrail

```mermaid
%%{init: {"theme": "base", "themeVariables": {"background": "#FFFFFF", "mainBkg": "#F7F9FB", "clusterBkg": "#F7F9FB", "clusterBorder": "#D6DAE0", "primaryBorderColor": "#6B7280", "primaryTextColor": "#111827", "lineColor": "#6B7280"}}}%%
flowchart TB
  classDef rule fill:#E8F4EA,stroke:#2F6F3E,color:#102A19
  classDef llm fill:#EAF2F8,stroke:#1F4E79,color:#0B1F33
  classDef guard fill:#FFF3D6,stroke:#A66A00,color:#3B2700
  classDef stop fill:#FDECEC,stroke:#9B1C1C,color:#3B0A0A

  DRAFT["Draft report from rule workflow"] --> RULE["Rule-based ReviewerAgent"]
  RULE --> BASE["Rule reviewer notes"]
  BASE --> CFG{"--use-llm-reviewer enabled?"}
  CFG -->|no| FINAL["FinalQAAgent"]
  CFG -->|yes| LLM["Local OpenAI-compatible LLM only for reviewer note enhancement"]
  LLM --> THINK["chat_template_kwargs.enable_thinking=false"]
  THINK --> OG["OutputGuard checks DOI, variant coordinates, LowQual, KASP/CAPS wording, WGS/GBS limitation"]
  OG -->|pass| MERGE["Merge guarded LLM reviewer notes"]
  OG -->|fail / timeout / empty| FALLBACK["Fallback to rule ReviewerAgent"]
  MERGE --> FINAL
  FALLBACK --> FINAL
  FINAL --> QA["qa_check.json and manifest status"]

  class RULE,BASE,FALLBACK rule
  class LLM,THINK llm
  class OG,FINAL,QA guard
  class CFG stop
```

## Diagram 5: Evidence-To-Report Boundary

```mermaid
%%{init: {"theme": "base", "themeVariables": {"background": "#FFFFFF", "mainBkg": "#F7F9FB", "clusterBkg": "#F7F9FB", "clusterBorder": "#D6DAE0", "primaryBorderColor": "#6B7280", "primaryTextColor": "#111827", "lineColor": "#6B7280"}}}%%
flowchart TB
  classDef evidence fill:#EAF2F8,stroke:#1F4E79,color:#0B1F33
  classDef process fill:#F7F9FB,stroke:#6B7280,color:#111827
  classDef output fill:#E8F4EA,stroke:#2F6F3E,color:#102A19
  classDef limit fill:#FDECEC,stroke:#9B1C1C,color:#3B0A0A

  T["Transcriptomics statistics"]
  M["Metabolite correlation evidence"]
  A["Functional annotation"]
  L["Literature DOI evidence"]
  V["Variant evidence or variant_status=not_called"]

  T --> CAND["flavonoid_marker_candidates.tsv"]
  M --> CAND
  A --> CAND
  L --> CAND
  V --> CAND
  CAND --> REC["Candidate SNP/InDel/KASP/CAPS type recommendation"]
  REC --> REPORT["flavonoid_marker_report.md"]
  REC --> QA["QA checks: fixed genes, statistics, DOI, 群体, no fabricated variants"]
  QA --> MAN["manifest.json"]

  V -.when not_called.-> NOPOS["No final SNP/InDel positions are reported"]
  REC -.preliminary only.-> PRELIM["KASP/CAPS screening is not primer or enzyme plan"]
  REPORT -.requires follow-up.-> POP["Larger population genotype and flavonoid phenotype validation"]

  class T,M,A,L,V evidence
  class CAND,REC,QA process
  class REPORT,MAN output
  class NOPOS,PRELIM,POP limit
```

## Diagram 6: Gradio Boundary

```mermaid
%%{init: {"theme": "base", "themeVariables": {"background": "#FFFFFF", "mainBkg": "#F7F9FB", "clusterBkg": "#F7F9FB", "clusterBorder": "#D6DAE0", "primaryBorderColor": "#6B7280", "primaryTextColor": "#111827", "lineColor": "#6B7280"}}}%%
flowchart LR
  classDef ui fill:#EAF2F8,stroke:#1F4E79,color:#0B1F33
  classDef backend fill:#F7F9FB,stroke:#6B7280,color:#111827
  classDef output fill:#E8F4EA,stroke:#2F6F3E,color:#102A19
  classDef limit fill:#FDECEC,stroke:#9B1C1C,color:#3B0A0A

  UI["Gradio top-level tabs"] --> DEG["Transcriptomics DEG Module"]
  UI --> MET["Metabolomics Module"]
  UI --> GEN["Genomics / GWAS Module"]
  UI --> INT["Integration & Recommendation"]
  UI --> FLAV["谷子黄酮候选标记推荐"]

  DEG --> W1["workflows/rnaseq_deg.py"]
  FLAV --> W2["workflows/flavonoid_marker_aggregation.py"]
  FLAV --> W3["workflows/flavonoid_marker_langgraph.py"]
  FLAV --> STATUS["LLM reviewer status display"]

  W1 --> OUT1["reports + manifest + logs"]
  W2 --> OUT2["candidate table + report + qa_check"]
  W3 --> OUT3["graph_trace + node_decision_table + qa_check"]
  STATUS -.does not show.-> CFG["local llm config contents"]

  class UI,DEG,MET,GEN,INT,FLAV ui
  class W1,W2,W3 backend
  class OUT1,OUT2,OUT3,STATUS output
  class CFG limit
```
