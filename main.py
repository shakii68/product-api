import logging
import os
import time
from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pwdlib import PasswordHash
from pydantic import BaseModel, ConfigDict, field_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select
from starlette.exceptions import HTTPException as StarletteHTTPException

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-for-development")
ALGORITHM = os.getenv("ALGORITHM", "HS256")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)

app = FastAPI(title="CloudDeploy Product API", version="1.0.0")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")
password_hash = PasswordHash.recommended()
start_time = time.time()

LOG_FILE = os.getenv("LOG_FILE", "app.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        RotatingFileHandler(LOG_FILE, maxBytes=10_485_760, backupCount=5),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    email: str
    hashed_password: str
    full_name: str
    is_admin: bool = False


class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    full_name: str


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    email: str
    full_name: str
    is_admin: bool


class Product(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str
    price: float
    stock: int


class ProductCreate(BaseModel):
    name: str
    description: str
    price: float
    stock: int

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v):
        if not v.strip():
            raise ValueError("name cannot be empty")
        return v

    @field_validator("price")
    @classmethod
    def price_non_negative(cls, v):
        if v < 0:
            raise ValueError("price cannot be negative")
        return v

    @field_validator("stock")
    @classmethod
    def stock_non_negative(cls, v):
        if v < 0:
            raise ValueError("stock cannot be negative")
        return v


class ProductUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    price: float | None = None
    stock: int | None = None


def create_db():
    SQLModel.metadata.create_all(engine)


@app.on_event("startup")
def startup():
    create_db()


def get_session():
    with Session(engine) as session:
        yield session


def make_token(username: str):
    payload = {
        "sub": username,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
):
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise credentials_error
    except JWTError:
        raise credentials_error

    user = session.exec(select(User).where(User.username == username)).first()
    if not user:
        raise credentials_error
    return user


def get_current_admin(current_user: User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": True, "message": str(exc.detail)},
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    details = []

    for error in exc.errors():
        details.append(
            {
                "field": ".".join(str(x) for x in error["loc"]),
                "message": error["msg"],
                "type": error["type"],
            }
        )

    return JSONResponse(
        status_code=422,
        content={
            "error": True,
            "message": "Validation error",
            "details": details,
        },
    )


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started = time.time()
    response = await call_next(request)
    elapsed = time.time() - started
    logger.info(
        f"{request.method} {request.url.path} - Status: {response.status_code} - Time: {elapsed:.3f}s"
    )
    return response


@app.get("/")
def root():
    return {"message": "CloudDeploy Product API is running"}


@app.post("/register", response_model=UserPublic, status_code=201)
def register(user_data: UserCreate, session: Session = Depends(get_session)):
    if session.exec(select(User).where(User.username == user_data.username)).first():
        raise HTTPException(status_code=409, detail="username already exists")

    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=password_hash.hash(user_data.password),
        full_name=user_data.full_name,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@app.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
):
    user = session.exec(select(User).where(User.username == form_data.username)).first()
    if not user or not password_hash.verify(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"access_token": make_token(user.username), "token_type": "bearer"}


@app.get("/users", response_model=list[UserPublic])
def list_users(
    _: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    return session.exec(select(User)).all()


@app.post("/products", response_model=Product, status_code=201)
def create_product(
    product_data: ProductCreate,
    _: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    product = Product(**product_data.model_dump())
    session.add(product)
    session.commit()
    session.refresh(product)
    return product


@app.get("/products", response_model=list[Product])
def list_products(
    _: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return session.exec(select(Product)).all()


@app.get("/products/{product_id}", response_model=Product)
def get_product(
    product_id: int,
    _: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@app.patch("/products/{product_id}", response_model=Product)
def update_product(
    product_id: int,
    product_data: ProductUpdate,
    _: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    updates = product_data.model_dump(exclude_unset=True)
    if "name" in updates and not updates["name"].strip():
        raise HTTPException(status_code=422, detail="name cannot be empty")
    if "price" in updates and updates["price"] < 0:
        raise HTTPException(status_code=422, detail="price cannot be negative")
    if "stock" in updates and updates["stock"] < 0:
        raise HTTPException(status_code=422, detail="stock cannot be negative")

    for key, value in updates.items():
        setattr(product, key, value)

    session.add(product)
    session.commit()
    session.refresh(product)
    return product


@app.delete("/products/{product_id}", status_code=204)
def delete_product(
    product_id: int,
    _: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    session.delete(product)
    session.commit()


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
        "uptime": time.time() - start_time,
    }


@app.get("/metrics")
def metrics(_: User = Depends(get_current_admin)):
    import psutil

    return {
        "cpu_percent": psutil.cpu_percent(),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_usage": psutil.disk_usage("/").percent,
    }
