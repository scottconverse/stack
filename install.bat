@echo off
REM stack installer — Windows double-click launcher
REM Requires Python 3.10+ on PATH. Use Git Bash or WSL for best results.

python "%~dp0install.py" %*
pause
