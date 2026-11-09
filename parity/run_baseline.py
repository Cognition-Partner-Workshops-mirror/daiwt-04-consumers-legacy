"""Capture the reporting regression baseline from read-only sources."""
import argparse
import csv
import hashlib
import io
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import boto3
import yaml
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from consumers.api import db
from consumers.api.main import app


def redshift_rows(sql):
    client = boto3.client('redshift-data', region_name=os.getenv('AWS_REGION', 'us-east-1'))
    statement = client.execute_statement(
        SecretArn=os.environ['REDSHIFT_SECRET_ARN'], WorkgroupName=os.environ['REDSHIFT_WORKGROUP'],
        Database=os.environ['REDSHIFT_DATABASE'], Sql=sql)['Id']
    deadline = time.monotonic() + 300
    while True:
        status = client.describe_statement(Id=statement)
        if status['Status'] == 'FINISHED':
            break
        if status['Status'] in ('FAILED', 'ABORTED'):
            raise RuntimeError(status.get('Error', status['Status']))
        if time.monotonic() > deadline:
            raise TimeoutError('Redshift statement exceeded five minutes')
        time.sleep(1)
    rows = []
    for page in client.get_paginator('get_statement_result').paginate(Id=statement):
        columns = [col['name'] for col in page['ColumnMetadata']]
        for record in page['Records']:
            values = [None if cell.get('isNull') else next(iter(cell.values())) for cell in record]
            rows.append(dict(zip(columns, values)))
    return rows


def text_value(value):
    if value is None:
        return ''
    if isinstance(value, Decimal):
        return format(value, 'f')
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value)


def canonical_rows(rows, keys):
    def key_value(value):
        if value is None:
            return (0, '')
        if isinstance(value, (int, float, Decimal)):
            return (1, Decimal(str(value)))
        return (2, text_value(value))
    return sorted(rows, key=lambda row: tuple(key_value(row[k]) for k in keys)
                  + tuple((row[k] is not None, text_value(row[k])) for k in sorted(row)))


def csv_bytes(rows, keys):
    output = io.StringIO(newline='')
    columns = sorted(rows[0]) if rows else keys
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator='\n')
    writer.writeheader()
    writer.writerows({key: text_value(value) for key, value in row.items()}
                     for row in canonical_rows(rows, keys))
    return output.getvalue().encode('utf-8')


def capture(spec, destination):
    destination.mkdir(parents=True, exist_ok=True)
    manifest = {'captured_at': datetime.now(timezone.utc).isoformat(), 'entries': []}
    with TestClient(app) as api:
        for item in spec['entries']:
            if not re.fullmatch(r'[a-z0-9_]+', item['id']):
                raise ValueError('Invalid report identifier')
            sql = item['sql'].strip()
            if not sql.upper().startswith('SELECT ') or ';' in sql:
                raise ValueError('Only a single SELECT is supported')
            rows = db.fetch(sql) if item['source'] == 'mssql' else redshift_rows(sql)
            data = csv_bytes(rows, item['keys'])
            file = destination / (item['id'] + '.csv')
            file.write_bytes(data)
            record = {'id': item['id'], 'source': item['source'], 'row_count': len(rows),
                      'captured_at': manifest['captured_at'], 'sha256': hashlib.sha256(data).hexdigest(),
                      'file': file.name}
            if item['kind'] == 'endpoint':
                params = {key: value for key, value in item['sample_params'].items()
                          if '{' + key + '}' not in item['path'] and key != 'customer_key'}
                response = api.get(item['path'], params=params)
                response.raise_for_status()
                payload = response.json()
                if isinstance(payload, list):
                    payload = canonical_rows(payload, item['keys'])
                body = (json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + '\n').encode()
                json_file = destination / (item['id'] + '.json')
                json_file.write_bytes(body)
                record['response_file'] = json_file.name
                record['response_sha256'] = hashlib.sha256(body).hexdigest()
            manifest['entries'].append(record)
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', type=Path, default=ROOT / 'parity/report_spec.yaml')
    args = parser.parse_args()
    result = capture(yaml.safe_load(args.spec.read_text()), ROOT / 'parity/baseline')
    print(f"Captured {len(result['entries'])} report entries")
