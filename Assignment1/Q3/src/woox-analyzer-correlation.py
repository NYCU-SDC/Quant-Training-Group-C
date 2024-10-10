import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from datetime import datetime, timedelta

class CorrelationAnalyzer:
    def __init__(self, folder_path):
        self.folder_path = folder_path
        self.btc_file = self.find_csv_file('BTC')
        self.eth_file = self.find_csv_file('ETH')

        self.btc_df = self.load_and_process_data(self.btc_file, 'BTC')
        self.eth_df = self.load_and_process_data(self.eth_file, 'ETH')
        self.merge_df = self.merge_data()
    
    def find_csv_file(self, coin_type):
        for file in os.listdir(self.folder_path):
            if file.endswith('.csv') and coin_type in file:
                return os.path.join(self.folder_path, file)
        raise FileNotFoundError(f"No CSV file found for {coin_type} in {self.folder_path}")
    
    def load_and_process_data(self, file_path, coin_type):
        print(f"Loading {coin_type} data from {file_path}")
        df = pd.read_csv(file_path)
        df['start_timestamp'] = pd.to_datetime(df['start_timestamp'])
        df.set_index('start_timestamp', inplace=True)
        # remove the duplicate index
        df = df[~df.index.duplicated(keep='first')]
        return df
    
    def merge_data(self):
        common_index = self.btc_df.index.intersection(self.eth_df.index)
        btc_data = self.btc_df.loc[common_index]
        eth_data = self.eth_df.loc[common_index]

        btc_data['btc_pct_change'] = btc_data['close'].pct_change()
        eth_data['eth_pct_change'] = eth_data['close'].pct_change()

        merge_df = pd.concat([btc_data['btc_pct_change'], eth_data['eth_pct_change']], axis = 1)
        return merge_df.dropna()
    
    def analyze_eth_change(self, btc_threshold=0.01, tolerance=0.001):
        btc_up_1pct = self.merge_df[(self.merge_df['btc_pct_change'] > btc_threshold - tolerance) & 
                                     (self.merge_df['btc_pct_change'] < btc_threshold + tolerance)]
        
        if len(btc_up_1pct) == 0:
            print("Didn't find the situation of BTC increasing 1%")
            return
        
        avg_eth_change = btc_up_1pct['eth_pct_change'].mean()
        
        print(f"When BTC increases nearly {btc_threshold*100}% (Sample number: {len(btc_up_1pct)}):")
        print(f"The percentage of ETH average change: {avg_eth_change*100:.2f}%")
        
        correlation = self.merge_df['btc_pct_change'].corr(self.merge_df['eth_pct_change'])
        print(f"\nCorrelation of BTC and ETH price changes: {correlation:.4f}")
    
    def detailed_analysis(self):
        btc_bins = [-np.inf, -0.02, -0.01, 0, 0.01, 0.02, np.inf]
        btc_labels = ['<-2%', '-2%~-1%', '-1%~0%', '0~1%', '1%~2%', '>2%']
        
        self.merge_df['btc_group'] = pd.cut(self.merge_df['btc_pct_change'], bins=btc_bins, labels=btc_labels)
        eth_changes = self.merge_df.groupby('btc_group',observed= True)['eth_pct_change'].mean() 
        
        print("Average changes in ETH corresponding to different BTC increase ranges:")
        for group, change in eth_changes.items():
            print(f"BTC {group}: Average changes of ETH {change*100:.2f}%")
    
    def display_merge_df_summary(self):
        # Basic statistics
        summary = self.merge_df.describe()
        
        # Calculate correlation
        correlation = self.merge_df['btc_pct_change'].corr(self.merge_df['eth_pct_change'])
        summary.loc['correlation'] = [correlation, correlation]
        
        # Format the summary for better readability
        formatted_summary = summary.map(lambda x: f'{x:.4f}' if isinstance(x, (float, np.float64)) else x)
        
        print("Summary of merge_df:")
        print(formatted_summary)
        
        # Display first few rows of the actual data
        print("\nFirst few rows of merge_df:")
        print(self.merge_df.head())

        # Display data types of each column
        print("\nData types of merge_df columns:")
        print(self.merge_df.dtypes)
    
    def save_merge_df_to_csv(self, file_path):
        os.makedirs(output_dir, exist_ok=True)
        file_path = os.path.join(output_dir, 'merge_df_output.csv')
        self.merge_df.to_csv(file_path)
        print(f"Successfully saved merge_df to {file_path}")

    
    def plot_relationship(self, output_dir):
        plt.figure(figsize=(12, 8))
        x, y = self.merge_df['btc_pct_change'] *100, self.merge_df['eth_pct_change']*100
        plt.scatter(x, y, alpha=0.5)
        
        # Calculate linear regression
        coeffs = np.polyfit(x, y, 1)
        line = np.poly1d(coeffs)
        plt.plot(x, line(x), color='red', label=f'Regression line')

        #
        correlation = self.merge_df['btc_pct_change'].corr(self.merge_df['eth_pct_change'])
        plt.text(0.05, 0.95, f'Correlation: {correlation:.4f}', 
            transform=plt.gca().transAxes, verticalalignment='top')

        plt.xlabel('BTC Price Changes (%)')
        plt.ylabel('ETH Price Changes (%)')
        plt.title('BTC v.s ETH Price Change Correlation ')
        plt.grid(True)
        plt.axhline(y=0, color='black', linestyle='--')
        plt.axvline(x=0, color='black', linestyle='--')


        plt.legend()
        plt.tight_layout()

        os.makedirs(output_dir, exist_ok=True)
        plt.savefig(os.path.join(output_dir, 'btc_eth_correlation.png'))
        print(f"Correlation plot saved to output folder.")
        plt.close()

if __name__ == '__main__':
    # To make sure that perform this code from src folder
    if not os.path.basename(os.getcwd()) == 'src':
        print("Please perform this code from src folder")
        exit(1)
    
    folder_path = os.path.join('..', 'output')
    output_dir = os.path.join('..', 'output')
    os.makedirs(output_dir, exist_ok=True)

    analyzer = CorrelationAnalyzer(folder_path)
    
    # Analyze the changes of ETH when BTC increases 1%
    analyzer.analyze_eth_change()
    
    # Detailed analysis of ETH changes in different BTC growth ranges
    analyzer.detailed_analysis()

    # Display summary of merge_df
    analyzer.display_merge_df_summary()
    
    # Plot and save the correlation graph
    analyzer.plot_relationship(output_dir)
    
    # Save merge_df as CSV file
    analyzer.save_merge_df_to_csv(output_dir)