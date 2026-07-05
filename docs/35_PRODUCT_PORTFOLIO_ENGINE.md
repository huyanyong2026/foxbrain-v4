# 35 Product Portfolio Engine

## Goal

Product Portfolio Engine helps classify products by their business role and decision direction.

## Product Roles

- Hero Product
- Profit Product
- Traffic Product
- Image Product
- Clearance Product
- Basic Product
- New Test Product

## Model

`product_portfolios`

- `portfolio_id`
- `brand_id`
- `product_id`
- `product_role`
- `season`
- `status`
- `sales_level`
- `margin_level`
- `inventory_level`
- `markdown_level`
- `recommendation`
- `created_at`
- `updated_at`

## Inventory Matrix

- High sales + high margin: keep as core
- High sales + low margin: traffic control
- Low sales + high margin: precision recommendation
- Low sales + low margin: clearance handling
- High inventory + low margin: high risk
- New product + unknown: test and observe

## Safety

No product role should be treated as final without reviewed sales, margin and inventory evidence.

## Task016 Inventory Decision Integration

Product portfolio roles now feed the inventory decision flow:

- Hero products can trigger replenishment review.
- Traffic products need margin and cash pressure review.
- Clearance products can trigger markdown review.
- New test products should stay under observation before larger purchasing plans.

The inventory decision page keeps these as structured suggestions until a manager reviews them.
