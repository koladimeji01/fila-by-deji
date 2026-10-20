"""Atomic, temporary cap inventory holds. No payment or fulfillment transitions.

`ProductInventory.quantity` is AVAILABLE stock. Reservations decrement that field;
cancel/expiry restores stock exactly once. Expiry is lazy and also has an operator CLI.
Before public deployment add distributed rate limits, background expiry scheduling,
payment-provider verification and idempotency.
"""
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from fastapi import HTTPException
from .models import Order, Product, ProductInventory, User

HOLD_MINUTES = 15


def now_utc():
    return datetime.now(timezone.utc)


def aware(value):
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _restore_stock(db: Session, order: Order) -> None:
    for item in order.items:
        db.execute(update(ProductInventory).where(
            ProductInventory.product_id == item.product_id,
            ProductInventory.size == item.size,
        ).values(quantity=ProductInventory.quantity + item.quantity))


def expire_holds(db: Session) -> int:
    """Release overdue holds. CAS status avoids releasing the same hold twice.

    This function commits on success; do not call inside another write transaction.
    """
    expired = db.scalars(select(Order).where(
        Order.status == 'reserved', Order.reserved_until <= now_utc()
    ).order_by(Order.reserved_until).limit(250)).all()
    count = 0
    for order in expired:
        changed = db.execute(update(Order).where(Order.id == order.id,
                 Order.status == 'reserved', Order.reserved_until <= now_utc()).values(status='expired').execution_options(synchronize_session=False))
        if changed.rowcount == 1:
            _restore_stock(db, order)
            count += 1
    if count:
        db.commit()
        db.expire_all()
    return count


def reserve_order(db: Session, order: Order, owner: User) -> Order:
    """A customer may have only one active hold. All size checks are atomic."""
    expire_holds(db)
    # Serialize reservations per user on PostgreSQL. SQLite write locking applies
    # to the conditional stock updates; SQLite is for local development only.
    db.scalar(select(User).where(User.id == owner.id).with_for_update())
    db.refresh(order)
    if order.status != 'draft':
        raise HTTPException(409, 'Only a draft can be reserved')
    existing = db.scalar(select(Order.id).where(Order.user_id == owner.id, Order.status == 'reserved').limit(1))
    if existing:
        raise HTTPException(409, 'You already have an active reservation. Cancel it or wait for expiry.')
    until = now_utc() + timedelta(minutes=HOLD_MINUTES)
    claimed = db.execute(update(Order).where(Order.id == order.id, Order.status == 'draft')
                         .values(status='reserved', reserved_until=until))
    if claimed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, 'Order status changed. Please refresh.')
    try:
        # Revalidate products, prices, and quantities at reservation time.
        new_total = 0
        for item in order.items:
            product = db.get(Product, item.product_id)
            if product is None or not product.is_active:
                raise HTTPException(409, 'One of these products is no longer available')
            deducted = db.execute(update(ProductInventory).where(
                ProductInventory.product_id == item.product_id,
                ProductInventory.size == item.size,
                ProductInventory.quantity >= item.quantity
            ).values(quantity=ProductInventory.quantity - item.quantity))
            if deducted.rowcount != 1:
                raise HTTPException(409, f'Insufficient stock for {product.name} size {item.size}')
            item.product_name = product.name
            item.unit_price_kobo = product.price_kobo
            new_total += product.price_kobo * item.quantity
        order.total_kobo = new_total
        db.commit()
    except Exception:
        db.rollback()  # Restores all deductions and status on partial failure.
        raise
    db.refresh(order)
    return order


def cancel_order(db: Session, order: Order) -> Order:
    expire_holds(db)
    db.refresh(order)
    if order.status not in ('draft', 'reserved'):
        raise HTTPException(409, 'This order cannot be cancelled in its current state')
    was_reserved = order.status == 'reserved'
    changed = db.execute(update(Order).where(Order.id == order.id, Order.status == order.status)
                         .values(status='cancelled', reserved_until=None))
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, 'Order status changed. Please refresh.')
    if was_reserved:
        _restore_stock(db, order)
    db.commit()
    db.refresh(order)
    return order
