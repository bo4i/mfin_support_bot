import sqlite3

class Database():
    def __init__(self, db_name):
        self.connection = sqlite3.connect(db_name)
        self.cursor = self.connection.cursor()

    def add_users(self, user_name, user_phone, user_organization, telegram_id, telegram_username):
        self.cursor.execute(f"INSERT INTO user (user_name, user_phone, user_organization, telegram_id, telegram_username) VALUES (?, ?, ?, ?, ?)", (user_name, user_phone, user_organization, telegram_id, telegram_username))
        self.connection.commit()

    def select_users_id(self, telegram_id):
        user = self.cursor.execute("SELECT * FROM user WHERE telegram_id = ?", (telegram_id,))
        return user.fetchone()
    def select_name(self, user_name, user_phone, user_organization, telegram_username):
        name = self.cursor.execute("SELECT * FROM user WHERE user_name = ?", (user_name))
        phone = self.cursor.execute("SELECT * FROM user WHERE user_phone = ?", (user_phone))
        return name.fetchone(), phone.fetchone()   

    def edit_users_name(self, user_name, telegram_id):
        self.cursor.execute("UPDATE user SET user_name = ? WHERE telegram_id = ?", (user_name, telegram_id,))
        self.connection.commit()
    
    def edit_users_number(self, user_phone, telegram_id):
        self.cursor.execute("UPDATE user SET user_phone = ? WHERE telegram_id = ?", (user_phone, telegram_id,))
        self.connection.commit()
    
    def edit_users_instagram(self, user_organization, telegram_id):
        self.cursor.execute("UPDATE user SET user_organization = ? WHERE telegram_id = ?", (user_organization,telegram_id,))
        self.connection.commit()



    def __del__(self):
        self.cursor.close()
        self.connection.close()

