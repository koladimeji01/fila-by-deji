from datetime import datetime
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


class ProductResponse(BaseModel):
    id: str
    name: str
    category: str
    description: str
    price_ngn: int
    image_url: str
    # Only sizes with positive stock are advertised as available.
    available_sizes: list[str] = Field(default_factory=list)


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
    items: list[OrderItemResponse]
