@echo off
cd /d "E:\E.V.A"

:loop
start "" cmd /c "timeout /t 3 >nul & start http://localhost:5000"
echo. >> eva.log
echo ===== [start_eva.bat] Khoi dong luc %date% %time% ===== >> eva.log
"C:\Users\WIN11\AppData\Local\Programs\Python\Python313\pythonw.exe" main.py >> eva.log 2>&1
echo [start_eva.bat] EVA da dung luc %date% %time% - tu khoi dong lai sau 5 giay >> eva.log
timeout /t 5 >nul
goto loop
