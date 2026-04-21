from app.database import engine, Base
from app.models import Category, Task
from sqlalchemy import text, inspect

def run_migrations():
    # Creates tables if they don't exist
    Base.metadata.create_all(bind=engine)
    
    # Check for missing columns and add them if necessary
    with engine.connect() as conn:
        inspector = inspect(engine)
        
        # Check categories table
        columns = [c['name'] for c in inspector.get_columns('categories')]
        if 'description' not in columns:
            print("Adding 'description' column to 'categories' table...")
            conn.execute(text("ALTER TABLE categories ADD COLUMN description VARCHAR;"))
            
        # Check tasks table
        columns = [c['name'] for c in inspector.get_columns('tasks')]
        if 'description' not in columns:
            print("Adding 'description' column to 'tasks' table...")
            conn.execute(text("ALTER TABLE tasks ADD COLUMN description VARCHAR;"))
            
        conn.commit()
    
    print("Migration successful")

if __name__ == "__main__":
    run_migrations()