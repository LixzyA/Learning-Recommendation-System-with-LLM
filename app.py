from dotenv import load_dotenv
from os import makedirs
from sentence_transformers import SentenceTransformer
import torch
from weaviate_db import Database
from fastapi import FastAPI, Depends, Cookie, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from models import SessionLocal, User, UserSession, Preference
from contextlib import asynccontextmanager 
from security import *
from pydantic import BaseModel
from pathlib import Path
from typing import Optional

weaviate_db: Database | None = None
_model: SentenceTransformer | None = None
DEFAULT_ALPHA_VALUE = 0.3

@asynccontextmanager
async def lifespan(app:FastAPI):
    load_dotenv(dotenv_path=".env")
    load_model()

    global weaviate_db
    with Database() as weaviate_db:
        yield
    yield

app = FastAPI(lifespan=lifespan)

origins = [
    "http://localhost",
]

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency
def get_db():
    db = SessionLocal()  # Create a new session for each request
    try:
        yield db  # Yield the session to the caller
    finally:
        db.close()  # Ensure the session is closed after use

def get_current_user(db: Session = Depends(get_db), token: str = Cookie(None, alias="session_token")):
    if not token:
        raise HTTPException(status_code=401, detail="Missing session token")
    user_id = validate_session(db, token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return user_id
    
# Models
class UserCreate(BaseModel):
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

app.mount("/static", StaticFiles(directory="static"), name="static")

# GET request
@app.get("/", response_class=HTMLResponse)
async def get_page(request: Request, user_id: int = Depends(get_current_user)):
    try:
        return FileResponse("static/home.html")
    except HTTPException as e:
        if e.status_code == 401:
            return FileResponse("static/login.html")
        raise

@app.get("/login", response_class=HTMLResponse)
async def get_login_page(user_id: Optional[int] = Depends(get_current_user)):
    if user_id:
        return RedirectResponse("static/home.html")
    else:
        return FileResponse("static/login.html")

@app.get("/signup", response_class=HTMLResponse)
async def get_signup_page(user_id: Optional[int] = Depends(get_current_user)):
    if user_id:
        return RedirectResponse("static/home.html")
    else:
        return FileResponse("static/signup.html")

@app.get("/home", response_class=HTMLResponse)
async def get_home_page(user_id: int = Depends(get_current_user)):
    if user_id:
        return FileResponse("static/home.html")
    else:
        return RedirectResponse("static/login.html")

@app.get("/profile", response_class=HTMLResponse)
async def get_profile_page(user_id: int = Depends(get_current_user)):
    if not user_id:
        return RedirectResponse("static/login.html")
    return FileResponse("static/profile.html")

@app.get("/profile/preferences")
async def get_profile_preferences(user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        user_preferences = db.query(Preference).filter_by(user_id=user_id).first()
        results = {
            "file_type": user_preferences.file_type,
            "language": user_preferences.language,
            }
        return results
    except Exception as e:
        raise HTTPException(400, e)


# Static files handler
@app.get("/static/{file_path:path}")
async def serve_static(file_path: str):
    static_path = Path("static") / file_path
    if not static_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(static_path)

# POST request
@app.post("/login")
async def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == login_data.username).first()
    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect credentials")
    

    # In the login endpoint:
    existing_sessions = db.query(UserSession).filter(UserSession.user_id == user.id).all()
    for session in existing_sessions:
        db.delete(session)
    db.commit()  # Commit before creating the new session

    # Create new session
    session_token = create_session_token()
    new_session = UserSession(token=session_token, user_id=user.id)
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    
    response = JSONResponse(content={"token": session_token})
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return response

@app.post("/logout")
async def logout(db: Session = Depends(get_db), user_id: Optional[int] = Depends(get_current_user)):
    db.query(UserSession).filter(UserSession.user_id == user_id).delete()
    db.commit()
    return {"message": "Logged out successfully"}

@app.post("/signup")
async def signup(user: UserCreate, db: Session = Depends(get_db)):
    # Check existing user
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    # Create user
    hashed_password = get_password_hash(user.password)
    new_user = User(username=user.username, password_hash=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Create default preference
    default_preference = Preference(
        user_id=new_user.id,  # Link the preference to the new user
    )
    db.add(default_preference)
    db.commit()

    # Create session
    session_token = create_session_token()
    new_session = UserSession(token=session_token, user_id=new_user.id)
    db.add(new_session)
    db.commit()
    
    response = JSONResponse(content={"token": session_token})
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        samesite="Lax"
    )
    return response


@app.post("/recommendation")
async def recommendation_page(request: Request, payload: dict, user_id: Optional[int] = Depends(get_current_user)):
    global weaviate_db

    query = payload['input']
    try:
        alpha = float(payload.get('alpha', DEFAULT_ALPHA_VALUE)) 
    except ValueError:
        print(f"Invalid alpha value, using default {DEFAULT_ALPHA_VALUE}")
        alpha = DEFAULT_ALPHA_VALUE

    if not user_id:
        return RedirectResponse(url="static/login.html", status_code=303)

    model = load_model()
    try:
        query_embedding = model.encode(query).tolist()
        property = {"language": 'en', "file_type": "pdf"}
        results = weaviate_db.search(query, query_embedding, property, alpha)
        return {"message": f"Searching for: {query}", "results": results}
    except ValueError:
        raise HTTPException(status_code=404, detail="Query cannot be empty or whitespace.")

# Endpoint to handle voting
@app.post("/vote/{result_id}")
async def vote(result_id: str, vote: str, request: Request, user_id: int = Depends(get_current_user)):
    # Validate the vote direction
    if vote not in ["up", "down"]:
        raise HTTPException(status_code=400, detail="Invalid vote direction. Must be 'up' or 'down'.")

    global weaviate_db
    try:
        response = weaviate_db.update_vote(result_id, user_id, vote)
    except LookupError:
        return {"message": f"No object found with UUID {result_id}"}

    if response == (-1,-1):
        return {
            "message": "Vote recorded successfully",
            "status": 0, # User already voted on the object and it was the same vote
        }
    return {
        "message": "Vote recorded successfully",
        "status": 1,
        "upvote": response[0],
        "downvote": response[1], 
    }

class UpdateModel(BaseModel):
    file_type: str
    language: str

@app.post("/profile/update")
def update_profile(preference: UpdateModel, db: Session = Depends(get_db), user_id: int = Depends(get_current_user)):
    print(f"Preference is {preference}")
    
    if preference.file_type == None and preference.language == None:
        return {"status_code": 400, "message": "Preference not found"}
    
    # Get user
    user_to_update = db.query(Preference).filter_by(user_id=user_id).first()

    if user_to_update:
        user_to_update.language = preference.language
        user_to_update.file_type = preference.file_type
        db.commit()
        return {"status_code": 200, "message": "Sucessfuly updated preference"}
    else:
        return {"status_code": 404, "message": "User not found"}

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
    uvicorn.run("app:app", host="0.0.0.0", port=1234)
