#!/bin/sh
set -eu

# 由官方 PostgreSQL 镜像在新数据目录首次初始化时运行。
# psql 从环境读取口令，避免放入 SQL 文件或进程参数。
psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 <<'SQL'
\getenv app_password MT_DATABASE_PASSWORD
CREATE ROLE model_platform LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'app_password';
CREATE DATABASE model_platform OWNER model_platform;
SQL
