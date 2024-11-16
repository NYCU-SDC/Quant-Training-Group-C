import os
import json
import pandas as pd
import numpy as np
from datetime import datetime
import re

class SlippageAnalyzer:
    def __init__(self, folder_path):
        self.folder_path = folder_path
        self.all_data = dict()
    def data_preprocessing(self):
        print(os.listdir(self.folder_path))
        # Step 3: Iterate through each file in the folder
        for sub_folder in os.listdir(self.folder_path):
            print("catching ", sub_folder, " data")
            orderbook_data_list = []
            files = os.listdir(os.path.join(self.folder_path, sub_folder))
            sorted_files = sorted(files, key=self.extract_number)
            for filename in sorted_files:
                sub_folder_path = os.path.join(self.folder_path, sub_folder)

                if filename.endswith(".json"):  # Check if the file is a JSON file
                    file_path = os.path.join(sub_folder_path, filename)
                    
                    with open(file_path, "r") as file:
                        for line in file:
                            # Parse each line as a separate JSON object
                            data = json.loads(line)

                            # Extract timestamp and orderbook data
                            ts = data.get("ts", None)
                            orderbook_data = data.get("data", {})
                            asks = orderbook_data.get("asks", [])
                            bids = orderbook_data.get("bids", [])

                            if ts is not None:
                                timestamp = datetime.fromtimestamp(ts / 1000).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                            else:
                                timestamp = None
                            # Prepare a row for the current timestamp
                            row = [ts]  # Start with the timestamp

                            # Add ask prices and sizes to the row
                            for ask in asks:
                                price, size = ask
                                row.extend([price, size])  # Append price and size

                            # Add bid prices and sizes to the row
                            for bid in bids:
                                price, size = bid
                                row.extend([price, size])  # Append price and size

                            # Append the completed row to the list
                            orderbook_data_list.append(row)
                            
            max_entries = max(len(row) for row in orderbook_data_list)  # Find the maximum number of entries
            orderbook_np = np.array([row + [0] * (max_entries - len(row)) for row in orderbook_data_list], dtype=object)

            # Store in dictionary for each sub-folder
            self.all_data[sub_folder] = {
                "orderbook": orderbook_np,
                "bids": np.array([row[0:1] + row[len(asks)*2 + 1:] for row in orderbook_data_list], dtype=object),  # Extract only bids
                "asks": np.array([row[0:1] + row[1:len(asks)*2 + 1] for row in orderbook_data_list], dtype=object)  # Extract only asks
            }

            # Print shape and sample data
            print(f"Sub-folder '{sub_folder}' - Total Records: {orderbook_np.shape[0]}")

    def extract_number(self, filename):
        match = re.search(r'\d+', filename)
        return int(match.group()) if match else 0
    
    def analyze_slippage_with_volume(self, volume, symbol):
        print("analysing", symbol, "with volume", volume)
        slippage_data = pd.DataFrame(columns=["timestamp", "average_buy_slippage", "max_buy_slippage", "average_sell_slippage", "max_sell_slippage"])
        hour_step_in_ms = 3600 * 1000
        data = self.all_data[symbol]
        asks = data["asks"]
        bids = data["bids"]
        
        # calculate average slippage in each hour
        start_hour = datetime.fromtimestamp(asks[0][0] / 1000).replace(minute=0, second=0, microsecond=0)
        start_hour_ms = int(start_hour.timestamp() * 1000)
        while start_hour_ms < asks[-1][0]:
            end_hour_ms = start_hour_ms + hour_step_in_ms
            # find the index of the first entry in the hour
            start_index = 0
            end_index = 0
            for i in range(len(asks)):
                if asks[i][0] >= start_hour_ms:
                    start_index = i
                    break
            for i in range(len(asks)):
                if asks[i][0] >= end_hour_ms:
                    end_index = i
                    break
            print("start index is ", start_index, " end index is ", end_index)  
            # calculate the average slippage in the hour
            total_buy_slippage = 0
            total_sell_slippage = 0
            max_buy_slippage = 0
            max_sell_slippage = 0
            count = 0
            for i in range(start_index, end_index):
                # Buy slippage calculation
                j = 1
                sum = 0
                eaten_volume = 0
                residual_volume = volume
                while i < end_index and residual_volume > 0 and j < len(asks[i]):
                    # print("residual volume is ", residual_volume)
                    # print("current price is ", asks[i][j])
                    buy_amount = asks[i][j] * min(asks[i][j + 1], residual_volume)
                    eaten_volume += min(asks[i][j + 1], residual_volume)
                    sum += buy_amount
                    residual_volume -= buy_amount / asks[i][j]
                    j += 2
                if residual_volume <= 0:
                    slippage = sum / volume - asks[i][1]
                    slippage_bp = slippage / asks[i][1] * 10000
                    # print("slippage in a snapshot: ", slippage_bp)
                    total_buy_slippage += slippage_bp
                else:
                    print("order book is not able to fill the volume")
                    slippage = sum / eaten_volume - asks[i][1]
                    slippage_bp = slippage / asks[i][1] * 10000
                    # print("slippage in a snapshot: ", slippage_bp)
                    total_buy_slippage += slippage_bp
                    print("slippage in a snapshot: ", slippage_bp)
                if slippage_bp > max_buy_slippage:
                    max_buy_slippage = slippage_bp
                
                # Sell slippage calculation
                j = 1
                sum = 0
                eaten_volume = 0
                residual_volume = volume
                while i < end_index and residual_volume > 0 and j < len(bids[i]):
                    sell_amount = bids[i][j] * min(bids[i][j + 1], residual_volume)
                    eaten_volume += min(bids[i][j + 1], residual_volume)
                    residual_volume -= min(bids[i][j + 1], residual_volume)
                    sum += sell_amount
                    j += 2
                if residual_volume <= 0:
                    slippage_sell = bids[i][1] - sum / volume
                    slippage_bp = slippage_sell / bids[i][1] * 10000
                    total_sell_slippage += slippage_bp
                else:
                    print("order book is not able to fill the volume")
                    slippage_sell = bids[i][1] - sum / eaten_volume
                    slippage_bp = slippage_sell / bids[i][1] * 10000
                    total_sell_slippage += slippage_bp
                    print("slippage in a snapshot: ", slippage_bp)
                if slippage_bp > max_sell_slippage:
                    max_sell_slippage = slippage_bp
                count += 1

            if count != 0:
                average_buy_slippage = total_buy_slippage / count
                average_sell_slippage = total_sell_slippage / count
                hour_str = datetime.fromtimestamp(start_hour_ms / 1000).strftime('%Y-%m-%d %H:%M:%S')
                print("start hour is", hour_str)
                print("average buy slippage in is", average_buy_slippage, "bp")
                print("max buy slippage in is", max_buy_slippage, "bp")
                print("average sell slippage is", average_sell_slippage, "bp")
                print("max sell slippage is", max_sell_slippage, "bp")
                new_row = pd.DataFrame([{
                    "timestamp": hour_str, 
                    "average_buy_slippage": average_buy_slippage, 
                    "max_buy_slippage": max_buy_slippage, 
                    "average_sell_slippage": average_sell_slippage, 
                    "max_sell_slippage": max_sell_slippage
                }])

                # Concatenate the new row with the existing DataFrame
                slippage_data = pd.concat([slippage_data, new_row], ignore_index=True)
            start_hour_ms = end_hour_ms
        return slippage_data
    