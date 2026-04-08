import sqlite3, random, time
conn = sqlite3.connect('nids.db')
c = conn.cursor()
# Add 100 fake entries
for i in range(100):
    c.execute("INSERT INTO predictions (ts, src_ip, dst_ip, attack_score, label, true_label, reason) VALUES (?, ?, ?, ?, ?, ?, ?)", 
              (time.time(), f"192.168.1.{random.randint(10,50)}", "10.0.0.1", random.random(), random.randint(0,1), random.randint(0,1), "Simulated"))
conn.commit()
print("Data Added!")