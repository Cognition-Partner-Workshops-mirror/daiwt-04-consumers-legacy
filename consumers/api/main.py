import pyodbc
from fastapi import FastAPI, HTTPException, Path, Query

from . import db, queries

app = FastAPI(title='Wide World Importers customer & KPI reporting API')


def execute(sql, params=()):
    try:
        return db.fetch(sql, params)
    except (pyodbc.Error, KeyError):
        raise HTTPException(503, 'Reporting database unavailable') from None


@app.get('/health')
def health():
    execute('SELECT 1 AS available')
    return {'status': 'ok'}


@app.get('/customers/{customer_key}/summary')
def customer_summary(customer_key: int = Path(ge=1)):
    rows = execute(queries.CUSTOMER, (customer_key,))
    if not rows:
        raise HTTPException(404, 'No sales for customer')
    return rows[0]


@app.get('/kpis/monthly')
def monthly(year: int = Query(2016, ge=1900, le=9998)):
    return execute(queries.MONTHLY, (year, year))


@app.get('/sales/by-territory')
def territory(year: int = Query(2016, ge=1900, le=9998)):
    return execute(queries.TERRITORY, (year,))


@app.get('/stock-items/top')
def top_items(limit: int = Query(10, ge=1, le=100)):
    return execute(queries.TOP_ITEMS, (limit,))


@app.get('/customers/{customer_key}/orders')
def customer_orders(customer_key: int = Path(ge=1), limit: int = Query(20, ge=1, le=100)):
    return execute(queries.CUSTOMER_ORDERS, (limit, customer_key))
