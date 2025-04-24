"""


Ứng dụng này sử dụng:
1. Flask - Web framework
2. Flask-SocketIO - Socket.IO integration cho Flask
3. HTML/CSS/JavaScript - Frontend
"""

# QUAN TRỌNG: Thực hiện monkey patching trước khi import bất kỳ module nào khác
import eventlet
eventlet.monkey_patch()

# Sau đó mới import các module khác
import base64
import time
import os
import threading
import logging
import socket
import json
from flask import Flask, render_template, request, Response, redirect, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room

# Thiết lập logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Khởi tạo Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
# Tăng kích thước buffer cho socket để xử lý frame lớn
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=60, 
                   ping_interval=10, max_http_buffer_size=10 * 1024 * 1024,
                   async_mode='eventlet')

# Lưu trữ thông tin các phòng chat và người dùng
rooms = {}
users = {}

# Lưu trữ streams
active_streams = {}

# Lưu trữ frame gần nhất của livestream để gửi cho người dùng mới
latest_frames = {}

# Giám sát frame đã gửi
frame_stats = {}

# Hàm lấy địa chỉ IP của máy
def get_ip_address():
    try:
        # Thử cách 1: Sử dụng socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        # Thử cách 2: Lấy qua interfaces
        try:
            import netifaces
            interfaces = netifaces.interfaces()
            for interface in interfaces:
                # Bỏ qua loopback
                if interface.startswith('lo'):
                    continue
                
                addresses = netifaces.ifaddresses(interface)
                if netifaces.AF_INET in addresses:
                    ip = addresses[netifaces.AF_INET][0]['addr']
                    # Bỏ qua địa chỉ 127.0.0.1
                    if not ip.startswith('127.'):
                        return ip
        except:
            pass
        
        # Nếu không tìm thấy, trả về localhost
        return "127.0.0.1"

# Trang chủ
@app.route('/')
def index():
    server_ip = get_ip_address()
    return render_template('index.html', server_ip=server_ip)

# Phòng chat
@app.route('/chat/<room_id>')
def chat_room(room_id):
    username = request.args.get('username', '')
    if not username:
        return redirect(url_for('index', error="Vui lòng nhập tên trước khi tham gia phòng chat"))
    
    # Tạo phòng nếu chưa tồn tại
    if room_id not in rooms:
        rooms[room_id] = {"users": [], "messages": []}
    
    server_ip = get_ip_address()
    return render_template('chat.html', username=username, room=room_id, server_ip=server_ip)

# Xử lý sự kiện kết nối
@socketio.on('connect')
def handle_connect():
    logger.info(f"Client connected: {request.sid}")

# Xử lý sự kiện ngắt kết nối
@socketio.on('disconnect')
def handle_disconnect():
    for room_id in list(rooms.keys()):
        if request.sid in users and users[request.sid]["room"] == room_id:
            leave_room_handler(room_id)
    
    # Dừng livestream nếu người dùng đang stream
    if request.sid in active_streams:
        active_streams[request.sid]["active"] = False
        room_id = active_streams[request.sid]["room"]
        username = active_streams[request.sid]["username"]
        del active_streams[request.sid]
        socketio.emit('stream_ended', {"username": username}, room=room_id)
        
        # Xóa thống kê frame
        if request.sid in frame_stats:
            del frame_stats[request.sid]
    
    if request.sid in users:
        del users[request.sid]
    
    logger.info(f"Client disconnected: {request.sid}")

# Xử lý sự kiện tham gia phòng
@socketio.on('join_room')
def handle_join_room(data):
    room_id = data['room']
    username = data['username']
    
    join_room(room_id)
    users[request.sid] = {"username": username, "room": room_id}
    
    if room_id not in rooms:
        rooms[room_id] = {"users": [], "messages": []}
    
    rooms[room_id]["users"].append(username)
    
    # Thông báo người dùng mới tham gia
    message = f"{username} đã tham gia phòng chat"
    rooms[room_id]["messages"].append({"user": "System", "message": message})
    
    emit('update_users', rooms[room_id]["users"], room=room_id)
    emit('message', {"user": "System", "message": message}, room=room_id)
    
    # Gửi lịch sử tin nhắn cho người dùng mới
    for message in rooms[room_id]["messages"]:
        emit('message', message, room=request.sid)
    
    # Kiểm tra nếu có livestream đang diễn ra trong phòng
    for user_id, stream_info in active_streams.items():
        if stream_info["room"] == room_id and stream_info["active"]:
            # Thông báo cho người dùng mới về livestream đang diễn ra
            emit('stream_started', {"username": stream_info["username"]}, room=request.sid)
            
            # Gửi frame gần nhất nếu có
            if room_id in latest_frames:
                emit('stream_frame', {"frame": latest_frames[room_id]}, room=request.sid)
                logger.info(f"Gửi frame gần nhất cho người dùng mới {username} trong phòng {room_id}")
    
    logger.info(f"User {username} joined room {room_id}")

# Xử lý sự kiện rời phòng
@socketio.on('leave_room')
def leave_room_handler(room_id=None):
    if not room_id:
        data = request.get_json()
        room_id = data['room']
    
    if request.sid in users:
        username = users[request.sid]["username"]
        leave_room(room_id)
        
        if room_id in rooms and username in rooms[room_id]["users"]:
            rooms[room_id]["users"].remove(username)
            message = f"{username} đã rời phòng chat"
            rooms[room_id]["messages"].append({"user": "System", "message": message})
            
            emit('update_users', rooms[room_id]["users"], room=room_id)
            emit('message', {"user": "System", "message": message}, room=room_id)
            
            # Xóa phòng nếu không còn ai
            if not rooms[room_id]["users"]:
                del rooms[room_id]
        
        logger.info(f"User {username} left room {room_id}")

