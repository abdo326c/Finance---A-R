from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app import Student # افترض إن ملف السيستم بتاعك اسمه app.py

# الاتصال بقاعدة البيانات
engine = create_engine("sqlite:///finance.db")
Session = sessionmaker(bind=engine)
session = Session()

# تحديث كل الكليات لتكون حروف كبيرة (Uppercase) وبدون مسافات
students = session.query(Student).all()
for s in students:
    if s.college:
        s.college = s.college.strip().upper()

session.commit()
session.close()
print("✅ Database Cleaned! All colleges are now strictly UPPERCASE.")
