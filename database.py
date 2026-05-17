import psycopg2
from dotenv import load_dotenv
import os
from psycopg2.extras import DictCursor,RealDictCursor

# Load environment variables from .env
load_dotenv()

# Fetch variables
DATABASE_URL = os.getenv("DATABASE_URL")

# Connect to the database
def sqldb():
    connection = psycopg2.connect(DATABASE_URL)
    return connection

def isitordered(itemid):
    with sqldb() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM orders WHERE item = %s",(itemid,))
        data = cur.fetchall()
    return data

def tickets():
    query = """
SELECT users.phone_number,
users.fullname,
orders.lotto_ticket
FROM orders JOIN users ON orders.ordered_by = users.id
"""
    with sqldb() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(query)
        ticketlist = cur.fetchall()
    clean_results = [dict(row) for row in ticketlist]
    return clean_results

def realWinners():
    query = """SELECT 
    u.fullname,
    u.phone_number,
    p.prize AS prize_name  -- Optional: grabs the prize name too while you're at it
FROM winner w
JOIN orders o ON w.user_ = o.lotto_ticket
JOIN users u ON o.ordered_by = u.id
JOIN prizes p ON w.prize = p.id; -- Optional: joins the prize table"""
    with sqldb() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(query)
        winners = cur.fetchall()
    clean_results = [dict(row) for row in winners]
    return clean_results

# print(realWinners())