import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog
import threading
import argparse
import logging
import time
import os
import socket
from datetime import datetime
from p2p_chat_peer import PeerClient, Message
from PIL import Image, ImageTk
from live_stream import VideoStream

class P2PChatGUI:
    """Ứng dụng chat P2P với giao diện đồ họa"""
    def __init__(self, root):
        self.root = root
        self.root.title("P2P Chat Application")
        self.root.geometry("1200x800")  # Tăng kích thước mặc định để có không gian rộng hơn
        self.root.minsize(800, 600)
        
        # Thiết lập style cho ttk
        self.setup_styles()
        
        self.video_stream = None
        self.current_stream_username = None
        self.stream_active = False

        self.host_channels = set()

        # Logger
        self.set_logger()
        
        # Thiết lập các biến trạng thái
        self.peer_client = None
        
        # Thiết lập UI
        self.setup_ui()
        
        # Hiển thị màn hình đăng nhập
        self.show_login_screen()

    def setup_styles(self):
        """Cài đặt style cho các widget"""
        style = ttk.Style()
        
        # Thiết lập màu nền và màu chữ cho các widget
        style.configure("TFrame", background="#f0f0f0")
        style.configure("TLabel", background="#f0f0f0", font=("Arial", 10))
        style.configure("TButton", font=("Arial", 10), padding=5)
        style.configure("TLabelframe", background="#f0f0f0", font=("Arial", 10, "bold"))
        style.configure("TLabelframe.Label", font=("Arial", 10, "bold"))
        
        # Style cho các button điều khiển stream
        style.configure("Stream.TButton", background="#4CAF50", foreground="white")
        style.configure("Stop.TButton", background="#F44336", foreground="white")
        
        # Style cho nhãn hiển thị trạng thái
        style.configure("Status.TLabel", font=("Arial", 9, "italic"))
        
        # Style cho label channel hiện tại
        style.configure("Channel.TLabel", font=("Arial", 14, "bold"))
        
    def set_logger(self):
        """Cài đặt logger cho ứng dụng"""
        self.logger = logging.getLogger("P2PChatGUI")
        self.logger.setLevel(logging.INFO)
        
        # Tạo thư mục logs nếu chưa tồn tại
        if not os.path.exists("logs"):
            os.makedirs("logs")
            
        log_filename = f"logs/p2p_chat_gui_{int(time.time())}.log"
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        fh = logging.FileHandler(log_filename, encoding="utf-8")
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)
        
        self.logger.info("P2P Chat GUI started.")
            
    def setup_ui(self):
        """Thiết lập giao diện người dùng"""
        # Frame chính
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Frame đăng nhập
        self.login_frame = ttk.Frame(self.root)
        
        # Thiết lập giao diện chính
        self.setup_main_ui()
        
    def setup_main_ui(self):
        """Thiết lập giao diện chính của ứng dụng"""
        # Thanh bên trái cho danh sách kênh (chiếm 25% chiều rộng)
        self.sidebar_frame = ttk.Frame(self.main_frame, width=300)
        self.sidebar_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        
        # Phần thông tin người dùng
        self.user_frame = ttk.LabelFrame(self.sidebar_frame, text="Thông tin người dùng")
        self.user_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.username_label = ttk.Label(self.user_frame, text="Chưa đăng nhập")
        self.username_label.pack(anchor=tk.W, padx=5, pady=2)
        
        # Add status display
        self.current_status_label = ttk.Label(self.user_frame, text="Status: Online", style="Status.TLabel")
        self.current_status_label.pack(anchor=tk.W, padx=5, pady=2)
        
        # Add change status button
        self.change_status_button = ttk.Button(self.user_frame, text="Change Status", command=self.change_status)
        self.change_status_button.pack(side=tk.RIGHT, padx=5)

        # Phần danh sách kênh
        self.channels_frame = ttk.LabelFrame(self.sidebar_frame, text="Danh sách kênh")
        self.channels_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Listbox hiển thị danh sách kênh đã tham gia
        self.channel_listbox = tk.Listbox(self.channels_frame, selectmode=tk.SINGLE, 
                                        bg="white", fg="#333333", font=("Arial", 10))
        self.channel_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.channel_listbox.bind("<<ListboxSelect>>", self.on_channel_select)
        
        # Frame chứa các nút cho kênh
        self.channel_buttons_frame = ttk.Frame(self.channels_frame)
        self.channel_buttons_frame.pack(fill=tk.X, padx=5, pady=5)

        self.create_button = ttk.Button(self.channel_buttons_frame, text="Tạo kênh", command=self.create_channel_dialog)
        self.create_button.pack(side=tk.LEFT, padx=2)
        
        self.join_button = ttk.Button(self.channel_buttons_frame, text="Tham gia kênh", command=self.join_channel_dialog)
        self.join_button.pack(side=tk.LEFT, padx=2)
        
        self.refresh_button = ttk.Button(self.channel_buttons_frame, text="Làm mới", command=self.refresh_peers)
        self.refresh_button.pack(side=tk.LEFT, padx=2)
        
        # Phần danh sách peer
        self.peers_frame = ttk.LabelFrame(self.sidebar_frame, text="Danh sách người dùng online")
        self.peers_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.peers_listbox = tk.Listbox(self.peers_frame, selectmode=tk.SINGLE,
                                    bg="white", fg="#333333", font=("Arial", 10))
        self.peers_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Frame chính bên phải (chiếm 75% chiều rộng)
        self.content_frame = ttk.Frame(self.main_frame)
        self.content_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Thông tin kênh hiện tại
        self.channel_info_frame = ttk.Frame(self.content_frame)
        self.channel_info_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.current_channel_label = ttk.Label(self.channel_info_frame, text="Chưa chọn kênh", style="Channel.TLabel")
        self.current_channel_label.pack(side=tk.LEFT, padx=5)
        
        self.channel_owner_label = ttk.Label(self.channel_info_frame, text="", style="Status.TLabel")
        self.channel_owner_label.pack(side=tk.RIGHT, padx=5)

        # Tạo frame chứa cả khu vực video và chat
        self.main_content_frame = ttk.Frame(self.content_frame)
        self.main_content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Frame cho live stream - Chiếm khoảng 45% chiều cao
        self.video_frame = ttk.LabelFrame(self.main_content_frame, text="Live Stream")
        self.video_frame.pack(fill=tk.BOTH, expand=False, padx=5, pady=5)

        # Tạo frame để hiển thị video với border
        self.video_display_frame = tk.Frame(self.video_frame, bg="black", bd=2, relief=tk.SUNKEN, height=350)
        self.video_display_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.video_display_frame.pack_propagate(False)  # Ngăn không cho frame co lại kích thước của nội dung
        
        # Label để hiển thị video với background màu đen
        self.video_label = tk.Label(self.video_display_frame, bg="black")
        self.video_label.pack(fill=tk.BOTH, expand=True)
        self.video_label.pack(fill=tk.BOTH, expand=True)

        # Thêm frame điều khiển stream
        self.stream_controls_frame = ttk.Frame(self.video_frame)
        self.stream_controls_frame.pack(fill=tk.X, padx=5, pady=5)

        # Nút điều khiển stream với style tùy chỉnh
        self.start_stream_button = ttk.Button(
            self.stream_controls_frame, 
            text="Start Live Stream", 
            command=self.start_streaming,
            style="Stream.TButton"
        )
        self.start_stream_button.pack(side=tk.LEFT, padx=5)

        self.stop_stream_button = ttk.Button(
            self.stream_controls_frame, 
            text="Stop Streaming", 
            command=self.stop_streaming,
            style="Stop.TButton"
        )
        self.stop_stream_button.pack(side=tk.LEFT, padx=5)
        self.stop_stream_button.config(state=tk.DISABLED)

        # Hiển thị thông tin stream
        self.stream_info_label = ttk.Label(
            self.stream_controls_frame, 
            text="No active stream",
            style="Status.TLabel"
        )
        self.stream_info_label.pack(side=tk.RIGHT, padx=5)
        
        # Khu vực hiển thị tin nhắn - Chiếm phần còn lại của chiều cao
        self.messages_frame = ttk.LabelFrame(self.main_content_frame, text="Tin nhắn")
        self.messages_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Text hiển thị tin nhắn với style tùy chỉnh
        self.messages_text = scrolledtext.ScrolledText(
            self.messages_frame, 
            wrap=tk.WORD, 
            state=tk.DISABLED, 
            height=10,
            bg="white",
            fg="#333333",
            font=("Arial", 10)
        )
        self.messages_text.pack(fill=tk.BOTH, expand=True)
        
        # Khu vực nhập tin nhắn
        self.input_frame = ttk.Frame(self.content_frame)
        self.input_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.message_entry = ttk.Entry(self.input_frame, font=("Arial", 10))
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        self.send_button = ttk.Button(self.input_frame, text="Gửi", command=self.send_message)
        self.send_button.pack(side=tk.RIGHT, padx=5)

        # Bind phím Enter để gửi tin nhắn
        self.message_entry.bind("<Return>", lambda event: self.send_message())
        
    def show_login_screen(self):
        """Hiển thị màn hình đăng nhập"""
        # Ẩn giao diện chính
        self.main_frame.pack_forget()
        
        # Hiển thị giao diện đăng nhập
        self.login_frame.pack(fill=tk.BOTH, expand=True)
        
        # Xóa các widget cũ
        for widget in self.login_frame.winfo_children():
            widget.destroy()
            
        # Tạo các widget đăng nhập
        ttk.Label(self.login_frame, text="P2P Chat Login", font=("TkDefaultFont", 16, "bold")).pack(pady=20)
        
        login_inner_frame = ttk.Frame(self.login_frame)
        login_inner_frame.pack(padx=50, pady=20)
        
        ttk.Label(login_inner_frame, text="Username:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.username_entry = ttk.Entry(login_inner_frame, width=30)
        self.username_entry.grid(row=0, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(login_inner_frame, text="Password:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.password_entry = ttk.Entry(login_inner_frame, width=30, show="*")
        self.password_entry.grid(row=1, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(login_inner_frame, text="Tracker IP:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.tracker_ip_entry = ttk.Entry(login_inner_frame, width=30)
        self.tracker_ip_entry.insert(0, "127.0.0.1")
        
        self.tracker_ip_entry.grid(row=2, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(login_inner_frame, text="Tracker Port:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.tracker_port_entry = ttk.Entry(login_inner_frame, width=30)
        self.tracker_port_entry.insert(0, "22110")
        self.tracker_port_entry.grid(row=3, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(login_inner_frame, text="Local Port:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.local_port_entry = ttk.Entry(login_inner_frame, width=30)
        self.local_port_entry.insert(0, "20000")
        self.local_port_entry.grid(row=4, column=1, sticky=tk.W, pady=5)

        # Thêm lựa chọn trạng thái khi đăng nhập
        ttk.Label(login_inner_frame, text="Status:").grid(row=5, column=0, sticky=tk.W, pady=5)
        status_frame = ttk.Frame(login_inner_frame)
        status_frame.grid(row=5, column=1, sticky=tk.W)
        
        self.status_var = tk.StringVar(value="online")
        ttk.Radiobutton(status_frame, text="Online", variable=self.status_var, value="online").grid(row=0, column=0, sticky=tk.W)
        ttk.Radiobutton(status_frame, text="Invisible", variable=self.status_var, value="invisible").grid(row=0, column=1, sticky=tk.W)
        ttk.Radiobutton(status_frame, text="Offline", variable=self.status_var, value="offline").grid(row=0, column=2, sticky=tk.W)
        
        buttons_frame = ttk.Frame(login_inner_frame)
        buttons_frame.grid(row=6, column=0, columnspan=2, pady=20)
        
        ttk.Button(buttons_frame, text="Đăng nhập", command=self.login).pack(side=tk.LEFT, padx=10)
        ttk.Button(buttons_frame, text="Đăng nhập với chế độ khách", command=self.login_as_guest).pack(side=tk.LEFT, padx=10)
        
        # Thông tin demo
        ttk.Label(self.login_frame, text="Các tài khoản mẫu: alice/password1, bob/password2, charlie/password3").pack(pady=10)
        
    def login(self):
        """Xử lý đăng nhập thông thường"""
        self.do_login(is_guest=False)
        
    def login_as_guest(self):
        """Xử lý đăng nhập khách"""
        self.do_login(is_guest=True)
        
    def do_login(self, is_guest=False):
        """Xử lý đăng nhập"""
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip() if not is_guest else ""
        tracker_ip = self.tracker_ip_entry.get().strip()
        
        tracker_port = int(self.tracker_port_entry.get().strip())
        local_port = int(self.local_port_entry.get().strip())

        user_status = self.status_var.get()
            
        if not username:
            messagebox.showerror("Lỗi", "Username không được trống")
            return
            
        if not is_guest and not password:
            messagebox.showerror("Lỗi", "Password không được trống")
            return
        
        # Khởi tạo PeerClient
        self.peer_client = PeerClient(
            username=username,
            password=password,
            tracker_ip=tracker_ip,
            tracker_port=tracker_port,
            local_port=local_port,
            is_guest=is_guest,
            message_handler=self.handle_new_message,
            user_status=user_status
        )
        
        # Khởi động PeerClient
        if self.peer_client.start():
            self.show_main_ui()
            self.refresh_peers()
        else:
            messagebox.showerror("Lỗi", "Đăng nhập thất bại. Vui lòng kiểm tra thông tin đăng nhập.")

        if self.peer_client:
            self.peer_client.peer_server.video_callback = self.handle_video_frame
    
    def handle_new_message(self, message):
        """Xử lý khi có tin nhắn mới"""
        # Cập nhật hiển thị tin nhắn nếu đang ở kênh tương ứng
        if self.peer_client and self.peer_client.current_channel == message.channel:
            self.update_messages_display()
            
    def show_main_ui(self):
        """Hiển thị giao diện chính sau khi đăng nhập thành công"""
        # Ẩn giao diện đăng nhập
        self.login_frame.pack_forget()
        
        # Hiển thị giao diện chính
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Cập nhật thông tin người dùng
        mode = "Khách" if self.peer_client.is_guest else "Người dùng"
        self.username_label.config(text=f"Tên: {self.peer_client.username} ({mode})")
        self.current_status_label.config(text=f"Status: {self.peer_client.user_status}")
        
        # Cập nhật danh sách kênh đã tham gia
        self.update_channel_list()
        
        # Chọn kênh đầu tiên nếu có
        if len(self.peer_client.channels) > 0:
            first_channel = next(iter(self.peer_client.channels))
            self.switch_channel(first_channel)
        
    def refresh_peers(self):
        """Cập nhật danh sách peer và kênh"""
        if not self.peer_client:
            return
            
        # Lấy danh sách peer
        peers = self.peer_client.get_peers()
        
        # Cập nhật danh sách peer
        self.peers_listbox.delete(0, tk.END)
        for peer in peers:
            username, ip, port, session_id, mode,status = peer
            # Bỏ qua chính mình
            if session_id == self.peer_client.session_id or status == "invisible" or status == "offline":
                continue
            self.peers_listbox.insert(tk.END, f"{username} ({ip}:{port}) - {mode}")
        
        # Cập nhật danh sách kênh
        self.update_channel_list()
    def update_channel_info(self, channel_name):
        """Cập nhật thông tin kênh trên giao diện"""
        if not self.peer_client or not channel_name:
            return
            
        # Hiển thị tên kênh
        self.current_channel_label.config(text=f"Kênh: {channel_name}")
        
        # Kiểm tra xem người dùng hiện tại có phải chủ kênh không
        is_owner = self.peer_client.is_host(channel_name)
        
        # Kiểm tra và điều chỉnh trạng thái nút stream dựa trên quyền sở hữu kênh
        if is_owner:
            self.start_stream_button.config(state=tk.NORMAL)
            self.channel_owner_label.config(text="Bạn là chủ kênh (Có quyền phát trực tiếp)")
        else:
            self.start_stream_button.config(state=tk.DISABLED)
            # Tìm thông tin chủ kênh từ database
            owner_name = None
            if self.peer_client.db_manager:
                owner_name = self.peer_client.db_manager.get_channel_owner(channel_name)
            
            if owner_name:
                self.channel_owner_label.config(text=f"Chủ kênh: {owner_name} (Chỉ chủ kênh mới có quyền phát trực tiếp)")
            else:
                self.channel_owner_label.config(text="Bạn không phải chủ kênh (Không có quyền phát trực tiếp)")        
            
    def join_channel_dialog(self):
        """Hiển thị hộp thoại để tham gia kênh"""
        channel_name = simpledialog.askstring("Tham gia kênh", "Nhập tên kênh:")
        if channel_name:
            self.join_channel(channel_name)
            
    def join_channel(self, channel_name):
        """Tham gia kênh chat"""
        if not self.peer_client:
            return
            
        if self.peer_client.join_channel(channel_name):
            # Cập nhật danh sách kênh
            self.update_channel_list()
            # Cập nhật hiển thị
            self.current_channel_label.config(text=f"Kênh: {channel_name}")
            # Hiển thị tin nhắn của kênh
            self.update_messages_display()
            messagebox.showinfo("Thành công", f"Đã tham gia kênh '{channel_name}'")
        else:
            messagebox.showerror("Lỗi", f"Không thể tham gia kênh '{channel_name}'")
            
    def update_channel_list(self):
        """Cập nhật danh sách kênh trên giao diện"""
        if not self.peer_client:
            return
            
        self.channel_listbox.delete(0, tk.END)
        
        # Lưu vị trí lựa chọn hiện tại
        current_channel = self.peer_client.current_channel
        index_to_select = 0
        
        # Thêm các kênh vào listbox
        i = 0
        for channel_name in self.peer_client.channels:
            self.channel_listbox.insert(tk.END, channel_name)
            if channel_name == current_channel:
                index_to_select = i
            i += 1
            
        # Chọn kênh hiện tại trong listbox
        if len(self.peer_client.channels) > 0:
            self.channel_listbox.selection_set(index_to_select)
            self.channel_listbox.see(index_to_select)
            
    def on_channel_select(self, event):
        """Xử lý sự kiện khi người dùng chọn một kênh từ danh sách"""
        selected_idx = self.channel_listbox.curselection()
        if not selected_idx:
            return
            
        channel_name = self.channel_listbox.get(selected_idx[0])
        self.switch_channel(channel_name)
        
    def switch_channel(self, channel_name):
        """Chuyển sang kênh đã chọn"""
        if not self.peer_client:
            return
            
        if self.peer_client.switch_channel(channel_name):
            # Cập nhật hiển thị
            self.update_channel_info(channel_name)
            
            # Hiển thị tin nhắn của kênh
            self.update_messages_display()
            
            self.logger.info(f"GUI - Đã chuyển sang kênh '{channel_name}'")
        else:
            messagebox.showerror("Lỗi", f"Kênh '{channel_name}' không tồn tại hoặc bạn chưa tham gia")
            
    # def update_messages_display(self):
    #     """Cập nhật khu vực hiển thị tin nhắn"""
    #     if not self.peer_client or not self.peer_client.current_channel:
    #         return
            
    #     # Lấy danh sách tin nhắn của kênh hiện tại
    #     messages = self.peer_client.get_channel_messages()
        
    #     # Lưu vị trí cuộn hiện tại
    #     current_pos = self.messages_text.yview()
        
    #     # Xóa và cập nhật tin nhắn
    #     self.messages_text.config(state=tk.NORMAL)
    #     self.messages_text.delete(1.0, tk.END)
        
    #     self.logger.info(f"Hiển thị {len(messages)} tin nhắn cho kênh {self.peer_client.current_channel}")
        
    #     # Tạo tags cho định dạng tin nhắn
    #     self.messages_text.tag_configure("timestamp", foreground="#888888", font=("Arial", 9, "italic"))
    #     self.messages_text.tag_configure("username", foreground="#0066CC", font=("Arial", 10, "bold"))
    #     self.messages_text.tag_configure("content", foreground="#333333", font=("Arial", 10))
    #     self.messages_text.tag_configure("status_message", foreground="#1E8449", font=("Arial", 9, "italic"))
        
    #     for message in messages:
    #         # Định dạng thời gian
    #         time_str = message.timestamp
    #         if isinstance(message.timestamp, (int, float)):
    #             time_str = datetime.fromtimestamp(message.timestamp).strftime("%H:%M:%S")
            
    #         # Hiển thị tin nhắn với định dạng màu sắc
    #         self.messages_text.insert(tk.END, f"[{time_str}] ", "timestamp")
    #         self.messages_text.insert(tk.END, f"{message.sender_username}: ", "username")
    #         self.messages_text.insert(tk.END, f"{message.content}\n", "content")
        
    #     self.messages_text.config(state=tk.DISABLED)
        
    #     # Cuộn xuống cuối nếu đang ở cuối
    #     if current_pos[1] == 1.0:
    #         self.messages_text.see(tk.END)
    #     else:
    #         self.messages_text.yview_moveto(current_pos[0])
        
    def update_messages_display(self):
        """Cập nhật khu vực hiển thị tin nhắn"""
        if not self.peer_client or not self.peer_client.current_channel:
            return
            
        # Lấy danh sách tin nhắn của kênh hiện tại
        messages = self.peer_client.get_channel_messages()
        
        # Lưu vị trí cuộn hiện tại
        current_pos = self.messages_text.yview()
        
        # Xóa và cập nhật tin nhắn
        self.messages_text.config(state=tk.NORMAL)
        self.messages_text.delete(1.0, tk.END)
        
        self.logger.info(f"Hiển thị {len(messages)} tin nhắn cho kênh {self.peer_client.current_channel}")
        
        # Tạo tags cho định dạng tin nhắn
        self.messages_text.tag_configure("timestamp", foreground="#888888", font=("Arial", 9, "italic"))
        self.messages_text.tag_configure("username", foreground="#0066CC", font=("Arial", 10, "bold"))
        self.messages_text.tag_configure("content", foreground="#333333", font=("Arial", 10))
        self.messages_text.tag_configure("status_message", foreground="#1E8449", font=("Arial", 9, "italic"))
        
        # Sử dụng một set để theo dõi message_id đã hiển thị
        displayed_messages = set()
        
        for message in messages:
            # Bỏ qua tin nhắn trùng lặp
            if message.id in displayed_messages:
                continue
                
            displayed_messages.add(message.id)
            
            # Định dạng thời gian
            time_str = message.timestamp
            if isinstance(message.timestamp, (int, float)):
                time_str = datetime.fromtimestamp(message.timestamp).strftime("%H:%M:%S")
            
            # Hiển thị tin nhắn với định dạng màu sắc
            self.messages_text.insert(tk.END, f"[{time_str}] ", "timestamp")
            
            # Chỉ hiển thị username một lần
            if message.sender_username:
                self.messages_text.insert(tk.END, f"{message.sender_username}: ", "username")
            
            # Nội dung tin nhắn
            self.messages_text.insert(tk.END, f"{message.content}\n", "content")
        
        self.messages_text.config(state=tk.DISABLED)
        
        # Cuộn xuống cuối nếu đang ở cuối
        if current_pos[1] == 1.0:
            self.messages_text.see(tk.END)
        else:
            self.messages_text.yview_moveto(current_pos[0])
    def send_message(self):
        """Gửi tin nhắn đến tất cả peer trong kênh hiện tại hoặc lưu để gửi sau nếu ở mode invisible/offline"""
        if not self.peer_client:
            return
            
        if self.peer_client.is_guest:
            messagebox.showinfo("Thông báo", "Bạn đang ở chế độ khách và không thể gửi tin nhắn")
            return
            
        if not self.peer_client.current_channel:
            messagebox.showinfo("Thông báo", "Vui lòng chọn một kênh trước khi gửi tin nhắn")
            return
            
        message_text = self.message_entry.get().strip()
        if not message_text:
            return
            
        # Gửi tin nhắn
        if self.peer_client.send_message(message_text):
            # Xóa ô nhập tin nhắn
            self.message_entry.delete(0, tk.END)
            
            # Nếu ở chế độ invisible/offline, hiển thị thông báo
            if self.peer_client.user_status in ["invisible", "offline"]:
                self.messages_text.config(state=tk.NORMAL)
                self.messages_text.insert(tk.END, "--- Tin nhắn được lưu và sẽ gửi khi trở lại online ---\n", "status_message")
                self.messages_text.config(state=tk.DISABLED)
                self.messages_text.see(tk.END)
        else:
            messagebox.showerror("Lỗi", "Không thể gửi tin nhắn")
        
    def on_closing(self):
        """Xử lý khi đóng ứng dụng"""
        if messagebox.askokcancel("Thoát", "Bạn có muốn thoát ứng dụng?"):
            # Dừng PeerClient
            if self.peer_client:
                self.peer_client.stop()
                
            if self.video_stream:
                self.video_stream.stop_streaming()

            self.logger.info("Ứng dụng đã đóng")
            self.root.destroy()

    def change_status(self):
        """Thay đổi trạng thái người dùng giữa 'online', 'invisible', và 'offline'"""
        if not self.peer_client:
            return
            
        # Tạo dialog để chọn trạng thái
        status_dialog = tk.Toplevel(self.root)
        status_dialog.title("Thay đổi trạng thái")
        status_dialog.geometry("350x180")
        status_dialog.resizable(False, False)
        status_dialog.transient(self.root)
        status_dialog.grab_set()
        
        ttk.Label(status_dialog, text="Chọn trạng thái của bạn:").pack(pady=10)
        
        status_var = tk.StringVar(value=self.peer_client.user_status)
        
        ttk.Radiobutton(status_dialog, text="Online - Mọi người đều nhìn thấy bạn", 
                      variable=status_var, value="online").pack(anchor=tk.W, padx=20)
        ttk.Radiobutton(status_dialog, text="Invisible - Ẩn nhưng tin nhắn vẫn được lưu", 
                      variable=status_var, value="invisible").pack(anchor=tk.W, padx=20)
        ttk.Radiobutton(status_dialog, text="Offline - Hiển thị như đã ngắt kết nối", 
                      variable=status_var, value="offline").pack(anchor=tk.W, padx=20)
        
        def on_status_selected():
            new_status = status_var.get()
            if self.peer_client.set_user_status(new_status):
                self.current_status_label.config(text=f"Status: {new_status}")
                
                if new_status == "online" and self.peer_client.offline_messages:
                    count = len(self.peer_client.offline_messages)
                    messagebox.showinfo("Tin nhắn Offline", 
                                       f"Đang gửi {count} tin nhắn đã lưu khi bạn ở chế độ invisible/offline.")
                    
                status_dialog.destroy()
            else:
                messagebox.showerror("Lỗi", "Không thể thay đổi trạng thái")
        
        ttk.Button(status_dialog, text="Thay đổi", command=on_status_selected).pack(pady=10)

    def start_streaming(self):
        """Start streaming video"""
        
        if self.peer_client.is_guest:
            messagebox.showinfo("Thông báo", "Khách không được phép phát trực tiếp!")
            return
            
        if not self.peer_client.current_channel:
            messagebox.showinfo("Thông báo", "Bạn phải tham gia một kênh trước khi phát trực tiếp")
            return
            
        current = self.peer_client.current_channel
        
        # Kiểm tra chặt chẽ xem có phải host không
        if not self.peer_client.is_host(current):
            messagebox.showerror("Lỗi", "Chỉ chủ kênh mới được phép phát trực tiếp!")
            return
                
        # Initialize video stream if not already done
        if not self.video_stream:
            self.video_stream = VideoStream(self.peer_client.username, logger=self.logger)
        
        # Start the video stream
        started = self.video_stream.start_streaming(self.peer_client.send_video_frame)
        if not started:
            messagebox.showerror("Lỗi", "Không thể kết nối với webcam. Vui lòng kiểm tra thiết bị của bạn!")
            return

        # Hiển thị thông báo bắt đầu stream thành công
        self.stream_info_label.config(text=f"Đang phát trực tiếp từ {self.peer_client.username}")
        
        # Cập nhật trạng thái các nút
        self.start_stream_button.config(state=tk.DISABLED)
        self.stop_stream_button.config(state=tk.NORMAL)
        
        # Cập nhật trạng thái stream
        self.stream_active = True
        self.current_stream_username = self.peer_client.username
        
        # Bắt đầu vòng lặp cập nhật video
        self.update_video_frame()
        
        # Hiển thị thông báo thành công
        self.messages_text.config(state=tk.NORMAL)
        self.messages_text.insert(tk.END, "--- Đã bắt đầu phát trực tiếp ---\n", "timestamp")
        self.messages_text.config(state=tk.DISABLED)
        self.messages_text.see(tk.END)
        
        
    def stop_streaming(self):
        """Stop streaming video"""
        if self.video_stream:
            self.video_stream.stop_streaming()
            
        # Hiển thị thông báo kết thúc stream
        self.stream_info_label.config(text="No active stream")
        
        # Cập nhật trạng thái các nút
        self.start_stream_button.config(state=tk.NORMAL)
        self.stop_stream_button.config(state=tk.DISABLED)
        
        # Cập nhật trạng thái stream
        self.stream_active = False
        self.current_stream_username = None
        
        # Xóa video khỏi label - xóa hình ảnh trên màn hình người phát
        self.video_label.config(image="")
        self.video_label.image = None  # Xóa tham chiếu để garbage collection có thể giải phóng bộ nhớ
        
        # Gửi thông báo dừng phát đến tất cả người xem
        # Thêm logic để gửi thông báo dừng phát đến người xem
        self._notify_stream_ended()

        # Hiển thị thông báo
        self.messages_text.config(state=tk.NORMAL)
        self.messages_text.insert(tk.END, "--- Đã dừng phát trực tiếp ---\n", "timestamp")
        self.messages_text.config(state=tk.DISABLED)
        self.messages_text.see(tk.END)
        
    def _notify_stream_ended(self):
        """Thông báo cho tất cả người xem biết stream đã kết thúc"""
        if self.peer_client and self.peer_client.current_channel:
            # Gửi tin nhắn thông báo stream đã kết thúc
            try:
                # Sử dụng phương thức send_message_raw để gửi tin nhắn đặc biệt
                self.peer_client.send_message("--- STREAM_ENDED ---")
                
                # Đảm bảo dừng luồng video và gửi tin nhắn trực tiếp tới tất cả các peer
                if self.peer_client and self.peer_client.current_channel:
                    try:
                        peers = self.peer_client.get_peers()
                        message = f"VIDEO_FRAME:{self.peer_client.current_channel}:{self.peer_client.username}:{time.time()}:STREAM_ENDED"
                        
                        for peer in peers:
                            username, ip, port, session_id, mode, status = peer
                            # Bỏ qua chính mình
                            if session_id == self.peer_client.session_id:
                                continue
                                
                            try:
                                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                                    s.settimeout(1)
                                    s.connect((ip, int(port)))
                                    s.sendall(message.encode())
                            except Exception as e:
                                self.logger.error(f"Error sending stop stream to {username} ({ip}:{port}): {e}")
                    except Exception as e:
                        self.logger.error(f"Error in notify stream ended: {e}")
            except Exception as e:
                self.logger.error(f"Error sending stream ended notification: {e}")
                pass

    def update_video_frame(self):
        """Update the video frame display"""
        if not self.stream_active:
            return
            
        if self.current_stream_username == self.peer_client.username:
            # Local preview
            photo = self.video_stream.get_current_frame_as_tk()
            if photo:
                self.video_label.config(image=photo)
                self.video_label.image = photo  # Keep a reference to prevent garbage collection
        else:
            # Remote stream
            frame_data = self.video_stream.get_next_viewing_frame()
            if frame_data:
                frame, username = frame_data
                try:
                    img = Image.fromarray(frame)
                    photo = ImageTk.PhotoImage(image=img)
                    self.video_label.config(image=photo)
                    self.video_label.image = photo  # Keep a reference
                    self.stream_info_label.config(text=f"Viewing stream from {username}")
                except Exception as e:
                    self.logger.error(f"Error displaying frame: {e}")
                    # Nếu có lỗi hiển thị frame, có thể dừng stream
                    if str(e).startswith("cannot identify image file"):
                        self.clear_remote_stream()
                        return
                
        # Schedule next update - Tăng tần suất cập nhật lên 24fps
        self.root.after(42, self.update_video_frame)  # ~30fps for display

    def handle_video_frame(self, frame_data, sender_username):
        """Handle incoming video frame"""
        if not self.video_stream:
            self.video_stream = VideoStream(self.peer_client.username, logger=self.logger)
            
        # Kiểm tra nếu đây là thông báo kết thúc stream
        if frame_data == "STREAM_ENDED" or frame_data == "--- STREAM_ENDED ---":
            # Xử lý kết thúc stream từ người phát
            if self.current_stream_username == sender_username:
                self.clear_remote_stream()
            return
            
        # Process the frame
        self.video_stream.process_received_frame(frame_data, sender_username)
        
        # If not streaming ourselves, start displaying the received stream
        if not self.stream_active or self.current_stream_username != self.peer_client.username:
            self.stream_active = True
            self.current_stream_username = sender_username
            self.stream_info_label.config(text=f"Viewing stream from {sender_username}")
            self.update_video_frame()

    def clear_remote_stream(self):
        """Xóa stream từ xa khi kết thúc"""
        # Xóa hình ảnh hiện tại
        self.video_label.config(image="")
        self.video_label.image = None  # Xóa tham chiếu để garbage collection có thể giải phóng bộ nhớ
        
        # Cập nhật trạng thái
        self.stream_active = False
        self.current_stream_username = None
        self.stream_info_label.config(text="No active stream")
        
        # Hiển thị thông báo
        self.messages_text.config(state=tk.NORMAL)
        self.messages_text.insert(tk.END, "--- Stream đã kết thúc ---\n", "timestamp")
        self.messages_text.config(state=tk.DISABLED)
        self.messages_text.see(tk.END)


    def create_channel_dialog(self):
        """Hiển thị hộp thoại tạo kênh mới"""
        name = simpledialog.askstring("Tạo kênh", "Tên kênh mới:")
        if name:
            success = self.peer_client.create_channel(name)
            if success:
                # Cập nhật danh sách kênh
                self.update_channel_list()
                # Chuyển sang kênh mới
                self.switch_channel(name)
                messagebox.showinfo("Thành công", f"Đã tạo kênh '{name}' và bạn là chủ kênh.")

def main():
    """Hàm chính khởi động ứng dụng"""
    parser = argparse.ArgumentParser(description="P2P Chat Application with GUI")
    
    args = parser.parse_args()

    # Tạo thư mục dữ liệu nếu chưa tồn tại
    os.makedirs("data", exist_ok=True)

    # Khởi động ứng dụng GUI
    root = tk.Tk()
    app = P2PChatGUI(root)
    
    # Thiết lập sự kiện đóng cửa sổ
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    # Chạy vòng lặp sự kiện chính
    root.mainloop()

if __name__ == "__main__":
    main()