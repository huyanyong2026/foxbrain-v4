# 06 Knowledge Center / 知识库规范

## 目标

FoxBrain 知识中心不是普通文件夹，而是企业长期记忆中心。它负责沉淀制度、SOP、品牌资料、产品资料、培训材料、合同、会议纪要、SAP 摘要、经营分析和 AI 问答记录，为后续 AI 推理、引用回答和智能体记忆提供基础。

## Knowledge Item 模型

每条知识至少支持以下字段：

- `knowledge_id`: 业务知识编号，例如 `KB-xxxx`
- `title`: 标题
- `content/body`: 正文或解析后的文本
- `source_type`: 来源类型，支持 `document`、`note`、`web`、`sap_report`、`meeting`、`image`、`audio`、`video`
- `source_id`: 外部来源标识
- `source_file_id`: 文件中心来源
- `object_type` / `object_id`: 关联门店、员工、品牌、产品、供应商、会员等档案对象
- `summary` / `human_summary`: 自动摘要和人工摘要
- `keywords`: 关键词
- `tags` / `auto_tags` / `manual_tags`: 自动标签和人工标签
- `status`: `draft`、`uploaded`、`parsed`、`summarized`、`embedded`、`ready`、`failed`
- `visibility`: `public_internal`、`manager_only`、`finance_only`、`owner_only`、`restricted`
- `embedding_status`: `pending`、`processing`、`done`、`failed`

## Document-to-Knowledge 管线

文件上传后进入以下流程：

1. 文件保存
2. 元数据保存
3. 解析占位
4. 文本切片
5. 摘要占位
6. 关键词和标签占位
7. 向量化占位
8. 知识条目创建
9. 关联档案对象
10. 进入搜索和 AI 查询

当前版本只在能安全解析到真实文本时生成切片；如果无法解析，不伪造内容，只显示等待解析和等待 AI 摘要状态。

## Chunk 模型

文档切片用于未来向量检索和引用回答。

## AI 查询结构

AI 查询中心 V1 返回引用准备结构，不编造经营结论。

## 权限

知识可见范围必须在查询、页面和 API 中同时生效。敏感合同、工资、财务资料不能默认给所有员工。

## Task008 Graph Integration

Knowledge items can become graph entities. If a knowledge item has `object_type` and `object_id`, the graph engine can create a `documented_by` relationship to the related archive object.

The graph engine must not infer unsupported facts from document text until a reviewed extraction workflow exists.
