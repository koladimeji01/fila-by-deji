from contextlib import asynccontextmanager
import re
from uuid import uuid4
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import get_settings
from .rate_limit import limit_request
from .database import get_db
from .models import Order, OrderItem, Product, ProductInventory, User, SavedItem, DeliveryQuoteAudit
from .schemas import (AdminOrderResponse, CreateDraftOrderRequest, LoginRequest, OrderItemResponse, OrderResponse,
                      ProductResponse, RegisterRequest, StockLevelResponse, StockUpdateRequest, TokenResponse, UserResponse,
                      SaveItemRequest, SavedItemResponse, DeliveryQuoteRequest, AdminOverviewResponse,
                      AdminProductResponse, AdminProductUpdateRequest, AdminProductCreateRequest)
from .security import create_token, get_current_admin, get_current_user, hash_password, verify_password
from .reservations import aware, cancel_order, expire_holds, reserve_order

settings = get_settings()


@asynccontextmanager
async def lifespan(application: FastAPI):
    # Fail before accepting requests when a developer forgets Alembic upgrades.
    # Tests use isolated SQLAlchemy-created schemas; migration history is not used there.
    if settings.app_env != 'test':
        from .doctor import check_readiness
        errors = check_readiness()
        if errors:
            raise RuntimeError('FÌLÀ backend not ready: ' + ' | '.join(errors))
    yield


app = FastAPI(title='FÌLÀ by Deji API', version='0.1.1', lifespan=lifespan, docs_url='/docs' if settings.app_env != 'production' else None,
              redoc_url=None)
app.middleware('http')(limit_request)


@app.middleware('http')
async def private_response_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith(('/api/v1/auth/', '/api/v1/orders', '/api/v1/admin', '/api/v1/products', '/api/v1/saved-items')):
        response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer'
    return response


# Added last: CORS wraps rate-limit/error responses so approved browsers can read 429/503.
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_credentials=False,
                   allow_methods=['GET', 'POST', 'PUT', 'DELETE'], allow_headers=['Authorization', 'Content-Type'])


def product_out(product: Product) -> ProductResponse:
    return ProductResponse(id=product.id, name=product.name, category=product.category,
                           description=product.description, price_ngn=product.price_kobo // 100,
                           image_url=product.image_url,
                           available_sizes=sorted((row.size for row in product.stock_levels if row.quantity > 0), key=int),
                           stock_by_size={row.size: row.quantity for row in product.stock_levels})


