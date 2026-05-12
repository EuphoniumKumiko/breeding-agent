# 文档清理总结

本次整理只处理 Markdown 文档，没有改业务代码、测试、configs、`data/private` 或 `outputs`。

## 1. 已删除的重复文档

- `docs/code_reading_guide.md`
- `docs/gradio_demo_usage.md`
- `docs/gradio_flavonoid_marker_usage.md`
- `docs/gradio_omics_modules_usage.md`

这些文档的内容已被 `README.md`、`docs/project_onboarding.md`、`docs/architecture_overview.md` 和 `docs/developer/gradio_to_langgraph_call_chain.md` 覆盖。

## 2. 已合并到 canonical 文档的内容

- 组会主线讲解收拢到 `docs/developer/code_walkthrough_for_meeting.md`
- Gradio 调用链收拢到 `docs/developer/gradio_to_langgraph_call_chain.md`
- LiteratureAgent v3 主线收拢到 `docs/developer/literature_agent_v3_walkthrough.md`
- 当前项目边界收拢到 `docs/developer/current_project_boundary_for_meeting.md`
- README 和 onboarding 更新了阅读顺序与边界说明
- `docs/architecture_overview.md` 更新为当前主架构入口

## 3. 保留的 canonical 文档

- `README.md`
- `docs/project_onboarding.md`
- `docs/architecture_overview.md`
- `docs/developer/code_walkthrough_for_meeting.md`
- `docs/developer/gradio_to_langgraph_call_chain.md`
- `docs/developer/literature_agent_v3_walkthrough.md`
- `docs/developer/current_project_boundary_for_meeting.md`
- `docs/developer/testing_and_release_checklist.md`
- `docs/developer/demo_data_restore_guide.md`
- `docs/local_llm_reviewer_agent.md`

## 4. 仍然保留为历史参考的 Deprecated 文档

以下文档已在顶部标记 Deprecated，保留给需要追溯历史或对照旧版实现的人：

- `docs/agent_interface_design.md`
- `docs/deepagents_flavonoid_marker_poc.md`
- `docs/developer/business_logic_by_file.md`
- `docs/developer/codebase_map.md`
- `docs/developer/gradio_workbench_walkthrough.md`
- `docs/developer/local_llm_integration_walkthrough.md`
- `docs/developer/workflow_tracing_guide.md`
- `docs/flavonoid_marker_aggregation_usage.md`
- `docs/four_github_projects_to_demo_mapping.md`
- `docs/langgraph_flavonoid_marker_workflow.md`
- `docs/lobster_external_agent_benchmark.md`
- `docs/modules/gradio_workbench.md`
- `docs/teacher_demo_brief.md`

## 5. 新的推荐阅读顺序

1. `README.md`
2. `docs/project_onboarding.md`
3. `docs/architecture_overview.md`
4. `docs/developer/code_walkthrough_for_meeting.md`
5. `docs/developer/gradio_to_langgraph_call_chain.md`
6. `docs/developer/literature_agent_v3_walkthrough.md`
7. `docs/developer/current_project_boundary_for_meeting.md`
8. `docs/developer/testing_and_release_checklist.md`
9. `docs/developer/demo_data_restore_guide.md`
10. `docs/local_llm_reviewer_agent.md`

## 6. 仍需人工确认的文档

- `docs/report/architecture_diagrams.md`
- `docs/report/ppt_outline.md`
- `docs/modules/transcriptomics_deg.md`
- `docs/modules/genomics_region.md`
- `docs/modules/metabolomics_evidence.md`
- `docs/modules/flavonoid_marker_recommendation.md`
- `docs/modules/testing_and_validation.md`
- `docs/flavonoid_marker_package_import.md`
- `docs/genomics_variant_calling_usage.md`
- `docs/promoter_dataset_inventory.md`
- `docs/promoter_design_task.md`

这些文档内容仍然有效，但它们更像模块参考、阶段性汇报材料或 scaffold 说明，是否继续保留为长文档可以在下一轮再做一次收缩。

