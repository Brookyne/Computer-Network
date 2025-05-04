# live_stream.py (File đầy đủ)
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
from tkinter import scrolledtext
import cv2
import socket
import threading
import time
import pickle
import struct
import base64
import numpy as np
from PIL import Image, ImageTk
import io
import queue
import logging

class VideoStream:
    """Handles video streaming for the P2P chat application"""
    def __init__(self, username, logger=None):
        self.username = username
        self.streaming = False
        self.viewing = False
        self.camera = None
        self.stream_thread = None
        self.view_threads = {} 
        self.frame_queue = queue.Queue(maxsize=10)  
        self.logger = logger or logging.getLogger(f"VideoStream_{username}")
        self.frame_display_callback = None
        self.current_frame = None
        self.video_stream = None
        self.current_stream_username = None
        self.stream_active = False
        
    def start_camera(self):
        """Initialize the webcam"""
        try:
            self.camera = cv2.VideoCapture(0)  # open webcam (0 for webcam)
            if not self.camera.isOpened():
                self.logger.error("Could not open webcam")
                return False
            return True
        except Exception as e:
            self.logger.error(f"Error starting camera: {e}")
            return False
    
    def stop_camera(self):
        """Release the webcam"""
        if self.camera:
            self.camera.release()
            self.camera = None
            
    def start_streaming(self, send_frame_callback):
        """Start streaming video from webcam"""
        if self.streaming:
            return False
            
        if not self.start_camera():
            return False
            
        self.streaming = True
        self.stream_thread = threading.Thread(target=self._stream_video, args=(send_frame_callback,), daemon=True)
        self.stream_thread.start()
        self.logger.info("Started video streaming")
        return True
        
    def stop_streaming(self):
        """Stop streaming video"""
        self.streaming = False
        if self.stream_thread:
            self.stream_thread = None
        self.stop_camera()
        self.logger.info("Stopped video streaming")
        
    def _stream_video(self, send_frame_callback):
        """Capture and send video frames"""
        prev_time = time.time()
        while self.streaming and self.camera:
            try:
                current_time = time.time()
                # Giảm thời gian chờ để tăng tốc độ khung hình
                if current_time - prev_time < 0.05:  # Cho phép tối đa ~20fps
                    time.sleep(0.01)
                    continue
                    
                prev_time = current_time
                
                # Capture frame
                ret, frame = self.camera.read()
                if not ret:
                    self.logger.error("Failed to capture frame")
                    continue
                
                # QUAN TRỌNG: KHÔNG chuyển đổi BGR sang RGB ở đây
                # Lưu khung hình BGR gốc cho việc hiển thị local (sẽ chuyển đổi sau)
                frame_resized = cv2.resize(frame, (640, 480)) # 480p
                
                self.current_frame = frame_resized
                
                # Nén frame với định dạng JPEG nhưng KHÔNG chuyển màu
                _, buffer = cv2.imencode('.jpg', frame_resized, [cv2.IMWRITE_JPEG_QUALITY, 85])
                encoded_frame = base64.b64encode(buffer).decode('utf-8')
                
                # Gửi frame đến các peers
                send_frame_callback(encoded_frame)
                
            except Exception as e:
                self.logger.error(f"Error in streaming: {e}")
                time.sleep(0.1)  # Brief pause on error
                
    def process_received_frame(self, encoded_frame, sender_username):
        """Process a received frame"""
        try:
            # Decode the frame
            img_data = base64.b64decode(encoded_frame)
            nparr = np.frombuffer(img_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if frame is None:
                self.logger.error("Failed to decode frame")
                return
            
            # Không chuyển đổi BGR sang RGB ở đây, giữ nguyên định dạng màu
            # frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) - BỎ dòng này
            
            # Put in queue for display with original BGR format
            if self.frame_queue.full():
                self.frame_queue.get()  # Remove oldest frame if queue is full
            self.frame_queue.put((frame, sender_username))
            
            # If we have a callback for displaying frames, call it
            if self.frame_display_callback:
                self.frame_display_callback(frame, sender_username)
                
        except Exception as e:
            self.logger.error(f"Error processing received frame: {e}")
            
    def set_frame_display_callback(self, callback):
        """Set callback for displaying frames"""
        self.frame_display_callback = callback
        
    def get_current_frame_as_tk(self):
        """Get current frame as Tkinter PhotoImage"""
        if self.current_frame is None:
            return None
            
        try:
            # Chuyển đổi BGR sang RGB chỉ khi chuẩn bị hiển thị
            rgb_frame = cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb_frame)
            return ImageTk.PhotoImage(image=img)
        except Exception as e:
            self.logger.error(f"Error converting frame to PhotoImage: {e}")
            return None
            
    def get_next_viewing_frame(self):
        """Get next frame from queue for viewing"""
        try:
            if not self.frame_queue.empty():
                frame, username = self.frame_queue.get(block=False)
                # Chuyển đổi BGR sang RGB chỉ khi chuẩn bị hiển thị
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                return rgb_frame, username
            return None
        except queue.Empty:
            return None


