import sqlite3
conn = sqlite3.connect('/data/zeus.db')
conn.execute("UPDATE users SET subscription_plan='enterprise', subscription_status='active' WHERE email='dominic.rowle@yahoo.com'")
conn.commit()
print('Done')
conn.close()
