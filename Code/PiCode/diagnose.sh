#!/bin/bash
echo "=== System Info ==="
lsb_release -a
echo ""
echo "=== Bluetooth Status ==="
sudo systemctl status bluetooth --no-pager | head -20
echo ""
echo "=== Bluetooth Adapter ==="
hciconfig -a
echo ""
echo "=== Python Version ==="
python3 --version
echo ""
echo "=== Installed Python Packages ==="
pip list
echo ""
echo "=== Reactor Console Files ==="
ls -la /home/experiment/reactor_console/
echo ""
echo "=== Service Status ==="
sudo systemctl status reactor-console --no-pager 2>/dev/null || echo "Service not installed"
