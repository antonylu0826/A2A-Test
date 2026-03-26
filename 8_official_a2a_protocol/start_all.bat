@echo off
chcp 65001 >nul
echo =====================================================
echo   A2A Protocol v1.0 - Official SDK Implementation
echo   Launching 3 sub-agents + 1 orchestrator...
echo =====================================================

cd /d "%~dp0"

echo [1/4] Starting ClaudeAgent (Port 8001)...
start "ClaudeAgent [Port 8001]" cmd /k "python -m ClaudeAgent"

timeout /t 2 /nobreak >nul

echo [2/4] Starting GoogleAgent (Port 8002)...
start "GoogleAgent [Port 8002]" cmd /k "python -m GoogleAgent"

timeout /t 2 /nobreak >nul

echo [3/4] Starting HumanAgent (Port 8003)...
start "HumanAgent - Human Gate [Port 8003]" cmd /k "python -m HumanAgent"

timeout /t 3 /nobreak >nul

echo [4/4] Starting Reception / Orchestrator...
echo.
echo All sub-agents launched! Starting Reception now...
echo Reception will auto-discover agents via AgentCard.
echo.
python -m Reception

pause
