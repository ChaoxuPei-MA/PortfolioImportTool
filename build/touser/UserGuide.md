# Portfolio Import Tool — User Guide

This tool has two stages:

1. **Convert** — turns your portfolio/counterparty data into RICS bulk-import files.
2. **Import** — loads those RICS files into Moody's SG and produces a `.bhs` simulation.

You can run them separately or together, either from the **Excel workbook** or from
the **command line**. No Python installation is needed — everything is in the `.exe` files.

---

## 1. What's in this folder

```
Portfolio_Import_Tool.xlsm     Excel workbook (two tabs: Convert, Import)
dist\
  Converter.exe                Convert only
  Importer.exe                 Import only
  Pipeline.exe                 Convert THEN Import (one command)
configs\
  convert_config.yaml          settings for Convert
  import_config.yaml           settings for Import
  pipeline_config.yaml         settings for both (Pipeline)
UserData\                      <-- PUT YOUR INPUT DATA HERE
  granularCounterparty\ (GC, GCCRE, AgencyMBS)
  portfolio\
RICSFormatData\                results (RICS files + the .bhs) are written here
UserGuide.md                   this file
```

The folder is self-contained: **zip it and share it**; the recipient just needs the
requirements below.

---

## 2. Requirements

- **Windows.**
- **Convert:** nothing extra — `Converter.exe` has the reference data built in.
- **Import:** a working **Moody's SG** installation and a valid **licence file** on the
  machine. (Import loads SG's .NET libraries at run time.)

---

## 3. Prepare your data

Put your input CSVs under `UserData\`, named `<Folder>_<Type>.csv`:

```
UserData\
├── granularCounterparty\
│   ├── GC\          GC_Issuers.csv, GC_IndustryFactors.csv, GC_Instruments.csv,
│   │                GC_LGDs.csv, GC_Cashflows.csv
│   ├── GCCRE\       GCCRE_Issuers.csv, GCCRE_GeographyPropertyFactors.csv,
│   │                GCCRE_Instruments.csv, GCCRE_LGDs.csv, GCCRE_Cashflows.csv
│   └── AgencyMBS\   AgencyMBS_Issuers.csv, AgencyMBS_Instruments.csv, AgencyMBS_Laggard.csv
└── portfolio\
    ├── Portfolios.csv
    └── Holdings.csv
```

Include only the subfolders you have, and list them in the config's
`converter_data_types.granular`.

---

## 4. Way A — Excel workbook (easiest)

1. Open **`Portfolio_Import_Tool.xlsm`**. If prompted, **Enable Content / Macros**.
2. If the tabs aren't there yet, press `Alt+F8`, run **`CreateConfigSheets`**.
3. On the **Convert** tab (yellow cells are editable):
   - `Converter Exe Path` defaults to `.\dist\Converter.exe` (already correct).
   - Set `Data Path` (e.g. `UserData`) and `RICSFormatData Path` (e.g. `RICSFormatData`).
   - Set the date and versions.
   - Click **Run Convert**. Results appear on the `PIT_Convert_Results` sheet.
4. On the **Import** tab (requires Moody's SG):
   - `Importer Exe Path` defaults to `.\dist\Importer.exe`.
   - Set **SG Path** to your Moody's SG folder (e.g. `C:\Program Files\Moody's\SG\10.5.0`).
   - Set **Licence Path**, **RICSFormatData Path** (the Convert output, e.g. `RICSFormatData`),
     and **RICS Sim Output Path** (e.g. `RICSFormatData\Portfolio_Import.bhs`).
   - Click **Run Import**. Results appear on `PIT_Import_Results`.

> Paths typed as relative (e.g. `UserData`) are resolved next to the workbook.

---

## 5. Way B — command line

Open a terminal (Command Prompt or PowerShell) **in this folder**, then:

**Convert only:**
```
dist\Converter.exe configs\convert_config.yaml
```

**Import only** (needs Moody's SG; edit the SG paths + licence in the config first):
```
dist\Importer.exe configs\import_config.yaml
```

**Both in one command** (Convert then Import — edit the SG paths + licence in the
`import:` section first):
```
dist\Pipeline.exe configs\pipeline_config.yaml
```
With Pipeline, the Convert output is fed to Import automatically and the date is
shared, so you do **not** set `rics_path` or `base_date` in the `import:` section.

> Run these from **this folder** so the relative paths (`UserData`, `RICSFormatData`) resolve.

---

## 6. Outputs

- **Convert** writes RICS files under `RICSFormatData\` (e.g. `RICSFormatData\granularCounterparty\GC\1_GCP.csv`,
  `RICSFormatData\portfolio\CompositePortfolio.csv`) plus `RICS_Format_Converter_Summary.txt`.
- **Import** writes the simulation `RICSFormatData\Portfolio_Import.bhs` — open it in Moody's SG.
- Each stage also writes a small results JSON and a `.log` next to its `.exe`
  (`dist\rics_converter_*.json/.log`, `dist\rics_import_*.json/.log`) — check the log if
  something fails.

---

## 7. Troubleshooting

| Problem | What to do |
|---|---|
| "Config file not found" | Run the command from **this folder**; check the path after the exe. |
| Convert produced no files | Check the log in `dist\rics_converter.log`; verify your `UserData` layout and file names. |
| Import fails immediately | Verify the **SG Path**, that Moody's SG is installed, and the **licence** path is valid. Import needs SG; Convert does not. |
| Excel "macros disabled" | File → Options → Trust Center → Macro Settings → enable macros; reopen and Enable Content. |
| "Run" button missing | Press `Alt+F8`, run `CreateConfigSheets`. |

---

*Convert output has been validated to match the original Moody's converter exactly
(numeric values to machine precision). Import correctness should be confirmed by
opening the produced `.bhs` in Moody's SG.*
