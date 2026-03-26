@echo off
chcp 65001
echo Starting A2A Agents...

echo Starting Reception...
cd /d "%~dp0Reception"
start "Reception" cmd /k "python main.py"

echo Waiting 3 seconds for Reception server to start...
timeout /t 3 /nobreak > nul

echo Starting ClaudeAgent...
cd /d "%~dp0ClaudeAgent"
start "ClaudeAgent" cmd /k "python main.py"

echo Starting GoogleAgent...
cd /d "%~dp0GoogleAgent"
start "GoogleAgent" cmd /k "python main.py"

echo Starting HumanAgent...
cd /d "%~dp0HumanAgent"
start "HumanAgent" cmd /k "python main.py"

echo All agents started! You can close this window.
pause
