-- The same fixture on Postgres, so the discovery loop can be exercised on both engines.
-- Idempotent: drops what it creates first.
--
--   docker compose up -d --wait
--   PGPASSWORD=postgres psql -h 127.0.0.1 -p 55432 -U postgres -d postgres \
--     -c 'CREATE DATABASE semantiql_workspace'
--   PGPASSWORD=postgres psql -h 127.0.0.1 -p 55432 -U postgres -d semantiql_workspace -f seed.sql
--
-- Its OWN database, never `semantiql_test`. That one belongs to the `pg` suite, whose fixtures drop
-- and recreate tables between runs, and this file's `DROP SCHEMA staging CASCADE` is exactly the kind
-- of statement that reaches further than intended. Seeding into it also buried this fixture's four
-- relations among the suite's five, which quietly changes what the discovery loop is being asked to
-- model. Both were observed before this comment existed.
--
-- Kept as SQL rather than folded into build.py because it also serves as the thing you hand a DBA
-- who asks what the test fixture actually is.

DROP VIEW IF EXISTS order_totals;
DROP TABLE IF EXISTS order_lines;
DROP TABLE IF EXISTS customers;
DROP SCHEMA IF EXISTS staging CASCADE;

CREATE TABLE order_lines (
    line_id          bigint,
    order_id         bigint,
    customer_email   text,
    placed_at        timestamptz,
    channel          text,
    quantity         integer,
    unit_price       numeric(10, 2),
    gross_amount     numeric(10, 2),
    discount_amount  numeric(10, 2),
    refund_amount    numeric(10, 2),
    net_amount       numeric(10, 2)
);

INSERT INTO order_lines VALUES
    (1, 100, 'ana@example.com', '2026-07-01 10:00:00+00', 'web',   2, 10.00, 20.00, 2.00,  0.00, 18.00),
    (2, 100, 'ana@example.com', '2026-07-01 10:00:00+00', 'web',   1, 30.00, 30.00, 0.00, 30.00,  0.00),
    (3, 101, 'bo@example.com',  '2026-07-31 23:30:00+00', 'store', 3,  5.00, 15.00, 0.00,  0.00, 15.00),
    (4, 102, 'cy@example.com',  '2026-08-05 09:00:00+00', 'web',   1, 40.00, 40.00, 4.00,  0.00, 36.00),
    (5, 102, 'cy@example.com',  '2026-08-05 09:00:00+00', 'web',   2, 12.50, 25.00, 0.00, 25.00,  0.00);

CREATE TABLE customers (
    customer_email  text,
    country         text,
    signed_up_at    date,
    plan            text
);

INSERT INTO customers VALUES
    ('ana@example.com', 'US', '2026-01-15', 'pro'),
    ('bo@example.com',  'TH', '2026-03-02', 'free'),
    ('cy@example.com',  'US', '2026-06-20', 'pro');

CREATE VIEW order_totals AS
SELECT order_id,
       MIN(placed_at)  AS placed_at,
       MIN(channel)    AS channel,
       SUM(net_amount) AS net_amount,
       COUNT(*)        AS line_count
FROM order_lines
GROUP BY order_id;

CREATE SCHEMA staging;
CREATE TABLE staging.raw_events (payload text);

-- Ground truth, so a mis-seeded database is loud rather than subtly wrong.
DO $$
DECLARE gross numeric; net numeric; orders bigint;
BEGIN
    SELECT SUM(gross_amount), SUM(net_amount), COUNT(DISTINCT order_id)
      INTO gross, net, orders FROM order_lines;
    ASSERT gross = 130.00, 'gross should be 130.00, got ' || gross;
    ASSERT net = 69.00,    'net should be 69.00, got ' || net;
    ASSERT orders = 3,     'distinct orders should be 3, got ' || orders;
END $$;
