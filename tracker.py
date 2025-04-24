import socket
import threading
import uuid
import logging

class TrackerServer:
    def __init__(self, host='', port=22110):
        self.host = "10.0.131.183"
        self.port = port
        # Danh sách lưu thông tin các peer: (username, ip, port, session_id, is_guest, channels)
        self.peers = []
        self.peers_lock = threading.Lock()
        # Danh sách tài khoản cho xác thực (cho LOGIN)
        self.users = {
            "alice": "password1",
            "bob": "password2",
            "charlie": "password3",
            "PhuongNguyen":"2212311",
            "HaNguyen":"123456",
            "HaiNguyen":"123456"
        }
        # Setup logger cho tracker
        self.logger = logging.getLogger("TrackerServer")
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        fh = logging.FileHandler("tracker.log", encoding="utf-8")
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)
        self.logger.info("Tracker Server khởi động")
    def _get_local_ip(self):
        """Lấy địa chỉ IP local của máy"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except:
            return "127.0.0.1"
    def start(self):
        threading.Thread(target=self.command_loop, daemon=True).start()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((self.host, self.port))
            s.listen(10) #10 kết nối đồng thời
            self.logger.info(f"[Tracker] Tracker Server lắng nghe trên {self.host}:{self.port}")
            print(f"[Tracker] Tracker Server lắng nghe trên {self.host}:{self.port}")
            while True:
                conn, addr = s.accept()
                handler = ClientHandler(conn, addr, self)
                handler.start()

    def command_loop(self):
        while True:
            cmd = input("Tracker Command> ").strip().lower()
            if cmd == "list":
                self.print_peers_table()
            elif cmd in ("exit", "quit"):
                print("[Tracker] Đang thoát...")
                self.logger.info("Tracker Server bị đóng theo lệnh terminal.")
                exit(0)
            else:
                print("Lệnh không xác định. Sử dụng 'list' để xem danh sách peer hoặc 'exit' để thoát.")

    def print_peers_table(self):
        with self.peers_lock:
            if self.peers:
                print("\n" + "=" * 100)
                print("Danh sách các Peer đang đăng ký".center(100))
                print("=" * 100)
                print("{:<15} {:<15} {:<10} {:<36} {:<10}".format("Username", "IP", "Port", "SessionID", "Mode"))
                print("-" * 100)
                for peer in self.peers:
                    mode = "Guest" if peer[4] else "User"
                    print("{:<15} {:<15} {:<10} {:<36} {:<10}".format(peer[0], peer[1], peer[2], peer[3], mode))
                print("=" * 100 + "\n")
            else:
                print("[Tracker] Hiện không có peer nào đăng ký.")

    def register_peer(self, username, peer_ip, peer_port, is_guest=False, channels=None):
        session_id = str(uuid.uuid4())
        if channels is None:
            channels = []
        peer_entry = (username, peer_ip, peer_port, session_id, is_guest, channels)
        with self.peers_lock:
            # Kiểm tra xem đã có bản ghi của peer chưa (dựa trên username, ip và port)
            for i, p in enumerate(self.peers):
                if p[0] == username and p[1] == peer_ip and p[2] == peer_port:
                    self.peers[i] = peer_entry
                    return session_id
            self.peers.append(peer_entry)
        return session_id

    def get_peers(self):
        with self.peers_lock:
            return list(self.peers)

    def join_channel(self, username, channel):
        # Thêm kênh vào danh sách kênh của peer
        with self.peers_lock:
            for i, peer in enumerate(self.peers):
                if peer[0] == username:
                    if channel not in peer[5]:
                        self.peers[i] = (peer[0], peer[1], peer[2], peer[3], peer[4], peer[5] + [channel])
                    return True
        return False

    def list_channels(self):
        channels = set()
        with self.peers_lock:
            for peer in self.peers:
                channels.update(peer[5])
        return list(channels)

    def deregister_peer(self, session_id):
        with self.peers_lock:
            new_list = []
            for p in self.peers:
                if p[3] != session_id:
                    new_list.append(p)
            self.peers = new_list

class ClientHandler(threading.Thread):
    def __init__(self, conn, addr, tracker):
        super().__init__(daemon=True)
        self.conn = conn
        self.addr = addr
        self.tracker = tracker
        self.logged_in = False
        self.session_id = None
        self.username = None
        self.is_guest = False

    def run(self):
        print(f"[Tracker] Kết nối từ {self.addr}")
        self.tracker.logger.info(f"Kết nối từ {self.addr}")
        try:
            with self.conn:
                while True:
                    data = self.conn.recv(1024).decode().strip()
                    if not data:
                        break
                    
                    print(f"[Tracker] Nhận từ {self.addr}: {data}")
                    self.tracker.logger.info(f"Nhận từ {self.addr}: {data}")
                    tokens = data.split()
                    command = tokens[0].upper()
                    
                    if command == "LOGIN":
                        if len(tokens) < 5:
                            self.conn.sendall(b"ERROR Invalid LOGIN format\n")
                            continue
                        
                        username = tokens[1] 
                        password = tokens[2]
                        peer_ip = tokens[3]
                        peer_port = tokens[4]
                        if username in self.tracker.users and self.tracker.users[username] == password:
                            #Nội dung response: LOGIN_SUCCESS <session_id> hoặc LOGIN_FAIL với mục part bên class TrackerConnection
                            self.username = username
                            self.session_id = self.tracker.register_peer(username, peer_ip, peer_port, is_guest=False)
                            self.logged_in = True
                            response = f"LOGIN_SUCCESS {self.session_id}\n"
                            self.conn.sendall(response.encode())
                        else:
                            self.conn.sendall(b"LOGIN_FAIL\n")
                    elif command == "GUEST":
                        if len(tokens) < 4:
                            self.conn.sendall(b"ERROR Invalid GUEST format\n")
                            continue
                        username = tokens[1]
                        peer_ip = tokens[2]
                        peer_port = tokens[3]
                        self.username = username
                        self.session_id = self.tracker.register_peer(username, peer_ip, peer_port, is_guest=True)
                        self.logged_in = True
                        self.is_guest = True
                        response = f"GUEST_LOGIN_SUCCESS {self.session_id}\n"
                        self.conn.sendall(response.encode())
                    elif command == "GETPEERS":
                        peers = self.tracker.get_peers()
                        response = ""
                        for peer in peers:
                            mode = "Guest" if peer[4] else "User"
                            response += f"{peer[0]} {peer[1]} {peer[2]} {peer[3]} {mode}\n"
                        if response == "":
                            response = "NO_PEERS\n"
                        self.conn.sendall(response.encode())
                    elif command == "JOIN":
                        if len(tokens) < 2:
                            self.conn.sendall(b"ERROR Invalid JOIN format\n")
                            continue
                        channel = tokens[1]
                        if self.tracker.join_channel(self.username, channel):
                            self.conn.sendall(f"JOINED {channel}\n".encode())
                        else:
                            self.conn.sendall(f"ALREADY_JOINED {channel}\n".encode())
                    elif command == "LISTCHANNELS":
                        channels = self.tracker.list_channels()
                        if channels:
                            response = "Channels:" + "\n".join(channels)
                        else:
                            response = "No channels available."
                        self.conn.sendall(response.encode())
                    elif command == "DEREGISTER":
                        if len(tokens) < 2:
                            self.conn.sendall(b"ERROR Invalid DEREGISTER format\n")
                            continue
                        session_id = tokens[1]
                        self.tracker.deregister_peer(session_id)
                        self.conn.sendall(b"DEREGISTERED\n")
                    else:
                        self.conn.sendall(b"ERROR Unknown command\n")
        except Exception as e:
            self.tracker.logger.error(f"Exception từ {self.addr}: {e}")
            print(f"[Tracker] Exception: {e} từ {self.addr}")
        finally:
            print(f"[Tracker] Đóng kết nối từ {self.addr}")
            self.tracker.logger.info(f"Đóng kết nối từ {self.addr}")

if __name__ == "__main__":
    server = TrackerServer()
    server.start()
