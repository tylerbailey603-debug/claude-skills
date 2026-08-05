# Screen properties to set manually after pasting

Paste code inserts controls only. After pasting each fragment into its screen,
set these screen-level properties in the formula bar:

## Analytics

- `Fill: =RGBA(247, 248, 250, 1)`

## Approvals

- `Fill: =RGBA(247, 248, 250, 1)`

## Dashboard

- `Fill: =RGBA(247, 248, 250, 1)`

## NewRequisition

- `Fill: =RGBA(247, 248, 250, 1)`
- `OnVisible: |`
- `=Set(varStep, 1);`
- `If(IsEmpty(colNewLines), Collect(colNewLines, {SKU:"", Desc:"", Qty:1, Price:0}))`

## RequisitionDetail

- `Fill: =RGBA(247, 248, 250, 1)`
- `OnVisible: |`
- `=Set(varPr, LookUp(colRequisitions, Id = varSelectedPr))`

## Requisitions

- `Fill: =RGBA(247, 248, 250, 1)`
- `OnVisible: |`
- `=Set(varReqTab, "All")`

## Settings

- `Fill: =RGBA(247, 248, 250, 1)`

## Suppliers

- `Fill: =RGBA(247, 248, 250, 1)`

