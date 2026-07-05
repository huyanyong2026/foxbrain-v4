# 30 Content Publishing Engine

## Goal

The Content Publishing Engine helps FoxBrain turn internal knowledge, brand assets, product files, store stories, reports and AI analysis into reviewable multi-platform content drafts.

It does not publish automatically in V1.

## Route

- `/content`
- `/content-center`

## Models

`content_drafts`

- `content_id`
- `title`
- `content_type`
- `topic`
- `body`
- `summary`
- `target_platforms`
- `status`
- `campaign_id`
- `related_object_type`
- `related_object_id`
- `source_type`
- `source_id`
- `created_by`
- `reviewed_by`
- `reviewed_at`
- `review_notes`
- `compliance_status`
- `scheduled_at`
- `published_at`
- `created_at`
- `updated_at`

`content_platform_versions`

- `version_id`
- `content_id`
- `platform`
- `title`
- `body`
- `hashtags`
- `media_requirements`
- `length_limit`
- `tone`
- `status`
- `created_at`
- `updated_at`

`content_campaigns`

- `campaign_id`
- `campaign_name`
- `campaign_type`
- `start_date`
- `end_date`
- `target_stores`
- `target_brands`
- `target_products`
- `goal`
- `budget`
- `status`
- `created_at`
- `updated_at`

`content_publish_queue`

- `queue_id`
- `content_version_id`
- `platform`
- `scheduled_at`
- `status`
- `error_message`
- `published_url`
- `created_at`

## Platforms

- WeChat Official Account
- WeChat Channels
- Douyin
- Xiaohongshu
- Website
- Mini Program placeholder
- Facebook placeholder
- Instagram
- TikTok

## Review Flow

Create draft -> Generate platform versions -> Submit review -> Approve / Reject -> Schedule -> Export

AI-generated public content must be reviewed before publishing.

## Templates

- Osprey communication template
- VAFOX brand content template

## Export

- Markdown
- Plain text
- HTML
- Copy to clipboard placeholder
- Word/PDF placeholder for later

## Safety

- Do not invent product facts, prices, promotion details or brand claims.
- Do not publish automatically without secure platform integration.
- Ordinary users cannot approve official public content.

## Task014 Store Growth Integration

Store growth plans can provide topics for:

- Xiaohongshu store notes
- WeChat Channels store activity videos
- WeChat Official Account activity previews
- Moments scripts
- Community notices
- Employee shooting checklists

When no AI model is configured, the content engine returns a safe skeleton only.

## Task015 Brand Growth Integration

Brand strategies can provide content topics:

- Brand story
- Product note
- Xiaohongshu post
- WeChat article
- Store sales script
- Member communication draft

No brand claim, product spec or promotion detail may be invented.

## Task019 Customer Growth Integration

Customer events and private-domain groups can provide content topics:

- Event invitation copy
- Member day notice
- Equipment class message
- Product experience invitation
- Dormant customer reactivation draft
- Store group notice

Public or private customer messages require human review before use.
