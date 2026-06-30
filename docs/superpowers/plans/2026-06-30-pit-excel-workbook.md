# PIT Excel Workbook (two-tab) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce `excelTool\Portfolio_Import_Tool.xlsm` — one workbook with a **Convert** tab and an **Import** tab — driven by a single unified VBA module, auto-built and validated via Excel automation (win32com). Each tab gathers simplified inputs, derives the rest, runs the matching exe (`Converter.exe` / `Importer.exe`), and shows results.

**Architecture:** The VBA is **data-driven**: one field-definition table per tab (section, internal key, display label, type, default, validation, derived?) drives a generic sheet-builder and a generic config-collector. All user-facing labels and derivation rules live in ONE place, so renaming a field later is a one-line edit (the internal config keys the Python CLIs receive never change). A win32com builder injects the `.bas` and writes the `.xlsm`. Validation drives Excel headlessly: set inputs → generate the config → assert it equals the expected internal config.

**Tech Stack:** VBA (Excel), Python 3.11 + pywin32 (win32com), pytest, PyYAML. Windows + Excel (Office16) with `AccessVBOM=1` (enabled).

## Global Constraints

- **The internal config the Python CLIs receive is UNCHANGED** — same keys/structure as `configs\convert.example.yaml` / the importer config (`paths{}`, `settings{}`, `converter_paths{}`, `parameters_default_values{}`, etc.). The VBA maps friendly labels → internal keys and fills derived values. No Python changes.
- **Centralized labels + derivations:** all display labels and derivation rules live in one VBA definitions block. Renaming = one-line edit. Internal keys stay fixed.
- **Tool Configuration shows only the exe path.** Results-JSON and log paths are derived as `<exe folder>\rics_converter_results.json` / `rics_converter.log` (Convert) and `rics_import_results.json` / `rics_import.log` (Import) — where each CLI writes them. Not shown, not entered.
- **Derivations:**
  - Convert: Start Date entered `mm/dd/yyyy` → emitted as `YYYYMMDD`.
  - Import: single **SG Path** → `paths.assembly_path = <SG Path>`, `paths.runtime_config = <SG Path>\MoodysAnalytics.SG.UI.runtimeconfig.json`, `paths.data_path = <SG Path>\Data`, `paths.model_path = <SG Path>\Models`.
