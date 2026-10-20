"""Local operator-only inventory CLI; no public stock mutation endpoint.

  python -m app.inventory show
  python -m app.inventory set premium 39 5

Only run by an authorized operator with database access. Stock is NOT reserved by drafts.
"""
import argparse
from sqlalchemy import select
from .database import SessionLocal
from .models import Product, ProductInventory

SIZES = ('32', '35', '39', '41')


def main():
    parser = argparse.ArgumentParser(description='FÌLÀ local stock manager')
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('show', help='List all stock quantities, including zero')
    set_cmd = sub.add_parser('set', help='Set the physically verified stock level')
    set_cmd.add_argument('product_id')
    set_cmd.add_argument('size', choices=SIZES)
    set_cmd.add_argument('quantity', type=int)
    args = parser.parse_args()
    with SessionLocal() as db:
        if args.action == 'show':
            rows = db.execute(select(ProductInventory.product_id, ProductInventory.size,
                                     ProductInventory.quantity).order_by(ProductInventory.product_id,
                                                                        ProductInventory.size)).all()
            for product_id, size, count in rows:
                print(f'{product_id:14} size {size}: {count}')
            if not rows:
                print('No stock rows found. Run migrations and python -m app.seed.')
        elif args.action == 'set':
            if args.quantity < 0 or args.quantity > 100000:
                parser.error('quantity must be between 0 and 100000')
            if db.get(Product, args.product_id) is None:
                parser.error('unknown product ID')
            record = db.get(ProductInventory, (args.product_id, args.size))
            if record is None:
                record = ProductInventory(product_id=args.product_id, size=args.size, quantity=0)
                db.add(record)
            record.quantity = args.quantity
            db.commit()
            print(f'Stock updated: {args.product_id} size {args.size} = {args.quantity}')


if __name__ == '__main__':
    main()
