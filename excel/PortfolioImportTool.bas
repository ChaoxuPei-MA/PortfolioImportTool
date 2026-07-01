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
Public Sub BuildConfigSheet(ws As Worksheet, fields As Variant, title As String)
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

' =========================================================================
' YAML BUILDERS
' =========================================================================

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
    ' Issuer/Bond Output - empty inputs => empty lists => no outputs added
    y = y & "Issuer_Bond_Output:" & nl
    y = y & "  outputs: [" & QuoteCsv(v("outputs")) & "]" & nl
    y = y & "  selection: [" & SelectionYaml(v("selection")) & "]" & nl
    BuildImportYAML = y
End Function

Private Function QuoteCsv(s As String) As String  ' "A","B"
    Dim p() As String, i As Long, out As String
    If Trim(s) = "" Then Exit Function
    p = Split(s, ",")
    For i = LBound(p) To UBound(p)
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

' =========================================================================
' PUBLIC MACROS
' =========================================================================

Public Sub CreateConfigSheets()
    BuildConfigSheet GetOrCreateSheet(CONVERT_CONFIG_SHEET), FieldsConvert(), "Portfolio Import Tool - Convert"
    BuildConfigSheet GetOrCreateSheet(IMPORT_CONFIG_SHEET), FieldsImport(), "Portfolio Import Tool - Import"
    AddRunButton GetOrCreateSheet(CONVERT_CONFIG_SHEET), "Run Convert", "RunConvert"
    AddRunButton GetOrCreateSheet(IMPORT_CONFIG_SHEET), "Run Import", "RunImport"
End Sub

' Descriptor-driven run: which sheet, which fields, which YAML builder, result file name
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
    Dim ws As Worksheet: Set ws = ThisWorkbook.Worksheets(CONVERT_CONFIG_SHEET)
    RunTool CONVERT_CONFIG_SHEET, FieldsConvert(), BuildConvertYAML(CollectValues(ws, FieldsConvert())), _
            CONVERT_RESULTS_JSON, CONVERT_LOG, CONVERT_RESULTS_SHEET
End Sub

Public Sub RunImport()
    Dim ws As Worksheet: Set ws = ThisWorkbook.Worksheets(IMPORT_CONFIG_SHEET)
    RunTool IMPORT_CONFIG_SHEET, FieldsImport(), BuildImportYAML(CollectValues(ws, FieldsImport())), _
            IMPORT_RESULTS_JSON, IMPORT_LOG, IMPORT_RESULTS_SHEET
End Sub

Public Sub ViewConvertLog()
    On Error GoTo ErrorHandler
    Dim ws As Worksheet: Set ws = ThisWorkbook.Worksheets(CONVERT_CONFIG_SHEET)
    Dim exePath As String: exePath = Trim(CStr(ws.Range("row_exe_path").Value))
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
    Dim exePath As String: exePath = Trim(CStr(ws.Range("row_exe_path").Value))
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

Public Sub AddRunButton(ws As Worksheet, caption As String, macroName As String)
    On Error Resume Next
    ' Remove existing button with same caption
    Dim shp As Shape
    For Each shp In ws.Shapes
        If shp.Name = "btn_" & macroName Then shp.Delete
    Next shp

    Dim buttonRow As Long
    buttonRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).row + 2
    If buttonRow < 30 Then buttonRow = 30

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
' ERROR HANDLING
' =========================================================================

Public Sub ShowError(message As String)
    MsgBox message, vbExclamation, TOOL_NAME
End Sub
