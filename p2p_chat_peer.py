import socket
import threading
import logging
import time
import uuid
from datetime import datetime
import os
import traceback

class Message:
    """Đại diện cho một tin nhắn"""
    def __init__(self, channel, sender, content, timestamp=None, message_id=None, sender_username=None):
        self.id = message_id or str(uuid.uuid4())  # Mỗi tin nhắn có ID duy nhất
        self.channel = channel
        self.sender = sender  # Địa chỉ IP:port
        self.sender_username = sender_username  # Thêm username của người gửi
        self.content = content
        self.timestamp = timestamp or time.time()
        
    def format(self):
        """Định dạng tin nhắn để hiển thị"""
        time_str = datetime.fromtimestamp(self.timestamp).strftime("%H:%M:%S") \
                   if isinstance(self.timestamp, (int, float)) \
                   else self.timestamp.strftime("%H:%M:%S")
        # Ưu tiên hiển thị username 
        display_sender = self.sender_username
        return f"[{time_str}] {display_sender}: {self.content}"
    
    def to_network_format(self, sender_ip, sender_port, sender_username):
        """Chuyển đổi tin nhắn sang định dạng để gửi qua mạng"""
        return f"CHANNEL:{self.channel} TIMESTAMP:{self.timestamp} SENDER_IP:{sender_ip} SENDER_PORT:{sender_port} SENDER_USERNAME:{sender_username} MESSAGE_ID:{self.id} MESSAGE:{self.content}"

class Channel:
    """Đại diện cho một kênh chat"""
    def __init__(self, name):
        self.name = name
        self.messages = []
        self.message_ids = set()  # Dùng để lưu ID các tin nhắn đã nhận, tránh trùng lặp
        self.switch_time = time.time()  # Thời điểm tham gia/chuyển đến kênh
        
    def add_message(self, message):
        """Thêm tin nhắn vào kênh, tránh trùng lặp bằng message_id"""
        # Nếu tin nhắn có ID đã tồn tại trong kênh, bỏ qua
        if message.id in self.message_ids:
            return False
            
        # Thêm ID vào danh sách đã xử lý
        self.message_ids.add(message.id)
        
        # Thêm tin nhắn vào danh sách
        self.messages.append(message)
        
        # Sắp xếp tin nhắn theo thời gian
        self.messages.sort(key=lambda x: x.timestamp)
        return True

class TrackerConnection:
    """Quản lý kết nối với Tracker Server"""
    def __init__(self, username, password, tracker_ip, tracker_port, local_ip, local_port, is_guest=False, logger=None):
        self.username = username
        self.password = password
        self.tracker_ip = tracker_ip
        self.tracker_port = tracker_port
        self.local_ip = local_ip
        self.local_port = local_port
        self.is_guest = is_guest
        self.session_id = None
        self.tracker_conn = None
        self.logger = logger or logging.getLogger("TrackerConnection")
        
    def connect(self):
        """Thiết lập kết nối đến tracker server"""
        try:
            self.tracker_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tracker_conn.connect((self.tracker_ip, self.tracker_port)) # Kết nối đến tracker
            self.logger.info(f"[Tracker] Kết nối tới tracker {self.tracker_ip}:{self.tracker_port} thành công.")
        except Exception as e:
            self.logger.error(f"Lỗi kết nối tới tracker {self.tracker_ip}:{self.tracker_port}: {e}")
            return False
        return True
        
            
    def login(self):
        """Đăng nhập vào tracker server"""
        if self.tracker_conn is None:
            if not self.connect():
                return False

        if self.is_guest:
            cmd = f"GUEST {self.username} {self.local_ip} {self.local_port}\n"
        else:
            cmd = f"LOGIN {self.username} {self.password} {self.local_ip} {self.local_port}\n"
                
        self.tracker_conn.sendall(cmd.encode())
        response = self.tracker_conn.recv(1024).decode().strip()
        self.logger.info(f"Nhận từ tracker: {response}")
            
        if (self.is_guest and response.startswith("GUEST_LOGIN_SUCCESS")) or \
            (not self.is_guest and response.startswith("LOGIN_SUCCESS")):
            parts = response.split()    
            if len(parts) >= 2:
                self.session_id = parts[1]
                self.logger.info(f"Login with session_id: {self.session_id}")
                return True
        return False


            
    def get_peers(self):
        """Lấy danh sách các peer đang online"""
        if self.tracker_conn is None:
            if not self.connect():
                return []
                
        try:
            self.tracker_conn.sendall(b"GETPEERS\n")
            data = self.tracker_conn.recv(4096).decode()
            
            peers = []
            if data.strip() == "NO_PEERS":
                return peers
                
            lines = data.strip().split("\n")
            for line in lines:
                parts = line.split()
                if len(parts) >= 5:
                    username, ip, port, session_id, mode = parts[0], parts[1], int(parts[2]), parts[3], parts[4]
                    peers.append((username, ip, port, session_id, mode))
                    
            self.logger.info("Lấy danh sách peer thành công.")
            return peers
        except Exception as e:
            self.logger.error(f"Error get list: {e}")
            return []
            
    def join_channel(self, channel):
        """Đăng ký tham gia một kênh"""
        if self.tracker_conn is None:
            if not self.connect():
                return False
                
        try:
            cmd = f"JOIN {channel}\n"
            self.tracker_conn.sendall(cmd.encode())
            response = self.tracker_conn.recv(1024).decode().strip()
            self.logger.info(f"Nhận từ tracker: {response}")
            
            if response.startswith("JOINED") or response.startswith("ALREADY_JOINED"):
                return True
            return False
        except Exception as e:
            self.logger.error(f"Lỗi tham gia kênh: {e}")
            return False
            
    def list_channels(self):
        """Lấy danh sách các kênh hiện có"""
        if self.tracker_conn is None:
            if not self.connect():
                return []
                
        try:
            self.tracker_conn.sendall(b"LISTCHANNELS\n")
            data = self.tracker_conn.recv(1024).decode().strip()
            
            channels = []
            if data.startswith("Channels:"):
                channels = data.split("\n")[1:]
                
            self.logger.info("Lấy danh sách kênh thành công.")
            return channels
        except Exception as e:
            self.logger.error(f"Lỗi lấy danh sách kênh: {e}")
            return []

