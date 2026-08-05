# Solvias Requisitions — built canvas app

Canvas app (tablet, 1366 × 768) compiled from the `Requisition_Management_App_3.zip`
Power Apps handoff package (`powerapps-handoff/pa-yaml/` source-format YAML).

## Contents

| Path | Purpose |
| --- | --- |
| `SolviasRequisitions.msapp` | The built canvas app. Import into Power Apps Studio. |
| `sources/SolviasRequisitions.msapr` | msapp-reference archive (everything except `Src/`) used by `pac canvas pack` (SourceCode layout). |
| `sources/Src/*.pa.yaml` | App + 8 screen sources (Dashboard, Requisitions, RequisitionDetail, NewRequisition, Approvals, Suppliers, Analytics, Settings). |

## Import

1. In Power Apps: **Apps → Import canvas app** (or open the `.msapp` directly from Studio: **Open → Browse**).
2. Open the app **for edit** in Studio once before playing it — the app is packed with
   `LoadFromYaml: true`, so Studio rebuilds the control tree from the YAML sources on
   first open (this is the documented `pac canvas pack` validation step).
3. Run **App.OnStart** (App → Run OnStart) to load the demo collections.
4. Save. Studio regenerates the compiled control JSON and checksums.

## Rebuild from sources

```bash
pac canvas pack --sources ./sources --msapp SolviasRequisitions.msapp --layout SourceCode --overwrite
```

Requires Power Platform CLI ≥ 2.x (`dotnet tool install --global Microsoft.PowerApps.CLI.Tool`,
needs the .NET 10 SDK).

## Build notes / deviations from the handoff zip

- The handoff shipped only `Src/*.pa.yaml` files; the SourceCode packer additionally
  requires a `.msapr` reference archive (Header/Properties/References/Resources of a
  base msapp). The `.msapr` here was seeded from Microsoft's own modern test app
  (`microsoft/PowerApps-Tooling`, `Persistence.Tests/_TestData/AlmApps`, DocVersion 1.348 /
  MSAppStructureVersion 2.4.0 — the minimum versions the packer supports) and then
  cleaned: `DataSources.json` emptied, `LocalDatabaseReferences` cleared,
  `ComponentsMetadata.json` emptied and the stray component removed, app renamed,
  layout already tablet 1366 × 768 landscape.
- Screen files were flattened from `Src/Screens/*.pa.yaml` to `Src/*.pa.yaml` to match
  the documented msapp source layout.
- Renamed all 18 Gallery variants from the retired early-preview names
  (`galleryVertical`/`galleryHorizontal`) to the Source Code schema names
  (`Vertical`/`Horizontal`) — Studio rejects the old names with
  `PA2109: Unknown variant` / `PA4102: Early Preview code detected` on import.
- Fixed 4 YAML syntax errors in `NewRequisition.pa.yaml` (lines with
  `OnChange: =Patch(colNewLines, ThisItem, {SKU: Self.Text})` etc.): an unquoted
  `{Key: Value}` record literal breaks YAML parsing, so those formulas were moved to
  `|-` block scalars. The same four lines are also broken in the handoff's paste-code
  fragment `yaml/new-requisition.yaml` if anyone uses the paste-code route.
- Suppliers, Analytics and Settings are titled stubs by design (per the handoff README);
  their bodies are specced in the zip's `screens-spec.md`.
- The app runs entirely on demo collections from `App.OnStart`. Wiring to the real
  SharePoint lists (provisioning schema, seed data, flows) is described in the zip's
  `sharepoint-lists.md` and `data-model.md` and is a separate step.
