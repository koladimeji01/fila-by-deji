"""Stage 8: accurate, private date-scoped operational analytics (never revenue)."""
import csv
import io
from datetime import timedelta
from zoneinfo import ZoneInfo
from datetime import datetime
from app.database import SessionLocal
from app.models import Order, User
from app import main as app_main


def approved_staff(client, auth):
    headers = auth(client)
    with SessionLocal() as db:
        db.query(User).filter_by(email='ada@example.com').one().is_admin = True
        db.commit()
    return headers


def create_selection(client, headers, quantity=2):
    response = client.post('/api/v1/orders/drafts', headers=headers, json={
        'items':[{'product_id':'premium','size':'39','quantity':quantity}],
        'delivery_destination':'Ikeja, Lagos',
    })
    assert response.status_code == 201,response.text
    return response.json()['id']


def test_reports_enforce_admin_access_and_day_choices(client,auth):
    h = auth(client)
    endpoint='/api/v1/admin/reports'
    assert client.get(endpoint).status_code==401
    assert client.get(endpoint,headers=h).status_code==403
    assert client.get(endpoint+'/export',headers=h).status_code==403
    with SessionLocal() as db:
        db.query(User).filter_by(email='ada@example.com').one().is_admin=True
        db.commit()
    for days in ('0','6','31','91','365','abc'):
        assert client.get(endpoint+'?days='+days,headers=h).status_code==422
        assert client.get(endpoint+'/export?days='+days,headers=h).status_code==422
    good=client.get(endpoint+'?days=7',headers=h)
    assert good.status_code==200
    result=good.json()
    assert result['days']==7 and len(result['daily'])==7
    assert result['timezone']=='Africa/Lagos'
    assert result['metrics']['enquiries']==0
    assert result['products']==[]
    assert 'revenue_ngn' not in str(result).lower()
    assert 'sales' not in result['metrics']


def test_reports_count_actual_unpaid_enquiries_and_product_demand(client,auth):
    headers=approved_staff(client,auth)
    ref=create_selection(client,headers,2)
    create_selection(client,headers,1)
    quote=client.put('/api/v1/admin/orders/'+ref+'/delivery-quote',headers=headers,
                     json={'shipping_amount_ngn':2500})
    assert quote.status_code==200,quote.text
    report=client.get('/api/v1/admin/reports?days=30',headers=headers)
    assert report.status_code==200,report.text
    data=report.json()
    assert data['truncated'] is False
    assert data['analyzed_entries']==2
    assert data['metrics']['enquiries']==2
    assert data['metrics']['selected_units']==3
    assert data['metrics']['unique_customers']==1
    assert data['metrics']['quoted']==1
    assert data['metrics']['drafts']==2
    assert len(data['daily'])==30
    assert sum(day['enquiries'] for day in data['daily'])==2
    assert sum(day['selected_units'] for day in data['daily'])==3
    product=next(x for x in data['products'] if x['product_id']=='premium')
    assert product['selected_units']==3 and product['enquiries']==2
    assert 'income' not in data['metrics'] and 'revenue' not in data['metrics']


def test_report_windows_use_lagos_calendar_and_include_last_day(client,auth):
    headers=approved_staff(client,auth)
    oid=create_selection(client,headers)
    today=datetime.now(ZoneInfo('Africa/Lagos')).date()
    with SessionLocal() as db:
        order=db.get(Order,oid)
        # 15 calendar days old, stored in UTC
        local_dt=datetime.combine(today-timedelta(days=15),datetime.min.time(),
                                  tzinfo=ZoneInfo('Africa/Lagos')).replace(hour=14)
        order.created_at=local_dt
        db.commit()
    short=client.get('/api/v1/admin/reports?days=7',headers=headers).json()
    long=client.get('/api/v1/admin/reports?days=30',headers=headers).json()
    assert short['metrics']['enquiries']==0
    assert long['metrics']['enquiries']==1
    assert long['start_date']==(today-timedelta(days=29)).isoformat()
    assert long['end_date']==today.isoformat()
    assert sum(day['enquiries'] for day in long['daily'])==1


def test_full_period_csv_is_private_formula_safe_and_excludes_staff_notes(client,auth):
    headers=approved_staff(client,auth)
    oid=create_selection(client,headers)
    with SessionLocal() as db:
        user=db.query(User).filter_by(email='ada@example.com').one()
        user.name='=HYPERLINK("https://evil.invalid", "click")'
        db.commit()
    note=client.put('/api/v1/admin/orders/'+oid+'/followup',headers=headers,json={
        'stage':'contacted','internal_note':'Secret customer address note',
    })
    assert note.status_code==200
    result=client.get('/api/v1/admin/reports/export?days=7',headers=headers)
    assert result.status_code==200,result.text
    assert result.headers['content-type'].startswith('text/csv')
    assert 'attachment' in result.headers['content-disposition']
    assert result.headers['cache-control']=='no-store'
    assert result.content.startswith(b'\xef\xbb\xbf')
    records=list(csv.reader(io.StringIO(result.text.lstrip('\ufeff'))))
    assert len(records)==2
    assert records[1][1]==oid
    assert records[1][2].startswith("'=HYPERLINK")
    assert 'Secret customer address note' not in result.text
    assert 'payment_reference' not in result.text
    assert client.get('/api/v1/admin/reports/export').status_code==401


def test_truncated_windows_announce_partial_results_and_block_csv(client,auth,monkeypatch):
    headers=approved_staff(client,auth)
    create_selection(client,headers,1)
    create_selection(client,headers,2)
    monkeypatch.setattr(app_main,'REPORT_MAX_ORDERS',1)
    result=client.get('/api/v1/admin/reports?days=7',headers=headers).json()
    assert result['truncated'] is True
    assert result['analyzed_entries']==1
    assert result['metrics']['enquiries']==1
    block=client.get('/api/v1/admin/reports/export?days=7',headers=headers)
    assert block.status_code==409
    assert 'shorter period' in block.json()['detail'].lower()


def test_admin_analytics_frontend_has_period_switch_export_and_accessible_chart():
    from pathlib import Path
    root=Path(__file__).resolve().parents[2]
    html=(root/'admin-site'/'index.html').read_text(encoding='utf-8')
    js=(root/'admin-site'/'js'/'admin.js').read_text(encoding='utf-8')
    for item in ('admin-report-period','admin-report-refresh','admin-export-report',
                 'admin-report-chart','admin-report-chart-axis','admin-report-by-product'):
        assert 'id="'+item+'"' in html
    assert 'role="img"' in html
    assert "'/admin/reports?days='" in js
    assert "'/admin/reports/export?days='" in js
    assert "apiRequest('/admin/orders?limit=100" not in js
    assert 'new URLSearchParams' not in js
    assert 'renderReports(report)' in js
