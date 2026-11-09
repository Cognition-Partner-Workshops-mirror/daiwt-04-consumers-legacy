import os
from unittest.mock import MagicMock

import pyodbc
import pytest
from fastapi.testclient import TestClient

from consumers.api import db
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
])
def test_routes(connection, path, params):
    conn, cursor = connection
    response = client.get(path)
    assert response.status_code == 200
    assert cursor.execute.call_args.args[1:] == params
    cursor.close.assert_called_once()
    conn.close.assert_called_once()


@pytest.mark.parametrize('path', ['/kpis/monthly', '/sales/by-territory', '/stock-items/top'])
def test_empty(connection, path):
    connection[1].fetchall.return_value = []
    assert client.get(path).json() == []


def test_missing_customer(connection):
    connection[1].fetchall.return_value = []
    assert client.get('/customers/1/summary').status_code == 404


@pytest.mark.parametrize('path', ['/customers/1/summary', '/kpis/monthly', '/sales/by-territory', '/stock-items/top', '/health'])
def test_unavailable(connection, path):
    connection[1].execute.side_effect = pyodbc.OperationalError('private connection detail')
    response = client.get(path)
    assert response.status_code == 503
    assert 'private' not in response.text


@pytest.mark.parametrize('path', ['/customers/0/summary', '/kpis/monthly?year=9999', '/sales/by-territory?year=no', '/stock-items/top?limit=101'])
def test_invalid(path):
    assert client.get(path).status_code == 422


@pytest.mark.contract
@pytest.mark.skipif(not os.getenv('MSSQL_HOST'), reason='MSSQL_HOST not set')
def test_live_contract():
    assert client.get('/health').json() == {'status': 'ok'}
    for path in ['/kpis/monthly?year=2016', '/sales/by-territory?year=2016', '/stock-items/top?limit=1']:
        response = client.get(path)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
