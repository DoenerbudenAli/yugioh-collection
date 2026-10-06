@echo off
rem Laeuft als Dienstkonto (einrichten.sh, Stufe 5). Der Key wird per DPAPI dieses Kontos verschluesselt.
"C:\Program Files\Python313\python.exe" -E -s "%~dp0dienst.py" key-import --daten "C:\ProgramData\harness-broker"
echo.
"C:\Program Files\Python313\python.exe" -E -s "%~dp0dienst.py" key-pruefen --daten "C:\ProgramData\harness-broker"
echo.
pause
