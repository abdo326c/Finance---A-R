import sys
import os
import time
print("STARTING PYTHON...")
import threading

file_path = r'C:\Users\Abdelrahman\Downloads\Tpl_Bulk_Invoices_(Tuition).xlsx'

from api.bulk import process_bulk_upload
from database import SessionLocal

class DummyUser:
    username = "abdo"

class DummyFile:
    def __init__(self, contents):
        self.contents = contents
    def read(self):
        return self.contents

class DummyUploadFile:
    def __init__(self, contents):
        self.file = DummyFile(contents)

print("READING FILE...")
with open(file_path, 'rb') as f:
    contents = f.read()

upload_file = DummyUploadFile(contents)

print("CONNECTING TO DB...")
db = SessionLocal()

print("Starting function call...")
start_time = time.time()
try:
    process_bulk_upload(b_type='Bulk Invoices (Tuition)', file=upload_file, current_user=DummyUser(), db=db)
except Exception as e:
    import traceback
    traceback.print_exc()
print(f"Time taken: {time.time() - start_time:.2f} seconds")
