# 文档清单与维护建议

本文档用于帮助新人快速判断哪些 Markdown 是当前主线，哪些是历史参考，哪些已经被替代。

说明：

- `latest=是` 表示当前仍建议优先阅读。
- `duplicate=是` 表示内容与其他文档明显重叠。
- `suggestion` 只给四类：`keep`、`merge`、`delete`、`deprecated`。

## A. 建议优先阅读的 canonical 文档

| path | theme | latest | duplicate | suggestion |
| --- | --- | --- | --- | --- |
| `README.md` | 项目入口、运行命令、边界、阅读顺序 | 是 | 否 | keep |
| `docs/project_onboarding.md` | 新人上手总览 | 是 | 否 | keep |
| `docs/architecture_overview.md` | 分层架构、主线数据流、边界 | 是 | 是 | keep |
| `docs/developer/code_walkthrough_for_meeting.md` | 组会代码主线 | 是 | 是 | keep |
| `docs/developer/gradio_to_langgraph_call_chain.md` | Gradio -> LangGraph 调用链 | 是 | 是 | keep |
| `docs/developer/literature_agent_v3_walkthrough.md` | LiteratureAgent v3 主线 | 是 | 是 | keep |
| `docs/developer/current_project_boundary_for_meeting.md` | 可讲/不可讲边界 | 是 | 是 | keep |
| `docs/developer/testing_and_release_checklist.md` | 测试与发布前检查 | 是 | 是 | keep |
| `docs/developer/demo_data_restore_guide.md` | demo 恢复流程 | 是 | 是 | keep |
| `docs/local_llm_reviewer_agent.md` | 本地 ReviewerAgent 边界 | 是 | 是 | keep |
| `docs/flavonoid_marker_package_import.md` | mini 数据包导入 | 是 | 是 | keep |
| `docs/genomics_variant_calling_usage.md` | 候选区域变异 calling 使用说明 | 是 | 是 | keep |
| `docs/promoter_design_task.md` | Promoter Design scaffold | 是 | 是 | keep |
| `docs/modules/transcriptomics_deg.md` | RNA-seq DEG 模块导读 | 是 | 是 | keep |
| `docs/modules/genomics_region.md` | Genomics Region 模块导读 | 是 | 是 | keep |
| `docs/modules/metabolomics_evidence.md` | Metabolomics 模块导读 | 是 | 是 | keep |
| `docs/modules/flavonoid_marker_recommendation.md` | 黄酮标记模块导读 | 是 | 是 | keep |
| `docs/modules/testing_and_validation.md` | 测试与验证导读 | 是 | 是 | keep |

## B. 已标记 Deprecated 的历史文档

| path | theme | latest | duplicate | suggestion |
| --- | --- | --- | --- | --- |
| `docs/agent_interface_design.md` | Agent 接口设计 | 否 | 是 | deprecated |
| `docs/deepagents_flavonoid_marker_poc.md` | Deep Agents POC 说明 | 否 | 是 | deprecated |
| `docs/developer/business_logic_by_file.md` | 文件级业务说明 | 否 | 是 | deprecated |
| `docs/developer/codebase_map.md` | 代码地图 | 否 | 是 | deprecated |
| `docs/developer/gradio_workbench_walkthrough.md` | Gradio 后端映射 | 否 | 是 | deprecated |
| `docs/developer/local_llm_integration_walkthrough.md` | 本地 LLM 接入说明 | 否 | 是 | deprecated |
| `docs/developer/workflow_tracing_guide.md` | Workflow 追踪 | 否 | 是 | deprecated |
| `docs/flavonoid_marker_aggregation_usage.md` | 规则版 aggregation 说明 | 否 | 是 | deprecated |
| `docs/four_github_projects_to_demo_mapping.md` | 外部项目映射 | 否 | 是 | deprecated |
| `docs/langgraph_flavonoid_marker_workflow.md` | LangGraph workflow 说明 | 否 | 是 | deprecated |
| `docs/lobster_external_agent_benchmark.md` | Lobster-style benchmark | 否 | 是 | deprecated |
| `docs/modules/gradio_workbench.md` | Gradio Workbench 导读 | 否 | 是 | deprecated |
| `docs/teacher_demo_brief.md` | 老师汇报简报 | 否 | 是 | deprecated |

## C. 已删除的重复文档

| path | theme | reason |
| --- | --- | --- |
| `docs/code_reading_guide.md` | 代码阅读指南 | 已被 `README.md`、`docs/architecture_overview.md`、`docs/developer/code_walkthrough_for_meeting.md` 替代 |
| `docs/gradio_demo_usage.md` | Gradio demo 使用说明 | 已被 `docs/developer/gradio_to_langgraph_call_chain.md` 和 `docs/architecture_overview.md` 替代 |
| `docs/gradio_flavonoid_marker_usage.md` | 黄酮标记 Gradio 使用说明 | 已被 `docs/developer/gradio_to_langgraph_call_chain.md` 和 `README.md` 替代 |
| `docs/gradio_omics_modules_usage.md` | 多组学 Gradio 使用说明 | 已被 `docs/developer/gradio_to_langgraph_call_chain.md` 和 `docs/project_onboarding.md` 替代 |

## D. 阶段性汇报材料和产物

| path | theme | latest | duplicate | suggestion |
| --- | --- | --- | --- | --- |
| `docs/report/architecture_diagrams.md` | 架构图 Mermaid 源文件 | 阶段性 | 否 | stage artifact |
| `docs/report/ppt_outline.md` | 组会 PPT outline | 阶段性 | 否 | stage artifact |

## 维护建议

1. 新人首读只看 `README.md`、`docs/project_onboarding.md`、`docs/architecture_overview.md` 和 4 份 `docs/developer/*` canonical 文档。
2. 模块级文档保留为参考，不再承担入口职责。
3. 历史说明统一保留 Deprecated 标记，不再新增重复长文档。

