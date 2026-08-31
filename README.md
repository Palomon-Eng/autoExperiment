# autoExperiment
This repository contains the code, details, part lists, and instructions of the automatic experiment

## Instructions

The service will start on boot. If it hasn't turned on by itself, open the command terminal on ubuntu using ```ctrl``` + ```alt``` + ```T``` , and use the command ```sudo systemctl restart reactor-console.service```
When the system launches, it will host a web server at port 8000, which you can access locally on the raspberry pi by going to [http:0.0.0.0:8000](http:0.0.0.0:8000) or using the command ```hostname -I``` to get the local ip, and going to [hhtp:pi-ip:8000] on a device connected to the same network
Make sure that the raspberry pi and whatever device you use to control the system isn't connected to eduroam, as it will block remote connections and won't allow the airsence to work.

On opening the page, you will be greeted by a terminal with live serial data from the arduino, along with a row of buttons underneath with pre-programmed functions. 
|Text|Function|
|---|---|
|Start||
|Stop|Will close all valves and turn off pump|

Next, you will see the list of sensors and live readings. There is one M5 taking readings, two aranet sensors called Intake and Chamber, and one block for the airSence sensor. They will all display their current readings, and the aranet sensors have live graphs of the level of CO2 over time.
There is a button at the top with the text download CSV. This will download a csv file containing all the data recorded, and all the commands given, with exact time stamps.
To process this csv into a more readable format, use the code in formatting.py

To set this system up from scratch, everything is in the code tab. Start by flashing the arduino code onto the Arduino Uno R3, and the M5 code on the M5 Stick C Plus 2.
Clone this repository by using:
```bash
git clone https://github.com/Palomon-Eng/autoExperiment.git
```
Then set up the system by going to Code/PiCode and running the install script
```bash
cd autoExperiment/Code/PiCode
chmod +x install.sh
./install.sh
```
