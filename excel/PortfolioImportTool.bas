Attribute VB_Name = "PortfolioImportTool"
' =========================================================================
' Portfolio Import Tool - Unified Excel VBA Module v1.0.0
' =========================================================================
' Data-driven: field tables drive sheet layout, config collection, and YAML.
' Shared helpers ported from RICSConverterAddin.bas.
'
' Public macros: CreateConfigSheets, RunConvert, RunImport,
'                ViewConvertLog, ViewImportLog, ViewConvertSummary
' =========================================================================

Option Explicit

' =========================================================================
' CONSTANTS
' =========================================================================
Private Const TOOL_NAME As String = "Portfolio Import Tool"
Private Const CONVERT_CONFIG_SHEET As String = "PIT_Convert_Config"
Private Const IMPORT_CONFIG_SHEET As String = "PIT_Import_Config"
Private Const CONVERT_RESULTS_SHEET As String = "PIT_Convert_Results"
Private Const IMPORT_RESULTS_SHEET As String = "PIT_Import_Results"
Private Const CONVERT_RESULTS_JSON As String = "rics_converter_results.json"
Private Const CONVERT_LOG As String = "rics_converter.log"
Private Const IMPORT_RESULTS_JSON As String = "rics_import_results.json"
Private Const IMPORT_LOG As String = "rics_import.log"

' =========================================================================
' FIELD-SPEC INDICES (0-based positions in pipe-delimited spec string)
' =========================================================================
Private Const F_SECTION As Integer = 0
Private Const F_KEY As Integer = 1
Private Const F_LABEL As Integer = 2
Private Const F_TYPE As Integer = 3
Private Const F_DEFAULT As Integer = 4
Private Const F_VALID As Integer = 5
Private Const F_DERIVED As Integer = 6

' =========================================================================
' FIELD-DEFINITION ENGINE
' =========================================================================

Private Function FieldPart(spec As String, idx As Integer) As String
    Dim parts() As String: parts = Split(spec, "|")
    If idx <= UBound(parts) Then FieldPart = Trim(parts(idx)) Else FieldPart = ""
End Function

Private Function IsDerived(spec As String) As Boolean
    IsDerived = (FieldPart(spec, F_DERIVED) = "1")
End Function

' Lays out the sheet from the field table. Stores each input field's row as a
' defined Name "row_<key>" so CollectValues can read it back.
' Returns the first free row after layout (so grids can continue below it).
Public Function BuildConfigSheet(ws As Worksheet, fields As Variant, title As String) As Long
    ws.Cells.Clear
    ws.Range("A1").Value = title
    ws.Range("A1").Font.Bold = True
    ws.Range("A1").Font.Size = 14
    Dim row As Long: row = 3
    Dim lastSection As String: lastSection = ""
    Dim i As Long, spec As String
    For i = LBound(fields) To UBound(fields)
        spec = CStr(fields(i))
        If IsDerived(spec) Then GoTo ContinueLoop
        Dim section As String: section = FieldPart(spec, F_SECTION)
        If section <> lastSection Then
            ws.Cells(row, 1).Value = section
            ws.Cells(row, 1).Font.Bold = True
            ws.Cells(row, 1).Interior.Color = RGB(217, 225, 242)
            lastSection = section
            row = row + 1
        End If
        Dim key As String: key = FieldPart(spec, F_KEY)
        ws.Cells(row, 1).Value = FieldPart(spec, F_LABEL)
        ws.Cells(row, 2).Value = FieldPart(spec, F_DEFAULT)
        ws.Cells(row, 2).Interior.Color = RGB(255, 255, 200)
        ApplyValidation ws.Cells(row, 2), FieldPart(spec, F_TYPE), FieldPart(spec, F_VALID)
        ws.Names.Add Name:="row_" & key, RefersTo:="=" & ws.Name & "!$B$" & row
        row = row + 1
ContinueLoop:
    Next i
    ws.Columns("A:A").ColumnWidth = 42
    ws.Columns("B:B").ColumnWidth = 80
    BuildConfigSheet = row
End Function

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

' =========================================================================
' FIELD TABLES
' =========================================================================

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
        "Advanced Settings|ImpliedCreditClass_default_value|ImpliedCreditClass default value|bool|TRUE||", _
        "Advanced Settings|CreditClass_default_value|CreditClass default value|text|CS15||", _
        "Advanced Settings|interpolate_lgd_lgdk_for_amortising|Interpolate LGD/LGDK (amortising)|bool|FALSE||", _
        "Advanced Settings|Using_GCorr_Corp_RSQ|Using GCorr Corp RSQ|bool|FALSE||", _
        "Advanced Settings|Using_GCorr_Corp_country|Using GCorr Corp country|bool|TRUE||", _
        "Advanced Settings|Using_GCorr_Corp_industry|Using GCorr Corp industry|bool|FALSE||", _
        "Advanced Settings|corp_rsq_fill_default_value|Fill missing RSQ with default value|bool|TRUE||", _
        "Advanced Settings|corp_rsq_default_value|Corp RSQ default value|text|0.159719318||", _
        "Advanced Settings|corp_factors_fill_value_groupby|Fill factors by groupby|bool|TRUE||", _
        "Advanced Settings|corp_private_groupby_columnName|Private groupby column|text|securityType||" _
    )
End Function

