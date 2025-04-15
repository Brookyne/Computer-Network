import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog
import threading
import argparse
import logging
import time
import os
from datetime import datetime
from p2p_chat_peer import PeerClient, Message

class P2PChatGUI:
    """Ứng dụng chat P2P với giao diện đồ họa"""
    def __init__(self, root):
        self.root = root
        self.root.title("P2P Chat Application")
        self.root.geometry("1000x700")
        self.root.minsize(800, 600)
        
        # Logger
        self.set_logger()
        
        # Thiết lập các biến trạng thái
        self.peer_client = None
        
        # Thiết lập UI
        self.setup_ui()
        
        # Hiển thị màn hình đăng nhập
        self.show_login_screen()
        
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
        # Thanh bên trái cho danh sách kênh
        self.sidebar_frame = ttk.Frame(self.main_frame, width=250)
        self.sidebar_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        
        # Phần thông tin người dùng
        self.user_frame = ttk.LabelFrame(self.sidebar_frame, text="Thông tin người dùng")
        self.user_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.username_label = ttk.Label(self.user_frame, text="Chưa đăng nhập")
        self.username_label.pack(anchor=tk.W, padx=5, pady=2)
        
        self.status_label = ttk.Label(self.user_frame, text="Trạng thái: Offline")
        self.status_label.pack(anchor=tk.W, padx=5, pady=2)
        
        # Phần danh sách kênh
        self.channels_frame = ttk.LabelFrame(self.sidebar_frame, text="Danh sách kênh")
        self.channels_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Listbox hiển thị danh sách kênh đã tham gia
        self.channel_listbox = tk.Listbox(self.channels_frame, selectmode=tk.SINGLE)
        self.channel_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.channel_listbox.bind("<<ListboxSelect>>", self.on_channel_select)
        
        # Frame chứa các nút cho kênh
        self.channel_buttons_frame = ttk.Frame(self.channels_frame)
        self.channel_buttons_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.join_button = ttk.Button(self.channel_buttons_frame, text="Tham gia kênh", command=self.join_channel_dialog)
        self.join_button.pack(side=tk.LEFT, padx=2)
        
        self.refresh_button = ttk.Button(self.channel_buttons_frame, text="Làm mới", command=self.refresh_peers)
        self.refresh_button.pack(side=tk.LEFT, padx=2)
        
        # Phần danh sách peer
        self.peers_frame = ttk.LabelFrame(self.sidebar_frame, text="Danh sách người dùng online")
        self.peers_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.peers_listbox = tk.Listbox(self.peers_frame, selectmode=tk.SINGLE)
        self.peers_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Frame chính bên phải
        self.content_frame = ttk.Frame(self.main_frame)
        self.content_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Thông tin kênh hiện tại
        self.channel_info_frame = ttk.Frame(self.content_frame)
        self.channel_info_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.current_channel_label = ttk.Label(self.channel_info_frame, text="Chưa chọn kênh", font=("TkDefaultFont", 14, "bold"))
        self.current_channel_label.pack(side=tk.LEFT, padx=5)
        
        # Khu vực hiển thị tin nhắn
        self.messages_frame = ttk.Frame(self.content_frame)
        self.messages_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.messages_text = scrolledtext.ScrolledText(self.messages_frame, wrap=tk.WORD, state=tk.DISABLED)
        self.messages_text.pack(fill=tk.BOTH, expand=True)
        
        # Khu vực nhập tin nhắn
        self.input_frame = ttk.Frame(self.content_frame)
        self.input_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.message_entry = ttk.Entry(self.input_frame)
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
        self.tracker_port_entry.insert(0, "12345")
        self.tracker_port_entry.grid(row=3, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(login_inner_frame, text="Local Port:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.local_port_entry = ttk.Entry(login_inner_frame, width=30)
        self.local_port_entry.insert(0, "20000")
        self.local_port_entry.grid(row=4, column=1, sticky=tk.W, pady=5)
        
        buttons_frame = ttk.Frame(login_inner_frame)
        buttons_frame.grid(row=5, column=0, columnspan=2, pady=20)
        
        ttk.Button(buttons_frame, text="Đăng nhập", command=self.login).pack(side=tk.LEFT, padx=10)
        ttk.Button(buttons_frame, text="Đăng nhập khách", command=self.login_as_guest).pack(side=tk.LEFT, padx=10)
        
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
        
        try:
            tracker_port = int(self.tracker_port_entry.get().strip())
            local_port = int(self.local_port_entry.get().strip())
        except ValueError:
            messagebox.showerror("Lỗi", "Port phải là số nguyên")
            return
            
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
            message_handler=self.handle_new_message
        )
        
        # Khởi động PeerClient
        if self.peer_client.start():
            self.show_main_ui()
            self.refresh_peers()
        else:
            messagebox.showerror("Lỗi", "Đăng nhập thất bại. Vui lòng kiểm tra thông tin đăng nhập.")
    
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
        self.status_label.config(text=f"Trạng thái: Online | IP: {self.peer_client.local_ip}:{self.peer_client.local_port}")
        
    def refresh_peers(self):
        """Cập nhật danh sách peer và kênh"""
        if not self.peer_client:
            return
            
        # Lấy danh sách peer
        peers = self.peer_client.get_peers()
        
        # Cập nhật danh sách peer
        self.peers_listbox.delete(0, tk.END)
        for peer in peers:
            username, ip, port, session_id, mode = peer
            # Bỏ qua chính mình
            if session_id == self.peer_client.session_id:
                continue
            self.peers_listbox.insert(tk.END, f"{username} ({ip}:{port}) - {mode}")
        
        # Cập nhật danh sách kênh
        self.update_channel_list()
            
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
            self.current_channel_label.config(text=f"Kênh: {channel_name}")
            
            # Hiển thị tin nhắn của kênh
            self.update_messages_display()
            
            self.logger.info(f"GUI - Đã chuyển sang kênh '{channel_name}'")
        else:
            messagebox.showerror("Lỗi", f"Kênh '{channel_name}' không tồn tại hoặc bạn chưa tham gia")
            
    def update_messages_display(self):
        """Cập nhật khu vực hiển thị tin nhắn"""
        if not self.peer_client or not self.peer_client.current_channel:
            return
            
        # Lấy danh sách tin nhắn của kênh hiện tại
        messages = self.peer_client.get_channel_messages()
        
        # Xóa và cập nhật tin nhắn
        self.messages_text.config(state=tk.NORMAL)
        self.messages_text.delete(1.0, tk.END)
        
        self.logger.info(f"Hiển thị {len(messages)} tin nhắn cho kênh {self.peer_client.current_channel}")
        
        for message in messages:
            formatted_msg = message.format() + "\n"
            self.messages_text.insert(tk.END, formatted_msg)
            
        self.messages_text.config(state=tk.DISABLED)
        
        # Cuộn xuống cuối
        self.messages_text.see(tk.END)
        
    def send_message(self):
        """Gửi tin nhắn đến tất cả peer trong kênh hiện tại"""
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
        else:
            messagebox.showerror("Lỗi", "Không thể gửi tin nhắn")
        
    def on_closing(self):
        """Xử lý khi đóng ứng dụng"""
        if messagebox.askokcancel("Thoát", "Bạn có muốn thoát ứng dụng?"):
            # Dừng PeerClient
            if self.peer_client:
                self.peer_client.stop()
                
            self.logger.info("Ứng dụng đã đóng")
            self.root.destroy()



def main():
    """Hàm chính khởi động ứng dụng"""
    parser = argparse.ArgumentParser(description="P2P Chat Application with GUI")
    
    args = parser.parse_args()
    
    
    
    # Khởi động ứng dụng GUI
    root = tk.Tk()
    app = P2PChatGUI(root)
    
    # Thiết lập sự kiện đóng cửa sổ
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    # Chạy vòng lặp sự kiện chính
    root.mainloop()

if __name__ == "__main__":
    main()