def order_out(order: Order) -> OrderResponse:
    return OrderResponse(
        id=order.id, status=order.status, total_ngn=order.total_kobo // 100,
        created_at=order.created_at, reserved_until=aware(order.reserved_until),
        delivery_destination=order.delivery_destination,
        shipping_quote_ngn=order.shipping_quote_kobo // 100 if order.shipping_quote_kobo is not None else None,
        estimated_total_ngn=(order.total_kobo + order.shipping_quote_kobo) // 100 if order.shipping_quote_kobo is not None else None,
        shipping_quoted_at=aware(order.shipping_quoted_at),
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
    expire_holds(db)
    entries = db.scalars(select(Product).where(Product.is_active.is_(True)).order_by(Product.id)).all()
    return [product_out(p) for p in entries]


@app.get('/api/v1/products/{product_id}', response_model=ProductResponse)
def product(product_id: str, db: Session = Depends(get_db)):
    expire_holds(db)
    entry = db.get(Product, product_id)
    if entry is None or not entry.is_active:
        raise HTTPException(404, 'Product not found')
    return product_out(entry)


def saved_out(item: SavedItem, db: Session) -> SavedItemResponse:
    product = db.get(Product, item.product_id)
    stock = db.get(ProductInventory, (item.product_id, item.size))
    available = stock.quantity if stock and product and product.is_active else 0
    return SavedItemResponse(
        product_id=item.product_id, product_name=product.name if product else 'Unavailable cap',
        size=item.size, quantity=item.quantity,
        unit_price_ngn=product.price_kobo // 100 if product else 0,
        available_quantity=available,
    )


@app.get('/api/v1/saved-items', response_model=list[SavedItemResponse])
def saved_items(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.scalars(select(SavedItem).where(SavedItem.user_id == user.id)
                      .order_by(SavedItem.created_at.desc(), SavedItem.product_id, SavedItem.size)).all()
    return [saved_out(item, db) for item in rows]


@app.put('/api/v1/saved-items/{product_id}/{size}', response_model=SavedItemResponse)
def save_item(product_id: str, size: str, body: SaveItemRequest,
              db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if size not in ('32', '35', '39', '41'):
        raise HTTPException(422, 'Unsupported cap size')
    product = db.get(Product, product_id)
    if product is None or not product.is_active:
        raise HTTPException(404, 'Cap is no longer available to save')
    item = db.get(SavedItem, (user.id, product_id, size))
    if item is None:
        item = SavedItem(user_id=user.id, product_id=product_id, size=size, quantity=body.quantity)
        db.add(item)
    else:
        item.quantity = body.quantity
    db.commit()
    return saved_out(item, db)


@app.delete('/api/v1/saved-items/{product_id}/{size}', status_code=status.HTTP_204_NO_CONTENT)
def remove_saved_item(product_id: str, size: str,
                      db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.get(SavedItem, (user.id, product_id, size))
    if item:
        db.delete(item)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def existing_order_request(db: Session, user: User, body: CreateDraftOrderRequest) -> Order | None:
    """Idempotent request replay: only for the original owner and identical basket.

    This prevents two unpaid drafts if a response is lost or a customer double-clicks.
    """
    existing = db.scalar(select(Order).where(Order.client_request_id == str(body.client_request_id)))
    if existing is None:
        return None
    original = sorted((item.product_id, item.size, item.quantity) for item in existing.items)
    requested = sorted((item.product_id, item.size, item.quantity) for item in body.items)
    if existing.user_id != user.id or original != requested or existing.delivery_destination != body.delivery_destination:
        raise HTTPException(409, 'Order request reference cannot be reused with another selection')
    return existing


@app.post('/api/v1/orders/drafts', response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_draft_order(body: CreateDraftOrderRequest, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    expire_holds(db)
    if body.client_request_id is not None:
        prior = existing_order_request(db, user, body)
        if prior:
            return order_out(prior)
    products = {p.id: p for p in db.scalars(select(Product).where(
        Product.id.in_([item.product_id for item in body.items]), Product.is_active.is_(True))).all()}
    if len(products) != len({item.product_id for item in body.items}):
        raise HTTPException(400, 'One or more products are unavailable')
    # A draft does not reserve inventory. Check each requested variation now,
    # then re-check transactionally in a future confirmed-payment workflow.
    stock = {(row.product_id, row.size): row.quantity for row in db.scalars(
        select(ProductInventory).where(ProductInventory.product_id.in_(products))).all()}
    unavailable = [item for item in body.items
                   if stock.get((item.product_id, item.size), 0) < item.quantity]
    if unavailable:
        raise HTTPException(409, 'Requested cap size or quantity is unavailable. Refresh your bag and try again.')
    total = sum(products[item.product_id].price_kobo * item.quantity for item in body.items)
    order = Order(user_id=user.id, total_kobo=total, status='draft',
                  client_request_id=str(body.client_request_id) if body.client_request_id else None,
                  delivery_destination=body.delivery_destination)
    for item in body.items:
        p = products[item.product_id]
        order.items.append(OrderItem(product_id=p.id, product_name=p.name, size=item.size,
                                     quantity=item.quantity, unit_price_kobo=p.price_kobo))
    db.add(order)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if body.client_request_id is not None:
            prior = existing_order_request(db, user, body)
            if prior:
                return order_out(prior)
        raise HTTPException(409, 'Could not record order request; please retry safely')
    db.refresh(order)
    return order_out(order)


@app.get('/api/v1/orders', response_model=list[OrderResponse])
def my_orders(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
              db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    expire_holds(db)
    return [order_out(o) for o in db.scalars(select(Order).where(Order.user_id == user.id)
                    .order_by(Order.created_at.desc(), Order.id.desc()).offset(offset).limit(limit)).all()]


@app.get('/api/v1/orders/{order_id}', response_model=OrderResponse)
def order_detail(order_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    expire_holds(db)
    order = db.scalar(select(Order).where(Order.id == order_id, Order.user_id == user.id))
    if order is None:
        raise HTTPException(404, 'Order not found')
    return order_out(order)


@app.post('/api/v1/orders/{order_id}/reserve', response_model=OrderResponse)
def reserve_my_draft(order_id: str, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    order = db.scalar(select(Order).where(Order.id == order_id, Order.user_id == user.id))
    if order is None:
        raise HTTPException(404, 'Order not found')
    return order_out(reserve_order(db, order, user))


@app.post('/api/v1/orders/{order_id}/cancel', response_model=OrderResponse)
def cancel_my_order(order_id: str, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    order = db.scalar(select(Order).where(Order.id == order_id, Order.user_id == user.id))
    if order is None:
        raise HTTPException(404, 'Order not found')
    return order_out(cancel_order(db, order))


@app.get('/api/v1/admin/overview', response_model=AdminOverviewResponse)
def admin_overview(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    """Only actual administrators can view these operational totals."""
    expire_holds(db)
    active = db.scalar(select(func.count()).select_from(Product).where(Product.is_active.is_(True)))
    # Only products actually visible to customers count in available stock KPIs.
    available = db.scalar(select(func.coalesce(func.sum(ProductInventory.quantity), 0))
                          .join(Product).where(Product.is_active.is_(True)))
    sold_out = db.scalar(select(func.count()).select_from(ProductInventory)
                         .join(Product).where(ProductInventory.quantity == 0,
                                              Product.is_active.is_(True)))
    active_enquiry = (Order.status == 'draft') & Order.delivery_destination.is_not(None)
    total = db.scalar(select(func.count()).select_from(Order).where(active_enquiry))
    unquoted = db.scalar(select(func.count()).select_from(Order).where(
        active_enquiry, Order.shipping_quote_kobo.is_(None)))
    quoted = db.scalar(select(func.count()).select_from(Order).where(
        active_enquiry, Order.shipping_quote_kobo.is_not(None)))
    holds = db.scalar(select(func.count()).select_from(Order).where(Order.status == 'reserved'))
    return AdminOverviewResponse(
        active_products=active, available_units=available, out_of_stock_variants=sold_out,
        total_enquiries=total, unquoted_enquiries=unquoted,
        quoted_enquiries=quoted, active_stock_holds=holds,
    )


@app.get('/api/v1/admin/products', response_model=list[AdminProductResponse])
def admin_products(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    """All catalog products, including archived products. Admin role is checked in DB."""
    expire_holds(db)
    products = db.scalars(select(Product).order_by(Product.id)).all()
    return [AdminProductResponse(**product_out(p).model_dump(), is_active=p.is_active) for p in products]


@app.post('/api/v1/admin/products', response_model=AdminProductResponse,
          status_code=status.HTTP_201_CREATED)
def admin_create_product(body: AdminProductCreateRequest,
                         db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    """Only verified administrators can create database-backed catalog entries.

    Image URLs point to externally hosted public JPEG/PNG/WebP files. The API never
    downloads user-provided URLs or creates unreviewed files in the storefront.
    """
    slug = re.sub(r'[^a-z0-9]+', '-', body.name.lower()).strip('-')[:49].strip('-') or 'fila-cap'
    product_id = f'{slug}-{uuid4().hex[:8]}'
    product = Product(id=product_id, name=body.name, category=body.category,
                      description=body.description, price_kobo=body.price_ngn * 100,
                      image_url=body.image_url, is_active=body.is_active)
    for size in ('32', '35', '39', '41'):
        product.stock_levels.append(ProductInventory(
            size=size, quantity=body.stock_by_size.get(size, 0)
        ))
    db.add(product)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Could not create product; please retry')
    db.refresh(product)
    return AdminProductResponse(**product_out(product).model_dump(), is_active=product.is_active)


@app.put('/api/v1/admin/products/{product_id}', response_model=AdminProductResponse)
def admin_update_product(product_id: str, body: AdminProductUpdateRequest,
                         db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    """Edit existing catalog information without granting image upload or public privilege."""
    expire_holds(db)
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(404, 'Product not found')
    if product.is_active and not body.is_active:
        active_holds = db.scalar(
            select(func.count()).select_from(OrderItem).join(Order, Order.id == OrderItem.order_id)
            .where(OrderItem.product_id == product_id, Order.status == 'reserved')
        )
        if active_holds:
            raise HTTPException(409, 'Cannot archive a product with active stock holds')
    product.name = body.name
    product.category = body.category
    product.description = body.description
    product.price_kobo = body.price_ngn * 100
    product.is_active = body.is_active
    db.commit()
    db.refresh(product)
    return AdminProductResponse(**product_out(product).model_dump(), is_active=product.is_active)


@app.get('/api/v1/admin/inventory', response_model=list[StockLevelResponse])
def admin_inventory(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    expire_holds(db)
    rows = db.scalars(select(ProductInventory).order_by(ProductInventory.product_id, ProductInventory.size)).all()
    return [StockLevelResponse(product_id=r.product_id, size=r.size,
                               available_quantity=r.quantity) for r in rows]


@app.put('/api/v1/admin/inventory/{product_id}/{size}', response_model=StockLevelResponse)
def admin_set_available(product_id: str, size: str, body: StockUpdateRequest,
                        db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    expire_holds(db)
    if size not in ('32', '35', '39', '41'):
        raise HTTPException(422, 'Invalid size')
    if db.get(Product, product_id) is None:
        raise HTTPException(404, 'Product not found')
    result = db.execute(update(ProductInventory).where(
        ProductInventory.product_id == product_id, ProductInventory.size == size
    ).values(quantity=body.available_quantity))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, 'Stock record missing. Run the product seed step.')
    db.commit()
    return StockLevelResponse(product_id=product_id, size=size, available_quantity=body.available_quantity)


@app.get('/api/v1/admin/orders', response_model=list[AdminOrderResponse])
def admin_orders(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                 db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    expire_holds(db)
    rows = db.scalars(select(Order).order_by(Order.created_at.desc(), Order.id.desc())
                      .offset(offset).limit(limit)).all()
    return [AdminOrderResponse(**order_out(o).model_dump(), user_id=o.user_id,
                               customer_name=o.user.name, customer_email=o.user.email) for o in rows]


@app.put('/api/v1/admin/orders/{order_id}/delivery-quote', response_model=AdminOrderResponse)
def admin_quote_delivery(order_id: str, body: DeliveryQuoteRequest,
                         db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    """Admin-only delivery estimate, visible to the buyer. Never a payment receipt."""
    order = db.scalar(select(Order).where(Order.id == order_id).with_for_update())
    if order is None:
        raise HTTPException(404, 'Enquiry not found')
    if order.status != 'draft' or not order.delivery_destination:
        raise HTTPException(409, 'Only active enquiries with a delivery destination can be quoted')
    quote_kobo = body.shipping_amount_ngn * 100
    if order.shipping_quote_kobo != quote_kobo:
        db.add(DeliveryQuoteAudit(
            order_id=order.id, admin_user_id=admin.id,
            previous_amount_kobo=order.shipping_quote_kobo,
            new_amount_kobo=quote_kobo,
        ))
        order.shipping_quote_kobo = quote_kobo
        from .models import utcnow
        order.shipping_quoted_at = utcnow()
        db.commit()
        db.refresh(order)
    return AdminOrderResponse(**order_out(order).model_dump(), user_id=order.user_id,
                              customer_name=order.user.name, customer_email=order.user.email)


@app.post('/api/v1/admin/reservations/release-expired')
def admin_release_expired(db: Session = Depends(get_db),
                          admin: User = Depends(get_current_admin)):
    return {'expired': expire_holds(db)}
