# SharePoint lists — simplified schema (Single line of text / Number only)

Every custom column below is either **Single line of text** or **Number** — no Choice,
Person, Lookup, Date, Currency, Yes/No, or Multi-line columns anywhere. Create the
lists top-to-bottom; column names must match exactly (they are what the app and flows
bind to).

## How the original types were converted

| Original type | Now | Convention |
| --- | --- | --- |
| Choice (Status etc.) | Single line of text | Fixed value set documented per column — enter values exactly as listed |
| Person | Single line of text | Two columns: display name + email (email is the stable key) |
| Date | Single line of text | ISO format `YYYY-MM-DD` (sorts correctly as text; app converts with `DateValue()`) |
| Date + time | Single line of text | ISO format `YYYY-MM-DD HH:MM` (24h) |
| Currency | Number | 2 decimal places; currency code lives in its own text column |
| Yes/No | Number | `1` = yes, `0` = no |
| Lookup | Single line of text | Stores the PRNumber string (e.g. `PR-2026-00184`) |
| Multi-line text | Single line of text | ⚠️ Single-line caps at 255 characters — see note at the end |

Every list also has the built-in **Title** column (already Single line of text) — the
table for each list says what to put in it. Built-in **ID** (number) stays untouched.

---

## 1. `Requisitions` — core list (the app's main data source)

**Title column =** the requisition title (e.g. `HPLC column replacement — Q2 batch`).

| Column | Type | Required | Values / format |
| --- | --- | --- | --- |
| Title | Single line of text (built-in) | Yes | Requisition short title |
| PRNumber | Single line of text | Yes | `PR-YYYY-NNNNN` (e.g. `PR-2026-00184`). Assigned by the autonumber flow — never typed by users. **Index this column.** |
| Vendor | Single line of text | Yes | Supplier name, matches a `Suppliers` Title |
| CostCenter | Single line of text | Yes | Cost-center code, matches a `CostCenters` Title (e.g. `QC-AnalyticalDev`) |
| Amount | Number (2 decimals) | Yes | Total requisition value, e.g. `12450.00` |
| Currency | Single line of text | No | `USD`, `CHF`, or `EUR` (default `USD`) |
| Status | Single line of text | Yes | Exactly one of: `Draft`, `Pending`, `Review`, `Approved`, `Rejected`, `Returned`, `Closed`. **Index this column.** |
| Requester | Single line of text | Yes | Display name, e.g. `Lina Roth` |
| RequesterEmail | Single line of text | No | e.g. `lina.roth@company.com` (stable key for flows/role checks) |
| NeededBy | Single line of text | Yes | `YYYY-MM-DD`, e.g. `2026-06-12` |
| Justification | Single line of text | No | Free text (255-char cap — see note) |
| DecisionMode | Single line of text | No | Empty, `Approve`, `Reject`, or `Return` |
| DecisionReason | Single line of text | No | Free text (255-char cap) |
| SubmittedOn | Single line of text | No | `YYYY-MM-DD HH:MM` — set by flow on submit |

## 2. `RequisitionLines` — line items per requisition

**Title column =** the SKU (duplicate of the SKU column, keeps the default view readable).

| Column | Type | Required | Values / format |
| --- | --- | --- | --- |
| Title | Single line of text (built-in) | Yes | Same value as SKU |
| PRNumber | Single line of text | Yes | Parent requisition's PRNumber. **Index this column.** |
| SKU | Single line of text | Yes | Catalog number, e.g. `ZGC18-250` |
| Description | Single line of text | Yes | Line description (255-char cap) |
| Qty | Number (0 decimals) | Yes | e.g. `4` |
| Unit | Single line of text | Yes | e.g. `ea`, `kit`, `box`, `pack` |
| UnitPrice | Number (2 decimals) | Yes | e.g. `2280.00` |

Line total is **not stored** — the app computes `Qty * UnitPrice`.

## 3. `Attachments` — file references per requisition

Pure list (text/number only). The file itself lives wherever you keep documents
(a plain document library, Teams, etc.); this list is what the app reads.

**Title column =** the file name (duplicate of FileName).

