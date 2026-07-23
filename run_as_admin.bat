@echo off
:: Launch Shadow elevated (needed for firewall network block)
powershell -NoProfile -Command "Start-Process -FilePath '%~dp0run.bat' -Verb RunAs"
