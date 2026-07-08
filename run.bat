@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ================================================
echo   감정 포토부스 - 키오스크 모드 (Kiosk)
echo   종료: Ctrl + Shift + Q  (확인 대화상자에서 예)
echo ================================================
echo.
uv run python main.py
echo.
echo [종료됨] 아무 키나 누르면 창이 닫힙니다.
pause >nul
