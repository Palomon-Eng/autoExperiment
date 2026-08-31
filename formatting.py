'''This code will take any csv you have inserted and turn it into a more readable fromat for processing,
either on excel, matlab, or R. It takes the readings and sorts them by device, measurement, and finally timestamps. 
The csv will also include the commands given by the user'''

import pandas as pd
df = pd.read_csv("C:/Path/to/file/reactor_data_log.csv")
wide = df.pivot_table(index="timestamp_iso", columns=["source", "field"], values="value", aggfunc="first")
wide.to_csv("reactor_data_output.csv") #The formatted csv file will be saved in the same directory as this code.
print("File saved successfully!")
