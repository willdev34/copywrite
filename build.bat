@echo off
pyinstaller --onefile --noconsole --name CopyWrite main.py
echo.
echo Executavel gerado em dist\CopyWrite.exe