class PeerServer:
    """Quản lý P2P server để nhận tin nhắn từ các peer khác"""
    def __init__(self, local_port, message_callback=None, logger=None):
        self.local_port = local_port
        self.server_socket = None
        self.message_callback = message_callback  # Callback để hiển thị tin nhắn nhận được lên GUI
        self.running = False
        self.logger = logger or logging.getLogger("PeerServer")
        
    def start(self):
        """Bắt đầu P2P server"""
        self.running = True
        threading.Thread(target=self._run_server, daemon=True).start()
        
    def _run_server(self):
        """Chạy server"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        self.server_socket.bind(('', self.local_port))
        self.server_socket.listen(5)
        self.logger.info(f"P2P Server đang lắng nghe trên cổng {self.local_port}")
            
        while self.running:
            try:
                conn, addr = self.server_socket.accept()
                threading.Thread(target=self._handle_connection, args=(conn, addr), daemon=True).start()
            except Exception as e:
                if self.running:  # Chỉ log nếu vẫn đang chạy
                    self.logger.error(f"Lỗi chấp nhận kết nối: {e}")
                # tắt ở đây này

        if self.server_socket:
            self.server_socket.close()

        
                
    def _handle_connection(self, conn, addr):
        """Xử lý kết nối từ peer khác"""
        with conn:
            try:
                data = conn.recv(1024).decode().strip()
                if data:
                    self.logger.info(f"Nhận dữ liệu thô từ {addr}: {data}")
                    if data.startswith("CHANNEL:"):
                        try:
                            # Định dạng tin nhắn mới: 
                            # "CHANNEL:<channel> TIMESTAMP:<timestamp> SENDER_IP:<ip> SENDER_PORT:<port> SENDER_USERNAME:<username> MESSAGE_ID:<id> MESSAGE:<message_text>"
                            parts = data.split(" MESSAGE:", 1)
                            header = parts[0].strip()
                            message_text = parts[1].strip()
                            
                            # Phân tích thông tin từ header
                            header_parts = header.split()
                            channel = header_parts[0].split(":", 1)[1].strip()
                            
                            # Tìm timestamp
                            timestamp_part = [p for p in header_parts if p.startswith("TIMESTAMP:")][0]
                            msg_timestamp = float(timestamp_part.split(":", 1)[1].strip())
                            
                            # Tìm thông tin IP và Port của người gửi
                            sender_ip_part = [p for p in header_parts if p.startswith("SENDER_IP:")][0]
                            sender_ip = sender_ip_part.split(":", 1)[1].strip()
                            
                            sender_port_part = [p for p in header_parts if p.startswith("SENDER_PORT:")][0]
                            sender_port = sender_port_part.split(":", 1)[1].strip()
                            
                            # Lấy username người gửi nếu có
                            sender_username = None
                            
                            sender_username_part = [p for p in header_parts if p.startswith("SENDER_USERNAME:")][0]
                            sender_username = sender_username_part.split(":", 1)[1].strip()
                            
                            
                            # Lấy Message ID để tránh trùng lặp
                            message_id_part = [p for p in header_parts if p.startswith("MESSAGE_ID:")][0]
                            message_id = message_id_part.split(":", 1)[1].strip()
                            
                            self.logger.info(f"Đã phân tích tin nhắn: kênh={channel}, timestamp={msg_timestamp}, sender={sender_ip}:{sender_port}, username={sender_username}, id={message_id}, message={message_text}")
                            
                            # Gọi callback để hiển thị tin nhắn
                            if self.message_callback:
                                self.message_callback(channel, sender_ip, sender_port, msg_timestamp, message_text, message_id, sender_username)
                        except Exception as ex:
                            self.logger.error(f"Lỗi phân tích tin nhắn từ {addr}: {ex}")    
                            self.logger.error(traceback.format_exc())
                    else:
                        self.logger.info(f"Tin nhắn không đúng định dạng từ {addr}: {data}")
            except Exception as e:
                self.logger.error(f"Lỗi nhận dữ liệu từ {addr}: {e}")
                self.logger.error(traceback.format_exc())
                
    def stop(self):
        """Dừng P2P server"""
        self.running = False
        # Tạo kết nối đến chính nó để unblock socket.accept()
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(('127.0.0.1', self.local_port))
        except:
            pass
        if self.server_socket:
            self.server_socket.close()

class PeerClient:
    """Client P2P để xử lý các tác vụ chat P2P"""
    def __init__(self, username, password, tracker_ip, tracker_port, local_port, is_guest=False, message_handler=None):
        # Thông tin cơ bản
        self.username = username
        self.password = password
        self.is_guest = is_guest
        self.session_id = None
        self.local_ip = self._get_local_ip()
        self.local_port = local_port
        
        # Các kênh đã tham gia
        self.channels = {}  # name -> Channel object
        self.current_channel = None 
        
        # Thiết lập logger
        self.setup_logger()
        
        # Kết nối đến tracker
        self.tracker_conn = TrackerConnection(
            username=username,
            password=password,
            tracker_ip=tracker_ip,
            tracker_port=tracker_port,
            local_ip=self.local_ip,
            local_port=local_port,
            is_guest=is_guest,
            logger=self.logger
        )
        
        # P2P Server để nhận tin nhắn
        self.peer_server = PeerServer(
            local_port=local_port,
            message_callback=self.handle_incoming_message,
            logger=self.logger
        )
        
        # Message handler để thông báo cho GUI khi có tin nhắn mới
        self.message_handler = message_handler
        
    def setup_logger(self):
        """Cài đặt logger"""
        self.logger = logging.getLogger(f"PeerClient_{self.username}_{self.local_port}")
        self.logger.setLevel(logging.INFO)
        
        # Tạo thư mục logs nếu chưa tồn tại
        if not os.path.exists("logs"):
            os.makedirs("logs")
            
        log_filename = f"logs/peer_{self.username}_{self.local_port}.log"
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        fh = logging.FileHandler(log_filename, encoding="utf-8")
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)
        
        self.logger.info("PeerClient started.")
        
    def _get_local_ip(self):
        """Lấy địa chỉ IP local của máy"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except:
            return "127.0.0.1"
            
    def start(self):
        """Khởi động client"""
        # Kết nối đến tracker và đăng nhập
        if self.tracker_conn.login():
            self.session_id = self.tracker_conn.session_id
            # Khởi động P2P server
            self.peer_server.start()
            self.logger.info("PeerClient started successfully.")
            return True
        else:
            self.logger.error("Failed to start PeerClient.")
            return False
            
    def stop(self):
        """Dừng client"""
        if self.tracker_conn and self.session_id:
            try:
                self.tracker_conn.tracker_conn.sendall(f"DEREGISTER {self.session_id}\n".encode())
            except:
                pass
        if self.peer_server:
            self.peer_server.stop()
        self.logger.info("PeerClient stopped.")
        
    def handle_incoming_message(self, channel, sender_ip, sender_port, timestamp, message_text, message_id, sender_username=None):
        """Xử lý tin nhắn nhận được từ P2P server"""
        self.logger.info(f"Nhận tin nhắn từ {sender_ip}:{sender_port} trên kênh '{channel}': {message_text}")
        
        # Kiểm tra xem đã tham gia kênh này chưa
        if channel not in self.channels:
            self.logger.info(f"Bỏ qua tin nhắn từ kênh '{channel}' chưa tham gia")
            return
            
        # Kiểm tra thời gian switch
        switch_time = self.channels[channel].switch_time
        if timestamp < switch_time:
            self.logger.info(f"Bỏ qua tin nhắn cũ (trước khi tham gia) từ kênh '{channel}'")
            return
            
        # Nếu không có sender_username từ tin nhắn, tìm từ danh sách peers
        if not sender_username:
            peers = self.tracker_conn.get_peers()
            for peer in peers:
                username, ip, port, session_id, mode = peer
                if ip == sender_ip and int(port) == int(sender_port):
                    sender_username = username
                    break
                
        # Tạo đối tượng Message
        sender = f"{sender_ip}:{sender_port}"
        message = Message(channel, sender, message_text, timestamp, message_id, sender_username)
        
        # Thêm vào kênh, chỉ thêm nếu tin nhắn chưa tồn tại (dựa vào message_id)
        if self.channels[channel].add_message(message):
            # Thông báo cho GUI nếu có message handler và đang ở kênh này
            if self.message_handler and self.current_channel == channel:
                self.message_handler(message)
                
    def join_channel(self, channel_name):
        """Tham gia kênh chat"""
        if not channel_name:
            return False
            
        # Kiểm tra xem đã tham gia kênh này chưa
        if channel_name in self.channels:
            self.switch_channel(channel_name)
            return True
            
        # Đăng ký kênh với tracker
        if self.tracker_conn.join_channel(channel_name):
            # Tạo đối tượng Channel mới
            channel = Channel(channel_name)
            self.channels[channel_name] = channel
            
            # Chuyển sang kênh mới
            self.switch_channel(channel_name)
            
            self.logger.info(f"Đã tham gia kênh '{channel_name}'")
            return True
        else:
            self.logger.error(f"Không thể tham gia kênh '{channel_name}'")
            return False
            
    def switch_channel(self, channel_name):
        """Chuyển sang kênh đã chọn"""
        if channel_name not in self.channels:
            self.logger.error(f"Kênh '{channel_name}' không tồn tại hoặc bạn chưa tham gia")
            return False
            
        # Cập nhật kênh hiện tại
        self.current_channel = channel_name
        
        # Cập nhật thời gian chuyển kênh
        self.channels[channel_name].switch_time = time.time()
        
        self.logger.info(f"Đã chuyển sang kênh '{channel_name}'")
        return True
        
    def send_message(self, message_text):
        """Gửi tin nhắn đến tất cả peer trong kênh hiện tại"""
        if self.is_guest:
            self.logger.error("Bạn đang ở chế độ khách và không thể gửi tin nhắn")
            return False
            
        if not self.current_channel:
            self.logger.error("Vui lòng chọn một kênh trước khi gửi tin nhắn")
            return False
            
        if not message_text:
            return False
        
        # Debug log
        self.logger.info(f"Chuẩn bị gửi tin nhắn trong kênh {self.current_channel}: {message_text}")    
            
        # Lấy danh sách peer
        peers = self.tracker_conn.get_peers()
        self.logger.info(f"Tìm thấy {len(peers)} peers để gửi tin nhắn")
        
        # Tạo tin nhắn
        message = Message(
            channel=self.current_channel,
            sender=f"{self.local_ip}:{self.local_port}",
            content=message_text,
            sender_username=self.username
        )
        
        # Thêm tin nhắn của mình vào kênh hiện tại
        self.channels[self.current_channel].add_message(message)
        
        # Định dạng tin nhắn để gửi
        formatted_message = message.to_network_format(self.local_ip, self.local_port, self.username)
        self.logger.info(f"Tin nhắn định dạng mạng: {formatted_message}")
        
        # Gửi tin nhắn đến tất cả peer
        sent_count = 0
        for peer in peers:
            username, ip, port, session_id, mode = peer
            
            # Bỏ qua chính mình
            if session_id == self.session_id:
                self.logger.info(f"Bỏ qua gửi cho chính mình {username} ({ip}:{port})")
                continue
                
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(5)  # Thiết lập timeout để tránh treo
                    s.connect((ip, port))
                    s.sendall(formatted_message.encode())
                    sent_count += 1
                    self.logger.info(f"Đã gửi tin nhắn đến {username} ({ip}:{port})")
            except Exception as e:
                self.logger.error(f"Lỗi gửi tin nhắn đến {username} ({ip}:{port}): {e}")
                
        # Thông báo cho GUI nếu có message handler
        if self.message_handler:
            self.message_handler(message)
            
        self.logger.info(f"Đã gửi tin nhắn đến {sent_count} peer: {message_text}")
        return True
        
    def get_peers(self):
        "Lấy danh sách peer từ tracker"
        return self.tracker_conn.get_peers()
        
    def get_channel_messages(self, channel_name=None):
        "Lấy danh sách tin nhắn của kênh hiện tại hoặc kênh được chỉ định"
        channel = channel_name or self.current_channel
        if not channel or channel not in self.channels:
            return []
        return self.channels[channel].messages  