Public Function FieldsImport() As Variant
    FieldsImport = Array( _
        "Tool Configuration|exe_path|Importer Exe Path|text|.\dist\Importer.exe||", _
        "Paths|sg_path|SG Path|text|C:\Program Files\Moody's\SG\10.5.0||", _
        "Paths|licence_path|Licence Path|text|||", _
        "Paths|rics_path|RICSFormatData Path|text|RICS_Files||", _
        "Paths|output_path|RICSSimOutput Path|text|output\Portfolio_Import.bhs||", _
        "Paths|load_sim_path|LoadExistingRICSSim Path|text|||", _
        "Settings|load_sim|Load Existing Sim|bool|FALSE||", _
        "Settings|keep_existing_portfolios|Keep Existing Portfolios|bool|FALSE||", _
        "Settings|import_economies|Import Economies|bool|TRUE||", _
        "Settings|import_transition_matrices|Import Transition Matrices|bool|TRUE||", _
        "Settings|import_mpr_models|Import MPR Models|bool|TRUE||", _
        "Settings|import_zscore_models|Import Z-Score Models|bool|TRUE||", _
        "Settings|base_date|Base Date|text|2025-06-30||", _
        "Settings|base_economy|Base Economy|text|USD||" _
    )
End Function

' =========================================================================
' DERIVATION HELPERS
' =========================================================================

Private Function DeriveDateYYYYMMDD(s As String) As String
    If IsDate(s) Then DeriveDateYYYYMMDD = Format(CDate(s), "yyyymmdd") Else DeriveDateYYYYMMDD = s
End Function

Private Function Q(s As String) As String   ' yaml double-quote with forward slashes
    Q = """" & Replace(s, "\", "/") & """"
End Function

Private Function SgRuntimeConfig(sg As String) As String
    SgRuntimeConfig = sg & "\MoodysAnalytics.SG.UI.runtimeconfig.json"
End Function

Private Function SgSub(sg As String, sub_ As String) As String
    SgSub = sg & "\" & sub_
End Function

' Resolve a path for the config/exe. Absolute paths (X:\... or \\UNC) are kept
' as-is; relative paths are made absolute against the workbook's folder, so the
' tool works regardless of the working directory Excel launches the exe from.
' (When the workbook is unsaved, GetLocalWorkbookPath is "" and the relative
' path is returned unchanged.)
Private Function ResolvePath(p As String) As String
    Dim s As String: s = Trim(p)
    If s = "" Then Exit Function
    If Left(s, 2) = "\\" Or (Len(s) >= 2 And Mid(s, 2, 1) = ":") Then
        ResolvePath = s: Exit Function
    End If
    If Left(s, 2) = ".\" Then s = Mid(s, 3)
    Dim base As String: base = GetLocalWorkbookPath()
    If base = "" Then ResolvePath = s Else ResolvePath = base & "\" & s
End Function

' =========================================================================
' YAML BUILDERS
' =========================================================================

