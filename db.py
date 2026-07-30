"""
db.py — persistent booking storage, replacing the ephemeral bookings.log file.
"""

import os
from dotenv import load_dotenv
load_dotenv()
import psycopg2
from psycopg2.extras import Json

DATABASE_URL = os.environ.get("DATABASE_URL")


def get_connection():
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is not set. Add it to .env locally and to Render's "
            "Environment tab (same pattern as STRIPE_SECRET_KEY)."
        )
    return psycopg2.connect(DATABASE_URL, sslmode="require")


def init_db():
    """Run once to create the bookings table if it doesn't exist yet."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bookings (
                    id SERIAL PRIMARY KEY,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    job_type TEXT,
                    urgency TEXT,
                    is_emergency TEXT,
                    summary TEXT,
                    suggested_action TEXT,
                    caller_number TEXT,
                    customer_name TEXT,
                    service_address TEXT,
                    business_name TEXT,
                    status TEXT NOT NULL DEFAULT 'booked',
                    raw_payload JSONB
                );
            """)
        conn.commit()
        print("bookings table ready.")
    finally:
        conn.close()


def save_booking(data: dict) -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO bookings
                    (job_type, urgency, is_emergency, summary, suggested_action,
                     caller_number, customer_name, service_address, business_name, raw_payload)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """, (
                data.get("job_type"),
                data.get("urgency"),
                str(data.get("is_emergency")),
                data.get("summary"),
                data.get("suggested_action"),
                data.get("caller_number") or "",
                data.get("customer_name") or "",
                data.get("service_address") or "",
                data.get("business_name") or "",
                Json(data),
            ))
            new_id = cur.fetchone()[0]
        conn.commit()
        return new_id
    finally:
        conn.close()


def list_bookings(limit: int = 50):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, created_at, job_type, urgency, is_emergency,
                       summary, caller_number, customer_name, service_address,
                       business_name, status
                FROM bookings
                ORDER BY created_at DESC
                LIMIT %s;
            """, (limit,))
            return cur.fetchall()
    finally:
        conn.close()
