@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PHOTOBOOTH_DEV=1
echo ================================================
echo   감정 포토부스 - 개발/창 모드 (Dev)
echo   일반 창입니다. 창의 X 버튼으로 종료하세요.
echo   (커서 보임 / 항상위 해제 / ESC-무입력잠금 완화)
echo ================================================
echo.
uv run python main.py
echo.
echo [종료됨] 아무 키나 누르면 창이 닫힙니다.
pause >nul
