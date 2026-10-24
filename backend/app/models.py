from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, LargeBinary, String, Text
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
    can_manage_staff: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default='0')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    orders: Mapped[list['Order']] = relationship(back_populates='user')


class StaffApplication(Base):
    """Only explicit staff requests are eligible for role changes."""
    __tablename__ = 'staff_applications'
    user_id: Mapped[str] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE'), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='pending')
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    __table_args__ = (CheckConstraint(
        "status IN ('pending','approved','rejected','revoked')", name='ck_staff_application_status'
    ),)


class StaffAccessAudit(Base):
    """Immutable account-approval and access-revocation log."""
    __tablename__ = 'staff_access_audit'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    subject_user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    actor_user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (CheckConstraint(
        "action IN ('approved','rejected','revoked')", name='ck_staff_audit_action'
    ),)


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


class ProductPhoto(Base):
    """Optimized photo bytes stored in Postgres, keyed by its catalog product.

    This is deliberately not exposed to Supabase's public Data API.
    """
    __tablename__ = 'product_photos'
    product_id: Mapped[str] = mapped_column(
        ForeignKey('products.id', ondelete='CASCADE'), primary_key=True
    )
    image_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(32), nullable=False, default='image/webp')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


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



class EnquiryFollowup(Base):
    """Private staff-only follow-up metadata, separate from unpaid order state."""
    __tablename__ = 'enquiry_followups'
    order_id: Mapped[str] = mapped_column(
        ForeignKey('orders.id', ondelete='CASCADE'), primary_key=True
    )
    stage: Mapped[str] = mapped_column(String(20), nullable=False, default='new')
    internal_note: Mapped[str] = mapped_column(Text, nullable=False, default='')
    updated_by: Mapped[str] = mapped_column(
        ForeignKey('users.id', ondelete='RESTRICT'), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    __table_args__ = (CheckConstraint(
        "stage IN ('new','contacted','awaiting_reply','closed')",
        name='ck_enquiry_followup_stage'
    ),)


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
