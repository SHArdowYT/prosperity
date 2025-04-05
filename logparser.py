import json
import pandas as pd
# hi team hihihihihihihihi
from io import StringIO
import csv

LOG_FILE = r"61c9d3b3-794f-4e18-8e2f-ba1645ff73c0.log"
LOG_FILE = r"C:\Users\SHArdow\Projects\github projects\prosperity 14032025\prosperity\61c9d3b3-794f-4e18-8e2f-ba1645ff73c0.log"

with open(LOG_FILE) as file:
    file_lines = [line for line in file]

program_output_list = []
for i in range(1, 10000, 5):
    program_output_list.append(json.loads("\n".join(file_lines[i:i+5])))

program_output_dataframe = pd.DataFrame([list(row.values()) for row in program_output_list], columns=list((program_output_list[0]).keys()))



activity_log = [row for row in csv.reader(StringIO("".join(file_lines[10005:14006])), delimiter=";")]
activity_log_dataframe = pd.DataFrame(activity_log[1:], columns=activity_log[0])


trade_data = json.loads("\n".join(file_lines[14011:]))

trade_data_dataframe = pd.DataFrame([list(row.values()) for row in trade_data], columns=list((trade_data[0]).keys()))




print(program_output_dataframe)
print(activity_log_dataframe)
print(trade_data_dataframe)
