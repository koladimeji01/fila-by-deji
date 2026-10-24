from datetime import datetime
from typing import Literal
import ipaddress
from urllib.parse import urlsplit
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

SIZES = {'32', '35', '39', '41'}


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)

    @field_validator('name')
    @classmethod
    def normalize_name(cls, value: str) -> str:
        result = value.strip()
        if len(result) < 2:
            raise ValueError('Name must contain at least two non-whitespace characters')
        return result


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    email: EmailStr


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'


class StaffDisplayNameRequest(BaseModel):
    """Self-service display name; cannot update email, role or permissions."""
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=2, max_length=100)

    @field_validator('name')
    @classmethod
    def normalise_name(cls, value: str) -> str:
        cleaned = ' '.join(value.split())
        if len(cleaned) < 2 or len(cleaned) > 100:
            raise ValueError('Please enter a display name between 2 and 100 characters')
        return cleaned


class StaffPasswordChangeRequest(BaseModel):
    """Requires the current password even when an admin JWT is valid."""
    model_config = ConfigDict(extra='forbid')
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class BusinessNotification(BaseModel):
    key: str
    kind: Literal['enquiry', 'stock', 'staff']
    title: str
    detail: str
    destination: Literal['enquiries', 'inventory', 'staff']
    created_at: datetime | None = None
    is_read: bool = False


class BusinessNotificationList(BaseModel):
    unread_count: int
    notifications: list[BusinessNotification]


class NotificationReadRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    key: str = Field(min_length=4, max_length=140)


class StaffStatusResponse(BaseModel):
    status: str
    message: str


class StaffAccountResponse(BaseModel):
    user_id: str
    name: str
    email: EmailStr
    status: str
    is_admin: bool
    can_manage_staff: bool
    requested_at: datetime | None = None
    reviewed_at: datetime | None = None


class StaffDecisionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: Literal['approve', 'reject', 'revoke']


class ProductResponse(BaseModel):
    id: str
    name: str
    category: str
    description: str
    price_ngn: int
    image_url: str
    # Only sizes with positive stock are advertised as available.
    available_sizes: list[str] = Field(default_factory=list)
    stock_by_size: dict[str, int] = Field(default_factory=dict)


class OrderItemInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    product_id: str = Field(min_length=1, max_length=60)
    size: str
    quantity: int = Field(ge=1, le=10)

    @field_validator('size')
    @classmethod
    def valid_size(cls, size: str) -> str:
        if size not in SIZES:
            raise ValueError('Unsupported size')
        return size


class CreateDraftOrderRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    items: list[OrderItemInput] = Field(min_length=1, max_length=30)
    client_request_id: UUID | None = None
    delivery_destination: str | None = Field(default=None, min_length=3, max_length=120)

    @field_validator('delivery_destination')
    @classmethod
    def normalise_destination(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = ' '.join(value.split())
        if len(cleaned) < 3 or len(cleaned) > 120:
            raise ValueError('Delivery destination must be 3-120 characters')
        return cleaned

    @model_validator(mode='after')
    def no_duplicate_lines(self):
        keys = [(item.product_id, item.size) for item in self.items]
        if len(keys) != len(set(keys)):
            raise ValueError('Combine duplicate product/size lines')
        return self


class OrderItemResponse(BaseModel):
    product_id: str
    product_name: str
    size: str
    quantity: int
    unit_price_ngn: int
    line_total_ngn: int


class OrderResponse(BaseModel):
    id: str
    status: str
    total_ngn: int
    created_at: datetime
    reserved_until: datetime | None = None
    delivery_destination: str | None = None
    shipping_quote_ngn: int | None = None
    estimated_total_ngn: int | None = None
    shipping_quoted_at: datetime | None = None
    items: list[OrderItemResponse]


class AdminProductResponse(ProductResponse):
    is_active: bool


class AdminProductUpdateRequest(BaseModel):
    """Editable catalog fields; images remain controlled by deployed assets."""
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=2, max_length=150)
    category: str = Field(min_length=2, max_length=50)
    description: str = Field(min_length=5, max_length=2000)
    price_ngn: int = Field(ge=100, le=10_000_000, strict=True)
    is_active: bool

    @field_validator('name', 'category', 'description')
    @classmethod
    def normalise_text(cls, value: str, info) -> str:
        cleaned = ' '.join(value.split())
        min_length = 5 if info.field_name == 'description' else 2
        if len(cleaned) < min_length:
            raise ValueError('Field is too short after removing whitespace')
        return cleaned


