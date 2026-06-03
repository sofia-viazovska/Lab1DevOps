"""Task Tracker web application (variant V3=2).

Implements the API mandated by the lab specification:

* ``GET  /tasks``              — list all tasks (id, title, status, created_at)
* ``POST /tasks``              — create a new task (payload: title)
* ``POST /tasks/<id>/done``    — mark a task as done

Common endpoints required by the spec:

* ``GET  /``                   — text/html only, lists all business endpoints
* ``GET  /health/alive``       — liveness probe (always 200 OK)
* ``GET  /health/ready``       — readiness probe (200 if DB is reachable, else 500)

Endpoints that return business data honour the ``Accept`` header:
``application/json`` (default) → JSON, ``text/html`` → plain HTML (no CSS, no JS,
lists are rendered as tables, per spec).
"""

from datetime import datetime
from html import escape
from typing import List

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from . import models, schemas
from .database import SessionLocal

app = FastAPI(title="mywebapp — Task Tracker", docs_url=None, redoc_url=None, openapi_url=None)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _wants_html(accept: str | None) -> bool:
    return bool(accept) and "text/html" in accept.lower()


def _html_page(title: str, body: str) -> HTMLResponse:
    """Render a plain HTML page — no CSS, no JS, as required by the spec."""
    return HTMLResponse(
        f"<!DOCTYPE html>\n"
        f"<html><head><meta charset=\"utf-8\"><title>{escape(title)}</title></head>"
        f"<body>{body}</body></html>"
    )


# --------------------------------------------------------------------------- #
# Health endpoints                                                            #
# --------------------------------------------------------------------------- #

@app.get("/health/alive")
def health_alive() -> Response:
    return Response(content="OK", media_type="text/plain", status_code=200)


@app.get("/health/ready")
def health_ready(db: Session = Depends(get_db)) -> Response:
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        return Response(
            content=f"database unavailable: {exc.__class__.__name__}",
            media_type="text/plain",
            status_code=500,
        )
    return Response(content="OK", media_type="text/plain", status_code=200)


# --------------------------------------------------------------------------- #
# Root endpoint — plain HTML index of business-logic endpoints                #
# --------------------------------------------------------------------------- #

@app.get("/")
def index(accept: str | None = Header(default=None)) -> Response:
    """Always returns text/html with the list of business endpoints."""
    if not _wants_html(accept) and accept and "*/*" not in accept:
        # Spec: the root endpoint expects and returns only text/html.
        return Response(status_code=status.HTTP_406_NOT_ACCEPTABLE)

    body = (
        "<h1>mywebapp — Task Tracker</h1>"
        "<p>Available business-logic endpoints:</p>"
        "<ul>"
        "<li><a href=\"/tasks\">GET /tasks</a> — list all tasks</li>"
        "<li>POST /tasks — create a task (JSON body: <code>{&quot;title&quot;: &quot;...&quot;}</code>)</li>"
        "<li>POST /tasks/&lt;id&gt;/done — mark a task as done</li>"
        "</ul>"
    )
    return _html_page("mywebapp", body)


# --------------------------------------------------------------------------- #
# Business endpoints                                                          #
# --------------------------------------------------------------------------- #

@app.get("/tasks")
def list_tasks(
    accept: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    tasks: List[models.Task] = (
        db.query(models.Task).order_by(models.Task.created_at.asc()).all()
    )

    if _wants_html(accept):
        rows = "".join(
            "<tr>"
            f"<td>{t.id}</td>"
            f"<td>{escape(t.title)}</td>"
            f"<td>{'done' if t.status else 'pending'}</td>"
            f"<td>{t.created_at.isoformat(timespec='seconds')}</td>"
            "</tr>"
            for t in tasks
        )
        body = (
            "<h1>Tasks</h1>"
            "<p><a href=\"/\">&larr; back</a></p>"
            "<table border=\"1\" cellpadding=\"4\" cellspacing=\"0\">"
            "<thead><tr>"
            "<th>id</th><th>title</th><th>status</th><th>created_at</th>"
            "</tr></thead>"
            f"<tbody>{rows}</tbody>"
            "</table>"
        )
        return _html_page("Tasks", body)

    return JSONResponse(
        content=[
            {
                "id": t.id,
                "title": t.title,
                "status": t.status,
                "created_at": t.created_at.isoformat(),
            }
            for t in tasks
        ]
    )


@app.post("/tasks", status_code=201)
def create_task(payload: schemas.TaskCreate, db: Session = Depends(get_db)) -> dict:
    task = models.Task(title=payload.title, status=False, created_at=datetime.utcnow())
    db.add(task)
    db.commit()
    db.refresh(task)
    return {
        "id": task.id,
        "title": task.title,
        "status": task.status,
        "created_at": task.created_at.isoformat(),
    }


@app.post("/tasks/{task_id}/done")
def mark_task_done(task_id: int, db: Session = Depends(get_db)) -> dict:
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    task.status = True
    db.commit()
    db.refresh(task)
    return {
        "id": task.id,
        "title": task.title,
        "status": task.status,
        "created_at": task.created_at.isoformat(),
    }
