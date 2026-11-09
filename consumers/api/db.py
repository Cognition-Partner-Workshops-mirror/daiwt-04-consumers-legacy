import os
from contextlib import closing

import pyodbc


def connect():
    def escaped(value):
        return '{' + str(value).replace('}', '}}') + '}'
    values = {
        'DRIVER': 'ODBC Driver 18 for SQL Server',
        'SERVER': f"{os.environ['MSSQL_HOST']},{os.getenv('MSSQL_PORT', '1433')}",
        'DATABASE': os.getenv('MSSQL_DB', 'WideWorldImportersDW'),
        'UID': os.environ['MSSQL_USER'], 'PWD': os.environ['MSSQL_PASSWORD'],
        'Encrypt': 'yes', 'TrustServerCertificate': 'no', 'ApplicationIntent': 'ReadOnly',
    }
    return pyodbc.connect(';'.join(f'{k}={escaped(v)}' for k, v in values.items()), timeout=15)


def fetch(sql, params=()):
    with closing(connect()) as connection, closing(connection.cursor()) as cursor:
        cursor.execute(sql, *params)
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
