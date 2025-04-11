# P2P Chat Application

Ứng dụng chat P2P với tính năng đa kênh và hỗ trợ đăng nhập khách.

## Tổng quan

Ứng dụng P2P Chat cho phép người dùng kết nối và trò chuyện với nhau trực tiếp qua mạng peer-to-peer, với sự hỗ trợ của một máy chủ tracker trung tâm. Ứng dụng bao gồm các tính năng chính sau:

- Trao đổi tin nhắn trực tiếp giữa các người dùng (P2P)
- Hỗ trợ nhiều kênh chat
- Đăng nhập thông thường và đăng nhập khách
- Giao diện đồ họa thân thiện với người dùng

## Cài đặt

### Yêu cầu

- Python 3.6 trở lên
- Các thư viện Python: tkinter

### Cài đặt thư viện cần thiết

```bash
pip install tk
```

Thư viện tkinter thường đã được cài đặt sẵn với Python, nếu không bạn có thể cài đặt theo hướng dẫn tùy thuộc vào hệ điều hành.

## Các thành phần của ứng dụng

1. **tracker.py**: Máy chủ Tracker - quản lý đăng nhập và thông tin của các peer
2. **p2p_chat_peer.py**: Phần logic P2P - xử lý kết nối và trao đổi tin nhắn giữa các peer
3. **p2p_chat_gui.py**: Giao diện người dùng đồ họa

## Cách sử dụng

### 1. Khởi động máy chủ Tracker

Để khởi động một máy chủ Tracker riêng, chạy lệnh:

```bash
python tracker.py
```

Máy chủ Tracker mặc định sẽ lắng nghe trên cổng 12345.

### 2. Khởi động ứng dụng Client với Tracker tích hợp

Để chạy ứng dụng với một máy chủ Tracker tích hợp, sử dụng lệnh:

```bash
python p2p_chat_gui.py --start-tracker
```

### 3. Khởi động chỉ ứng dụng Client

Để chạy ứng dụng client kết nối đến một máy chủ Tracker hiện có:

```bash
python p2p_chat_gui.py
```

### 4. Đăng nhập và bắt đầu chat

1. **Đăng nhập**: Nhập thông tin đăng nhập, hoặc chọn "Đăng nhập khách"
   - Tài khoản mẫu: alice/password1, bob/password2, charlie/password3
   - Mỗi instance của ứng dụng cần một cổng khác nhau

2. **Tham gia kênh chat**:
   - Nhấn "Tham gia kênh" và nhập tên kênh
   - Hoặc chọn một kênh đã tham gia từ danh sách

3. **Gửi tin nhắn**:
   - Chọn kênh muốn chat
   - Nhập tin nhắn và nhấn "Gửi" hoặc phím Enter

## Thao tác chi tiết

### Đăng nhập

1. Khởi động ứng dụng
2. Nhập thông tin:
   - **Username**: Tên đăng nhập
   - **Password**: Mật khẩu (chỉ cần khi đăng nhập thông thường)
   - **Tracker IP**: Địa chỉ của máy chủ Tracker (mặc định: 127.0.0.1)
   - **Tracker Port**: Cổng của máy chủ Tracker (mặc định: 12345)
   - **Local Port**: Cổng để peer lắng nghe (ví dụ: 20000, 20001, ...)
3. Nhấn "Đăng nhập" hoặc "Đăng nhập khách"

### Tham gia và chuyển đổi kênh

1. Nhấn "Tham gia kênh"
2. Nhập tên kênh (ví dụ: "general", "help", "random")
3. Chọn kênh từ danh sách để chuyển đổi

### Gửi và nhận tin nhắn

1. Đảm bảo đã chọn một kênh (hiển thị ở đầu khu vực tin nhắn)
2. Nhập tin nhắn vào ô nhập liệu ở dưới cùng
3. Nhấn "Gửi" hoặc phím Enter để gửi tin nhắn
4. Tin nhắn sẽ được gửi đến tất cả người dùng cùng tham gia kênh đó

### Xem danh sách người dùng online

- Danh sách người dùng đang online hiển thị ở bên trái giao diện
- Nhấn "Làm mới" để cập nhật danh sách

## Lưu ý

- Người dùng ở chế độ khách (Guest) chỉ có thể xem tin nhắn, không thể gửi tin nhắn
- Mỗi instance của ứng dụng cần một cổng Local Port khác nhau
- Tin nhắn chỉ được nhận sau khi tham gia kênh, không thể xem tin nhắn cũ

## Xử lý sự cố

### Không thể kết nối tới Tracker

- Kiểm tra địa chỉ IP và cổng của máy chủ Tracker
- Đảm bảo máy chủ Tracker đang chạy
- Kiểm tra tường lửa và cài đặt mạng

### Không nhận được tin nhắn

- Kiểm tra đã tham gia đúng kênh chưa 
- Nhấn "Làm mới" để cập nhật danh sách peer
- Kiểm tra log trong thư mục "logs"

### Lỗi đăng nhập

- Đảm bảo đã nhập đúng username và password
- Thử đăng nhập ở chế độ khách

## Log và Debug

Ứng dụng tự động tạo và lưu các file log trong thư mục "logs". Kiểm tra các file này để theo dõi quá trình gửi và nhận tin nhắn khi gặp vấn đề.

## Mở rộng

Dự án này có thể được mở rộng với các tính năng như:
- Truyền file
- Tin nhắn riêng tư
- Mã hóa tin nhắn
- Giao diện người dùng nâng cao

---

© 2025 P2P Chat Application