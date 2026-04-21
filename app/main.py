from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
import os
from datetime import datetime
from . import models, database, schemas
from sqlalchemy import text

app = FastAPI(title="Daily Task Tracker")


# Dependency to get DB session
def get_db():
    db = database.SessionLocal()
    try:
        # Check for missing columns and add them if necessary (automatic migration)
        # This is a safety measure if the external migration script wasn't run
        from sqlalchemy import inspect
        inspector = inspect(database.engine)
        
        # Check categories table
        if 'categories' in inspector.get_table_names():
            columns = [c['name'] for c in inspector.get_columns('categories')]
            if 'description' not in columns:
                db.execute(text("ALTER TABLE categories ADD COLUMN description VARCHAR;"))
                db.commit()
            
        # Check tasks table
        if 'tasks' in inspector.get_table_names():
            columns = [c['name'] for c in inspector.get_columns('tasks')]
            if 'description' not in columns:
                db.execute(text("ALTER TABLE tasks ADD COLUMN description VARCHAR;"))
                db.commit()

        yield db
    finally:
        db.close()


# --- System Endpoints ---

@app.get("/health/alive")
def health_alive():
    return "OK"


@app.get("/health/ready")
def health_ready(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return "OK"
    except Exception:
        raise HTTPException(status_code=500, detail="Database connection failed")


# --- Visual Part (HTML) ---

@app.get("/", response_class=HTMLResponse)
def read_root():
    """
    Main Dashboard Interface
    """
    template_path = os.path.join("templates", "index.html")
    try:
        with open(template_path, "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        return """
        <html>
            <body style="font-family: sans-serif; padding: 50px;">
                <h2>Error: HTML Template not found.</h2>
                <p>Please ensure <b>app/templates/index.html</b> exists.</p>
                <nav>
                    <a href="/tasks">View Raw Tasks (JSON)</a> | 
                    <a href="/categories">View Raw Categories (JSON)</a>
                </nav>
            </body>
        </html>
        """


# --- API Endpoints ---

@app.get("/tasks")
def get_tasks(category_id: int = None, sort_by: str = "priority", db: Session = Depends(get_db), accept: str = Header(None)):
    """
    Returns tasks. Supports filtering by category, sorting and HTML/JSON response based on headers.
    """
    query = db.query(models.Task)

    if category_id:
        query = query.filter(models.Task.category_id == category_id)

    # Status-aware sorting: In progress tasks first, then completed tasks
    # Completed tasks (status=True) are moved to the end and not included in primary sorting
    if sort_by == "deadline":
        tasks = query.order_by(models.Task.status.asc(), models.Task.deadline.asc()).all()
    else:
        tasks = query.order_by(models.Task.status.asc(), models.Task.priority.asc()).all()

    # Check if browser requested HTML
    if accept and "text/html" in accept:
        rows = ""
        now = datetime.utcnow()
        for t in tasks:
            status_label = "Completed" if t.status else "In Progress"
            status_color = "green" if t.status else "orange"
            deadline_str = t.deadline.strftime('%d.%m.%Y') if t.deadline else "N/A"
            is_overdue = t.deadline and t.deadline < now and not t.status
            deadline_color = "red" if is_overdue else "black"

            rows += f"""
            <tr>
                <td>{t.id}</td>
                <td>{t.title}</td>
                <td>{t.priority}</td>
                <td style="color: {deadline_color};">{deadline_str}</td>
                <td style="color: {status_color}; font-weight: bold;">{status_label}</td>
            </tr>
            """

        return HTMLResponse(f"""
        <html>
            <head>
                <title>Task List</title>
                <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
            </head>
            <body class="container mt-5">
                <h2>Task List</h2>
                <nav class="mb-3">
                    <a href="/" class="btn btn-secondary btn-sm">Home</a>
                    <span class="ms-3">Sort by:</span>
                    <a href="/tasks?sort_by=priority" class="btn btn-outline-primary btn-sm">Priority</a>
                    <a href="/tasks?sort_by=deadline" class="btn btn-outline-primary btn-sm">Deadline</a>
                </nav>
                <table class="table table-bordered table-striped">
                    <thead class="table-dark">
                        <tr>
                            <th>ID</th>
                            <th>Title</th>
                            <th>Priority</th>
                            <th>Deadline</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows}
                    </tbody>
                </table>
            </body>
        </html>
        """)

    return tasks


@app.post("/tasks", response_model=schemas.Task)
def create_task(task: schemas.TaskCreate, db: Session = Depends(get_db)):
    db_task = models.Task(**task.dict())
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task


@app.post("/categories", response_model=schemas.Category)
def create_category(category: schemas.CategoryCreate, db: Session = Depends(get_db)):
    db_category = models.Category(**category.dict())
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category


@app.patch("/tasks/{task_id}/toggle", response_model=schemas.Task)
def toggle_task_status(task_id: int, db: Session = Depends(get_db)):
    db_task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    db_task.status = not db_task.status
    db.commit()
    db.refresh(db_task)
    return db_task


@app.delete("/categories/{category_id}")
def delete_category(category_id: int, db: Session = Depends(get_db)):
    db_category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not db_category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    # Check if there are tasks associated with this category
    tasks_count = db.query(models.Task).filter(models.Task.category_id == category_id).count()
    if tasks_count > 0:
        raise HTTPException(status_code=400, detail="Cannot delete category with associated tasks")

    db.delete(db_category)
    db.commit()
    return {"message": "Category deleted successfully"}


@app.get("/categories")
def get_categories(db: Session = Depends(get_db), accept: str = Header(None)):
    """
    Returns categories. Supports HTML/JSON.
    """
    categories = db.query(models.Category).all()

    if accept and "text/html" in accept:
        list_items = "".join([f"""
            <li class='list-group-item d-flex justify-content-between align-items-center'>
                {c.name} (ID: {c.id})
                <button class='btn btn-danger btn-sm' onclick='deleteCategory({c.id})'>Delete</button>
            </li>""" for c in categories])
        return HTMLResponse(f"""
        <html>
            <head>
                <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
                <script>
                    async function deleteCategory(id) {{
                        if (!confirm('Are you sure you want to delete this category?')) return;
                        const response = await fetch('/categories/' + id, {{ method: 'DELETE' }});
                        if (response.ok) {{
                            location.reload();
                        }} else {{
                            const data = await response.json();
                            alert('Error: ' + (data.detail || 'Could not delete category'));
                        }}
                    }}
                </script>
            </head>
            <body class="container mt-5">
                <h2>Categories</h2>
                <a href="/" class="btn btn-secondary mb-3">Back to Dashboard</a>
                <ul class="list-group w-50">{list_items}</ul>
            </body>
        </html>
        """)
    return categories