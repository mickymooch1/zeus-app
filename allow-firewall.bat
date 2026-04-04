@echo off
echo Adding Windows Firewall rule for Zeus on port 8000...
netsh advfirewall firewall add rule name="Zeus Backend Port 8000" protocol=TCP dir=in localport=8000 action=allow
echo Done.
pause
