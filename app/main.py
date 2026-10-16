from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import users
from app.api.routes import teams
from app.api.routes import projects
from app.api.routes import tasks
from app.api.routes import comments
from app.api.routes import auth
from app.api.routes import invites
from app.api.routes import messages
from app.api.routes import ws
from app.api.routes import notifications
from app.core.exceptions import integrity_error_handler, sqlalchemy_error_handler, unhandled_exception_handler
from app.core.config import settings
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(messages.router)
app.include_router(teams.router)
app.include_router(projects.router)
app.include_router(tasks.router)
app.include_router(comments.router)
app.include_router(auth.router)
app.include_router(invites.router)
app.include_router(ws.router)
app.include_router(notifications.router)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}



app.add_exception_handler(IntegrityError, integrity_error_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)