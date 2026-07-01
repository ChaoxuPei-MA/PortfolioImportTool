@echo off
REM Build all three executables into dist\ and assemble the ToUser\ package.
setlocal
cd /d "%~dp0.."
call .venv\Scripts\pyinstaller.exe --clean --noconfirm --distpath dist --workpath build\_work build\converter.spec
if errorlevel 1 exit /b 1
call .venv\Scripts\pyinstaller.exe --clean --noconfirm --distpath dist --workpath build\_work build\importer.spec
if errorlevel 1 exit /b 1
call .venv\Scripts\pyinstaller.exe --clean --noconfirm --distpath dist --workpath build\_work build\pipeline.spec
if errorlevel 1 exit /b 1
echo Built dist\Converter.exe, dist\Importer.exe, dist\Pipeline.exe
REM Assemble the shareable ToUser\ folder (needs the workbook built too: excel\build_workbook.py)
call .venv\Scripts\python.exe build\make_touser.py
if errorlevel 1 exit /b 1
echo.
echo Done. Zip the ToUser folder and share it.
