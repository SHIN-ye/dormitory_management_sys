@echo off
ssh -o StrictHostKeyChecking=no -o PasswordAuthentication=no -p 443 -R0:localhost:5000 a.pinggy.io
pause