# Xử lý sự kiện gửi tin nhắn
@socketio.on('send_message')
def handle_send_message(data):
    room_id = data['room']
    message = data['message']
    
    if request.sid in users and room_id in rooms:
        username = users[request.sid]["username"]
        message_data = {"user": username, "message": message}
        rooms[room_id]["messages"].append(message_data)
        
        emit('message', message_data, room=room_id)
        logger.info(f"Message in room {room_id} from {username}: {message}")

# Xử lý bắt đầu livestream
@socketio.on('start_stream')
def handle_start_stream(data):
    room_id = data['room']
    
    if request.sid in users and room_id in rooms:
        username = users[request.sid]["username"]
        
        # Kiểm tra nếu đã có người đang stream trong phòng
        for user_id, stream_info in active_streams.items():
            if stream_info["room"] == room_id and stream_info["active"]:
                emit('stream_error', {"message": "Đã có người đang stream trong phòng này"})
                return
        
        # Tạo stream mới
        active_streams[request.sid] = {
            "username": username,
            "room": room_id,
            "active": True,
            "start_time": time.time()
        }
        
        # Khởi tạo thống kê frame
        frame_stats[request.sid] = {
            "frames_sent": 0,
            "last_frame_time": time.time()
        }
        
        # Thông báo cho cả phòng
        emit('stream_started', {"username": username}, room=room_id)
        logger.info(f"User {username} started streaming in room {room_id}")

# Xử lý kết thúc livestream
@socketio.on('end_stream')
def handle_end_stream():
    if request.sid in active_streams:
        room_id = active_streams[request.sid]["room"]
        username = active_streams[request.sid]["username"]
        start_time = active_streams[request.sid]["start_time"]
        
        # Tính thống kê
        duration = time.time() - start_time
        frames_sent = frame_stats.get(request.sid, {}).get("frames_sent", 0)
        fps = frames_sent / duration if duration > 0 else 0
        
        active_streams[request.sid]["active"] = False
        del active_streams[request.sid]
        
        # Xóa frame gần nhất
        if room_id in latest_frames:
            del latest_frames[room_id]
        
        # Thông báo cho cả phòng
        emit('stream_ended', {"username": username}, room=room_id)
        logger.info(f"User {username} ended streaming in room {room_id}. Stats: {frames_sent} frames, {duration:.2f}s, {fps:.2f} fps")
        
        # Xóa thống kê
        if request.sid in frame_stats:
            del frame_stats[request.sid]

# Xử lý dữ liệu video stream
@socketio.on('stream_data')
def handle_stream_data(data):
    if request.sid not in active_streams or not active_streams[request.sid]["active"]:
        return
    
    room_id = active_streams[request.sid]["room"]
    frame_data = data.get('frame', '')
    
    # Kiểm tra frame có hợp lệ không
    if not frame_data or not isinstance(frame_data, str) or not frame_data.startswith('data:image'):
        logger.warning(f"Nhận được frame không hợp lệ từ {request.sid}")
        return
    
    # Cập nhật thống kê
    if request.sid in frame_stats:
        frame_stats[request.sid]["frames_sent"] += 1
        frame_stats[request.sid]["last_frame_time"] = time.time()
    
    # Lưu frame gần nhất
    latest_frames[room_id] = frame_data
    
    # Gửi frame đến tất cả người dùng trong phòng
    emit('stream_frame', {"frame": frame_data, "timestamp": int(time.time() * 1000)}, 
         room=room_id, include_self=False)
    
    # Log để debug (định kỳ để không quá tải log)
    if frame_stats.get(request.sid, {}).get("frames_sent", 0) % 50 == 0:
        logger.info(f"Đã gửi {frame_stats[request.sid]['frames_sent']} frames cho phòng {room_id}")

# Xử lý xác nhận đã nhận frame
@socketio.on('frame_received')
def handle_frame_received(data):
    if request.sid in users:
        room_id = users[request.sid]["room"]
        username = users[request.sid]["username"]
        
        # Thông báo cho người stream
        for streamer_id, stream_info in active_streams.items():
            if stream_info["room"] == room_id and stream_info["active"]:
                emit('viewer_received_frame', {
                    "username": username,
                    "timestamp": data.get("timestamp", 0)
                }, room=streamer_id)
                break

# Tạo templates khi chạy ứng dụng
def create_templates():
    # Tạo thư mục templates nếu chưa tồn tại
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    # Tạo file index.html
    

# Khởi động server
if __name__ == '__main__':
    try:
        # Cố gắng cài đặt các thư viện cần thiết
        try:
            import netifaces
        except ImportError:
            print("Đang cài đặt thư viện netifaces...")
            import subprocess
            subprocess.check_call(["pip", "install", "netifaces"])
            import netifaces
        
        # Tạo các file template
        create_templates()
        
        server_ip = get_ip_address()
        print(f"=== Chat App với Livestream - Phiên bản sửa lỗi ===")
        print(f"Máy chủ đang chạy tại địa chỉ IP: {server_ip}")
        print(f"Truy cập ứng dụng tại: http://{server_ip}:5000")
        print(f"Máy khác trong mạng LAN có thể truy cập qua địa chỉ này.")
        print("=== Nhấn Ctrl+C để thoát ===")
        
        # Khởi động server
        socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        print("\nĐã dừng server.")
    except Exception as e:
        print(f"Lỗi khi khởi động server: {e}")