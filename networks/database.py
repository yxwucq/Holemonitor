from .config import config
import pandas as pd 
import sqlite3

class SQLDatabase(object):
    def __init__(self, database_name):
        self.database_name = database_name
        self.remove_exisited = config['Defaults']['remove_exisited'] == 'True'
        if self.remove_exisited and os.path.exists(database_name):
            os.remove(database_name)

    def create_holes_table(self):
        with sqlite3.connect(self.database_name) as conn:
            self.conn = sqlite3.connect(self.database_name)
            self.c = self.conn.cursor()
            self.c.execute(f'''CREATE TABLE IF NOT EXISTS holes
                        (pid INTEGER PRIMARY KEY,
                        text TEXT,
                        type TEXT,
                        time TEXT,
                        reply INTEGER,
                        likenum INTEGER,
                        last_retrive TEXT)''')
            self.conn.commit()
    
    def update_holes_data(self, data:pd.DataFrame):
        with sqlite3.connect(self.database_name) as conn:
            c = conn.cursor()
            for index, row in data.iterrows():
                pid = index
                text = row['text']
                dtype = row['type']
                time = str(row['time'])
                reply = row['reply']
                likenum = row['likenum']
                last_retrive = row['last_retrive']
                c.execute("SELECT * FROM holes WHERE pid=?", (pid,))
                result = c.fetchone()
                if result:
                    c.execute("UPDATE holes SET text=?, type=?, time=?, reply=?, likenum=?, last_retrive=? WHERE pid=?", (text, dtype, time, reply, likenum, last_retrive, pid))
                else:
                    c.execute("INSERT INTO holes (pid, text, type, time, reply, likenum, last_retrive) VALUES (?, ?, ?, ?, ?, ?, ?)", (pid, text, dtype, time, reply, likenum, last_retrive))
            conn.commit()

    def export_to_csv(self, table_name, filename):
        with sqlite3.connect(self.database_name) as conn:
            df = pd.read_sql_query(f"SELECT * from {table_name}", conn)
            df.to_csv(filename, index=True)
    
    def get_statistics(self, table_name:str): # holes or pages
        with sqlite3.connect(self.database_name) as conn:
            c = conn.cursor()
            c.execute(f"SELECT COUNT(*) FROM {table_name}")
            total_rows = c.fetchone()[0]
            c.execute(f"SELECT time FROM {table_name} ORDER BY pid DESC LIMIT 1")
            latest_time = c.fetchone()[0]
            c.execute(f"SELECT time FROM {table_name} ORDER BY pid LIMIT 1")
            oldest_time = c.fetchone()[0]
            c.execute(f"SELECT last_retrive FROM {table_name} ORDER BY pid DESC LIMIT 1")
            last_update_time = c.fetchone()[0]
            
            print(f"Total number of holes: {total_rows}")
            print(f"From time: {oldest_time}")
            print(f"To time: {latest_time}")
            print(f"Last Update: {last_update_time}")

    def create_comments_table(self):
        with sqlite3.connect(self.database_name) as conn:
            self.conn = sqlite3.connect(self.database_name)
            self.c = self.conn.cursor()
            self.c.execute(f'''CREATE TABLE IF NOT EXISTS comments
                        (cid INTEGER PRIMARY KEY,
                        pid INTEGER,
                        text TEXT,
                        name TEXT,
                        time TEXT,
                        comment_id TEXT,
                        last_retrive TEXT)''')
            self.conn.commit()

    def update_comments_data(self, data:pd.DataFrame):
        with sqlite3.connect(self.database_name) as conn:
            c = conn.cursor()
            for index, row in data.iterrows():
                try:
                    cid = index
                    pid = row['pid']
                    text = row['text']
                    name = row['name']
                    time = str(row['time'])
                    comment_id = row['comment_id']
                    last_retrive = row['last_retrive']
                    c.execute("SELECT * FROM comments WHERE cid=?", (cid,))
                    result = c.fetchone()
                except:
                    print("Error!")
                    print(index, row)
                if not result:
                    c.execute("INSERT INTO comments (cid, pid, text, name, time, comment_id, last_retrive) VALUES (?, ?, ?, ?, ?, ?, ?)", (cid, pid, text, name, time, comment_id, last_retrive))

            conn.commit()
