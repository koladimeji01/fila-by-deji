from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default='0')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    orders: Mapped[list['Order']] = relationship(back_populates='user')


class Product(Base):
    __tablename__ = 'products'
    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    price_kobo: Mapped[int] = mapped_column(Integer, nullable=False)
    image_url: Mapped[str] = mapped_column(String(300), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    stock_levels: Mapped[list['ProductInventory']] = relationship(back_populates='product', cascade='all, delete-orphan', lazy='selectin')
    __table_args__ = (CheckConstraint('price_kobo > 0', name='ck_product_positive_price'),)


class Order(Base):
    __tablename__ = 'orders'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='draft')
    total_kobo: Mapped[int] = mapped_column(Integer, nullable=False)
    client_request_id: Mapped[str | None] = mapped_column(String(36), unique=True, nullable=True, index=True)
    delivery_destination: Mapped[str | None] = mapped_column(String(120), nullable=True)
    shipping_quote_kobo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shipping_quoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    reserved_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user: Mapped[User] = relationship(back_populates='orders')
    items: Mapped[list['OrderItem']] = relationship(back_populates='order', cascade='all, delete-orphan', lazy='selectin')
    __table_args__ = (CheckConstraint('total_kobo >= 0', name='ck_order_nonnegative_total'),)


class OrderItem(Base):
    __tablename__ = 'order_items'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    order_id: Mapped[str] = mapped_column(ForeignKey('orders.id', ondelete='CASCADE'), nullable=False)
    product_id: Mapped[str] = mapped_column(ForeignKey('products.id', ondelete='RESTRICT'), nullable=False)
    product_name: Mapped[str] = mapped_column(String(150), nullable=False)
    size: Mapped[str] = mapped_column(String(4), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_kobo: Mapped[int] = mapped_column(Integer, nullable=False)
    order: Mapped[Order] = relationship(back_populates='items')
    __table_args__ = (
        CheckConstraint('quantity > 0', name='ck_order_item_positive_quantity'),
        CheckConstraint('unit_price_kobo > 0', name='ck_order_item_positive_price'),
    )


class ProductInventory(Base):
    """Explicit per-size stock. A missing row is treated as unavailable."""
    __tablename__ = 'product_inventory'
    product_id: Mapped[str] = mapped_column(ForeignKey('products.id', ondelete='CASCADE'), primary_key=True)
    size: Mapped[str] = mapped_column(String(4), primary_key=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    product: Mapped[Product] = relationship(back_populates='stock_levels')
    __table_args__ = (CheckConstraint('quantity >= 0', name='ck_inventory_nonnegative_quantity'),
                      CheckConstraint("size IN ('32', '35', '39', '41')", name='ck_inventory_valid_size'))


class SavedItem(Base):
    """A user's saved cap/size. Never reserves stock or represents an order."""
    __tablename__ = 'saved_items'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey('products.id', ondelete='CASCADE'), primary_key=True)
    size: Mapped[str] = mapped_column(String(4), primary_key=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    __table_args__ = (
        CheckConstraint("size IN ('32','35','39','41')", name='ck_saved_item_size'),
        CheckConstraint('quantity BETWEEN 1 AND 10', name='ck_saved_item_quantity'),
    )


class DeliveryQuoteAudit(Base):
    """Immutable log of staff changes to a shipping quote; no payment is taken."""
    __tablename__ = 'delivery_quote_audit'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    order_id: Mapped[str] = mapped_column(ForeignKey('orders.id', ondelete='RESTRICT'), nullable=False, index=True)
    admin_user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    previous_amount_kobo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    new_amount_kobo: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (CheckConstraint('new_amount_kobo >= 0', name='ck_delivery_quote_audit_amount'),)
