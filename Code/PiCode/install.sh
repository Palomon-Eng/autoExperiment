#!/bin/bash
# install.sh - Complete installation for Reactor Console on Raspberry Pi 4

set -e

echo "=== Reactor Console Installation ==="
echo "Raspberry Pi 4 - Ubuntu 26.04.1 LTS"
echo ""

# Check if running as experiment user
if [ "$USER" != "experiment" ]; then
    echo "NOTE: Running as '$USER' user. This will not work."
fi

# Update system
echo "Step 1/7: Updating system packages..."
sudo apt update
sudo apt upgrade -y

# Install system dependencies
echo "Step 2/7: Installing system dependencies..."
# Note: bluez-utils is now part of bluez on newer Ubuntu
sudo apt install -y python3-venv python3-pip bluetooth bluez \
    libglib2.0-dev libbluetooth-dev build-essential

# Create virtual environment
echo "Step 3/7: Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
echo "Step 4/7: Upgrading pip..."
pip install --upgrade pip

# Install Python packages
echo "Step 5/7: Installing Python dependencies..."
pip install -r requirements.txt

# Set Bluetooth capabilities
echo "Step 6/7: Configuring Bluetooth..."
sudo setcap 'cap_net_raw,cap_net_admin+eip' $(readlink -f $(which python3))

# Create logs directory
mkdir -p logs

# Create systemd service
echo "Step 7/7: Creating systemd service..."
sudo tee /etc/systemd/system/reactor-console.service > /dev/null << 'SERVICE'
[Unit]
Description=Reactor Console - 1 Minute Polling
After=network.target bluetooth.target
Wants=bluetooth.target

[Service]
Type=simple
User=experiment
WorkingDirectory=/home/experiment/autoExperiment/Code/PiCode
Environment="PATH=/home/experiment/autoExperiment/Code/PiCode/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStartPre=/usr/bin/sudo /usr/bin/hciconfig hci0 down
ExecStartPre=/usr/bin/sudo /usr/bin/hciconfig hci0 up
ExecStart=/home/experiment/autoExperiment/Code/PiCode/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SERVICE

# Reload systemd
sudo systemctl daemon-reload

echo ""
echo "=== Installation Complete! ==="
echo ""
echo "To start the Reactor Console:"
echo "  sudo systemctl start reactor-console"
echo ""
echo "To enable automatic startup on boot:"
echo "  sudo systemctl enable reactor-console"
echo ""
echo "To check status:"
echo "  sudo systemctl status reactor-console"
echo ""
echo "To view logs:"
echo "  journalctl -u reactor-console -f"
echo ""
echo "The web interface will be available at:"
echo "  http://$(hostname -I | awk '{print $1}'):8000"
echo ""
echo "NOTE: Edit config.py to set your specific device MAC addresses first!"
