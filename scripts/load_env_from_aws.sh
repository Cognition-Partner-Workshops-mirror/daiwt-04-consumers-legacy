#!/usr/bin/env bash
# Source this file to populate connection variables in the current shell.
_wwi_load_env() {
  local region="${AWS_REGION:-us-east-1}"
  local mssql_secret="${MSSQL_SECRET_NAME:-daiwt-02-sqlserver}"
  local retail_secret="${REDSHIFT_CONNECTION_SECRET_NAME:-daiwt-03-redshift-connection}"
  local exports
  exports=$(AWS_REGION="$region" MSSQL_SECRET_NAME="$mssql_secret" REDSHIFT_CONNECTION_SECRET_NAME="$retail_secret" python3 - <<'PY'
import json
import os
import shlex
import boto3

client = boto3.client('secretsmanager', region_name=os.environ['AWS_REGION'])
def secret(name):
    response = client.get_secret_value(SecretId=name)
    return json.loads(response['SecretString']), response['ARN']
sql, _ = secret(os.environ['MSSQL_SECRET_NAME'])
retail, arn = secret(os.environ['REDSHIFT_CONNECTION_SECRET_NAME'])
def pick(mapping, *keys, default=None):
    for key in keys:
        if mapping.get(key) is not None:
            return mapping[key]
    if default is not None:
        return default
    raise ValueError('Connection secret is missing required field: ' + keys[0])
values = {
    'AWS_REGION': os.environ['AWS_REGION'],
    'MSSQL_HOST': os.getenv('MSSQL_HOST') or pick(sql, 'host', 'hostname', 'server', default='daiwt-02-sqlserver.c0x4mes64o5e.us-east-1.rds.amazonaws.com'),
    'MSSQL_PORT': pick(sql, 'port', default='1433'),
    'MSSQL_USER': pick(sql, 'username', 'user'),
    'MSSQL_PASSWORD': pick(sql, 'password'),
    'MSSQL_DB': os.getenv('MSSQL_DB', 'WideWorldImportersDW'),
    'REDSHIFT_SECRET_ARN': pick(retail, 'secret_arn', 'secretArn', default=arn),
    'REDSHIFT_WORKGROUP': pick(retail, 'workgroup', 'workgroup_name', 'workgroupName'),
    'REDSHIFT_DATABASE': pick(retail, 'database', 'dbname', 'database_name'),
}
for name, value in values.items():
    print('export ' + name + '=' + shlex.quote(str(value)))
PY
  ) || return
  eval "$exports"
}
_wwi_load_env
_wwi_status=$?
unset -f _wwi_load_env
return "$_wwi_status" 2>/dev/null || exit "$_wwi_status"
