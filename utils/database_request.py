import sqlite3

class Database_request():
    def __init__(self, db_name):
        self.connection = sqlite3.connect(db_name)
        self.cursor = self.connection.cursor()

    def add_problem(self, problem, telegram_id):
        self.cursor.execute(f"INSERT INTO request (problem, telegram_id) VALUES (?, ?)", (problem, telegram_id))
        self.connection.commit()
    def select_problem(self, problem):
        problem = self.cursor.execute("SELECT telegram_id, problem FROM request ORDER BY rowid DESC LIMIT 1")
        return problem.fetchone()
    
    def edit_status(self):
        self.cursor.execute("UPDATE request SET status = 1 WHERE status = 0 ")
        self.connection.commit()

    def __del__(self):
        self.cursor.close()
        self.connection.close()