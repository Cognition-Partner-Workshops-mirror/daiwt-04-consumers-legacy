import os
from contextlib import closing

import pyodbc


def connect():
    trust_certificate = os.getenv('MSSQL_TRUST_SERVER_CERTIFICATE', 'no').lower()
    if trust_certificate not in ('yes', 'no'):
        raise ValueError('MSSQL_TRUST_SERVER_CERTIFICATE must be yes or no')
    def escaped(value):
        return '{' + str(value).replace('}', '}}') + '}'
    values = {
        'DRIVER': 'ODBC Driver 18 for SQL Server',
        'SERVER': f"{os.environ['MSSQL_HOST']},{os.getenv('MSSQL_PORT', '1433')}",
        'DATABASE': os.getenv('MSSQL_DB', 'WideWorldImportersDW'),
        'UID': os.environ['MSSQL_USER'], 'PWD': os.environ['MSSQL_PASSWORD'],
        'Encrypt': 'yes', 'TrustServerCertificate': trust_certificate, 'ApplicationIntent': 'ReadOnly',
    }
    query_timeout = int(os.getenv('MSSQL_QUERY_TIMEOUT_SECONDS', '120'))
    if query_timeout <= 0:
        raise ValueError('MSSQL_QUERY_TIMEOUT_SECONDS must be positive')
    connection = pyodbc.connect(';'.join(f'{k}={escaped(v)}' for k, v in values.items()), timeout=15)
    connection.timeout = query_timeout
    return connection


def fetch(sql, params=()):
    with closing(connect()) as connection, closing(connection.cursor()) as cursor:
        cursor.execute(sql, *params)
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
