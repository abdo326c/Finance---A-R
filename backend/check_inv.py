import pandas as pd
import io

file_path = r'C:\Users\Abdelrahman\Downloads\Tpl_Bulk_Invoices_(Tuition).xlsx'
try:
    df = pd.read_excel(file_path, nrows=25000)
    print("Len before dropna:", len(df))
    df.dropna(how='all', inplace=True)
    print("Len after dropna:", len(df))
    df.columns = [str(c).strip() for c in df.columns]
    
    print("Columns:", df.columns.tolist())
    
    # Let's count unique students
    student_ids_in_file = []
    for col in ["ID", "id", "Student ID", "student id"]:
        if col in df.columns:
            student_ids_in_file = df[col].dropna().astype(int).unique().tolist()
            break
            
    print("Unique Students:", len(student_ids_in_file))
    
except Exception as e:
    print(f"Error: {e}")
