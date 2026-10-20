"""Local operator-only admin role bootstrap. Run only with authorized DB access.

  python -m app.admin grant --email operator@example.com
  python -m app.admin revoke --email operator@example.com

Requires an existing registered user. No public self-promotion endpoint exists.
"""
import argparse
from sqlalchemy import select
from .database import SessionLocal
from .models import User


def main():
    parser = argparse.ArgumentParser(description='Local admin operator access')
    parser.add_argument('action', choices=('grant', 'revoke'))
    parser.add_argument('--email', required=True)
    args = parser.parse_args()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == args.email.strip().lower()))
        if user is None:
            parser.error('Email not registered; register the operator first')
        if not user.is_active:
            parser.error('Cannot change administrative rights on an inactive account')
        user.is_admin = args.action == 'grant'
        db.commit()
        print(f'Administrator access {"granted to" if user.is_admin else "revoked from"} {user.email}')


if __name__ == '__main__':
    main()
