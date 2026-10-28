@echo off
rem Szuka portu COM, na ktorym odpowiada RPLIDAR, i zapamietuje go dla TouchDesignera.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\find-port.ps1"
pause
