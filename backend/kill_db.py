from sqlalchemy import create_engine, text
engine = create_engine('postgresql+psycopg://hawkeye:hawkeye@localhost:5432/postgres')
with engine.connect() as conn:
    conn.execute(text("""
        SELECT pg_terminate_backend(pg_stat_activity.pid)
        FROM pg_stat_activity
        WHERE pg_stat_activity.datname = 'hawkeye_test'
          AND pid <> pg_backend_pid();
    """))
    conn.commit()
