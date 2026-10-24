"""Stage 9: admin-only stock alerts and append-only manual adjustment history."""
from app.database import SessionLocal
from app.models import Product, ProductInventory, InventoryChangeAudit, User


def authorize(client, auth):
    headers = auth(client)
    with SessionLocal() as db:
        db.query(User).filter_by(email='ada@example.com').one().is_admin = True
        db.commit()
    return headers


def test_alerts_are_admin_only_and_reflect_available_stock_not_sales(client,auth):
    normal=auth(client)
    alerts='/api/v1/admin/inventory/alerts'
    history='/api/v1/admin/inventory/changes'
    assert client.get(alerts).status_code==401
    assert client.get(alerts,headers=normal).status_code==403
    assert client.get(history).status_code==401
    assert client.get(history,headers=normal).status_code==403
    staff=normal  # The same session is checked against its current database role.
    with SessionLocal() as db:
        db.query(User).filter_by(email='ada@example.com').one().is_admin=True
        db.get(ProductInventory,('premium','39')).quantity=2
        db.get(ProductInventory,('classic','35')).quantity=0
        db.get(ProductInventory,('ceremonial','32')).quantity=5
        db.commit()
    result=client.get(alerts+'?threshold=3',headers=staff)
    assert result.status_code==200,result.text
    data=result.json()
    assert data['low_stock']==1 and data['out_of_stock']==1
    assert len(data['alerts'])==2
    assert data['alerts'][0]['status']=='out'
    assert {x['product_id'] for x in data['alerts']}=={'premium','classic'}
    larger=client.get(alerts+'?threshold=5',headers=staff).json()
    assert larger['low_stock']==2 and larger['out_of_stock']==1
    for value in ('0','26','-1','wat'):
        assert client.get(alerts+'?threshold='+value,headers=staff).status_code==422
    assert client.get(history+'?limit=101',headers=staff).status_code==422


def test_manual_stock_changes_have_staff_id_delta_and_reason(client,auth):
    staff=authorize(client,auth)
    address='/api/v1/admin/inventory/premium/39'
    old=client.get('/api/v1/admin/inventory',headers=staff).json()
    row=next(x for x in old if x['product_id']=='premium' and x['size']=='39')
    assert row['available_quantity']==8
    changed=client.put(address,headers=staff,json={'available_quantity':12,'reason':'restock'})
    assert changed.status_code==200,changed.text
    assert changed.json()['available_quantity']==12
    again=client.put(address,headers=staff,json={'available_quantity':12,'reason':'restock'})
    assert again.status_code==200
    changed2=client.put(address,headers=staff,json={'available_quantity':7,'reason':'damage'})
    assert changed2.status_code==200
    history=client.get('/api/v1/admin/inventory/changes',headers=staff)
    assert history.status_code==200
    assert len(history.json())==2
    newest=history.json()[0]
    assert newest['product_id']=='premium' and newest['size']=='39'
    assert newest['previous_quantity']==12 and newest['new_quantity']==7
    assert newest['reason']=='damage'
    assert newest['changed_by_name']=='Ada Example'
    assert newest['changed_at'] is not None
    with SessionLocal() as db:
        rows=db.query(InventoryChangeAudit).all()
        assert len(rows)==2
        assert sorted((e.previous_quantity,e.new_quantity) for e in rows)==[(8,12),(12,7)]
        assert all(e.changed_by for e in rows)
        assert db.get(ProductInventory,('premium','39')).quantity==7


def test_invalid_manual_adjustments_do_not_touch_stock_or_audit(client,auth):
    staff=authorize(client,auth)
    url='/api/v1/admin/inventory/classic/32'
    for data in (
        {'available_quantity':-1,'reason':'restock'},
        {'available_quantity':2.5,'reason':'restock'},
        {'available_quantity':True,'reason':'restock'},
        {'available_quantity':100001,'reason':'restock'},
        {'available_quantity':0,'reason':'refund'},
        {'available_quantity':0,'reason':'damage','is_admin':True},
    ):
        assert client.put(url,headers=staff,json=data).status_code==422
    with SessionLocal() as db:
        assert db.get(ProductInventory,('classic','32')).quantity==8
        assert db.query(InventoryChangeAudit).count()==0
    assert client.put('/api/v1/admin/inventory/unknown/32',headers=staff,json={
        'available_quantity':2
    }).status_code==404
    assert client.put('/api/v1/admin/inventory/premium/40',headers=staff,json={
        'available_quantity':2
    }).status_code==422


def test_archived_product_does_not_trigger_customer_availability_alert(client,auth):
    staff=authorize(client,auth)
    with SessionLocal() as db:
        db.get(Product,'premium').is_active=False
        db.get(ProductInventory,('premium','39')).quantity=0
        db.commit()
    data=client.get('/api/v1/admin/inventory/alerts?threshold=3',headers=staff).json()
    assert not any(a['product_id']=='premium' for a in data['alerts'])


def test_stock_reservations_do_not_create_fake_staff_change_events(client,auth):
    staff=authorize(client,auth)
    draft=client.post('/api/v1/orders/drafts',headers=staff,json={
        'items':[{'product_id':'premium','size':'39','quantity':1}]
    })
    assert draft.status_code==201,draft.text
    reserve=client.post('/api/v1/orders/'+draft.json()['id']+'/reserve',headers=staff)
    assert reserve.status_code==200,reserve.text
    with SessionLocal() as db:
        assert db.get(ProductInventory,('premium','39')).quantity==7
        assert db.query(InventoryChangeAudit).count()==0
    assert client.post('/api/v1/orders/'+draft.json()['id']+'/cancel',headers=staff).status_code==200
    with SessionLocal() as db:
        assert db.get(ProductInventory,('premium','39')).quantity==8
        assert db.query(InventoryChangeAudit).count()==0


def test_inventory_monitor_staff_ui_wiring():
    from pathlib import Path
    root=Path(__file__).resolve().parents[2]
    html=(root/'admin-site'/'index.html').read_text(encoding='utf-8')
    js=(root/'admin-site'/'js'/'admin.js').read_text(encoding='utf-8')
    for control in ('admin-stock-threshold','admin-inventory-refresh','admin-inventory-alerts-summary',
                    'admin-inventory-alerts-list','admin-inventory-history-list'):
        assert f'id="{control}"' in html
    assert "'/admin/inventory/alerts?threshold='" in js
    assert "'/admin/inventory/changes?limit=30'" in js
    assert "reason:reason.value" in js
    assert "loadStockMonitoring()" in js
    assert "body:{available_quantity:qty,reason:reason.value}" in js
