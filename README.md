# autoExperiment
This repository contains the code, details, part lists, and instructions of the automatic experiment

## Instructions

The service will start on boot. If it hasn't turned on by itself, open the command terminal on ubuntu using ```ctrl``` + ```alt``` + ```T``` , and use the command ```sudo systemctl restart reactor-console.service```
When the system launches, it will host a web server at port 8000, which you can access locally on the raspberry pi by going to [http:0.0.0.0:8000](http:0.0.0.0:8000) or using the command ```hostname -I``` to get the local ip, and going to [hhtp:<pi-ip>:8000] on a device connected to the same network
