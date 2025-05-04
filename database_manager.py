import sqlite3
import os
import time
import logging
from datetime import datetime

class DatabaseManager:
    """Quản lý cơ sở dữ liệu cho ứng dụng P2P Chat"""
    
    def __init__(self, db_file="p2p_chat.db", logger=None):
        """Khởi tạo kết nối và tạo cấu trúc cơ sở dữ liệu nếu chưa tồn tại"""
        self.db_file = db_file
        self.logger = logger or logging.getLogger("DatabaseManager")
        
        # Kiểm tra xem thư mục có tồn tại chưa
        db_dir = os.path.dirname(db_file)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
            
        # Kết nối đến cơ sở dữ liệu
        self.conn = sqlite3.connect(db_file, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Để truy cập kết quả theo tên cột
        
        # Tạo cấu trúc cơ sở dữ liệu nếu chưa tồn tại
        self._create_tables()
        
    def _create_tables(self):
        """Tạo các bảng trong cơ sở dữ liệu nếu chưa tồn tại"""
        cursor = self.conn.cursor()
        
        # Bảng users - lưu trữ thông tin người dùng
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            last_seen REAL,
            ip TEXT,
            port INTEGER
        )
        ''')
        
        # Bảng channels - lưu trữ thông tin kênh
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS channels (
            name TEXT PRIMARY KEY,
            created_at REAL,
            owner TEXT,
            FOREIGN KEY (owner) REFERENCES users(username)
        )
        ''')
        
        # Bảng messages - lưu trữ tin nhắn
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            channel TEXT,
            sender TEXT,
            content TEXT,
            timestamp REAL,
            FOREIGN KEY (channel) REFERENCES channels(name),
            FOREIGN KEY (sender) REFERENCES users(username)
        )
        ''')
        
        # Bảng channel_members - lưu trữ thành viên của kênh
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS channel_members (
            channel TEXT,
            username TEXT,
            joined_at REAL,
            PRIMARY KEY (channel, username),
            FOREIGN KEY (channel) REFERENCES channels(name),
            FOREIGN KEY (username) REFERENCES users(username)
        )
        ''')
        
        self.conn.commit()
        
    def add_user(self, username, ip, port):
        """Thêm hoặc cập nhật thông tin người dùng"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            INSERT OR REPLACE INTO users (username, last_seen, ip, port)
            VALUES (?, ?, ?, ?)
            ''', (username, time.time(), ip, port))
            self.conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Lỗi khi thêm người dùng: {e}")
            return False
            
    def update_user_last_seen(self, username):
        """Cập nhật thời gian hoạt động cuối cùng của người dùng"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            UPDATE users SET last_seen = ? WHERE username = ?
            ''', (time.time(), username))
            self.conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Lỗi khi cập nhật last_seen: {e}")
            return False
            
    def add_channel(self, name, owner):
        """Thêm kênh mới"""
        try:
            cursor = self.conn.cursor()
            
            # Kiểm tra xem kênh đã tồn tại chưa
            cursor.execute('SELECT name FROM channels WHERE name = ?', (name,))
            if cursor.fetchone():
                return False  # Kênh đã tồn tại
                
            # Thêm kênh mới
            cursor.execute('''
            INSERT INTO channels (name, created_at, owner)
            VALUES (?, ?, ?)
            ''', (name, time.time(), owner))
            
            # Thêm chủ kênh là thành viên đầu tiên
            cursor.execute('''
            INSERT INTO channel_members (channel, username, joined_at)
            VALUES (?, ?, ?)
            ''', (name, owner, time.time()))
            
            self.conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Lỗi khi thêm kênh: {e}")
            return False
            
    def join_channel(self, channel_name, username):
        """Thêm người dùng vào kênh"""
        try:
            cursor = self.conn.cursor()
            
            # Kiểm tra xem kênh tồn tại không
            cursor.execute('SELECT name FROM channels WHERE name = ?', (channel_name,))
            if not cursor.fetchone():
                # Nếu kênh chưa tồn tại, tạo kênh mới và đặt người dùng làm chủ
                cursor.execute('''
                INSERT INTO channels (name, created_at, owner)
                VALUES (?, ?, ?)
                ''', (channel_name, time.time(), username))
                
            # Thêm thành viên vào kênh nếu chưa tham gia
            cursor.execute('''
            INSERT OR IGNORE INTO channel_members (channel, username, joined_at)
            VALUES (?, ?, ?)
            ''', (channel_name, username, time.time()))
            
            self.conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Lỗi khi tham gia kênh: {e}")
            return False
            
    def add_message(self, message_id, channel, sender, content, timestamp=None):
        """Thêm tin nhắn mới vào cơ sở dữ liệu"""
        try:
            if timestamp is None:
                timestamp = time.time()
                
            cursor = self.conn.cursor()
            
            # Kiểm tra xem tin nhắn đã tồn tại chưa
            cursor.execute('SELECT id FROM messages WHERE id = ?', (message_id,))
            if cursor.fetchone():
                return False  # Tin nhắn đã tồn tại
                
            # Thêm tin nhắn mới
            cursor.execute('''
            INSERT INTO messages (id, channel, sender, content, timestamp)
            VALUES (?, ?, ?, ?, ?)
            ''', (message_id, channel, sender, content, timestamp))
            
            self.conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Lỗi khi thêm tin nhắn: {e}")
            return False
            
    def get_channel_messages(self, channel_name, limit=100, offset=0):
        """Lấy tin nhắn của kênh, sắp xếp theo thời gian"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            SELECT id, channel, sender, content, timestamp 
            FROM messages 
            WHERE channel = ? 
            ORDER BY timestamp ASC
            LIMIT ? OFFSET ?
            ''', (channel_name, limit, offset))
            
            messages = []
            for row in cursor.fetchall():
                messages.append({
                    'id': row['id'],
                    'channel': row['channel'],
                    'sender': row['sender'],
                    'content': row['content'],
                    'timestamp': row['timestamp']
                })
            return messages
        except Exception as e:
            self.logger.error(f"Lỗi khi lấy tin nhắn kênh: {e}")
            return []
            
    def get_user_channels(self, username):
        """Lấy danh sách kênh mà người dùng đã tham gia"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            SELECT c.name, c.created_at, c.owner, cm.joined_at 
            FROM channels c
            JOIN channel_members cm ON c.name = cm.channel
            WHERE cm.username = ?
            ORDER BY cm.joined_at DESC
            ''', (username,))
            
            channels = []
            for row in cursor.fetchall():
                channels.append({
                    'name': row['name'],
                    'created_at': row['created_at'],
                    'owner': row['owner'],
                    'joined_at': row['joined_at'],
                    'is_owner': row['owner'] == username
                })
            return channels
        except Exception as e:
            self.logger.error(f"Lỗi khi lấy kênh của người dùng: {e}")
            return []
            
    def get_all_user_channels(self, username):
        """Lấy tất cả kênh mà người dùng đã tham gia, bao gồm thông tin chủ kênh"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            SELECT c.name, c.created_at, c.owner, cm.joined_at 
            FROM channels c
            JOIN channel_members cm ON c.name = cm.channel
            WHERE cm.username = ?
            ORDER BY cm.joined_at DESC
            ''', (username,))
            
            channels = []
            for row in cursor.fetchall():
                channels.append({
                    'name': row['name'],
                    'created_at': row['created_at'],
                    'owner': row['owner'],
                    'joined_at': row['joined_at'],
                    'is_owner': row['owner'] == username
                })
            return channels
        except Exception as e:
            self.logger.error(f"Lỗi khi lấy tất cả kênh của người dùng: {e}")
            return []
            
    def is_channel_owner(self, channel_name, username):
        """Kiểm tra xem người dùng có phải là chủ kênh không"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            SELECT owner FROM channels WHERE name = ?
            ''', (channel_name,))
            
            row = cursor.fetchone()
            if row:
                return row['owner'] == username
            return False
        except Exception as e:
            self.logger.error(f"Lỗi khi kiểm tra chủ kênh: {e}")
            return False
            
    def get_channel_members(self, channel_name):
        """Lấy danh sách thành viên của kênh"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            SELECT u.username, u.last_seen, cm.joined_at 
            FROM users u
            JOIN channel_members cm ON u.username = cm.username
            WHERE cm.channel = ?
            ORDER BY cm.joined_at ASC
            ''', (channel_name,))
            
            members = []
            for row in cursor.fetchall():
                members.append({
                    'username': row['username'],
                    'last_seen': row['last_seen'],
                    'joined_at': row['joined_at']
                })
            return members
        except Exception as e:
            self.logger.error(f"Lỗi khi lấy thành viên kênh: {e}")
            return []
            
    def close(self):
        """Đóng kết nối cơ sở dữ liệu"""
        if self.conn:
            self.conn.close()