| Column | Type | Required | Values / format |
| --- | --- | --- | --- |
| Title | Single line of text (built-in) | Yes | Same value as FileName |
| PRNumber | Single line of text | Yes | Parent requisition's PRNumber. **Index this column.** |
| FileName | Single line of text | Yes | e.g. `Quote_MilliporeSigma_2026-05.pdf` |
| FileUrl | Single line of text | No | Full URL to the stored file |
| SizeKB | Number (0 decimals) | No | File size in KB |

> Alternative that stays within the rule: make `RequisitionDocs` a normal **document
> library** and add one custom column `PRNumber` (Single line of text). The library
> stores real files; the only custom column is still plain text.

## 4. `Suppliers` — vendor master (Suppliers screen + vendor pick lists)

**Title column =** supplier name.

| Column | Type | Required | Values / format |
| --- | --- | --- | --- |
| Title | Single line of text (built-in) | Yes | e.g. `MilliporeSigma` |
| Category | Single line of text | No | e.g. `Chromatography`, `Consumables`, `Service` |
| ContactEmail | Single line of text | No | Sales/AM contact |
| Phone | Single line of text | No | |
| Country | Single line of text | No | |
| Active | Number (0 decimals) | Yes | `1` = active, `0` = inactive |
| Rating | Number (0 decimals) | No | 1–5 |

## 5. `CostCenters` — cost-center master (form dropdown + routing)

**Title column =** the cost-center code.

| Column | Type | Required | Values / format |
| --- | --- | --- | --- |
| Title | Single line of text (built-in) | Yes | Code, e.g. `QC-AnalyticalDev` |
| Name | Single line of text | Yes | Readable name, e.g. `QC Analytical Development` |
| OwnerName | Single line of text | No | Budget owner display name |
| OwnerEmail | Single line of text | No | Budget owner email |
| Active | Number (0 decimals) | Yes | `1` = active, `0` = inactive |

## 6. `ApprovalRules` — routing table read by the on-submit flow

**Title column =** a readable rule name.

| Column | Type | Required | Values / format |
| --- | --- | --- | --- |
| Title | Single line of text (built-in) | Yes | e.g. `QC up to 10k` |
| CostCenter | Single line of text | Yes | Exact code, or a prefix ending in `*` (e.g. `QC-*`) |
| MinAmount | Number (2 decimals) | Yes | Rule applies when Amount ≥ MinAmount |
| MaxAmount | Number (2 decimals) | Yes | Rule applies when Amount < MaxAmount (use `999999999` for "no cap") |
| ApproverName | Single line of text | Yes | Display name |
| ApproverEmail | Single line of text | Yes | Where the approval request goes |
| Level | Number (0 decimals) | Yes | `1` = first approver, `2` = second, … |
| Active | Number (0 decimals) | Yes | `1` = active, `0` = inactive |

## 7. `DecisionLog` — audit trail written by the decision flow

**Title column =** `<PRNumber> <Action>` (e.g. `PR-2026-00178 Reject`).

| Column | Type | Required | Values / format |
| --- | --- | --- | --- |
| Title | Single line of text (built-in) | Yes | `<PRNumber> <Action>` |
| PRNumber | Single line of text | Yes | **Index this column.** |
| Action | Single line of text | Yes | `Approve`, `Reject`, or `Return` |
| ActorName | Single line of text | Yes | Who decided |
| ActorEmail | Single line of text | No | |
| Reason | Single line of text | No | 255-char cap |
| DecidedOn | Single line of text | Yes | `YYYY-MM-DD HH:MM` |
| Level | Number (0 decimals) | No | Which approval level acted |

---

## Seed data (matches the app's demo data exactly)

Load these after creating the lists so the live wiring shows the same content as the demo.

**Requisitions** (Currency `USD`, RequesterEmail/SubmittedOn blank):

