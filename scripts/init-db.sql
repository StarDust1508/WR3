-- wr3 Postgres init script
-- Runs once on first container start (data volume must be empty)

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Audit roles for least-privilege (used in prod, dev runs as wr3 superuser)
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'wr3_app') THEN
    CREATE ROLE wr3_app LOGIN PASSWORD 'wr3_app';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'wr3_readonly') THEN
    CREATE ROLE wr3_readonly LOGIN PASSWORD 'wr3_readonly';
  END IF;
END$$;

GRANT CONNECT ON DATABASE wr3 TO wr3_app, wr3_readonly;
