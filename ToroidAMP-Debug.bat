@echo off
setlocal
echo ============================================================
echo ToroidAMP v0.667 — Diagnostic / Console Launch
echo ============================================================
echo Starting ToroidAMP with attached terminal output...
echo Persistent file log: %%LOCALAPPDATA%%\ToroidAMP\logs\toroidamp.log
echo.

python -m toroidamp %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ToroidAMP exited with error code %ERRORLEVEL%.
    pause
)
endlocal
