import os
import sys
from pathlib import Path

import pyodbc

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from consumers.api.db import fetch

if 'ODBC Driver 18 for SQL Server' not in pyodbc.drivers():
    raise SystemExit('Install Microsoft ODBC Driver 18 for SQL Server before connecting.')
print('ODBC Driver 18 for SQL Server available')
if not os.getenv('MSSQL_HOST'):
    raise SystemExit('Set MSSQL_HOST and credentials to run the connectivity check.')
assert fetch('SELECT 1 AS available') == [{'available': 1}]
print('SQL Server read-only connectivity check successful')
