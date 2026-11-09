import hashlib
import json
from decimal import Decimal

import pytest

from parity import run_baseline as baseline


def spec(kind='tile', source='mssql', sql='SELECT 1 AS value'):
    return {'entries': [{'id': 'sample', 'source': source, 'kind': kind, 'sql': sql,
                         'keys': ['value'], 'path': '/stock-items/top', 'sample_params': {'limit': 2}}]}


def test_csv_deterministic():
    rows = [{'value': 10, 'amount': Decimal('2.00')}, {'value': 2, 'amount': None}]
    assert baseline.csv_bytes(rows, ['value']) == b'amount,value\n,2\n2.00,10\n'
    assert baseline.csv_bytes(rows[::-1], ['value']) == baseline.csv_bytes(rows, ['value'])
    assert baseline.csv_bytes([], ['value']) == b'value\n'


@pytest.mark.parametrize('source', ['mssql', 'redshift'])
@pytest.mark.parametrize('rows', [[], [{'value': 1}]])
def test_capture(monkeypatch, tmp_path, source, rows):
    monkeypatch.setattr(baseline.db, 'fetch', lambda sql: rows)
    monkeypatch.setattr(baseline, 'redshift_rows', lambda sql: rows)
    result = baseline.capture(spec(source=source), tmp_path)
    record = result['entries'][0]
    assert record['row_count'] == len(rows)
    assert record['sha256'] == hashlib.sha256((tmp_path / 'sample.csv').read_bytes()).hexdigest()
    assert json.loads((tmp_path / 'manifest.json').read_text()) == result


def test_endpoint_capture(monkeypatch, tmp_path):
    monkeypatch.setattr(baseline.db, 'fetch', lambda sql, params=(): [{'value': 2}, {'value': 1}])
    result = baseline.capture(spec(kind='endpoint'), tmp_path)
    assert json.loads((tmp_path / 'sample.json').read_text()) == [{'value': 1}, {'value': 2}]
    assert result['entries'][0]['response_file'] == 'sample.json'


def test_source_error(monkeypatch, tmp_path):
    def unavailable(sql):
        raise RuntimeError('unavailable')
    monkeypatch.setattr(baseline.db, 'fetch', unavailable)
    with pytest.raises(RuntimeError, match='unavailable'):
        baseline.capture(spec(), tmp_path)
    assert not (tmp_path / 'manifest.json').exists()


@pytest.mark.parametrize('sql', ['DELETE FROM Fact.Sale', 'SELECT 1; SELECT 2'])
def test_reject_non_select(tmp_path, sql):
    with pytest.raises(ValueError, match='single SELECT'):
        baseline.capture(spec(sql=sql), tmp_path)
