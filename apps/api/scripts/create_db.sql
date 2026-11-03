-- Creates the VYSEL role and database. Idempotent: safe to re-run (also resets the password).
-- Run as a PostgreSQL superuser, passing the app password as a psql variable:
--
--   psql -h localhost -U postgres -d postgres -v ON_ERROR_STOP=1 -v app_password='...' -f apps/api/scripts/create_db.sql
--
-- Then put the same password in apps/api/.env (DATABASE_URL).

SELECT format('CREATE ROLE vysel LOGIN PASSWORD %L', :'app_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'vysel') \gexec

SELECT format('ALTER ROLE vysel WITH LOGIN PASSWORD %L', :'app_password') \gexec

SELECT 'CREATE DATABASE vysel OWNER vysel ENCODING ''UTF8'' TEMPLATE template0'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'vysel') \gexec

-- PostgreSQL 15: the public schema belongs to the database owner, so vysel can create tables.
SELECT 'db=' || datname || ' owner=' || pg_get_userbyid(datdba) AS result FROM pg_database WHERE datname = 'vysel';
