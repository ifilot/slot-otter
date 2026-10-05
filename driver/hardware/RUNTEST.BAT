@echo off
HWTEST
if errorlevel 1 goto failed
S:\HELLO.COM > EXEC.LOG
if errorlevel 1 goto failed
copy /b S:\BIG.BIN COPIED.BIN > COPY.LOG
if errorlevel 1 goto failed
HWTEST /EXTRA
if errorlevel 1 goto failed
echo ALL AUTOMATED TESTS PASSED. Keep all .LOG files.
goto end
:failed
echo TEST FAILED OR SETUP REFUSED. Keep all .LOG files; see MANUAL.TXT.
:end
