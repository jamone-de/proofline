@echo off
echo ============================================================
echo  Proofline Demo Runner
echo ============================================================

echo.
echo [STEP 1] Running proofline tests first...
cd /d %~dp0
python -m pytest proofline\tests -v
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] Some tests failed - check output above
)

echo.
echo [STEP 2] Running full end-to-end demo...
python run_demo.py

echo.
echo Done! Open docs\index.html to see the certificate.
pause
