# 37 Purchasing Engine

## Goal

Purchasing Engine helps the owner, purchasing team and store managers prepare reviewed buying plans.

It links:

- Sales targets
- Inventory structure
- Cash occupation
- Supplier risk
- Brand strategy
- Product portfolio roles
- Future orders

## Page

Purchasing V1 is included in `/inventory-decision`.

## Model

`purchasing_plans`

- `plan_id`
- `brand_id`
- `supplier_id`
- `season`
- `budget_amount`
- `planned_amount`
- `expected_margin`
- `cash_pressure`
- `strategy`
- `status`
- `created_by`
- `created_at`
- `updated_at`

## Workflow

1. Review current inventory and slow moving risk.
2. Review brand role and product portfolio role.
3. Estimate planned order amount and margin target.
4. Check cash pressure and future order exposure.
5. Create tasks for owner or purchasing review.
6. Approve manually before supplier commitment.

## API

- `GET /api/inventory-decision/purchasing-plans`
- `POST /api/inventory-decision/purchasing-plans`

## Safety

Purchasing Engine must not create supplier commitments automatically. All plans remain draft or review status until approved by the business owner.
