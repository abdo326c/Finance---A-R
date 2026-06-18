import pandas as pd
import sys
import math

file_path = r'C:\Users\Abdelrahman\Downloads\Template_Bulk_Scholarships (3).xlsx'
try:
    df = pd.read_excel(file_path, nrows=25000)
    df.dropna(how='all', inplace=True)
    df.columns = [str(c).strip() for c in df.columns]
    
    print('Columns:', df.columns.tolist())
    print('Total rows:', len(df))
    
    for i, row in df.iterrows():
        print(f'\n--- Row {i} ---')
        orig = row.to_dict()
        print('Data:', orig)
        
        sid = int(row.get('ID', 0)) if pd.notnull(row.get('ID')) else 0
        s_n = str(row.get('Scholarship Name', '')).strip()
        
        print(f'Parsed Student ID: {sid}')
        print(f'Parsed Scholarship Name: "{s_n}"')
        
except Exception as e:
    print(f'Failed: {e}')
