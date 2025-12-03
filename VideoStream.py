class VideoStream:
    def __init__(self, filename):
        self.filename = filename
        try:
            self.file = open(filename, 'rb')
        except:
            raise IOError
        self.frameNum = 0

    def nextFrame(self):
        """Get next frame."""

        # --- QUAN TRỌNG: Sửa số 5 thành số 9 ---
        # Vì tool convert của bạn dùng zfill(9) nên ở đây phải read(9)
        data = self.file.read(9)

        if data:
            # Chuyển chuỗi 9 số thành số nguyên (kích thước ảnh)
            framelength = int(data)

            # Đọc dữ liệu ảnh theo kích thước đó
            data = self.file.read(framelength)
            self.frameNum += 1
        return data

    def frameNbr(self):
        """Get frame number."""
        return self.frameNum