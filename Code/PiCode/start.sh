#!/bin/bash
# Startup script for Reactor Console

cd /home/experiment/reactor_console

# Activate virtual environment
source venv/bin/activate

# Reset Bluetooth using bluetoothctl (the modern way)
echo "power off" | bluetoothctl > /dev/null 2>&1
sleep 1
echo "power on" | bluetoothctl > /dev/null 2>&1
sleep 2

# Start the application
exec uvicorn main:app --host 0.0.0.0 --port 8000