| Title | PRNumber | Vendor | CostCenter | Amount | Status | Requester | NeededBy | Justification | DecisionMode | DecisionReason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HPLC column replacement — Q2 batch | PR-2026-00184 | MilliporeSigma | QC-AnalyticalDev | 12450.00 | Pending | Lina Roth | 2026-06-12 | Replacement campaign tied to method-transfer for Project Mira. | | |
| Method-transfer reference standards | PR-2026-00181 | MilliporeSigma | RD-Methods | 9810.50 | Review | P. Schurr | 2026-06-04 | Certified reference standards for assay MT-118. | | |
| Cleanroom consumables (Q2) | PR-2026-00183 | VWR International | OPS-Cleanroom | 4820.00 | Pending | J. Hottinger | 2026-05-28 | Routine quarterly replenishment for ISO 7 suite. | | |
| Stability chamber service contract renewal | PR-2026-00182 | Memmert | QC-Stability | 2150.00 | Draft | Lina Roth | 2026-07-01 | Annual PM + IQ/OQ re-qualification. | | |
| Mass-spec consumables — preventative | PR-2026-00180 | Waters | QC-AnalyticalDev | 18240.00 | Approved | Lina Roth | 2026-05-22 | | | |
| Custom synthesis — impurity standards | PR-2026-00178 | Thermo Fisher | RD-Impurities | 24600.00 | Rejected | P. Schurr | 2026-06-30 | Single-source custom synthesis. | Reject | Quote exceeded threshold; re-scope requested. |

**RequisitionLines** (Title = SKU):

| PRNumber | SKU | Description | Qty | Unit | UnitPrice |
| --- | --- | --- | --- | --- | --- |
| PR-2026-00184 | ZGC18-250 | Symmetry C18 column, 5 µm, 4.6 × 250 mm | 4 | ea | 2280.00 |
| PR-2026-00184 | WAT-50000 | Inline filter, 0.5 µm × 0.062 in. | 12 | ea | 110.00 |
| PR-2026-00184 | KIT-09812 | Performance verification kit | 1 | kit | 2010.00 |

**Attachments** (Title = FileName): `PR-2026-00184` / `Quote_MilliporeSigma_2026-05.pdf`

**Suppliers** (all Active = 1): `MilliporeSigma`, `VWR International`, `Memmert`, `Waters`, `Thermo Fisher`

**CostCenters** (all Active = 1): `QC-AnalyticalDev`, `RD-Methods`, `OPS-Cleanroom`, `QC-Stability`, `RD-Impurities`

---

## Wiring the app to the lists

This all-text/number schema is actually the easy case for the app: its collections
already hold plain text and numbers, so there is **no `.Value` / `.DisplayName`
unwrapping anywhere**. Two renames/conversions happen at cache time in `App.OnStart`
(the app's field `Id` collides with SharePoint's built-in numeric ID, and dates come
in as text):

```
ClearCollect(colRequisitions,
    ForAll(Requisitions,
        {
            Id: PRNumber,
            Title: Title,
            Vendor: Vendor,
            CostCenter: CostCenter,
            Amount: Amount,
            Status: Status,
            Requester: Requester,
            NeededBy: DateValue(NeededBy),
            Justification: Justification,
            DecisionMode: DecisionMode,
            DecisionReason: DecisionReason
        }
    )
);
ClearCollect(colRequisitionLines,
    ShowColumns(RequisitionLines, PRNumber, SKU, Description, Qty, Unit, UnitPrice)
);
ClearCollect(colAttachments, ShowColumns(Attachments, PRNumber, FileName));
```

Everything downstream (galleries, detail screen, approvals) keeps working unchanged,
including `Text(NeededBy, "dd mmm yyyy")`, because `DateValue()` restores a real date
inside the collection.

## Notes and trade-offs of the text/number-only rule

- **255-character cap** — Single line of text truncates at 255 chars. `Justification`,
  `Description`, and `Reason` are the columns most likely to hit it. If that ever
  bites, flipping just those columns to "Multiple lines of text (plain)" is a
  one-setting change that doesn't affect the app formulas.
- **Dates sort as text** — only because of the `YYYY-MM-DD` convention. Keep the
  leading zeros (`2026-06-04`, not `2026-6-4`) or sorting and `DateValue()` both break.
- **No Choice columns means no built-in value enforcement** — SharePoint will accept
  any text in `Status`. The app only ever writes the seven documented values; if
  people also edit the list directly, add SharePoint column validation like
  `=OR([Status]="Draft",[Status]="Pending",[Status]="Review",[Status]="Approved",[Status]="Rejected",[Status]="Returned",[Status]="Closed")`.
- **Create the indexes while the lists are empty** (PRNumber everywhere it appears,
  plus Status on Requisitions) — indexed text columns keep `Filter()` delegable and
  avoid the 2,000-row delegation cliff.
- **Flows** (PRNumber autonumber, on-submit routing, decision logging) read/write
  these same text/number columns — no Person or Choice handling needed there either.
