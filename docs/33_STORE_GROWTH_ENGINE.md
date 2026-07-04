# 33 Store Growth Engine

## Goal

Store Growth Engine helps each store improve sales, traffic, conversion, inventory execution and daily management.

It connects:

- Store diagnosis
- Growth plans
- Store activities
- Staff execution tasks
- Product and brand focus
- Customer operations
- Content suggestions
- Review reports

## Route

- `/store-growth`

## Models

`store_diagnoses`

- `diagnosis_id`
- `store_id`
- `date_range_start`
- `date_range_end`
- `sales_status`
- `margin_status`
- `traffic_status`
- `conversion_status`
- `inventory_status`
- `staff_status`
- `customer_status`
- `key_problems`
- `opportunities`
- `ai_suggestions`
- `data_sources`
- `status`
- `created_by`
- `created_at`
- `updated_at`

`store_growth_plans`

- `growth_plan_id`
- `store_id`
- `title`
- `goal`
- `start_date`
- `end_date`
- `target_sales`
- `target_margin`
- `target_customers`
- `target_tasks`
- `key_actions`
- `related_brands`
- `related_products`
- `owner`
- `status`
- `created_at`
- `updated_at`

`store_activities`

- `activity_id`
- `store_id`
- `title`
- `activity_type`
- `start_date`
- `end_date`
- `target_customer`
- `target_brand`
- `target_product`
- `budget`
- `expected_result`
- `content_plan`
- `task_plan`
- `status`
- `created_at`
- `updated_at`

`store_focus_items`

- `focus_id`
- `store_id`
- `brand_id`
- `product_id`
- `focus_reason`
- `period`
- `status`
- `created_at`
- `updated_at`

## Task Integration

Growth plans can generate employee-facing tasks. Generated tasks keep `source_type=store_growth` and link back to the growth plan.

## Content and Report Integration

Store growth plans can become store content drafts and store review reports.

V1 prepares the handoff to Content Publishing Engine and Reporting Engine.

## Safety

- Do not invent store sales, traffic, conversion, customer or inventory data.
- If no SAP/customer data exists, show waiting state and templates.
- Sensitive customer information must remain permission controlled.