class AdminProductCreateRequest(BaseModel):
    """Create a catalog entry from staff input; image must already be hosted."""
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=2, max_length=150)
    category: str = Field(min_length=2, max_length=50)
    description: str = Field(min_length=5, max_length=2000)
    price_ngn: int = Field(ge=100, le=10_000_000, strict=True)
    image_url: str = Field(min_length=12, max_length=300)
    is_active: bool = False
    stock_by_size: dict[str, int] = Field(default_factory=dict)

    @field_validator('name', 'category', 'description')
    @classmethod
    def strip_text(cls, value: str, info) -> str:
        cleaned = ' '.join(value.split())
        required = 5 if info.field_name == 'description' else 2
        if len(cleaned) < required:
            raise ValueError('Enter meaningful product information')
        return cleaned

    @field_validator('image_url')
    @classmethod
    def validate_image_url(cls, value: str) -> str:
        try:
            parts = urlsplit(value)
            host = parts.hostname
            if parts.scheme != 'https' or not host or parts.username or parts.password:
                raise ValueError()
            if parts.port not in (None, 443) or parts.fragment:
                raise ValueError()
            if host.lower() == 'localhost' or host.lower().endswith(('.local', '.internal')):
                raise ValueError()
            try:
                address = ipaddress.ip_address(host)
                if not address.is_global:
                    raise ValueError()
            except ValueError as error:
                # An invalid/private IP literal must be rejected; domain names are fine.
                if all(c in '0123456789.:' for c in host):
                    raise ValueError() from error
            if not parts.path.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                raise ValueError()
        except (ValueError, TypeError):
            raise ValueError('Use a public HTTPS image URL ending in .jpg, .jpeg, .png or .webp')
        return value

    @field_validator('stock_by_size')
    @classmethod
    def validate_stock(cls, values: dict[str, int]) -> dict[str, int]:
        if not set(values).issubset(SIZES):
            raise ValueError('Invalid cap size')
        if any(type(quantity) is not int or quantity < 0 or quantity > 100000 for quantity in values.values()):
            raise ValueError('Stock must be a whole number between 0 and 100000')
        return values


class StockUpdateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    available_quantity: int = Field(ge=0, le=100000, strict=True)
    reason: Literal['restock', 'correction', 'damage', 'other'] = 'correction'


class StockLevelResponse(BaseModel):
    product_id: str
    size: str
    available_quantity: int


class LowStockAlertResponse(BaseModel):
    product_id: str
    product_name: str
    size: str
    available_quantity: int
    status: Literal['out', 'low']


class InventoryAlertsResponse(BaseModel):
    threshold: int
    out_of_stock: int
    low_stock: int
    alerts: list[LowStockAlertResponse]


class InventoryChangeResponse(BaseModel):
    id: str
    product_id: str
    product_name: str
    size: str
    previous_quantity: int
    new_quantity: int
    reason: str
    changed_by_name: str
    changed_at: datetime


class EnquiryFollowupRequest(BaseModel):
    """Private staff workflow; does not accept payment or order status fields."""
    model_config = ConfigDict(extra='forbid')
    stage: Literal['new', 'contacted', 'awaiting_reply', 'closed']
    internal_note: str = Field(max_length=1200)

    @field_validator('internal_note')
    @classmethod
    def validate_note(cls, value: str) -> str:
        note = value.strip()
        if any(ord(character) < 32 and character not in '\n\t' for character in note):
            raise ValueError('Unsupported control character in note')
        return note


class AdminOrderResponse(OrderResponse):
    user_id: str
    customer_name: str | None = None
    customer_email: EmailStr | None = None
    followup_stage: str = 'new'
    internal_note: str = ''
    followup_updated_at: datetime | None = None


class SaveItemRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    quantity: int = Field(ge=1, le=10, strict=True)


class SavedItemResponse(BaseModel):
    product_id: str
    product_name: str
    size: str
    quantity: int
    unit_price_ngn: int
    available_quantity: int


class DeliveryQuoteRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    shipping_amount_ngn: int = Field(ge=0, le=2_000_000, strict=True)


class AdminOverviewResponse(BaseModel):
    """Admin operations counts; no payment or revenue claims."""
    active_products: int
    available_units: int
    out_of_stock_variants: int
    total_enquiries: int
    unquoted_enquiries: int
    quoted_enquiries: int
    active_stock_holds: int
