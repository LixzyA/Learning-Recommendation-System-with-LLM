from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import torch
from weaviate_db import Database
from fastapi import FastAPI, Depends, Request, Response, Form, Cookie, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from models import User
from sqlite_db import SessionLocal, engine
from utils import create_session, delete_session, get_user_by_session_token,cleanup_expired_sessions, get_user_by_username, create_user
from contextlib import asynccontextmanager 

# Create database tables
User.metadata.create_all(bind=engine)

weaviate_db: Database | None = None
_model: SentenceTransformer | None = None

@asynccontextmanager
async def lifespan(app:FastAPI):
    load_dotenv(dotenv_path=".env")
    sql_db = SessionLocal()
    cleanup_expired_sessions(sql_db)
    sql_db.close()
    load_model()

    global weaviate_db
    with Database() as weaviate_db:
        weaviate_db.create_or_get_collections("Embeddings_2")
        yield

app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory="templates")

origins = [
    "http://localhost",
    "http://localhost:1234",
]

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Session dependency
def get_current_user(db: Session = Depends(get_db), session_token: str = Cookie(default=None)):
    if not session_token:
        return None
    user = get_user_by_session_token(db, session_token)
    return user

# Serve static files (CSS/JS if needed)
app.mount("/assets", StaticFiles(directory="templates/assets"), name="assets")
app.mount("/images", StaticFiles(directory="templates/images"), name="images")

@app.get("/")
async def root(request: Request, current_user: User = Depends(get_current_user)):
    if current_user:
        return templates.TemplateResponse("index.html", {"request": request, "username": current_user.username})
    return templates.TemplateResponse("login.html", {"request": request})
    
    

@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(
    response: Response,
    username: str = Form(),
    password: str = Form(),
    db: Session = Depends(get_db)
):
    user = get_user_by_username(db, username)
    if not user or user.password != password:
        return Response(content="Invalid credentials", status_code=401)
    
    session_token = create_session(db, user)
    response = Response(status_code=303, headers={"Location": "/"})
    response.set_cookie(key="session_token", value=session_token)
    return response

@app.post("/logout")
async def logout(response: Response, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user:
        delete_session(db, current_user)
    response = Response(status_code=303, headers={"Location": "/"})
    response.delete_cookie(key="session_token")
    return response

@app.get("/signup")
async def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})

@app.post("/signup")
async def signup(
    username: str = Form(),
    password: str = Form(),
    db: Session = Depends(get_db)
):
    existing_user = get_user_by_username(db, username)
    if existing_user:
        return Response(content="Username already exists", status_code=400)
    
    create_user(db, username, password)
    return Response(status_code=303, headers={"Location": "/"})

@app.get("/profile")
async def user_page(request: Request, current_user: User = Depends(get_current_user)):
    if not current_user:
        return Response(status_code=303, headers={"Location": "/"})
    return templates.TemplateResponse("profile.html", {
        "request" : request,
        "user": current_user
    })


@app.get("/search")
async def recomendation_page(query: str):
    global _model, weaviate_db
    try:
        query_embedding = _model.encode(query, normalize_embeddings=True).tolist()
        property = {"language": 'en'}
        results = weaviate_db.search(query, query_embedding, property)
        return {"message": f"Searching for: {query}", "results": results}
    except Exception as e:
        raise HTTPException(status_code=404, detail=e)
    

def load_model():
    global _model
    if _model == None:
        model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-mpnet-base-v2")
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        model = model.to(device)
        _model = model
        
    return _model

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=1234, reload=True)
