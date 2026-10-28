@echo off
rem Diagnostyka czujnika: porty, model, firmware, health, 4 s odbioru danych.
rem UWAGA: port COM jest na wylacznosc - zamknij TouchDesignera przed uruchomieniem.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\test-lidar.ps1"