Public Function BuildConvertYAML(v As Object) As String
    Dim y As String, nl As String: nl = vbLf
    y = "start_date: " & """" & DeriveDateYYYYMMDD(v("start_date")) & """" & nl
    y = y & "RICS_version: """ & v("RICS_version") & """" & nl
    y = y & "GCorr_Corporate_version: """ & v("GCorr_Corporate_version") & """" & nl & nl
    y = y & "converter_paths:" & nl
    y = y & "  data_path: " & Q(ResolvePath(v("data_path"))) & nl
    y = y & "  output_path: " & Q(ResolvePath(v("output_path"))) & nl & nl
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
    y = y & "moodys_internal_data: " & Q(ResolvePath("MoodysInternalData")) & nl
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

' Combines the simple field-table values (via CollectValues) with the 4 grid
' sections (read back via their recorded Names) into the importer YAML.
Public Function BuildImportYAML(ws As Worksheet) As String
    Dim y As String, nl As String: nl = vbLf
    Dim v As Object: Set v = CollectValues(ws, FieldsImport())
    Dim sg As String: sg = ResolvePath(v("sg_path"))

    ' --- paths ---
    y = "paths:" & nl
    y = y & "  runtime_config: " & Q(SgRuntimeConfig(sg)) & nl
    y = y & "  assembly_path: " & Q(sg) & nl
    y = y & "  data_path: " & Q(SgSub(sg, "Data")) & nl
    y = y & "  model_path: " & Q(SgSub(sg, "Models")) & nl
    y = y & "  licence_path: " & Q(ResolvePath(v("licence_path"))) & nl
    y = y & "  rics_path: " & Q(ResolvePath(v("rics_path"))) & nl
    y = y & "  output_path: " & Q(ResolvePath(v("output_path"))) & nl
    y = y & "  load_sim_path: " & Q(ResolvePath(v("load_sim_path"))) & nl & nl

    ' --- multiple_gcp_types ---
    y = y & BuildGCPTypesYAML(ws) & nl

    ' --- structured_portfolios_parameters ---
    y = y & BuildStructuredPortfoliosYAML(ws) & nl

    ' --- userDefined_combined_structured_nonstructured_portfolios ---
    y = y & BuildUserDefinedPortfoliosYAML(ws) & nl

    ' --- settings ---
    y = y & "settings:" & nl
    y = y & "  load_sim: " & LCase(v("load_sim")) & nl
    y = y & "  keep_existing_portfolios: " & LCase(v("keep_existing_portfolios")) & nl
    y = y & "  import_economies: " & LCase(v("import_economies")) & nl
    y = y & "  import_transition_matrices: " & LCase(v("import_transition_matrices")) & nl
    y = y & "  import_mpr_models: " & LCase(v("import_mpr_models")) & nl
    y = y & "  import_zscore_models: " & LCase(v("import_zscore_models")) & nl
    y = y & "  base_date: """ & v("base_date") & """" & nl
    y = y & "  base_economy: """ & v("base_economy") & """" & nl & nl

    ' --- Issuer_Bond_Output ---
    y = y & BuildIssuerBondOutputYAML(ws)

    BuildImportYAML = y
End Function

Private Function GridFirstRow(ws As Worksheet, nm As String) As Long
    On Error Resume Next
    GridFirstRow = ws.Range(nm).Row
    On Error GoTo 0
End Function

Private Function BuildGCPTypesYAML(ws As Worksheet) As String
    Dim yaml As String: yaml = "multiple_gcp_types:"
    Dim f As Long, l As Long, r As Long
    f = GridFirstRow(ws, "imp_gcp_first")
    l = GridFirstRow(ws, "imp_gcp_last")
    If f = 0 Or l = 0 Then BuildGCPTypesYAML = yaml & " {}" & vbLf: Exit Function
    Dim hasTypes As Boolean: hasTypes = False
    For r = f To l
        Dim baseFolder As String, subTypes As String
        baseFolder = Trim(CStr(ws.Cells(r, 1).Value))
        subTypes = Trim(CStr(ws.Cells(r, 2).Value))
        If baseFolder <> "" And subTypes <> "" Then
            If Not hasTypes Then yaml = yaml & vbLf
            hasTypes = True
            yaml = yaml & "  " & baseFolder & ":" & vbLf
            Dim parts() As String, i As Long
            parts = Split(subTypes, ",")
            For i = LBound(parts) To UBound(parts)
                If Trim(parts(i)) <> "" Then yaml = yaml & "    - " & Trim(parts(i)) & vbLf
            Next i
        End If
    Next r
    If Not hasTypes Then yaml = yaml & " {}" & vbLf
    BuildGCPTypesYAML = yaml
End Function

Private Function BuildStructuredPortfoliosYAML(ws As Worksheet) As String
    Dim yaml As String: yaml = "structured_portfolios_parameters:" & vbLf
    Dim f As Long, l As Long, r As Long
    f = GridFirstRow(ws, "imp_struct_first")
    l = GridFirstRow(ws, "imp_struct_last")
    If f = 0 Or l = 0 Then BuildStructuredPortfoliosYAML = yaml: Exit Function
    For r = f To l
        Dim pType As String, enabled As String, ccy As String, wt As String
        pType = Trim(CStr(ws.Cells(r, 1).Value))
        enabled = Trim(CStr(ws.Cells(r, 2).Value))
        ccy = Trim(CStr(ws.Cells(r, 3).Value))
        wt = Trim(CStr(ws.Cells(r, 4).Value))
        If pType <> "" Then
            If ccy = "" Then ccy = "USD"
            If wt = "" Then wt = "MarketValue"
            Dim boolVal As String
            boolVal = IIf(UCase(enabled) = "TRUE", "true", "false")
            yaml = yaml & "  " & pType & ": [" & boolVal & "," & Chr(39) & ccy & Chr(39) & "," & Chr(39) & wt & Chr(39) & "]" & vbLf
        End If
    Next r
    BuildStructuredPortfoliosYAML = yaml
End Function

Private Function BuildUserDefinedPortfoliosYAML(ws As Worksheet) As String
    Dim yaml As String: yaml = "userDefined_combined_structured_nonstructured_portfolios:" & vbLf
    Dim f As Long, l As Long, r As Long
    f = GridFirstRow(ws, "imp_udef_first")
    l = GridFirstRow(ws, "imp_udef_last")
    If f = 0 Or l = 0 Then BuildUserDefinedPortfoliosYAML = yaml & " {}" & vbLf: Exit Function
    Dim hasEntries As Boolean: hasEntries = False
    For r = f To l
        Dim pName As String, toMerge As String, ccy As String, wt As String
        pName = Trim(CStr(ws.Cells(r, 1).Value))
        toMerge = Trim(CStr(ws.Cells(r, 2).Value))
        ccy = Trim(CStr(ws.Cells(r, 3).Value))
        wt = Trim(CStr(ws.Cells(r, 4).Value))
        If pName <> "" And toMerge <> "" Then
            hasEntries = True
            If ccy = "" Then ccy = "USD"
            If wt = "" Then wt = "MarketValue"
            Dim pArr() As String, i As Long
            pArr = Split(toMerge, ",")
            Dim pList As String: pList = "["
            For i = LBound(pArr) To UBound(pArr)
                Dim p As String: p = Trim(CStr(pArr(i)))
                If p <> "" Then
                    If pList <> "[" Then pList = pList & ", "
                    pList = pList & """" & p & """"
                End If
            Next i
            pList = pList & "]"
            yaml = yaml & "  " & pName & ": [" & pList & "," & Chr(39) & ccy & Chr(39) & "," & Chr(39) & wt & Chr(39) & "]" & vbLf
        End If
    Next r
    If Not hasEntries Then yaml = yaml & " {}" & vbLf
    BuildUserDefinedPortfoliosYAML = yaml
End Function

Private Function BuildIssuerBondOutputYAML(ws As Worksheet) As String
    Dim yaml As String: yaml = "Issuer_Bond_Output:" & vbLf
    Dim f As Long, l As Long, r As Long
    f = GridFirstRow(ws, "imp_out_first")
    l = GridFirstRow(ws, "imp_out_last")
    If f = 0 Or l = 0 Then
        BuildIssuerBondOutputYAML = yaml & "  outputs: []" & vbLf & "  selection: []" & vbLf
        Exit Function
    End If
    Dim outputList As String: outputList = "["
    Dim selectionList As String: selectionList = "["
    Dim hasData As Boolean: hasData = False
    For r = f To l
        Dim outputName As String, selStr As String
        outputName = Trim(CStr(ws.Cells(r, 1).Value))
        selStr = Trim(CStr(ws.Cells(r, 2).Value))
        If outputName <> "" Then
            hasData = True
            If outputList <> "[" Then outputList = outputList & ", "
            outputList = outputList & """" & outputName & """"
            If selectionList <> "[" Then selectionList = selectionList & ", "
            If selStr = "" Then
                selectionList = selectionList & "[]"
            Else
                Dim selArr() As String, j As Long
                selArr = Split(selStr, ",")
                Dim selBlock As String: selBlock = "["
                For j = LBound(selArr) To UBound(selArr)
                    Dim sel As String: sel = Trim(CStr(selArr(j)))
                    If sel <> "" Then
                        If selBlock <> "[" Then selBlock = selBlock & ", "
                        selBlock = selBlock & """" & sel & """"
                    End If
                Next j
                selectionList = selectionList & selBlock & "]"
            End If
        End If
    Next r
    ' FIX vs old addin: empty grid => empty lists, no CreditClass/TotalValue fallback
    If Not hasData Then
        yaml = yaml & "  outputs: []" & vbLf & "  selection: []" & vbLf
    Else
        yaml = yaml & "  outputs: " & outputList & "]" & vbLf
        yaml = yaml & "  selection: " & selectionList & "]" & vbLf
    End If
    BuildIssuerBondOutputYAML = yaml
End Function

' =========================================================================
' PUBLIC MACROS
' =========================================================================

Public Sub CreateConfigSheets()
    Dim discard As Long
    discard = BuildConfigSheet(GetOrCreateSheet(CONVERT_CONFIG_SHEET), FieldsConvert(), "Portfolio Import Tool - Convert")
    Dim wsImp As Worksheet: Set wsImp = GetOrCreateSheet(IMPORT_CONFIG_SHEET)
    Dim nextRow As Long
    nextRow = BuildConfigSheet(wsImp, FieldsImport(), "Portfolio Import Tool - Import")
    nextRow = nextRow + 1   ' blank separator row before grids
    BuildImportGrids wsImp, nextRow
    AddRunButton GetOrCreateSheet(CONVERT_CONFIG_SHEET), "Run Convert", "RunConvert"
    AddRunButton wsImp, "Run Import", "RunImport", 62
    ' Left-align all cells on both config tabs
    GetOrCreateSheet(CONVERT_CONFIG_SHEET).Columns("A:F").HorizontalAlignment = xlLeft
    wsImp.Columns("A:F").HorizontalAlignment = xlLeft
End Sub

' =========================================================================
' IMPORT GRID BUILDERS  (4 multi-column sections, dynamic Names)
' Section order on sheet: A. GCP, B. Output, C. Structured, D. UserDefined.
' Each grid records its data-row range as sheet-scoped defined Names so the
' YAML builder reads it back dynamically (no fixed row constants).
' =========================================================================

Private Sub BuildImportGrids(ws As Worksheet, startRow As Long)
    Dim r As Long: r = startRow
    r = BuildGCPGrid(ws, r)
    r = r + 1
    r = BuildOutputGrid(ws, r)
    r = r + 1
    r = BuildStructuredGrid(ws, r)
    r = r + 1
    r = BuildUserDefinedGrid(ws, r)
End Sub

Private Sub GridSectionHeader(ws As Worksheet, r As Long, title As String)
    ws.Cells(r, 1).Value = title
    ws.Cells(r, 1).Font.Bold = True
    ws.Cells(r, 1).Interior.Color = RGB(217, 225, 242)
End Sub

Private Sub GridColumnHeader(ws As Worksheet, r As Long, lastCol As Long)
    ws.Range(ws.Cells(r, 1), ws.Cells(r, lastCol)).Font.Bold = True
    ws.Range(ws.Cells(r, 1), ws.Cells(r, lastCol)).Interior.Color = RGB(242, 242, 242)
End Sub

' A. Merge Data — MULTIPLE GCP TYPES (A=Base Folder, B=Sub-Types [yellow])
Private Function BuildGCPGrid(ws As Worksheet, startRow As Long) As Long
    Dim r As Long: r = startRow
    GridSectionHeader ws, r, "Merge Data Settings": r = r + 1
    ws.Cells(r, 1).Value = "Base Folder"
    ws.Cells(r, 2).Value = "Sub-Types to Merge (comma-separated, leave blank to skip)"
    GridColumnHeader ws, r, 2: r = r + 1
    ws.Names.Add Name:="imp_gcp_first", RefersTo:="=" & ws.Name & "!$A$" & r
    ws.Cells(r, 1).Value = "GC":          ws.Cells(r, 2).Value = "GCP_CLO": r = r + 1
    ws.Cells(r, 1).Value = "GCCRE":       ws.Cells(r, 2).Value = "": r = r + 1
    ws.Cells(r, 1).Value = "GCRETAIL":    ws.Cells(r, 2).Value = "": r = r + 1
    ws.Cells(r, 1).Value = "GCPD":        ws.Cells(r, 2).Value = "": r = r + 1
    ws.Cells(r, 1).Value = "GCCREPD":     ws.Cells(r, 2).Value = "": r = r + 1
    ws.Cells(r, 1).Value = "GCRETAILPD":  ws.Cells(r, 2).Value = "": r = r + 1
    ws.Names.Add Name:="imp_gcp_last", RefersTo:="=" & ws.Name & "!$A$" & (r - 1)
    Dim f As Long: f = ws.Range("imp_gcp_first").Row
    Dim l As Long: l = ws.Range("imp_gcp_last").Row
    ws.Range(ws.Cells(f, 2), ws.Cells(l, 2)).Interior.Color = RGB(255, 255, 200)
    BuildGCPGrid = r
End Function

' B. Issuer/Bond Output — ISSUER/BOND OUTPUT CONFIGURATION
' (A=Output Types [yellow], B=Selection [yellow]). 8 EMPTY rows (empty => no outputs).
Private Function BuildOutputGrid(ws As Worksheet, startRow As Long) As Long
    Dim r As Long: r = startRow
    GridSectionHeader ws, r, "Issuer/Bond Output Settings": r = r + 1
    ws.Cells(r, 1).Value = "Output Types"
    ws.Cells(r, 2).Value = "Selection (comma-separated, one per output type)"
    GridColumnHeader ws, r, 2: r = r + 1
    ws.Names.Add Name:="imp_out_first", RefersTo:="=" & ws.Name & "!$A$" & r
    Dim j As Long
    For j = 1 To 8
        ws.Cells(r, 1).Value = "": ws.Cells(r, 2).Value = "": r = r + 1
    Next j
    ws.Names.Add Name:="imp_out_last", RefersTo:="=" & ws.Name & "!$A$" & (r - 1)
    Dim f As Long: f = ws.Range("imp_out_first").Row
    Dim l As Long: l = ws.Range("imp_out_last").Row
    ws.Range(ws.Cells(f, 1), ws.Cells(l, 2)).Interior.Color = RGB(255, 255, 200)
    ' Dropdown validation (match old addin): output types and selection lists
    Dim k As Long
    For k = f To l
        On Error Resume Next
        ws.Cells(k, 1).Validation.Delete
        ws.Cells(k, 1).Validation.Add Type:=xlValidateList, _
            Formula1:="CreditClass,DefaultFlag,TotalValue,Price,Interest,Principal,Recovery,TotalReturn,TotalReturnIndex"
        ws.Cells(k, 2).Validation.Delete
        ws.Cells(k, 2).Validation.Add Type:=xlValidateList, _
            Formula1:="All,GC,GCPD,GCCRE,GCCREPD,GCRETAIL,GCRETAILPD,MBS"
        On Error GoTo 0
    Next k
    BuildOutputGrid = r
End Function

' C. Structured Portfolios — STRUCTURED PORTFOLIOS PARAMETERS
' (A=Type, B=Enabled [bool], C=Currency, D=Weight Definition). B:D yellow.
Private Function BuildStructuredGrid(ws As Worksheet, startRow As Long) As Long
    Dim r As Long: r = startRow
    GridSectionHeader ws, r, "Structured Portfolios Settings": r = r + 1
    ws.Cells(r, 1).Value = "Portfolio Type"
    ws.Cells(r, 2).Value = "Enabled (TRUE/FALSE)"
    ws.Cells(r, 3).Value = "Currency"
    ws.Cells(r, 4).Value = "Weight Definition"
    GridColumnHeader ws, r, 4: r = r + 1
    ws.Names.Add Name:="imp_struct_first", RefersTo:="=" & ws.Name & "!$A$" & r
    ws.Cells(r,1).Value="agency_cmbs":                  ws.Cells(r,2).Value="FALSE": ws.Cells(r,3).Value="USD": ws.Cells(r,4).Value="MarketValue": r=r+1
    ws.Cells(r,1).Value="structured_clo":               ws.Cells(r,2).Value="FALSE": ws.Cells(r,3).Value="USD": ws.Cells(r,4).Value="MarketValue": r=r+1
    ws.Cells(r,1).Value="structured_cre":               ws.Cells(r,2).Value="FALSE": ws.Cells(r,3).Value="USD": ws.Cells(r,4).Value="MarketValue": r=r+1
    ws.Cells(r,1).Value="structured_retail":            ws.Cells(r,2).Value="FALSE": ws.Cells(r,3).Value="USD": ws.Cells(r,4).Value="MarketValue": r=r+1
    ws.Cells(r,1).Value="all_structured_selected":      ws.Cells(r,2).Value="FALSE": ws.Cells(r,3).Value="USD": ws.Cells(r,4).Value="MarketValue": r=r+1
    ws.Cells(r,1).Value="all_structured":               ws.Cells(r,2).Value="FALSE": ws.Cells(r,3).Value="USD": ws.Cells(r,4).Value="MarketValue": r=r+1
    ws.Cells(r,1).Value="all_structured_nonstructured": ws.Cells(r,2).Value="FALSE": ws.Cells(r,3).Value="USD": ws.Cells(r,4).Value="MarketValue": r=r+1
    ws.Names.Add Name:="imp_struct_last", RefersTo:="=" & ws.Name & "!$A$" & (r - 1)
    Dim f As Long: f = ws.Range("imp_struct_first").Row
    Dim l As Long: l = ws.Range("imp_struct_last").Row
    Dim k As Long
    For k = f To l
        On Error Resume Next
        ws.Cells(k, 2).Validation.Delete
        ws.Cells(k, 2).Validation.Add Type:=xlValidateList, Formula1:="TRUE,FALSE"
        On Error GoTo 0
    Next k
    ws.Range(ws.Cells(f, 2), ws.Cells(l, 4)).Interior.Color = RGB(255, 255, 200)
    BuildStructuredGrid = r
End Function

' D. User Defined Portfolios — USER DEFINED COMBINED PORTFOLIOS
' (A=Name, B=Portfolios to Merge, C=Currency, D=Weight Definition). A:D yellow. 7 empty rows.
Private Function BuildUserDefinedGrid(ws As Worksheet, startRow As Long) As Long
    Dim r As Long: r = startRow
    GridSectionHeader ws, r, "User Defined Combined Portfolios Settings": r = r + 1
    ws.Cells(r, 1).Value = "Portfolio Name"
    ws.Cells(r, 2).Value = "Portfolios to Merge (comma-separated)"
    ws.Cells(r, 3).Value = "Currency"
    ws.Cells(r, 4).Value = "Weight Definition"
    GridColumnHeader ws, r, 4: r = r + 1
    ws.Names.Add Name:="imp_udef_first", RefersTo:="=" & ws.Name & "!$A$" & r
    Dim j As Long
    For j = 1 To 7
        ws.Cells(r, 1).Value = "": ws.Cells(r, 2).Value = "": ws.Cells(r, 3).Value = "": ws.Cells(r, 4).Value = "": r = r + 1
    Next j
    ws.Names.Add Name:="imp_udef_last", RefersTo:="=" & ws.Name & "!$A$" & (r - 1)
    Dim f As Long: f = ws.Range("imp_udef_first").Row
    Dim l As Long: l = ws.Range("imp_udef_last").Row
    ws.Range(ws.Cells(f, 1), ws.Cells(l, 4)).Interior.Color = RGB(255, 255, 200)
    BuildUserDefinedGrid = r
End Function

' Descriptor-driven run: which sheet, which fields, which YAML builder, result file name
Private Sub RunTool(sheetName As String, fields As Variant, yaml As String, _
                    resultsName As String, logName As String, resultsSheet As String)
    Dim ws As Worksheet: Set ws = ThisWorkbook.Worksheets(sheetName)
    Dim v As Object: Set v = CollectValues(ws, fields)
    Dim exePath As String: exePath = ResolvePath(v("exe_path"))
    If Dir(exePath) = "" Then ShowError "Executable not found: " & exePath: Exit Sub
    Dim exeDir As String: exeDir = Left(exePath, InStrRev(exePath, "\") - 1)
    Dim cfg As String: cfg = Environ("TEMP") & "\" & resultsName & ".config.yaml"
    If Not WriteTextFile(cfg, yaml) Then ShowError "Failed to write config": Exit Sub
    Dim rc As Integer: rc = RunExe(exePath, cfg)
    Dim json As String: json = ReadTextFile(exeDir & "\" & resultsName)
    RenderResults GetOrCreateSheet(resultsSheet), json, exeDir & "\" & logName
End Sub

Public Sub RunConvert()
    Dim ws As Worksheet: Set ws = ThisWorkbook.Worksheets(CONVERT_CONFIG_SHEET)
    RunTool CONVERT_CONFIG_SHEET, FieldsConvert(), BuildConvertYAML(CollectValues(ws, FieldsConvert())), _
            CONVERT_RESULTS_JSON, CONVERT_LOG, CONVERT_RESULTS_SHEET
End Sub

Public Sub RunImport()
    Dim ws As Worksheet: Set ws = ThisWorkbook.Worksheets(IMPORT_CONFIG_SHEET)
    RunTool IMPORT_CONFIG_SHEET, FieldsImport(), BuildImportYAML(ws), _
            IMPORT_RESULTS_JSON, IMPORT_LOG, IMPORT_RESULTS_SHEET
End Sub

Public Sub ViewConvertLog()
    On Error GoTo ErrorHandler
    Dim ws As Worksheet: Set ws = ThisWorkbook.Worksheets(CONVERT_CONFIG_SHEET)
    Dim exePath As String: exePath = ResolvePath(Trim(CStr(ws.Range("row_exe_path").Value)))
    Dim exeDir As String: exeDir = Left(exePath, InStrRev(exePath, "\") - 1)
    Dim logPath As String: logPath = exeDir & "\" & CONVERT_LOG
    If Dir(logPath) <> "" Then
        Shell "notepad.exe """ & logPath & """", vbNormalFocus
    Else
        MsgBox "Log file not found: " & logPath, vbInformation, TOOL_NAME
    End If
    Exit Sub
ErrorHandler:
    ShowError "Error opening convert log: " & Err.Description
End Sub

Public Sub ViewImportLog()
    On Error GoTo ErrorHandler
    Dim ws As Worksheet: Set ws = ThisWorkbook.Worksheets(IMPORT_CONFIG_SHEET)
    Dim exePath As String: exePath = ResolvePath(Trim(CStr(ws.Range("row_exe_path").Value)))
    Dim exeDir As String: exeDir = Left(exePath, InStrRev(exePath, "\") - 1)
    Dim logPath As String: logPath = exeDir & "\" & IMPORT_LOG
    If Dir(logPath) <> "" Then
        Shell "notepad.exe """ & logPath & """", vbNormalFocus
    Else
        MsgBox "Log file not found: " & logPath, vbInformation, TOOL_NAME
    End If
    Exit Sub
ErrorHandler:
    ShowError "Error opening import log: " & Err.Description
End Sub

Public Sub ViewConvertSummary()
    On Error GoTo ErrorHandler
    Dim ws As Worksheet: Set ws = ThisWorkbook.Worksheets(CONVERT_CONFIG_SHEET)
    Dim outputPath As String: outputPath = Trim(CStr(ws.Range("row_output_path").Value))
    Dim startDate As String: startDate = DeriveDateYYYYMMDD(Trim(CStr(ws.Range("row_start_date").Value)))
    Dim summaryPath As String: summaryPath = outputPath & "\" & startDate & "\RICS_Format_Converter_Summary.txt"
    If Dir(summaryPath) <> "" Then
        Shell "notepad.exe """ & summaryPath & """", vbNormalFocus
    Else
        MsgBox "Summary file not found: " & summaryPath, vbInformation, TOOL_NAME
    End If
    Exit Sub
ErrorHandler:
    ShowError "Error opening summary: " & Err.Description
End Sub

' =========================================================================
' RESULTS RENDERING
' =========================================================================

Public Sub RenderResults(ws As Worksheet, jsonOutput As String, logPath As String)
    On Error Resume Next
    Dim status As String, message As String, outputPath As String, summaryFile As String
    status = "error"
    message = "No results"
    outputPath = ""
    summaryFile = ""

    If InStr(1, jsonOutput, """status"": ""success""", vbTextCompare) > 0 Or _
       InStr(1, jsonOutput, "completed", vbTextCompare) > 0 Then
        status = "success"
        message = "Operation completed successfully"
    Else
        status = "error"
        message = ExtractJSONValue(jsonOutput, "message", "Check log file for details")
    End If

    outputPath = ExtractJSONValue(jsonOutput, "output_path", "")
    summaryFile = ExtractJSONValue(jsonOutput, "summary_file", "")

    ws.Cells.Clear

    With ws
        .Range("A1").Value = TOOL_NAME & " Results"
        .Range("A1").Font.Bold = True
        .Range("A1").Font.Size = 14

        .Range("A3").Value = "Status:"
        .Range("A3").Font.Bold = True
        .Range("B3").Value = UCase(status)

        If status = "success" Then
            .Range("B3").Interior.Color = RGB(146, 208, 80)
        Else
            .Range("B3").Interior.Color = RGB(255, 0, 0)
            .Range("B3").Font.Color = RGB(255, 255, 255)
        End If

        .Range("A4").Value = "Timestamp:"
        .Range("A4").Font.Bold = True
        .Range("B4").Value = Now

        .Range("A6").Value = "Message:"
        .Range("A6").Font.Bold = True
        .Range("A7").Value = message
        .Range("A7").WrapText = True

        Dim row As Integer: row = 9

        If outputPath <> "" Then
            .Cells(row, 1).Value = "Output Path:"
            .Cells(row, 1).Font.Bold = True
            .Hyperlinks.Add Anchor:=.Cells(row, 2), Address:=outputPath, TextToDisplay:=outputPath
            row = row + 1
        End If

        If summaryFile <> "" And Dir(summaryFile) <> "" Then
            .Cells(row, 1).Value = "Summary File:"
            .Cells(row, 1).Font.Bold = True
            .Hyperlinks.Add Anchor:=.Cells(row, 2), Address:=summaryFile, TextToDisplay:=summaryFile
            row = row + 1
        End If

        .Cells(row, 1).Value = "Log File:"
        .Cells(row, 1).Font.Bold = True
        If logPath <> "" And Dir(logPath) <> "" Then
            .Hyperlinks.Add Anchor:=.Cells(row, 2), Address:=logPath, TextToDisplay:=logPath
        Else
            .Cells(row, 2).Value = "Not found: " & logPath
        End If

        .Columns("A:A").ColumnWidth = 15
        .Columns("B:B").ColumnWidth = 90
        .Rows("7:7").RowHeight = 60
    End With

    ws.Activate
    On Error GoTo 0
End Sub

' =========================================================================
' SHARED UTILITIES
' =========================================================================

Public Function GetOrCreateSheet(sheetName As String) As Worksheet
    On Error Resume Next
    Set GetOrCreateSheet = ThisWorkbook.Worksheets(sheetName)
    On Error GoTo 0
    If GetOrCreateSheet Is Nothing Then
        Set GetOrCreateSheet = ThisWorkbook.Worksheets.Add(After:=ThisWorkbook.Worksheets(ThisWorkbook.Worksheets.Count))
        GetOrCreateSheet.Name = sheetName
    End If
End Function

Public Sub AddRunButton(ws As Worksheet, caption As String, macroName As String, Optional targetRow As Long = 0)
    On Error Resume Next
    ' Remove existing button with same caption
    Dim shp As Shape
    For Each shp In ws.Shapes
        If shp.Name = "btn_" & macroName Then shp.Delete
    Next shp

    Dim buttonRow As Long
    If targetRow > 0 Then
        buttonRow = targetRow
    Else
        buttonRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).row + 1
        If buttonRow < 28 Then buttonRow = 28
    End If

    Dim btn As Button
    Set btn = ws.Buttons.Add(ws.Cells(buttonRow, 1).Left, ws.Cells(buttonRow, 1).Top, 250, 40)
    With btn
        .Name = "btn_" & macroName
        .Caption = caption
        .OnAction = macroName
        .Font.Bold = True
        .Font.Size = 14
    End With
    On Error GoTo 0
End Sub

Private Function RunExe(exePath As String, configPath As String) As Integer
    On Error GoTo Failed
    Dim wsh As Object: Set wsh = CreateObject("WScript.Shell")
    RunExe = wsh.Run("""" & exePath & """ """ & configPath & """", 0, True)
    Exit Function
