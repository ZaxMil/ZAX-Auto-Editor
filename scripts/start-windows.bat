@echo off
cd /d "%~dp0\.."
where python >nul 2>nul || (echo Python 3.11 or later required. & pause & exit /b 1)
where ffmpeg >nul 2>nul || (echo FFmpeg missing. Install using: winget install Gyan.FFmpeg & pause & exit /b 1)
python -m zax_editor.server
pause
