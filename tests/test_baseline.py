import hashlib
import json
from decimal import Decimal
from unittest.mock import MagicMock

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
    monkeypatch.setattr(baseline, 'mssql_rows', lambda sql, timeout: rows)
    monkeypatch.setattr(baseline, 'redshift_rows', lambda sql, timeout: rows)
    result = baseline.capture(spec(source=source), tmp_path)
    record = result['entries'][0]
    assert record['row_count'] == len(rows)
    assert record['sha256'] == hashlib.sha256((tmp_path / 'sample.csv').read_bytes()).hexdigest()
    assert json.loads((tmp_path / 'manifest.json').read_text()) == result


def test_endpoint_capture(monkeypatch, tmp_path):
    monkeypatch.setattr(baseline, 'mssql_rows', lambda sql, timeout: [{'value': 2}, {'value': 1}])
    monkeypatch.setattr(baseline.db, 'fetch', lambda sql, params=(): [{'value': 2}, {'value': 1}])
    result = baseline.capture(spec(kind='endpoint'), tmp_path)
    assert json.loads((tmp_path / 'sample.json').read_text()) == [{'value': 1}, {'value': 2}]
    assert result['entries'][0]['response_file'] == 'sample.json'


@pytest.mark.parametrize('source,expected', [('all', ['sql_entry', 'retail_entry']),
                                           ('mssql', ['sql_entry']), ('redshift', ['retail_entry'])])
def test_source_filter(monkeypatch, tmp_path, source, expected):
    mixed = {'entries': [dict(spec()['entries'][0], id='sql_entry'),
                         dict(spec(source='redshift')['entries'][0], id='retail_entry')]}
    calls = []
    def fetch(name):
        calls.append(name)
        return [{'value': 1}]
    monkeypatch.setattr(baseline, 'mssql_rows', lambda sql, timeout: fetch('sql_entry'))
    monkeypatch.setattr(baseline, 'redshift_rows', lambda sql, timeout: fetch('retail_entry'))
    result = baseline.capture(mixed, tmp_path, source=source)
    assert calls == expected
    assert [entry['id'] for entry in result['entries']] == expected
    assert result['source_filter'] == source
    assert sorted(p.stem for p in tmp_path.glob('*.csv')) == sorted(expected)


def test_source_filter_empty(monkeypatch, tmp_path):
    def unexpected(sql, timeout):
        pytest.fail('Excluded source was queried')
    monkeypatch.setattr(baseline, 'mssql_rows', unexpected)
    result = baseline.capture(spec(), tmp_path, source='redshift')
    assert result['entries'] == []
    assert not list(tmp_path.glob('*.csv'))


def test_source_filter_invalid(tmp_path):
    with pytest.raises(ValueError, match='Unknown baseline source'):
        baseline.capture(spec(), tmp_path, source='other')
    assert not (tmp_path / 'manifest.json').exists()


def test_query_timeout_invalid(tmp_path):
    with pytest.raises(ValueError, match='timeout must be positive'):
        baseline.capture(spec(), tmp_path, query_timeout=0)


def test_mssql_timeout_and_cleanup(monkeypatch):
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.description = [('value',)]
    cursor.fetchall.return_value = [(1,)]
    monkeypatch.setattr(baseline.db, 'connect', lambda: connection)
    assert baseline.mssql_rows('SELECT 1 AS value', 17) == [{'value': 1}]
    assert connection.timeout == 17
    cursor.close.assert_called_once()
    connection.close.assert_called_once()


def test_redshift_timeout_cancels(monkeypatch):
    client = MagicMock()
    client.execute_statement.return_value = {'Id': 'statement'}
    client.describe_statement.return_value = {'Status': 'STARTED'}
    monkeypatch.setattr(baseline.boto3, 'client', lambda *args, **kwargs: client)
    for name in ['REDSHIFT_SECRET_ARN', 'REDSHIFT_WORKGROUP', 'REDSHIFT_DATABASE']:
        monkeypatch.setenv(name, 'test-connection')
    ticks = iter([0, 2])
    monkeypatch.setattr(baseline.time, 'monotonic', lambda: next(ticks))
    with pytest.raises(TimeoutError, match='query timeout'):
        baseline.redshift_rows('SELECT 1', query_timeout=1)
    client.cancel_statement.assert_called_once_with(Id='statement')


def test_select_cte(monkeypatch, tmp_path):
    monkeypatch.setattr(baseline, 'mssql_rows', lambda sql, timeout: [{'value': 1}])
    result = baseline.capture(spec(sql='WITH values_cte AS (SELECT 1 AS value) SELECT value FROM values_cte'), tmp_path)
    assert result['entries'][0]['row_count'] == 1


def test_source_error(monkeypatch, tmp_path):
    def unavailable(sql, timeout):
        raise RuntimeError('unavailable')
    monkeypatch.setattr(baseline, 'mssql_rows', unavailable)
    with pytest.raises(RuntimeError, match='unavailable'):
        baseline.capture(spec(), tmp_path)
    assert not (tmp_path / 'manifest.json').exists()


@pytest.mark.parametrize('sql', ['DELETE FROM Fact.Sale', 'SELECT 1; SELECT 2', 'WITH x AS (SELECT 1 AS a) DELETE FROM Fact.Sale', 'SELECT * INTO changed FROM Fact.Sale'])
def test_reject_non_select(tmp_path, sql):
    with pytest.raises(ValueError, match='single SELECT'):
        baseline.capture(spec(sql=sql), tmp_path)
