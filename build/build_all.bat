@echo off
REM Build both executables into dist\ using the project venv.
setlocal
cd /d "%~dp0.."
call .venv\Scripts\pyinstaller.exe --clean --noconfirm --distpath dist --workpath build\_work build\converter.spec
if errorlevel 1 exit /b 1
call .venv\Scripts\pyinstaller.exe --clean --noconfirm --distpath dist --workpath build\_work build\importer.spec
if errorlevel 1 exit /b 1
echo Built dist\Converter.exe and dist\Importer.exe
