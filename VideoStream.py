class VideoStream:
    def __init__(self, filename):
        self.filename = filename
        try:
            self.file = open(filename, 'rb')
            print(f"[INFO] Đã mở file: {filename}")
        except:
            print(f"[ERROR] Không tìm thấy file: {filename}")
            raise IOError
        self.frameNum = 0

    def nextFrame(self):
        """Get next frame."""
        data = None
        
        # --- BƯỚC 1: Tự động dò độ dài header ---
        # Chúng ta sẽ đọc từng ký tự một cho đến khi gặp ký tự không phải là số
        # (thường là \xff - dấu hiệu bắt đầu của ảnh JPEG)
        
        frame_length_str = b""
        
        while True:
            # Đọc 1 byte
            byte = self.file.read(1)
            
            # Nếu hết file thì dừng
            if not byte:
                return None
            
            # Kiểm tra xem byte vừa đọc có phải là số (0-9) không?
            if byte.isdigit():
                frame_length_str += byte
            else:
                # Nếu không phải số (ví dụ gặp \xff), nghĩa là hết phần header
                # Chúng ta phải lùi con trỏ file lại 1 bước để lát nữa đọc ảnh không bị mất byte này
                self.file.seek(-1, 1)
                break

        # --- BƯỚC 2: Đọc dữ liệu ảnh ---
        if frame_length_str:
            try:
                framelength = int(frame_length_str)
                # Đọc đúng số lượng byte mà header đã báo
                data = self.file.read(framelength)
                self.frameNum += 1
            except ValueError:
                print("[ERROR] Header bị lỗi, không đọc được kích thước.")
                return None
        
        return data
        
    def frameNbr(self):
        """Get frame number."""
        return self.frameNum