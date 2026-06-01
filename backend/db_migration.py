import os
from sqlalchemy import create_engine, text

def run_migration():
    # Detect if we're using SQLite (local) or Postgres (production)
    db_url = os.environ.get("DB_URL", "sqlite:///./finance.db")
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        print("Starting database migration...")
        
        # 1. Add column to students
        try:
            print("Adding current_academic_status to students table...")
            conn.execute(text("ALTER TABLE students ADD COLUMN current_academic_status VARCHAR DEFAULT 'Active'"))
            print("Successfully added column.")
        except Exception as e:
            print(f"Column might already exist or error occurred: {e}")
            
        # 2. Create history table
        try:
            print("Creating academic_status_history table...")
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS academic_status_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                status VARCHAR NOT NULL,
                term VARCHAR NOT NULL,
                academic_year INTEGER NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_by VARCHAR,
                FOREIGN KEY(student_id) REFERENCES students(id)
            )
            """
            # Adjust auto-increment for Postgres if needed, but SQLAlchemy's Base.metadata.create_all handles Postgres nicely. 
            # If using SQLite, AUTOINCREMENT works.
            if "postgresql" in db_url:
                create_table_sql = """
                CREATE TABLE IF NOT EXISTS academic_status_history (
                    id SERIAL PRIMARY KEY,
                    student_id INTEGER NOT NULL,
                    status VARCHAR NOT NULL,
                    term VARCHAR NOT NULL,
                    academic_year INTEGER NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_by VARCHAR,
                    FOREIGN KEY(student_id) REFERENCES students(id)
                )
                """
            conn.execute(text(create_table_sql))
            print("Successfully created academic_status_history table.")
        except Exception as e:
            print(f"Error creating table: {e}")
            
        conn.commit()
        print("Migration complete!")

if __name__ == "__main__":
    run_migration()
