from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from .models import Order, OrderItem, Product, User
from .schemas import (CreateDraftOrderRequest, LoginRequest, OrderItemResponse, OrderResponse,
                      ProductResponse, RegisterRequest, TokenResponse, UserResponse)
from .security import create_token, get_current_user, hash_password, verify_password

settings = get_settings()
app = FastAPI(title='FÌLÀ by Deji API', version='0.1.0', docs_url='/docs' if settings.app_env != 'production' else None,
              redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_credentials=False,
                   allow_methods=['GET', 'POST'], allow_headers=['Authorization', 'Content-Type'])


def product_out(product: Product) -> ProductResponse:
    return ProductResponse(id=product.id, name=product.name, category=product.category,
                           description=product.description, price_ngn=product.price_kobo // 100,
                           image_url=product.image_url)


def order_out(order: Order) -> OrderResponse:
    return OrderResponse(
        id=order.id, status=order.status, total_ngn=order.total_kobo // 100,
        created_at=order.created_at,
        items=[OrderItemResponse(
            product_id=item.product_id, product_name=item.product_name, size=item.size,
            quantity=item.quantity, unit_price_ngn=item.unit_price_kobo // 100,
            line_total_ngn=item.unit_price_kobo * item.quantity // 100)
            for item in order.items],
    )


@app.get('/api/v1/health')
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text('SELECT 1'))
        return {'status': 'ok'}
    except Exception:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, 'Database unavailable')


@app.post('/api/v1/auth/register', response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    user = User(name=body.name, email=str(body.email).lower(), password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'An account with this email already exists')
    db.refresh(user)
    return user


@app.post('/api/v1/auth/login', response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == str(body.email).lower()))
    if not verify_password(body.password, user.password_hash if user else None) or not user or not user.is_active:
        raise HTTPException(401, 'Invalid email or password')
    return TokenResponse(access_token=create_token(user.id))


@app.get('/api/v1/auth/me', response_model=UserResponse)
def me(user: User = Depends(get_current_user)):
    return user


@app.get('/api/v1/products', response_model=list[ProductResponse])
def products(db: Session = Depends(get_db)):
    entries = db.scalars(select(Product).where(Product.is_active.is_(True)).order_by(Product.id)).all()
    return [product_out(p) for p in entries]


@app.get('/api/v1/products/{product_id}', response_model=ProductResponse)
def product(product_id: str, db: Session = Depends(get_db)):
    entry = db.get(Product, product_id)
    if entry is None or not entry.is_active:
        raise HTTPException(404, 'Product not found')
    return product_out(entry)


@app.post('/api/v1/orders/drafts', response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_draft_order(body: CreateDraftOrderRequest, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    products = {p.id: p for p in db.scalars(select(Product).where(
        Product.id.in_([item.product_id for item in body.items]), Product.is_active.is_(True))).all()}
    if len(products) != len({item.product_id for item in body.items}):
        raise HTTPException(400, 'One or more products are unavailable')
    total = sum(products[item.product_id].price_kobo * item.quantity for item in body.items)
    order = Order(user_id=user.id, total_kobo=total, status='draft')
    for item in body.items:
        p = products[item.product_id]
        order.items.append(OrderItem(product_id=p.id, product_name=p.name, size=item.size,
                                     quantity=item.quantity, unit_price_kobo=p.price_kobo))
    db.add(order)
    db.commit()
    db.refresh(order)
    return order_out(order)


@app.get('/api/v1/orders', response_model=list[OrderResponse])
def my_orders(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [order_out(o) for o in db.scalars(select(Order).where(Order.user_id == user.id)
                                               .order_by(Order.created_at.desc()).limit(100)).all()]


@app.get('/api/v1/orders/{order_id}', response_model=OrderResponse)
def order_detail(order_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    order = db.scalar(select(Order).where(Order.id == order_id, Order.user_id == user.id))
    if order is None:
        raise HTTPException(404, 'Order not found')
    return order_out(order)
