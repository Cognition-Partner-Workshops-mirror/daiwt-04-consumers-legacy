import os
from unittest.mock import MagicMock
from datetime import date
from decimal import Decimal

import pyodbc
import pytest
from fastapi.testclient import TestClient

from consumers.api import db
from consumers.api import queries
from consumers.api.main import app

client = TestClient(app)


@pytest.fixture
def connection(monkeypatch):
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.description = [('sales',)]
    cursor.fetchall.return_value = [(12.5,)]
    monkeypatch.setattr(db, 'connect', lambda: conn)
    return conn, cursor


@pytest.mark.parametrize('path,params', [
    ('/customers/1/summary', (1,)), ('/kpis/monthly?year=2016', (2016, 2016)),
    ('/sales/by-territory?year=2016', (2016,)), ('/stock-items/top?limit=5', (5,)),
    ('/health', ()),
    ('/customers/7/orders?limit=3', (3, 7)),
])
def test_routes(connection, path, params):
    conn, cursor = connection
    response = client.get(path)
    assert response.status_code == 200
    assert cursor.execute.call_args.args[1:] == params
    cursor.close.assert_called_once()
    conn.close.assert_called_once()


@pytest.mark.parametrize('path', ['/kpis/monthly', '/sales/by-territory', '/stock-items/top', '/customers/1/orders'])
def test_empty(connection, path):
    connection[1].fetchall.return_value = []
    assert client.get(path).json() == []


def test_missing_customer(connection):
    connection[1].fetchall.return_value = []
    assert client.get('/customers/1/summary').status_code == 404


def test_customer_orders_payload_and_default_limit(connection):
    _, cursor = connection
    cursor.description = [(name,) for name in ['order_id', 'order_date', 'order_value', 'quantity', 'unpicked_lines']]
    cursor.fetchall.return_value = [(42, date(2016, 5, 1), Decimal('125.50'), 8, 1)]
    response = client.get('/customers/7/orders')
    assert response.status_code == 200
    assert response.json() == [{'order_id': 42, 'order_date': '2016-05-01', 'order_value': 125.5,
                                'quantity': 8, 'unpicked_lines': 1}]
    cursor.execute.assert_called_once_with(queries.CUSTOMER_ORDERS, 20, 7)
    assert 'GROUP BY [WWI Order ID], [Order Date Key]' in queries.CUSTOMER_ORDERS
    assert 'ORDER BY order_date DESC, order_id DESC' in queries.CUSTOMER_ORDERS


@pytest.mark.parametrize('path', ['/customers/1/summary', '/kpis/monthly', '/sales/by-territory', '/stock-items/top', '/health', '/customers/1/orders'])
def test_unavailable(connection, path):
    connection[1].execute.side_effect = pyodbc.OperationalError('private connection detail')
    response = client.get(path)
    assert response.status_code == 503
    assert 'private' not in response.text


@pytest.mark.parametrize('path', ['/customers/0/summary', '/kpis/monthly?year=9999', '/sales/by-territory?year=no', '/stock-items/top?limit=101', '/customers/0/orders', '/customers/1/orders?limit=0', '/customers/1/orders?limit=101', '/customers/1/orders?limit=no'])
def test_invalid(path):
    assert client.get(path).status_code == 422


@pytest.mark.contract
@pytest.mark.skipif(not os.getenv('MSSQL_HOST'), reason='MSSQL_HOST not set')
def test_live_contract():
    assert client.get('/health').json() == {'status': 'ok'}
    for path in ['/kpis/monthly?year=2016', '/sales/by-territory?year=2016', '/stock-items/top?limit=1', '/customers/1/orders?limit=1']:
        response = client.get(path)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
