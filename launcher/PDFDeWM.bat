@echo off
:: PDFDeWM Launcher — Use this to launch the application.
:: The C-compiled PDFDeWM.exe launcher is built by GitHub Actions
:: and included in official releases. This .bat is for local use.
cd /d "%~dp0"
start "" python\pythonw.exe app\GUI.py %*
