"""Idempotent seed for the three products in the supplied Figma design.

Run only after `alembic upgrade head`. Prices are examples, not verified stock.
"""
from sqlalchemy.orm import Session
from .database import SessionLocal
from .models import Product, ProductInventory

PRODUCTS = [
    ('ceremonial', 'Ceremonial Fila', 'Ceremonial',
     'Perfect for special occasions and cultural ceremonies.', 1_000_000, 'assets/ceremonial.jpg'),
    ('classic', 'Traditional Aso-oke Fila', 'Classic',
     'Handwoven with traditional Nigerian Aso-oke fabric in vibrant colours.', 1_000_000, 'assets/classic.jpg'),
    ('premium', 'Royal Agbada Cap', 'Premium',
     'Matching cap for royal Agbada with intricate embroidery.', 1_000_000, 'assets/premium.jpg'),
]


def seed_products(session: Session) -> None:
    for product_id, name, category, description, price_kobo, image_url in PRODUCTS:
        if session.get(Product, product_id) is None:
            session.add(Product(id=product_id, name=name, category=category,
                                description=description, price_kobo=price_kobo,
                                image_url=image_url, is_active=True))
    session.flush()
    for product_id, *_ in PRODUCTS:
        for size in ('32', '35', '39', '41'):
            if session.get(ProductInventory, (product_id, size)) is None:
                session.add(ProductInventory(product_id=product_id, size=size, quantity=0))
    session.commit()


if __name__ == '__main__':
    with SessionLocal() as session:
        seed_products(session)
    print('FÌLÀ seed products inserted (existing catalog entries preserved).')
