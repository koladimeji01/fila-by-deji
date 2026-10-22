"""Static site regressions: never reference missing photographs or mismatched favicons."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
PAGES = sorted(ROOT.glob('*.html'))


def test_every_page_loads_site_script_and_styles():
    assert len(PAGES) == 11
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

def test_contact_uses_real_whatsapp_and_email_links_without_product_photo():
    page = (ROOT / 'contact.html').read_text(encoding='utf-8')
    script = (ROOT / 'js/app.js').read_text(encoding='utf-8')
    assert 'class="contact-image"' not in page
    assert 'Copy my enquiry' not in page
    assert 'mailto:filabydeji@gmail.com' in page
    assert 'tel:+234806722794' in page
    assert 'https://wa.me/234806722794' in page
    assert 'name="channel" value="email"' in page
    assert 'name="channel" value="whatsapp"' in page
    assert 'https://wa.me/234806722794?text=' in script
    assert 'mailto:filabydeji@gmail.com?subject=' in script


def test_vercel_deploys_only_storefront_assets():
    import json
    config = json.loads((ROOT / 'vercel.json').read_text())
    assert config['framework'] is None
    assert config['outputDirectory'] == 'dist'
    assert config['buildCommand'] == 'node scripts/build-storefront.cjs'
    builder = (ROOT / 'scripts/build-storefront.cjs').read_text()
    assert 'backend/' not in builder
    assert 'dist' in builder and 'index.html' in builder
    script = (ROOT / 'js/app.js').read_text()
    assert 'https://fila-by-deji-api.onrender.com/api/v1' in script
    assert "IS_LOCAL_PREVIEW" in script
    assert 'http://127.0.0.1:8000/api/v1' in script


def test_catalog_network_retries_only_safe_reads_and_never_overlays_home_navigation():
    script = (ROOT / 'js/app.js').read_text()
    css = (ROOT / 'css/style.css').read_text()
    assert "const attempts=method==='GET'?2:1" in script
    assert "attempt===0?65000:20000" in script
    assert "response.status>=500" in script
    assert "page==='home'?document.getElementById('home-products')" in script
    assert "if(grid)grid.before(el);else main.prepend(el)" in script
    assert "retry.textContent='Try again'" in script
    assert '.api-alert .button' in css


def test_normal_sign_in_returns_home_without_breaking_explicit_checkout_flow():
    script = (ROOT / 'js/app.js').read_text()
    assert "function safeNext(){const next=new URLSearchParams(location.search).get('next');" in script
    assert "['checkout.html','cart.html','index.html','collection.html','orders.html','profile.html'].includes(next)?next:'index.html';" in script
    assert "location.assign(next);" in script
    assert "location.assign('login.html?next=checkout.html')" in script


def test_profile_page_uses_real_authenticated_account_data():
    page = (ROOT / 'profile.html').read_text()
    script = (ROOT / 'js/app.js').read_text()
    assert 'data-page="profile"' in page
    for name in ('profile-avatar','profile-name','profile-email','profile-status','profile-signout'):
        assert f'id="{name}"' in page
    assert "apiRequest('/auth/me',{authorize:true})" in script
    assert "location.replace('login.html?next=profile.html')" in script
    assert "storeToken('');updateAuthNavigation();" in script
    assert "'profile.html'" in (ROOT / 'scripts/build-storefront.cjs').read_text()


def test_consistent_navigation_and_saved_for_later_copy():
    import re
    headers=[]
    for page in PAGES:
        content=page.read_text()
        match=re.search(r'<div class="header-inner wrap">.*?</header>',content,re.DOTALL)
        assert match, page.name
        headers.append(match.group(0))
        assert 'data-nav="orders">Saved for later</a>' in content, page.name
        assert 'class="account-link"' in content, page.name
        assert 'href="profile.html">My profile' in content, page.name
        visible_text=re.sub(r'<[^>]+>', ' ', content)
        assert not re.search(r'\\bdraft(s)?\\b', visible_text, re.I), page.name
    assert len(set(headers)) == 1


def test_save_for_later_moves_bag_items_locally_but_keeps_server_saved_selections():
    cart=(ROOT / 'cart.html').read_text()
    script=(ROOT / 'js/app.js').read_text()
    assert 'id="saved-local-items"' in cart
    assert 'Save for later' in cart
    assert 'SAVED_KEY=' in script and 'function saveBagItemForLater(' in script
    assert 'function moveSavedItemToBag(' in script
    assert "apiRequest('/orders/drafts'" in script
    assert "Save for later — no payment" in (ROOT / 'checkout.html').read_text()
