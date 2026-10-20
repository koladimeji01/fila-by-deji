"""Static site regressions: never reference missing photographs or mismatched favicons."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
PAGES = sorted(ROOT.glob('*.html'))


def test_every_page_loads_site_script_and_styles():
    assert len(PAGES) == 10
    for page in PAGES:
        markup = page.read_text(encoding='utf-8')
        assert 'href="css/style.css"' in markup, page.name
        assert 'src="js/app.js"' in markup, page.name
        assert '<main' in markup, page.name


def test_static_image_files_exist_and_have_correct_extension():
    for page in PAGES:
        markup = page.read_text(encoding='utf-8')
        for asset in re.findall(r'(?:src|href)="(assets/[^"?#]+)"', markup):
            assert (ROOT / asset).is_file(), f'{page.name} references missing {asset}'
        assert 'href="assets/fila-logo.png" type="image/png"' in markup, page.name


def test_stock_warning_and_checkout_controls_exist():
    cart = (ROOT / 'cart.html').read_text(encoding='utf-8')
    checkout = (ROOT / 'checkout.html').read_text(encoding='utf-8')
    assert 'id="bag-availability-notice"' in cart
    assert 'id="save-draft-order"' in checkout
    assert 'no payment' in checkout.lower()
