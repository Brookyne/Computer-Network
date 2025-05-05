import socket
import threading
import logging
import time
import uuid
from datetime import datetime
import os
import traceback
from database_manager import DatabaseManager
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
        
        # Sử dụng username là định danh chính, thay vì địa chỉ IP:port
        display_sender = self.sender_username or self.sender
        
        # Định dạng rõ ràng hơn
        return f"[{time_str}] {display_sender}: {self.content}"
    
    # def to_network_format(self, sender_ip, sender_port, sender_username):
    #     """Chuyển đổi tin nhắn sang định dạng để gửi qua mạng"""
    #     return f"CHANNEL:{self.channel} TIMESTAMP:{self.timestamp} SENDER_IP:{sender_ip} SENDER_PORT:{sender_port} SENDER_USERNAME:{sender_username} MESSAGE_ID:{self.id} MESSAGE:{self.content}"
    def to_network_format(self, sender_ip, sender_port, sender_username):
        """Convert message to network format"""
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
        
            
    def login(self, user_status):
        """Đăng nhập vào tracker server"""
        if self.tracker_conn is None:
            if not self.connect():
                return False

        if self.is_guest:
            cmd = f"GUEST {self.username} {self.local_ip} {self.local_port} {user_status}\n"
        else:
            cmd = f"LOGIN {self.username} {self.password} {self.local_ip} {self.local_port} {user_status}\n"
                
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
                if len(parts) >= 6:
                    username, ip, port, session_id, mode, status = parts[0], parts[1], int(parts[2]), parts[3], parts[4], parts[5]
                    peers.append((username, ip, port, session_id, mode, status))
                    
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

        self.current_channel = None

        
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
                data = conn.recv(65536).decode().strip()
                if data:
                    self.logger.info(f"Nhận dữ liệu thô từ {addr}: {data}")

                    if data.startswith("CONTROL:"):
                        parts = data.split(":", 3)
                        if len(parts) == 4:
                            _, channel, cmd, sender = parts
                            if cmd == "REQUEST_STREAM" and self.peer_client.is_host(channel):
                                self.peer_client.stream_viewers.add(sender)
                            return
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

                    if data.startswith("VIDEO_FRAME:"):
                        try:
                            parts = data.split(":", 4)
                            if len(parts) != 5:
                                self.logger.error(f"Invalid video frame format from {addr}")
                                return
                                
                            channel = parts[1]
                            sender_username = parts[2]
                            timestamp = float(parts[3])
                            frame_data = parts[4]
                            
                            # Verify if the sender is the channel owner
                            # This check is best effort on the receiver side
                            if self.peer_client and channel == self.current_channel:
                                # Only process frames if we're in this channel
                                # Additional check if possible: Verify that sender is the host
                                # If we can't verify, we'll trust the sender for now
                                self.video_callback(frame_data, sender_username)
                                
                        except Exception as e:
                            self.logger.error(f"Error processing video frame from {addr}: {e}")        
            
            
            
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
    def __init__(self, username, password, tracker_ip, tracker_port, local_port, is_guest=False, message_handler=None, user_status="online"):
        # Thông tin cơ bản
        self.username = username
        self.password = password
        self.is_guest = is_guest
        self.session_id = None
        self.local_ip = self._get_local_ip()
        self.local_port = local_port
        self.offline_messages = []  # Store messages when invisible/offline
        self.previous_status = "online"  # Track previous status

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
            message_callback=self._handle_incoming_message,
            logger=self.logger
        )
        
        # Message handler để thông báo cho GUI khi có tin nhắn mới
        self.message_handler = message_handler

        self.user_status = user_status # Initialize user status

        self.stream_viewers = set() # Danh sách các peer đang xem livestream

        self.host_channels = set()  # Danh sách các kênh mà peer này là host

        self.peer_server.peer_client = self # Để có thể gọi lại hàm trong PeerClient từ PeerServer
         # Khởi tạo database manager
        self.db_manager = DatabaseManager(db_file=f"data/{username}_chat.db", logger=self.logger)
        
        # Thêm người dùng vào cơ sở dữ liệu
        self.db_manager.add_user(username, self.local_ip, local_port)
        
        # Tải các kênh đã tham gia từ database
        self._load_joined_channels()

    def _load_joined_channels(self):
        """Tải tất cả kênh đã tham gia từ database"""
        if not hasattr(self, 'db_manager') or not self.db_manager:
            return
            
        channels_data = self.db_manager.get_all_user_channels(self.username)
        for channel_data in channels_data:
            channel_name = channel_data['name']
            
            # Kiểm tra xem đã có trong danh sách kênh chưa
            if channel_name not in self.channels:
                # Tạo đối tượng Channel mới
                channel = Channel(channel_name)
                self.channels[channel_name] = channel
                
                # Đánh dấu là host nếu là chủ kênh
                if channel_data['is_owner'] or channel_data['owner'] == self.username:
                    self.host_channels.add(channel_name)
                    
                # Tải tin nhắn cũ từ database
                self._load_channel_messages(channel_name)
                
                # Đăng ký kênh với tracker (chỉ đăng ký sau khi đã đăng nhập thành công)
                if self.session_id:
                    self.tracker_conn.join_channel(channel_name)

    def store_offline_message(self, message_text):
        """Store a message to be sent later when returning online"""
        if not self.current_channel:
            return False
            
        self.logger.info(f"Storing offline message for channel {self.current_channel}: {message_text}")
        
        # Create a message object to store
        message = {
            "channel": self.current_channel,
            "content": message_text,
            "timestamp": time.time()
        }
        
        # Add to offline messages queue
        self.offline_messages.append(message)
        return True



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
        if self.tracker_conn.login(self.user_status):
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
            
        # Đóng kết nối database
        if hasattr(self, 'db_manager'):
            self.db_manager.close()
            
        self.logger.info("PeerClient stopped.")
        
    def _handle_incoming_message(self, channel, sender_ip, sender_port, timestamp, message_text, message_id, sender_username=None):
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
                username, ip, port, session_id, mode, status = peer
                if ip == sender_ip and int(port) == int(sender_port):
                    sender_username = username
                    break
                
        # Tạo đối tượng Message
        sender = f"{sender_ip}:{sender_port}"
        message = Message(channel, sender, message_text, timestamp, message_id, sender_username)
        
        # Thêm vào kênh, chỉ thêm nếu tin nhắn chưa tồn tại (dựa vào message_id)
        if self.channels[channel].add_message(message):
            # Lưu tin nhắn vào database
            self.db_manager.add_message(
                message_id=message_id,
                channel=channel,
                sender=sender_username or sender,
                content=message_text,
                timestamp=timestamp
            )
            
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
            
            # Lưu thông tin tham gia kênh vào database
            self.db_manager.join_channel(channel_name, self.username)
            
            # Tải tin nhắn cũ từ database
            self._load_channel_messages(channel_name)
            
            # Chuyển sang kênh mới
            self.switch_channel(channel_name)
            
            self.logger.info(f"Đã tham gia kênh '{channel_name}'")

            if not self.is_host(channel_name):
                self.send_control_message(channel_name, "REQUEST_STREAM")
            return True
        else:
            self.logger.error(f"Không thể tham gia kênh '{channel_name}'")
            return False
            
    # Thêm phương thức để tải tin nhắn cũ từ database
    def _load_channel_messages(self, channel_name):
        """Tải tin nhắn cũ từ database"""
        if channel_name not in self.channels:
            return
            
        messages = self.db_manager.get_channel_messages(channel_name)
        for msg in messages:
            # Tạo đối tượng Message từ dữ liệu database
            message = Message(
                channel=msg['channel'],
                sender=msg['sender'],
                content=msg['content'],
                timestamp=msg['timestamp'],
                message_id=msg['id'],
                sender_username=msg['sender']
            )
            # Thêm vào kênh
            self.channels[channel_name].add_message(message)    
        
        
    def switch_channel(self, channel_name):
        """Chuyển sang kênh đã chọn"""
        if channel_name not in self.channels:
            self.logger.error(f"Kênh '{channel_name}' không tồn tại hoặc bạn chưa tham gia")
            return False
            
        # Cập nhật kênh hiện tại
        self.current_channel = channel_name
        self.peer_server.current_channel = channel_name
        
        # Cập nhật thời gian chuyển kênh
        self.channels[channel_name].switch_time = time.time()
        
        self.logger.info(f"Đã chuyển sang kênh '{channel_name}'")
        return True
        
    # def send_message(self, message_text):
    #     """Gửi tin nhắn đến tất cả peer trong kênh hiện tại"""
    #     if self.is_guest:
    #         self.logger.error("Bạn đang ở chế độ khách và không thể gửi tin nhắn")
    #         return False
            
    #     if not self.current_channel:
    #         self.logger.error("Vui lòng chọn một kênh trước khi gửi tin nhắn")
    #         return False
            
    #     if not message_text:
    #         return False
        
    #     # Debug log
    #     self.logger.info(f"Chuẩn bị gửi tin nhắn trong kênh {self.current_channel}: {message_text}")    
            
    #     # Lấy danh sách peer
    #     peers = self.tracker_conn.get_peers()
    #     self.logger.info(f"Tìm thấy {len(peers)} peers để gửi tin nhắn")
        
    #     # Tạo tin nhắn
    #     message = Message(
    #         channel=self.current_channel,
    #         sender=f"{self.local_ip}:{self.local_port}",
    #         content=message_text,
    #         sender_username=self.username
    #     )
        
    #     # Thêm tin nhắn của mình vào kênh hiện tại
    #     self.channels[self.current_channel].add_message(message)
        
    #     # Định dạng tin nhắn để gửi
    #     formatted_message = message.to_network_format(self.local_ip, self.local_port, self.username)
    #     self.logger.info(f"Tin nhắn định dạng mạng: {formatted_message}")
        
    #     # Gửi tin nhắn đến tất cả peer
    #     sent_count = 0
    #     for peer in peers:
    #         username, ip, port, session_id, mode, status = peer
            
    #         # Bỏ qua chính mình
    #         if session_id == self.session_id:
    #             self.logger.info(f"Bỏ qua gửi cho chính mình {username} ({ip}:{port})")
    #             continue
                
    #         try:
    #             with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    #                 s.settimeout(5)  # Thiết lập timeout để tránh treo
    #                 s.connect((ip, int(port)))
    #                 s.sendall(formatted_message.encode())
    #                 sent_count += 1
    #                 self.logger.info(f"Đã gửi tin nhắn đến {username} ({ip}:{port})")
    #         except Exception as e:
    #             self.logger.error(f"Lỗi gửi tin nhắn đến {username} ({ip}:{port}): {e}")
                
    #     # Thông báo cho GUI nếu có message handler
    #     if self.message_handler:
    #         self.message_handler(message)
            
    #     self.logger.info(f"Đã gửi tin nhắn đến {sent_count} peer: {message_text}")
    #     return True
        
    def send_message(self, message_text):
        """Gửi tin nhắn đến tất cả peer trong kênh hiện tại hoặc lưu trữ nếu invisible/offline"""
        if self.is_guest:
            self.logger.error("Bạn đang ở chế độ khách và không thể gửi tin nhắn")
            return False
            
        if not self.current_channel:
            self.logger.error("Vui lòng chọn một kênh trước khi gửi tin nhắn")
            return False
            
        if not message_text:
            return False
        
        # Nếu ở chế độ invisible/offline, lưu trữ tin nhắn cho sau này
        if self.user_status == "invisible" or self.user_status == "offline":
            # Tạo tin nhắn để hiển thị trong giao diện người dùng
            message = Message(
                channel=self.current_channel,
                sender=f"{self.local_ip}:{self.local_port}",
                content=message_text,
                sender_username=self.username
            )
            
            # Thêm tin nhắn vào kênh để hiển thị cục bộ
            self.channels[self.current_channel].add_message(message)
            
            # Lưu vào database
            self.db_manager.add_message(
                message_id=message.id,
                channel=self.current_channel,
                sender=self.username,
                content=message_text,
                timestamp=message.timestamp
            )
            
            # Lưu trữ để gửi sau này
            self.store_offline_message(message_text)
            
            # Thông báo cho GUI
            if self.message_handler:
                self.message_handler(message)
                
            return True
        
        # Original code for online mode
        # Debug log
        self.logger.info(f"Preparing to send message in channel {self.current_channel}: {message_text}")    
            
        # Get peer list
        peers = self.tracker_conn.get_peers()
        self.logger.info(f"Found {len(peers)} peers to send message")
        
        # Create message
        message = Message(
            channel=self.current_channel,
            sender=f"{self.local_ip}:{self.local_port}",
            content=message_text,
            sender_username=self.username
        )
        self.db_manager.add_message(
        message_id=message.id,
        channel=self.current_channel,
        sender=self.username,
        content=message_text,
        timestamp=message.timestamp
        )
        # Add own message to current channel
        self.channels[self.current_channel].add_message(message)
        
        # Format message for sending
        formatted_message = message.to_network_format(self.local_ip, self.local_port, self.username)
        self.logger.info(f"Network formatted message: {formatted_message}")
        
        # Send message to all peers
        sent_count = 0
        for peer in peers:
            username, ip, port, session_id, mode, status = peer
            
            # Skip self
            if session_id == self.session_id:
                self.logger.info(f"Skipping send to self {username} ({ip}:{port})")
                continue
                
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(5)  # Set timeout to avoid hanging
                    s.connect((ip, int(port)))
                    s.sendall(formatted_message.encode())
                    sent_count += 1
                    self.logger.info(f"Sent message to {username} ({ip}:{port})")
            except Exception as e:
                self.logger.error(f"Error sending message to {username} ({ip}:{port}): {e}")
                
        # Notify GUI if message handler exists
        if self.message_handler:
            self.message_handler(message)
            
        self.logger.info(f"Sent message to {sent_count} peers: {message_text}")
        return True
    
    def send_offline_messages(self):
        """Gửi tin nhắn đã lưu trữ khi offline/invisible"""
        if not self.offline_messages:
            return True
            
        self.logger.info(f"Đang gửi {len(self.offline_messages)} tin nhắn đã lưu trữ từ offline/invisible")
        
        success = True
        # Tạo một bản sao của danh sách để tránh vấn đề khi lặp
        messages_to_send = self.offline_messages.copy()
        
        for stored_msg in messages_to_send:
            # Chuyển đến kênh của tin nhắn này
            original_channel = self.current_channel
            self.switch_channel(stored_msg["channel"])
            
            # Gửi tin nhắn với timestamp gốc
            result = self._send_message_directly(stored_msg["content"], stored_msg["timestamp"])
            if result:
                # Xóa khỏi tin nhắn offline nếu gửi thành công
                self.offline_messages.remove(stored_msg)
            else:
                success = False
            
            # Thêm một khoảng thời gian ngắn giữa các tin nhắn để tránh lặp
            time.sleep(0.1)
                
        # Quay lại kênh ban đầu
        if original_channel:
            self.switch_channel(original_channel)
                
        return success
    def _send_message_directly(self, message_text, timestamp=None):
        """Gửi một tin nhắn cụ thể với timestamp tùy chọn"""
        if not self.current_channel:
            return False
            
        # Sử dụng timestamp được cung cấp hoặc thời gian hiện tại
        msg_timestamp = timestamp or time.time()
        
        # Lấy danh sách peer
        peers = self.tracker_conn.get_peers()
        
        # Tạo một ID tin nhắn mới để tránh trùng lặp
        message_id = str(uuid.uuid4())
        
        # Tạo tin nhắn với timestamp cụ thể và ID mới
        message = Message(
            channel=self.current_channel,
            sender=f"{self.local_ip}:{self.local_port}",
            content=message_text,
            timestamp=msg_timestamp,
            message_id=message_id,
            sender_username=self.username
        )
        
        # Định dạng tin nhắn để gửi
        formatted_message = message.to_network_format(self.local_ip, self.local_port, self.username)
        
        # Gửi tin nhắn đến tất cả peer
        sent_count = 0
        for peer in peers:
            username, ip, port, session_id, mode, status = peer
            
            # Bỏ qua chính mình
            if session_id == self.session_id:
                continue
                
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(5)
                    s.connect((ip, int(port)))
                    s.sendall(formatted_message.encode())
                    sent_count += 1
            except Exception as e:
                self.logger.error(f"Lỗi gửi tin nhắn offline đến {username}: {e}")
                
        return sent_count > 0
        
    
    def set_user_status(self, new_status):
        if new_status not in ("online", "invisible", "offline"):
            self.logger.error(f"Invalid status: {new_status}")
            return False
        
        previous_status = self.user_status
        
        if self.tracker_conn.tracker_conn:
            try:
                self.tracker_conn.tracker_conn.sendall(f"STATUS_CHANGE {self.session_id} {new_status}\n".encode())
                response = self.tracker_conn.tracker_conn.recv(1024).decode().strip()
                if response == "STATUS_CHANGED":
                    self.user_status = new_status
                    self.logger.info(f"Status changed to {new_status}")
                    
                    # If changing from invisible/offline to online, send stored messages
                    if (previous_status in ["invisible", "offline"]) and new_status == "online":
                        self.logger.info("Sending stored offline messages after returning online")
                        threading.Thread(target=self.send_offline_messages, daemon=True).start()
                    
                    return True
                else:
                    self.logger.error(f"Failed to change status: {response}")
                    return False
            except Exception as e:
                self.logger.error(f"Error changing status: {e}")
                return False
        else:
            self.logger.error("Not connected to tracker.")
            return False


    def get_peers(self):
        # """Lấy danh sách peer từ tracker"""
        # return self.tracker_conn.get_peers()
        peers = self.tracker_conn.get_peers()
        visible_peers = [peer for peer in peers if peer[5] == "online"] 
        return visible_peers
        
    def get_channel_messages(self, channel_name=None):
        """Lấy danh sách tin nhắn của kênh hiện tại hoặc kênh được chỉ định"""
        channel = channel_name or self.current_channel
        if not channel or channel not in self.channels:
            return []
        return self.channels[channel].messages  
    
    # def set_user_status(self, new_status):
    #     if new_status not in ("online", "invisible"):
    #         self.logger.error(f"Invalid status: {new_status}")
    #         return False
    
    #     if self.tracker_conn.tracker_conn:
    #         try:
    #             self.tracker_conn.tracker_conn.sendall(f"STATUS_CHANGE {self.session_id} {new_status}\n".encode())
    #             response = self.tracker_conn.tracker_conn.recv(1024).decode().strip()
    #             if response == "STATUS_CHANGED":
    #                 self.user_status = new_status
    #                 self.logger.info(f"Status changed to {new_status}")
    #                 return True
    #             else:
    #                 self.logger.error(f"Failed to change status: {response}")
    #                 return False
    #         except Exception as e:
    #             self.logger.error(f"Error changing status: {e}")
    #             return False
    #     else:
    #         self.logger.error("Not connected to tracker.")
    #         return False
        
    def send_video_frame(self, frame_data):
        if self.is_guest:
            self.logger.error("Khách không thể phát trực tiếp video")
            return False
            
        if not self.current_channel:
            self.logger.error("Vui lòng chọn một kênh để thực hiện")
            return False
            
        # Kiểm tra xem người dùng có phải là chủ kênh không
        if not self.is_host(self.current_channel):
            self.logger.error(f"Không phải chủ kênh {self.current_channel}, không được phép phát trực tiếp")
            return False
                
        # Create a video frame message
        message = f"VIDEO_FRAME:{self.current_channel}:{self.username}:{time.time()}:{frame_data}"
        
        # Get peers in the current channel
        peers = self.tracker_conn.get_peers()
        
        sent_count = 0
        for peer in peers:
            username, ip, port, session_id, mode, status = peer
            
            # Skip ourselves
            if session_id == self.session_id:
                continue
                
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1) 
                    s.connect((ip, int(port)))
                    s.sendall(message.encode())
                    sent_count += 1
            except Exception as e:
                self.logger.error(f"Error sending video frame to {username} ({ip}:{port}): {e}")
                
        return sent_count > 0
    
    def send_control_message(self, channel, cmd):
        # if cmd == "REQUEST_STREAM" and self.is_host(channel):
        #     # thêm vào danh sách viewer
        #     self.stream_viewers.add(sender)
        msg = f"CONTROL:{channel}:{cmd}:{self.username}"
        peers = self.tracker_conn.get_peers()
        for username, ip, port, session_id, mode, status in peers:
            if session_id == self.session_id:
                continue
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1)
                    s.connect((ip, int(port)))
                    s.sendall(msg.encode())
            except Exception as e:
                self.logger.error(f"Error sending control message to {username} ({ip}:{port}): {e}")

    def create_channel(self, channel_name):
        """Tạo kênh mới và đặt người dùng hiện tại làm chủ"""
        success = self.join_channel(channel_name)
        if success:
            # Thêm kênh vào danh sách kênh mà user này là host
            self.host_channels.add(channel_name)
            
            # Ghi vào database nếu có
            if hasattr(self, 'db_manager') and self.db_manager:
                self.db_manager.add_channel(channel_name, self.username)
            
            return success
        return False
    
    def is_host(self, channel):
        """Kiểm tra xem người dùng có phải là chủ kênh không"""
        # Kiểm tra trong bộ nhớ
        if channel in self.host_channels:
            return True
            
        # Kiểm tra từ database nếu có
        if hasattr(self, 'data') and self.db_manager:
            is_owner = self.db_manager.is_channel_owner(channel, self.username)
            # Cập nhật lại bộ nhớ nếu cần
            if is_owner and channel not in self.host_channels:
                self.host_channels.add(channel)
            return is_owner
        
        return False
    


    
        
        