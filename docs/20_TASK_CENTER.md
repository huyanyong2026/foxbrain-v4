# 20 Task Center / 任务中心

## 目标

任务中心把 AI 建议、经营问题和人工安排变成可执行事项，避免只看分析不行动。

## 页面

- `/tasks`
- `GET /api/tasks`
- `POST /api/tasks`
- `PUT /api/tasks/{id}`
- `POST /api/tasks/{id}/complete`

## 字段

- `task_id`
- `title`
- `description`
- `owner`
- `related_object_type`
- `related_object_id`
- `priority`: `low`、`normal`、`high`、`urgent`
- `status`: `todo`、`doing`、`waiting`、`done`、`cancelled`
- `due_date`
- `source_type`
- `source_id`
- `created_by`
- `created_at`
- `updated_at`

## AI 建议转任务

当前版本已经准备 `source_type` 和 `source_id`，后续可支持：

AI Suggestion -> Create Task -> Assign Owner -> Set Due Date -> Track Progress -> Timeline -> Audit Log

## 后续升级

- 任务编辑页
- 任务评论
- 企业微信提醒
- n8n 自动分发
- 门店任务看板

## Task009 Agent Tasks

Agent tasks are separate from employee tasks. They represent AI analysis or recommendation work and require human review before changing business state or creating employee-facing tasks.

## Task010 Jarvis Task Suggestions

Jarvis can recognize `task_creation` intent and create a pending action suggestion.

Flow:

Jarvis question -> Intent router -> Suggested action -> Human confirmation -> Task Center execution

In V1, Jarvis records the suggested action and requires a manager, boss or admin to confirm/cancel. This prevents accidental task creation from casual chat.

## Task013 Mobile Task View

Store employees can open `/mobile/tasks` on a phone to see and complete assigned tasks.

Mobile completion can include:

- Completion note
- Result photo
- Timeline event
- Audit log

Managers can convert reviewed mobile submissions into employee-facing tasks.

## Task014 Store Growth Tasks

Store growth plans can generate execution tasks for store teams.

Examples:

- Adjust display
- Push focus brand
- Push focus product
- Contact old customers
- Publish store content
- Run community activity
- Upload customer feedback

Generated tasks keep the growth plan as their source.