Failed:
    ShowError "Error running tool: " & Err.Description
    RunExe = 1
End Function

' =========================================================================
' PATH HELPERS (ported from RICSConverterAddin.bas)
' =========================================================================

Public Function GetLocalWorkbookPath() As String
    On Error Resume Next
    Dim wbPath As String: wbPath = ThisWorkbook.Path
    If wbPath = "" Then GetLocalWorkbookPath = "": Exit Function
    If Left(wbPath, 4) <> "http" Then GetLocalWorkbookPath = wbPath: Exit Function
    GetLocalWorkbookPath = ResolveOneDrivePath(wbPath)
    On Error GoTo 0
End Function

Private Function ResolveOneDrivePath(sharePointPath As String) As String
    On Error Resume Next
    Dim fullPath As String: fullPath = ThisWorkbook.FullName
    If Left(fullPath, 4) <> "http" And fullPath <> "" Then
        Dim lastSlash As Long: lastSlash = InStrRev(fullPath, "\")
        If lastSlash > 0 Then ResolveOneDrivePath = Left(fullPath, lastSlash - 1): Exit Function
    End If
    Dim oneDrivePath As String: oneDrivePath = GetOneDriveBasePath()
    If oneDrivePath <> "" Then
        Dim relativePath As String: relativePath = ExtractRelativePathFromURL(sharePointPath)
        If relativePath <> "" Then ResolveOneDrivePath = BuildOneDrivePath(oneDrivePath, relativePath): Exit Function
    End If
    ResolveOneDrivePath = ""
    On Error GoTo 0
End Function

Private Function GetOneDriveBasePath() As String
    On Error Resume Next
    Dim env As Object: Set env = CreateObject("WScript.Shell")
    If Not env Is Nothing Then
        GetOneDriveBasePath = env.ExpandEnvironmentStrings("%OneDriveCommercial%")
        If GetOneDriveBasePath = "%OneDriveCommercial%" Or GetOneDriveBasePath = "" Then
            GetOneDriveBasePath = env.ExpandEnvironmentStrings("%OneDrive%")
        End If
        If GetOneDriveBasePath = "%OneDrive%" Then GetOneDriveBasePath = ""
    End If
    On Error GoTo 0
End Function

Private Function ExtractRelativePathFromURL(url As String) As String
    On Error Resume Next
    Dim docPos As Long
    docPos = InStr(1, url, "/Documents/", vbTextCompare)
    If docPos > 0 Then
        ExtractRelativePathFromURL = Mid(url, docPos + 11)
        ExtractRelativePathFromURL = Replace(ExtractRelativePathFromURL, "/", "\")
        If Left(ExtractRelativePathFromURL, 10) = "Documents\" Then
            ExtractRelativePathFromURL = Mid(ExtractRelativePathFromURL, 11)
        End If
        Exit Function
    End If
    docPos = InStr(1, url, "/personal/", vbTextCompare)
    If docPos > 0 Then
        docPos = InStr(docPos, url, "/Documents/")
        If docPos > 0 Then
            ExtractRelativePathFromURL = Replace(Mid(url, docPos + 11), "/", "\")
            Exit Function
        End If
    End If
    ExtractRelativePathFromURL = ""
    On Error GoTo 0
End Function

Private Function BuildOneDrivePath(basePath As String, relativePath As String) As String
    If Right(basePath, 1) = "\" Then basePath = Left(basePath, Len(basePath) - 1)
    BuildOneDrivePath = basePath & "\Documents\" & relativePath
End Function

' =========================================================================
' FILE I/O HELPERS (ported from RICSConverterAddin.bas)
' =========================================================================

Public Function WriteTextFile(filePath As String, content As String) As Boolean
    On Error GoTo ErrorHandler
    Dim stream As Object: Set stream = CreateObject("ADODB.Stream")
    If stream Is Nothing Then ShowError "Cannot create file stream.": WriteTextFile = False: Exit Function
    stream.Type = 2   ' Text
    stream.Charset = "UTF-8"
    stream.Open
    stream.WriteText content, 0
    stream.SaveToFile filePath, 2   ' Overwrite
    stream.Close
    Set stream = Nothing
    WriteTextFile = True
    Exit Function
ErrorHandler:
    If Not stream Is Nothing Then
        On Error Resume Next: stream.Close: Set stream = Nothing: On Error GoTo 0
    End If
    ShowError "Error writing file: " & Err.Description
    WriteTextFile = False
End Function

Public Function ReadTextFile(filePath As String) As String
    On Error Resume Next
    Dim fso As Object: Set fso = CreateObject("Scripting.FileSystemObject")
    Dim file As Object: Set file = fso.OpenTextFile(filePath, 1)
    If Not file Is Nothing Then
        ReadTextFile = file.ReadAll
        file.Close
    Else
        ReadTextFile = ""
    End If
    Set file = Nothing: Set fso = Nothing
    On Error GoTo 0
End Function

' =========================================================================
' JSON HELPERS (ported from RICSConverterAddin.bas)
' =========================================================================

Public Function ExtractJSONValue(json As String, key As String, defaultValue As String) As String
    Dim startPos As Long, endPos As Long
    startPos = InStr(1, json, """" & key & """: """, vbTextCompare)
    If startPos > 0 Then
        startPos = startPos + Len(key) + 6
        endPos = InStr(startPos, json, """")
        If endPos > startPos Then
            ExtractJSONValue = Replace(Mid(json, startPos, endPos - startPos), "\""", """")
            ExtractJSONValue = Replace(ExtractJSONValue, "\\", "\")
            Exit Function
        End If
    End If
    ExtractJSONValue = defaultValue
End Function

' =========================================================================
' FROM-SHEET WRAPPERS (collect + build in one VBA call; avoids COM Dictionary
' marshalling issues when called from Python via xl.Run)
' =========================================================================

Public Function BuildConvertYAMLFromSheet(sheetName As String) As String
    Dim ws As Worksheet: Set ws = ThisWorkbook.Worksheets(sheetName)
    BuildConvertYAMLFromSheet = BuildConvertYAML(CollectValues(ws, FieldsConvert()))
End Function

Public Function BuildImportYAMLFromSheet(sheetName As String) As String
    Dim ws As Worksheet: Set ws = ThisWorkbook.Worksheets(sheetName)
    BuildImportYAMLFromSheet = BuildImportYAML(ws)
End Function

' =========================================================================
' ERROR HANDLING
' =========================================================================

Public Sub ShowError(message As String)
    MsgBox message, vbExclamation, TOOL_NAME
End Sub