- **Sheet/label names (current; easy to change later):** sheets `PIT_Convert_Config` / `PIT_Import_Config`, results `PIT_Convert_Results` / `PIT_Import_Results`; macros `RunConvert`, `RunImport`, `CreateConfigSheets`. Convert "Output Path" label = **RICSFormatData Path**. Import labels: **SG Path**, **RICSFormatData Path** (`paths.rics_path`), **RICS Sim Output Path** (`paths.output_path`), **Load Existing RICS Sim Path** (`paths.load_sim_path`).
- **Issuer/Bond Output:** empty input ⇒ no outputs (preserve `outputs: []`, `selection: []`).
- **Build artifact** goes to `excelTool\Portfolio_Import_Tool.xlsm` (gitignored `*.xlsm`); the `.bas` source is committed under `excel\`.
- **Excel automation env (verified):** `win32com` in the venv; `AccessVBOM=1` enables VBA import; use **native Windows paths (backslashes)** for `SaveAs`; `.xlsm` = `FileFormat=52`. Reference sources: the two original addins `RICSConverterAddin.bas` (~1400 lines) and `RICSImportAddin.bas` (~1600 lines) in the old projects — reuse their proven helpers (OneDrive path resolution, ADODB UTF-8 write, WScript.Shell exe run, JSON value extraction) but drive layout from field tables instead of hardcoded rows.

---

### Task 1: VBA shared core + field-definition engine

**Files:**
- Create: `excel/PortfolioImportTool.bas` (module `PortfolioImportTool`) — this task adds: constants, the field-definition format + parser, the generic sheet-builder, the generic config-collector, and the shared run/results helpers (ported from the original addins).
- Test: deferred to Task 4 (Excel-automation harness) — VBA can't be unit-tested standalone.

**Interfaces (VBA, used by later tasks):**
- A field definition is a pipe-delimited spec string:
  `"<section>|<internalKey>|<displayLabel>|<type>|<default>|<validation>|<derived>"`
  where `type ∈ {text, bool, date, dropdown, comment}`, `validation` is empty or a CSV list (dropdown) or `mm/dd/yyyy` (date), `derived` is empty or `1` (derived fields are not laid out as inputs).
- `FieldsConvert() As Variant` / `FieldsImport() As Variant` — return arrays of spec strings (defined in Task 2).
- `BuildConfigSheet(ws As Worksheet, fields As Variant, title As String)` — lays out sections + label/value rows, yellow-highlights editable value cells, applies dropdown/date validations, records each field's row in a name→row map stored on the sheet (e.g., via a hidden column or a Names collection) so the collector can read values back.
- `CollectValues(ws As Worksheet, fields As Variant) As Object` — returns a `Scripting.Dictionary` of `internalKey → raw cell value` for every non-derived field.
- Shared helpers ported verbatim-in-spirit from the originals: `GetLocalWorkbookPath`, `ResolveOneDrivePath`, `WriteTextFile` (ADODB UTF-8), `RunExe(exePath, configPath) As Integer` (WScript.Shell), `ReadTextFile`, `ExtractJSONValue(json, key, default)`, `ShowError`.

- [ ] **Step 1: Author the module header, constants, and shared helpers**

Create `excel/PortfolioImportTool.bas` starting with `Attribute VB_Name = "PortfolioImportTool"`, `Option Explicit`, constants for the sheet/results names and macro labels (per Global Constraints), and the shared helpers ported from `RICSConverterAddin.bas` (the originals already contain proven implementations of `GetLocalWorkbookPath`/`ResolveOneDrivePath`/`WriteTextFile`/`ReadTextFile`/`ExtractJSONValue`/`ShowError`; copy them and rename the module-scoped constants). Add `RunExe`:

```vba
Private Function RunExe(exePath As String, configPath As String) As Integer
    On Error GoTo Failed
    Dim wsh As Object: Set wsh = CreateObject("WScript.Shell")
    RunExe = wsh.Run("""" & exePath & """ """ & configPath & """", 0, True)
    Exit Function
Failed:
    ShowError "Error running tool: " & Err.Description
    RunExe = 1
End Function
```

- [ ] **Step 2: Implement the field-definition parser + generic sheet-builder**

```vba
' Field spec indices (0-based fields in the pipe-delimited string)
Private Const F_SECTION As Integer = 0
Private Const F_KEY As Integer = 1
Private Const F_LABEL As Integer = 2
Private Const F_TYPE As Integer = 3
Private Const F_DEFAULT As Integer = 4
Private Const F_VALID As Integer = 5
Private Const F_DERIVED As Integer = 6

Private Function FieldPart(spec As String, idx As Integer) As String
    Dim parts() As String: parts = Split(spec, "|")
    If idx <= UBound(parts) Then FieldPart = Trim(parts(idx)) Else FieldPart = ""
End Function

Private Function IsDerived(spec As String) As Boolean
    IsDerived = (FieldPart(spec, F_DERIVED) = "1")
End Function

' Lays out the sheet from the field table. Stores each input field's row as a
' defined Name "row_<key>" so CollectValues can read it back (rename-safe: the
' Name keys off the internal key, never the display label).
Public Sub BuildConfigSheet(ws As Worksheet, fields As Variant, title As String)
    ws.Cells.Clear
    ws.Range("A1").Value = title
    ws.Range("A1").Font.Bold = True: ws.Range("A1").Font.Size = 14
    Dim row As Long: row = 3
    Dim lastSection As String: lastSection = ""
    Dim i As Long, spec As String
    For i = LBound(fields) To UBound(fields)
        spec = CStr(fields(i))
        If IsDerived(spec) Then GoTo ContinueLoop   ' derived fields are not laid out
        Dim section As String: section = FieldPart(spec, F_SECTION)
        If section <> lastSection Then
            ws.Cells(row, 1).Value = section
            ws.Cells(row, 1).Font.Bold = True
            ws.Cells(row, 1).Interior.Color = RGB(217, 225, 242)
            lastSection = section: row = row + 1
        End If
        Dim key As String: key = FieldPart(spec, F_KEY)
        ws.Cells(row, 1).Value = FieldPart(spec, F_LABEL)
        ws.Cells(row, 2).Value = FieldPart(spec, F_DEFAULT)
        ws.Cells(row, 2).Interior.Color = RGB(255, 255, 200)   ' editable = yellow
        ApplyValidation ws.Cells(row, 2), FieldPart(spec, F_TYPE), FieldPart(spec, F_VALID)
        ws.Names.Add Name:="row_" & key, RefersTo:="=" & ws.Name & "!$B$" & row
        row = row + 1
    Next i
    ws.Columns("A:A").ColumnWidth = 42: ws.Columns("B:B").ColumnWidth = 80
End Sub

Private Sub ApplyValidation(cell As Range, vtype As String, valid As String)
    On Error Resume Next
    cell.Validation.Delete
    If vtype = "bool" Then
        cell.Validation.Add Type:=xlValidateList, Formula1:="TRUE,FALSE"
    ElseIf vtype = "dropdown" And valid <> "" Then
        cell.Validation.Add Type:=xlValidateList, Formula1:=valid
    End If
    On Error GoTo 0
End Sub
```

- [ ] **Step 3: Implement the generic collector**

```vba
Public Function CollectValues(ws As Worksheet, fields As Variant) As Object
    Dim d As Object: Set d = CreateObject("Scripting.Dictionary")
    Dim i As Long, spec As String, key As String
    For i = LBound(fields) To UBound(fields)
        spec = CStr(fields(i))
        If IsDerived(spec) Then GoTo ContinueLoop
        key = FieldPart(spec, F_KEY)
        On Error Resume Next
        d(key) = Trim(CStr(ws.Range("row_" & key).Value))
        On Error GoTo 0
ContinueLoop:
    Next i
    Set CollectValues = d
End Function
```

- [ ] **Step 4: Commit (module compiles only inside Excel; build/test happens in Task 4)**

```bash
git add excel/PortfolioImportTool.bas
git commit -m "feat(excel): VBA shared core + data-driven field-definition engine"
```

---

### Task 2: Convert & Import field tables + YAML assembly

**Files:**
- Modify: `excel/PortfolioImportTool.bas` — add `FieldsConvert()`, `FieldsImport()`, derivation helpers, and `BuildConvertYAML(d)` / `BuildImportYAML(d)`.

**Interfaces:**
- `FieldsConvert() As Variant` / `FieldsImport() As Variant` — `Array(spec, spec, …)`.
- `BuildConvertYAML(values As Object) As String` / `BuildImportYAML(values As Object) As String` — produce the internal YAML (matching `configs\convert.example.yaml` / importer config), applying derivations.
- Derivation helpers: `DeriveDateYYYYMMDD(s)`, `SgRuntimeConfig(sgPath)`, `SgDataPath(sgPath)`, `SgModelPath(sgPath)`.

- [ ] **Step 1: Define the Convert field table**

```vba
Public Function FieldsConvert() As Variant
    FieldsConvert = Array( _
        "Tool Configuration|exe_path|Converter Exe Path|text|.\dist\Converter.exe||", _
        "Paths|data_path|Data Path|text|UserData||", _
        "Paths|output_path|RICSFormatData Path|text|RICS_Files||", _
        "General Settings|start_date|Start Date (mm/dd/yyyy)|date|06/30/2025|mm/dd/yyyy|", _
        "General Settings|GCorr_Corporate_version|GCorr Corporate Version|dropdown|2019|2019,2024|", _
        "General Settings|RICS_version|RICS Version|dropdown|10.6|10.5,10.6|", _
        "Data Types to Process|granular|granularCounterparty|text|GC, GCCRE, AgencyMBS||", _
        "Data Types to Process|portfolio|portfolio|bool|TRUE||", _
        "Advanced Settings|ImpliedCreditClass_default_value|ImpliedCreditClass default|bool|TRUE||", _
        "Advanced Settings|CreditClass_default_value|CreditClass default|text|CS15||", _
        "Advanced Settings|interpolate_lgd_lgdk_for_amortising|Interpolate LGD/LGDK (amortising)|bool|FALSE||", _
        "Advanced Settings|Using_GCorr_Corp_RSQ|Using GCorr Corp RSQ|bool|FALSE||", _
        "Advanced Settings|Using_GCorr_Corp_country|Using GCorr Corp country|bool|TRUE||", _
        "Advanced Settings|Using_GCorr_Corp_industry|Using GCorr Corp industry|bool|FALSE||", _
        "Advanced Settings|corp_rsq_fill_default_value|Fill missing RSQ with default|bool|TRUE||", _
        "Advanced Settings|corp_rsq_default_value|Corp RSQ default value|text|0.159719318||", _
        "Advanced Settings|corp_factors_fill_value_groupby|Fill factors by groupby|bool|TRUE||", _
        "Advanced Settings|corp_private_groupby_columnName|Private groupby column|text|securityType||" _
    )
End Function
```

- [ ] **Step 2: Define the Import field table** (SG sub-paths are `derived=1`, so not laid out)

```vba
Public Function FieldsImport() As Variant
    FieldsImport = Array( _
        "Tool Configuration|exe_path|Importer Exe Path|text|.\dist\Importer.exe||", _
        "Paths|sg_path|SG Path|text|C:\Program Files\Moody's\SG\10.5.0||", _
        "Paths|licence_path|Licence Path|text|||", _
        "Paths|rics_path|RICSFormatData Path|text|RICS_Files||", _
        "Paths|output_path|RICS Sim Output Path|text|output\Portfolio_Import.bhs||", _
        "Paths|load_sim_path|Load Existing RICS Sim Path|text|||", _
        "Settings|load_sim|Load existing sim|bool|FALSE||", _
        "Settings|keep_existing_portfolios|Keep existing portfolios|bool|FALSE||", _
        "Settings|import_economies|Import economies|bool|TRUE||", _
        "Settings|import_transition_matrices|Import transition matrices|bool|TRUE||", _
        "Settings|import_mpr_models|Import MPR models|bool|TRUE||", _
        "Settings|import_zscore_models|Import Z-Score models|bool|TRUE||", _
        "Settings|base_date|Base Date (YYYY-MM-DD)|text|2025-06-30||", _
        "Settings|base_economy|Base Economy|text|USD||", _
        "Merge Data|merge_gc|GC base merge (comma sub-folders)|text|||", _
        "Issuer/Bond Output|outputs|Output types (comma)|text|||", _
        "Issuer/Bond Output|selection|Selection per type (semicolon-separated, comma within)|text|||" _
    )
End Function
```

> Merge Data / structured / user-defined portfolios: this task ships the common
> single-row `merge_gc` and the Issuer/Bond Output pair; the multi-row structured
> and user-defined portfolio grids are added in a follow-up if needed (the YAML
> builder emits empty `structured_portfolios_parameters` defaults so the importer
> config is complete). Keep them in the field table so they render and collect.

- [ ] **Step 3: Implement derivation helpers + `BuildConvertYAML`**

```vba
Private Function DeriveDateYYYYMMDD(s As String) As String
    If IsDate(s) Then DeriveDateYYYYMMDD = Format(CDate(s), "yyyymmdd") Else DeriveDateYYYYMMDD = s
End Function

Private Function Q(s As String) As String   ' yaml double-quote with forward slashes
    Q = """" & Replace(s, "\", "/") & """"
End Function

Public Function BuildConvertYAML(v As Object) As String
    Dim y As String, nl As String: nl = vbLf
    y = "start_date: " & """" & DeriveDateYYYYMMDD(v("start_date")) & """" & nl
    y = y & "RICS_version: """ & v("RICS_version") & """" & nl
    y = y & "GCorr_Corporate_version: """ & v("GCorr_Corporate_version") & """" & nl & nl
    y = y & "converter_paths:" & nl
    y = y & "  data_path: " & Q(v("data_path")) & nl
    y = y & "  output_path: " & Q(v("output_path")) & nl & nl
    y = y & "converter_data_types:" & nl & "  granular:" & nl
    Dim parts() As String, i As Long
    parts = Split(v("granular"), ",")
    For i = LBound(parts) To UBound(parts)
        If Trim(parts(i)) <> "" Then y = y & "    - """ & Trim(parts(i)) & """" & nl
    Next i
    If UCase(v("portfolio")) = "TRUE" Then
        y = y & "  portfolio:" & nl & "    - ""portfolio""" & nl & nl
    Else
        y = y & "  portfolio: []" & nl & nl
    End If
    y = y & "parameters_default_values:" & nl
    y = y & "  ImpliedCreditClass_default_value: " & LCase(v("ImpliedCreditClass_default_value")) & nl
    y = y & "  CreditClass_default_value: """ & v("CreditClass_default_value") & """" & nl
    y = y & "  interpolate_lgd_lgdk_for_amortising: " & LCase(v("interpolate_lgd_lgdk_for_amortising")) & nl
    y = y & "  Using_GCorr_Corp_RSQ: " & LCase(v("Using_GCorr_Corp_RSQ")) & nl
    y = y & "  Using_GCorr_Corp_country: " & LCase(v("Using_GCorr_Corp_country")) & nl
    y = y & "  Using_GCorr_Corp_industry: " & LCase(v("Using_GCorr_Corp_industry")) & nl
    y = y & "  corp_rsq_fill_default_value: " & LCase(v("corp_rsq_fill_default_value")) & nl
    y = y & "  corp_rsq_default_value: " & v("corp_rsq_default_value") & nl
    y = y & "  corp_factors_fill_value_groupby: " & LCase(v("corp_factors_fill_value_groupby")) & nl
    y = y & "  corp_private_groupby_columnName: """ & v("corp_private_groupby_columnName") & """" & nl & nl
    ' fixed blocks (match configs/convert.example.yaml)
    y = y & "file_types:" & nl
    y = y & "  granular: [""issuers"",""factors"",""pds"",""instruments"",""lgd"",""cashflows"",""couponPayments"",""laggard""]" & nl
    y = y & "  portfolio: [""Portfolios"",""Holdings""]" & nl & nl
    y = y & "moodys_internal_data: ""MoodysInternalData""" & nl
    y = y & "GCorr_Corporate: ""GCorr{version}""" & nl
    y = y & "GCorr_files:" & nl
    y = y & "  file_name: ""GCorr {version} Corp R-Squared Factors""" & nl
    y = y & "  factors: ""GCorrCorpFactors{version}""" & nl
    y = y & "  rsqs: ""RatingRSQGCorr{version}""" & nl
    y = y & "Mapping_File: ""GCorr_MappingTables.xlsx""" & nl
    y = y & "Mapping_Tables:" & nl & "  country: ""CountryNameMapping""" & nl & "  countryRegion: ""GCorrFactosMappping""" & nl & nl
    y = y & "model_assumptions:" & nl & "  RSQ:" & nl & "    GC: 0.159719318" & nl & "    GCCRE: 0.2077" & nl & nl
    y = y & "floating_reference_yield_curves:" & nl & "  ""USD 0-EDF SPOT"": ""NominalYieldCurve""" & nl
    BuildConvertYAML = y
End Function
```

- [ ] **Step 4: Implement SG derivations + `BuildImportYAML`** (emits the full importer config incl. derived SG paths, empty outputs ⇒ no outputs)

```vba
Private Function SgRuntimeConfig(sg As String) As String
    SgRuntimeConfig = sg & "\MoodysAnalytics.SG.UI.runtimeconfig.json"
End Function
Private Function SgSub(sg As String, sub_ As String) As String
    SgSub = sg & "\" & sub_
End Function

Public Function BuildImportYAML(v As Object) As String
    Dim y As String, nl As String: nl = vbLf
    Dim sg As String: sg = v("sg_path")
    y = "paths:" & nl
    y = y & "  runtime_config: " & Q(SgRuntimeConfig(sg)) & nl
    y = y & "  assembly_path: " & Q(sg) & nl
    y = y & "  data_path: " & Q(SgSub(sg, "Data")) & nl
    y = y & "  model_path: " & Q(SgSub(sg, "Models")) & nl
    y = y & "  licence_path: " & Q(v("licence_path")) & nl
    y = y & "  rics_path: " & Q(v("rics_path")) & nl
    y = y & "  output_path: " & Q(v("output_path")) & nl
    y = y & "  load_sim_path: " & Q(v("load_sim_path")) & nl & nl
    ' merge data
    y = y & "multiple_gcp_types:" & nl
    Dim merge As String: merge = v("merge_gc")
    If Trim(merge) <> "" Then
        y = y & "  GC:" & nl
        Dim mp() As String, i As Long: mp = Split(merge, ",")
        For i = LBound(mp) To UBound(mp)
            If Trim(mp(i)) <> "" Then y = y & "    - " & Trim(mp(i)) & nl
        Next i
    Else
        y = y & "  {}" & nl
    End If
    y = y & nl
    y = y & "structured_portfolios_parameters: {}" & nl & nl
    y = y & "userDefined_combined_structured_nonstructured_portfolios: {}" & nl & nl
    y = y & "settings:" & nl
    y = y & "  load_sim: " & LCase(v("load_sim")) & nl
    y = y & "  keep_existing_portfolios: " & LCase(v("keep_existing_portfolios")) & nl
    y = y & "  import_economies: " & LCase(v("import_economies")) & nl
    y = y & "  import_transition_matrices: " & LCase(v("import_transition_matrices")) & nl
    y = y & "  import_mpr_models: " & LCase(v("import_mpr_models")) & nl
    y = y & "  import_zscore_models: " & LCase(v("import_zscore_models")) & nl
    y = y & "  base_date: """ & v("base_date") & """" & nl
    y = y & "  base_economy: """ & v("base_economy") & """" & nl & nl
    ' Issuer/Bond Output — empty inputs => empty lists => no outputs added
    y = y & "Issuer_Bond_Output:" & nl
    y = y & "  outputs: [" & QuoteCsv(v("outputs")) & "]" & nl
    y = y & "  selection: [" & SelectionYaml(v("selection")) & "]" & nl
    BuildImportYAML = y
End Function

Private Function QuoteCsv(s As String) As String  ' "A","B"
    Dim p() As String, i As Long, out As String
    If Trim(s) = "" Then Exit Function
    p = Split(s, ","): For i = LBound(p) To UBound(p)
        If Trim(p(i)) <> "" Then out = out & IIf(out = "", "", ",") & """" & Trim(p(i)) & """"
    Next i
    QuoteCsv = out
End Function
Private Function SelectionYaml(s As String) As String  ' "x;y,z" -> ["x"],["y","z"]
    Dim groups() As String, i As Long, out As String
    If Trim(s) = "" Then Exit Function
    groups = Split(s, ";")
    For i = LBound(groups) To UBound(groups)
        If Trim(groups(i)) <> "" Then out = out & IIf(out = "", "", ",") & "[" & QuoteCsv(groups(i)) & "]"
    Next i
    SelectionYaml = out
End Function
```

- [ ] **Step 5: Commit**

```bash
git add excel/PortfolioImportTool.bas
git commit -m "feat(excel): Convert/Import field tables + YAML builders with derivations"
```

---

### Task 3: Public macros (CreateConfigSheets, RunConvert, RunImport, viewers)

**Files:**
- Modify: `excel/PortfolioImportTool.bas`.

**Interfaces:**
- `CreateConfigSheets()` — (re)creates both config sheets via `BuildConfigSheet` and adds Run buttons.
- `RunConvert()` / `RunImport()` — collect → build YAML → write temp config → run exe (from exe-path cell) → read results JSON from `<exe folder>` → render results sheet.
- `ViewConvertLog()` / `ViewImportLog()` / `ViewConvertSummary()`.

- [ ] **Step 1: Implement `CreateConfigSheets` + a generic runner**

```vba
Public Sub CreateConfigSheets()
    BuildConfigSheet GetOrCreateSheet("PIT_Convert_Config"), FieldsConvert(), "Portfolio Import Tool — Convert"
    BuildConfigSheet GetOrCreateSheet("PIT_Import_Config"), FieldsImport(), "Portfolio Import Tool — Import"
    AddRunButton GetOrCreateSheet("PIT_Convert_Config"), "Run Convert", "RunConvert"
    AddRunButton GetOrCreateSheet("PIT_Import_Config"), "Run Import", "RunImport"
End Sub

' descriptor-driven run: which sheet, which fields, which YAML builder, result file name
Private Sub RunTool(sheetName As String, fields As Variant, yaml As String, _
                    resultsName As String, logName As String, resultsSheet As String)
    Dim ws As Worksheet: Set ws = ThisWorkbook.Worksheets(sheetName)
    Dim v As Object: Set v = CollectValues(ws, fields)
    Dim exePath As String: exePath = v("exe_path")
    If Dir(exePath) = "" Then ShowError "Executable not found: " & exePath: Exit Sub
    Dim exeDir As String: exeDir = Left(exePath, InStrRev(exePath, "\") - 1)
    Dim cfg As String: cfg = Environ("TEMP") & "\" & resultsName & ".config.yaml"
    If Not WriteTextFile(cfg, yaml) Then ShowError "Failed to write config": Exit Sub
    Dim rc As Integer: rc = RunExe(exePath, cfg)
    Dim json As String: json = ReadTextFile(exeDir & "\" & resultsName)
    RenderResults GetOrCreateSheet(resultsSheet), json, exeDir & "\" & logName
End Sub

Public Sub RunConvert()
    Dim ws As Worksheet: Set ws = ThisWorkbook.Worksheets("PIT_Convert_Config")
    RunTool "PIT_Convert_Config", FieldsConvert(), BuildConvertYAML(CollectValues(ws, FieldsConvert())), _
            "rics_converter_results.json", "rics_converter.log", "PIT_Convert_Results"
End Sub

Public Sub RunImport()
    Dim ws As Worksheet: Set ws = ThisWorkbook.Worksheets("PIT_Import_Config")
    RunTool "PIT_Import_Config", FieldsImport(), BuildImportYAML(CollectValues(ws, FieldsImport())), _
            "rics_import_results.json", "rics_import.log", "PIT_Import_Results"
End Sub
```

- [ ] **Step 2: Implement `RenderResults`, `AddRunButton`, `GetOrCreateSheet`, viewers**

Port `RenderResults` (status cell green/red, message, elapsed, hyperlinks to output/summary/log) and `AddRunButton` from the original addins' `DisplayResults`/`PopulateResultsSheet`/`AddRunConverterButton`. `GetOrCreateSheet` returns an existing sheet or adds it. Viewers shell `notepad.exe` on the derived log/summary path.

- [ ] **Step 3: Commit**

```bash
git add excel/PortfolioImportTool.bas
git commit -m "feat(excel): macros — CreateConfigSheets, RunConvert/RunImport, results + viewers"
```

---

### Task 4: Workbook builder + Excel-automation validation harness

**Files:**
- Create: `excel/build_workbook.py` (win32com builder)
- Create: `tests/excel/__init__.py`, `tests/excel/test_workbook_yaml.py`

**Interfaces:**
- `build_workbook.build(bas_path, out_xlsm) -> str` — opens Excel, new workbook, imports the `.bas`, runs `CreateConfigSheets`, saves `.xlsm` (FileFormat 52) to `out_xlsm` (Windows path), quits Excel. Returns the output path.
- The validation test drives Excel: build the workbook, set known input cells on each tab (via the `row_<key>` Names), call `BuildConvertYAML`/`BuildImportYAML` through `Application.Run`, parse the returned YAML with PyYAML, and assert it equals the expected internal config (derivations applied).

- [ ] **Step 1: Write the builder**

```python
# excel/build_workbook.py
"""Build excelTool\\Portfolio_Import_Tool.xlsm from excel\\PortfolioImportTool.bas.

Requires Excel + AccessVBOM=1. Run with the venv python:
    .\\.venv\\Scripts\\python excel\\build_workbook.py
"""
from __future__ import annotations
import os, sys
import win32com.client as win32

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BAS = os.path.join(ROOT, "excel", "PortfolioImportTool.bas")
OUT = os.path.join(ROOT, "excelTool", "Portfolio_Import_Tool.xlsm")
XLSM = 52


def build(bas_path: str = BAS, out_xlsm: str = OUT) -> str:
    os.makedirs(os.path.dirname(out_xlsm), exist_ok=True)
    xl = win32.Dispatch("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False
    try:
        wb = xl.Workbooks.Add()
        wb.VBProject.VBComponents.Import(bas_path)
        xl.Run("CreateConfigSheets")
        if os.path.exists(out_xlsm):
            os.remove(out_xlsm)
        wb.SaveAs(out_xlsm, FileFormat=XLSM)
        wb.Close(False)
        return out_xlsm
    finally:
        xl.Quit()


if __name__ == "__main__":
    print("Built:", build())
```

- [ ] **Step 2: Write the YAML-equivalence test (the VBA's "no bugs" gate)**

```python
# tests/excel/test_workbook_yaml.py
"""Validate the VBA config-generation by driving Excel headlessly.

Requires Excel + AccessVBOM=1. Skips if win32com/Excel is unavailable so the
suite stays green elsewhere.
"""
import os
import pytest
import yaml

pytestmark = pytest.mark.skipif(
    os.environ.get("PIT_EXCEL") != "1",
    reason="set PIT_EXCEL=1 to run Excel-automation tests (needs Excel + AccessVBOM)",
)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BAS = os.path.join(ROOT, "excel", "PortfolioImportTool.bas")


def _excel_with_module():
    import win32com.client as win32
    xl = win32.Dispatch("Excel.Application"); xl.Visible = False; xl.DisplayAlerts = False
    wb = xl.Workbooks.Add()
    wb.VBProject.VBComponents.Import(BAS)
    xl.Run("CreateConfigSheets")
    return xl, wb


def _set(xl, wb, sheet, key, value):
    wb.Worksheets(sheet).Range("row_" + key).Value = value


def test_convert_yaml_matches_expected():
    import win32com.client  # noqa
    xl, wb = _excel_with_module()
    try:
        s = "PIT_Convert_Config"
        _set(xl, wb, s, "data_path", "UserData")
        _set(xl, wb, s, "output_path", "RICS_Files")
        _set(xl, wb, s, "start_date", "06/30/2025")
        _set(xl, wb, s, "granular", "GC, GCCRE, AgencyMBS")
        # collect -> build YAML via the VBA
        v = xl.Run("CollectValues", wb.Worksheets(s), xl.Run("FieldsConvert"))
        text = xl.Run("BuildConvertYAML", v)
        cfg = yaml.safe_load(text)
        assert cfg["start_date"] == "20250630"           # mm/dd/yyyy -> YYYYMMDD
        assert cfg["converter_paths"]["data_path"] == "UserData"
        assert cfg["converter_paths"]["output_path"] == "RICS_Files"
        assert cfg["converter_data_types"]["granular"] == ["GC", "GCCRE", "AgencyMBS"]
        assert cfg["moodys_internal_data"] == "MoodysInternalData"
        assert cfg["parameters_default_values"]["CreditClass_default_value"] == "CS15"
    finally:
        wb.Close(False); xl.Quit()


def test_import_yaml_derives_sg_paths_and_empty_outputs():
    import win32com.client  # noqa
    xl, wb = _excel_with_module()
    try:
        s = "PIT_Import_Config"
        _set(xl, wb, s, "sg_path", r"C:\Program Files\Moody's\SG\10.5.0")
        _set(xl, wb, s, "rics_path", "RICS_Files")
        _set(xl, wb, s, "output_path", r"output\sim.bhs")
        _set(xl, wb, s, "base_date", "2025-12-31")
        _set(xl, wb, s, "base_economy", "CAD")
        v = xl.Run("CollectValues", wb.Worksheets(s), xl.Run("FieldsImport"))
        cfg = yaml.safe_load(xl.Run("BuildImportYAML", v))
        p = cfg["paths"]
        assert p["assembly_path"].endswith("10.5.0")
        assert p["runtime_config"].endswith("MoodysAnalytics.SG.UI.runtimeconfig.json")
        assert p["data_path"].endswith("/Data")
        assert p["model_path"].endswith("/Models")
        assert cfg["settings"]["base_economy"] == "CAD"
        assert cfg["Issuer_Bond_Output"]["outputs"] == []      # no values => no outputs
        assert cfg["Issuer_Bond_Output"]["selection"] == []
    finally:
        wb.Close(False); xl.Quit()
```

- [ ] **Step 3: Build the workbook and run the validation**

Run: `.\.venv\Scripts\python excel\build_workbook.py` → confirm `excelTool\Portfolio_Import_Tool.xlsm` is created and opens with both tabs.
Run: `$env:PIT_EXCEL=1; .\.venv\Scripts\python -m pytest tests\excel -v` → both tests pass.
Also confirm the default suite still skips them: `.\.venv\Scripts\python -m pytest -q` (Excel tests skipped, everything else green).

- [ ] **Step 4: Commit**

```bash
git add excel/build_workbook.py tests/excel/
git commit -m "feat(excel): win32com workbook builder + headless YAML-equivalence validation"
```

---

### Task 5: End-to-end workbook smoke (optional, gated)

**Files:**
- Create: `tests/excel/test_workbook_e2e.py` (gated by `PIT_EXCEL=1`)

- [ ] **Step 1: Drive the built workbook to run the Converter exe** — only meaningful once `Converter.exe` exists (Plan 6). Set the Convert tab's `exe_path` to the built `Converter.exe`, set `data_path`/`output_path`, call `RunConvert`, and assert `PIT_Convert_Results` shows success and the output tree appears. If `Converter.exe` is not yet built, skip with a clear reason. Commit.

---

## Self-Review

**Spec coverage (Excel slice, spec §6):**
- Single `.xlsm`, two tabs, unified module — Tasks 1-4. ✓
- Simplified inputs (exe-only Tool Config; derived results/log; SG Path; mm/dd/yyyy; RICSFormatData/RICS Sim Output/Load Existing labels) — Task 2 field tables + derivations. ✓
- Centralized labels + derivations for easy renaming — the field tables + derive helpers are the single source. ✓
- Internal config unchanged (Python untouched) — YAML builders emit the existing config structure; validated by Task 4 against PyYAML. ✓
- "No values ⇒ no outputs" — Task 2 `BuildImportYAML` emits empty lists; asserted in Task 4. ✓
- Auto-build to `excelTool\` via win32com — Task 4 builder. ✓

**Placeholder scan:** New VBA/Python is given in full for the engine, field tables, YAML builders, builder, and tests. Task 3's `RenderResults`/`AddRunButton`/viewers are specified as ports of named, existing functions in the original addins (concrete sources), not invented — acceptable for a port. Task 5 is explicitly optional/gated on Plan 6.

**Type consistency:** field-spec indices (`F_*`), `FieldPart`, `BuildConfigSheet`/`CollectValues` (keyed by internal key via `row_<key>` Names), `BuildConvertYAML`/`BuildImportYAML(values)` are used consistently across tasks and by the Task 4 tests (`xl.Run("FieldsConvert")`, `CollectValues`, `BuildConvertYAML`).

**Risk notes (for execution):**
- VBA can't be unit-tested standalone; the Task 4 Excel-automation harness is the gate. It is `PIT_EXCEL=1`-gated so the normal suite stays green on machines without Excel.
- `xl.Run` passing a COM Dictionary object between Python and VBA (`CollectValues` → `BuildConvertYAML`) must round-trip; if COM marshalling of `Scripting.Dictionary` across `xl.Run` is unreliable, the test instead calls a single VBA entry (e.g., `BuildConvertYAMLFromSheet(sheetName)`) that collects + builds internally and returns the string. Add that thin wrapper if needed (note in report).
- Structured/user-defined portfolio multi-row grids are deferred (field table emits empty defaults); add when required.
