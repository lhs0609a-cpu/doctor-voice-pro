#!/usr/bin/env python
"""Check database users"""
import sqlite3

conn = sqlite3.connect('/data/doctorvoice.db')
cursor = conn.cursor()
cursor.execute("SELECT email, is_admin FROM users")
rows = cursor.fetchall()
print("Users in database:")
for row in rows:
    print(f"  {row[0]} (admin={row[1]})")
conn.close()
