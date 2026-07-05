# 36 Inventory Decision Engine

## Goal

Inventory Decision Engine turns inventory risk into reviewed action suggestions.

It covers:

- Inventory risk diagnosis
- Replenishment suggestions
- Store transfer suggestions
- Markdown and clearance suggestions
- Future order tracking
- Cash occupation overview
- Osprey inventory decision page

## Pages

- `/inventory-decision`
- `/brands/osprey-inventory-decision`

## Models

### `inventory_decision_risks`

- Brand, product and store references
- Risk type
- Risk level
- Inventory quantity and amount
- Sales quantity
- Days of cover
- Recommendation
- Status

### `replenishment_suggestions`

- Store, brand and product references
- Suggested quantity
- Reason
- Priority
- Status

### `transfer_suggestions`

- Source store
- Target store
- Brand and product references
- Suggested quantity
- Reason
- Status

### `markdown_suggestions`

- Brand and product references
- Current price
- Suggested price
- Suggested discount
- Reason
- Status

### `future_orders`

- Brand and supplier references
- Season
- Order amount
- Deposit amount
- Expected arrival date
- Risk note
- Status

## Decision Rules

V1 keeps the rules conservative:

- High inventory requires sales evidence before replenishment.
- Slow moving stock should create review tasks before markdown.
- Store transfer suggestions are recommendations, not automatic stock moves.
- Future orders must show cash occupation and supplier risk.
- Osprey inventory decisions should be reviewed together with pricing and rebate assumptions.

## API

- `GET /api/inventory-decision`
- `GET /api/inventory-decision/risks`
- `POST /api/inventory-decision/risks`
- `GET /api/inventory-decision/replenishment`
- `POST /api/inventory-decision/replenishment`
- `GET /api/inventory-decision/transfers`
- `POST /api/inventory-decision/transfers`
- `GET /api/inventory-decision/markdowns`
- `POST /api/inventory-decision/markdowns`
- `GET /api/inventory-decision/future-orders`
- `POST /api/inventory-decision/future-orders`
- `GET /api/inventory-decision/cash-occupation`
- `GET /api/inventory-decision/osprey`
- `POST /api/inventory-decision/create-task`

## Safety

Inventory recommendations are not execution orders. Purchasing, markdown, store transfer and future order decisions must be reviewed by an authorized user.
