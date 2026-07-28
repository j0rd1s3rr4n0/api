@echo off
cd /d "%~dp0"
dist\ultimater_multi.exe --processes 2 --threads 80 --scrape-workers 80 --timeout 2 --socket-timeout 1 --max-proxies 30000 --batch-pause 15 --child-timeout 900 --low-priority --log-file logs.log --git
