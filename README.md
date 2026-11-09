# Wide World Importers — analytics consumer handover

This repository contains the analytics team's reporting estate. SQL Server's
WideWorldImportersDW warehouse is the primary source. Connections use
`daiwt-02-sqlserver.c0x4mes64o5e.us-east-1.rds.amazonaws.com`. No data,
passwords or connection tokens are checked in. Database access is SELECT-only.

## Consumer inventory

| Consumer | Audience | Source tables | Refresh |
| --- | --- | --- | --- |
| Power BI: Sales Performance | Sales leadership | Fact.Sale; Dimension.Date, Customer, City, Stock Item | Import, 06:00 daily |
| Power BI: Order Fulfilment | Operations and regional managers | Fact.Order, Stock Holding; Dimension.Date, Customer, City, Stock Item | Import, 06:00 daily |
| Tableau: Regional Sales | Regional managers | Fact.Sale, Dimension.City, Customer | Extract, hourly |
| Tableau: Order Pipeline | Operations | Fact.Order | Extract, hourly |
| Tableau: Retail Channels | Retail leadership | Redshift core.orders | Extract, hourly |
| Customer & KPI reporting API | Customer portal | Fact.Sale, Order; Dimension.City, Stock Item | Live on each request |
| Monthly sales notebook and finance SQL | Finance analysts | Fact.Sale | Ad hoc |

The two PBIP projects include TMDL semantic definitions, M connection parameters,
native T-SQL fact partitions, dimension relationships, and report cards. The
Sales YoY card compares calendar 2016 with 2015; other cards show the unfiltered
warehouse. The Sales Analysis page breaks sales down by territory, calendar
month, top ten stock items, and buying group. A Sales Band calculated column
classifies invoice lines at a 1,000 value threshold. Order Fulfilment includes
stock-on-hand and below-reorder indicators from Fact.Stock Holding.
Financial ratios are fractions, not percentage points. Order counts
use distinct warehouse order IDs, not line counts. See `consumers/powerbi/NOTICE`
and `LICENSE` there for the upstream format attribution.

Each Tableau workbook contains three worksheets and an Overview dashboard with
all three sheets. Regional Sales covers territories, leading customers, and
regional targets; Order Pipeline covers monthly order value, unpicked lines,
and target coverage; Retail Channels covers channels, monthly trends, and
channel targets. Each retains a Target Value parameter and calculated fields
for Value vs Target, Above Target, and Share of Total. Regional Sales uses a
second Custom SQL datasource for its customer ranking.
SQL Server Custom SQL retains its native T-SQL syntax; the retail
workbook uses Redshift SQL. The retail datasource's logical server and database
must be mapped to the managed connection by the workbook publisher. Automated
query execution uses **only the Redshift Data API**, never a TCP connection.

## API

The Python service uses **pyodbc with Microsoft ODBC Driver 18 for SQL Server**.
Connections require encryption and validate the server certificate by default.
For a warehouse certificate that cannot be validated against the configured
hostname or trusted CA, explicitly export `MSSQL_TRUST_SERVER_CERTIFICATE=yes`.
This keeps traffic encrypted but disables server identity verification for the
API, notebook, connectivity check and baseline capture; leave it unset or set
to `no` when certificate validation is available. Power BI and Tableau use
their own client certificate settings.
Install the
driver on the host or build from the repository root with
`docker build -f consumers/api/Dockerfile -t wwi-reporting .`.
Supply credentials at runtime; do not include them in a build context or image.

| Endpoint | Result grain | Example |
| --- | --- | --- |
| `/customers/{customer_key}/summary` | One customer's invoiced sales, profit and invoice count | `/customers/1/summary` |
| `/customers/{customer_key}/orders?limit=` | Latest customer orders with value, quantity and unpicked lines; default 20, maximum 100 | `/customers/1/orders?limit=20` |
| `/kpis/monthly?year=` | Calendar month with sales | `/kpis/monthly?year=2016` |
| `/sales/by-territory?year=` | Territory | `/sales/by-territory?year=2016` |
| `/stock-items/top?limit=` | Stock item, ranked by sales | `/stock-items/top?limit=10` |
| `/health` | Database availability | `/health` |

No sales for a customer returns 404; list endpoints return an empty list for
empty result sets. Invalid parameters return 422, and unavailable connections
return a sanitized 503. Restrict access to the trusted internal reporting
network; the service does not provide end-user authorization.

## Setup / reset

Use Python 3.10 or newer. Install ODBC Driver 18, then:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
source scripts/load_env_from_aws.sh
make setup
make test
make api
```

Alternatively, set `MSSQL_HOST`, `MSSQL_PORT` (1433), `MSSQL_USER`,
`MSSQL_PASSWORD`, and `MSSQL_DB` (WideWorldImportersDW) yourself. The environment
loader reads two Secrets Manager secrets selected by `MSSQL_SECRET_NAME` and
`REDSHIFT_CONNECTION_SECRET_NAME`. `AWS_REGION` defaults to us-east-1. It exports
`REDSHIFT_SECRET_ARN`, `REDSHIFT_WORKGROUP`, and `REDSHIFT_DATABASE` for Data API
access. It does not write credentials to disk. Export `MSSQL_HOST` before sourcing
to override the host stored in the SQL secret. If the secret contains only
username/password, the host defaults to `daiwt-02-sqlserver.c0x4mes64o5e.us-east-1.rds.amazonaws.com`. `make setup` checks
warehouse connectivity.

`make test` runs offline tests using mocked connections. For live contract tests,
set the connection variables and run `.venv/bin/python -m pytest -m contract`.

## Report regression spec / baseline

`parity/report_spec.yaml` records each report card, DAX measure, Tableau sheet
and dashboard, endpoint, and analyst query, including equivalent source SQL,
grain, keys, and numeric tolerances. Tableau target calculations are also
specified at their worksheet grain. DAX equivalents describe the stated report
context rather than all possible interactive filters. The SQL is SELECT-only.

When both sources are available, `make baseline` captures deterministic,
key-sorted CSVs in `parity/baseline/`. Endpoint captures additionally call the
API in-process against the same live connection and save JSON responses. The
manifest contains row counts, source names, SHA-256 hashes and UTC capture
times. Capture stops on a failed source or endpoint; do not treat a partial run
as a complete baseline.

To capture a single source, run `.venv/bin/python parity/run_baseline.py --source
redshift` or use `--source mssql`. The default is `--source all`. Each run writes
a manifest for the selected source only; existing files for other sources are
left untouched. Capture timestamps change each run; data-file hashes can be
compared to check repeatability.

Captures execute entries sequentially with a 120-second per-query limit. Use
`--query-timeout 300` to select a different limit; timed-out Redshift statements
are cancelled through the Data API. The API and notebook use
`MSSQL_QUERY_TIMEOUT_SECONDS` (default 120). The manifest records `query_seconds`
for each source SELECT, excluding endpoint HTTP capture and file serialization.
The SQL Server regression queries use per-statement memory-grant bounds; they
do not alter database configuration or the consumer queries.

`make reset` (or `bash scripts/reset.sh`) restores tracked consumers and the
report spec from HEAD, removes prior capture files, and captures fresh baseline
files. This discards local tracked consumer/spec edits and requires working
live-source credentials. It never changes warehouse data.
