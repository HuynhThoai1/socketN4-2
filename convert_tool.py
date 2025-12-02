import sys
import os

def convert_to_lab_format(input_filename):
    """
    Chuyển đổi file MJPEG chuẩn sang định dạng Lab (thêm 5-byte header độ dài ASCII).
    """
    if not os.path.exists(input_filename):
        print(f"Lỗi: Không tìm thấy file '{input_filename}'")
        return

    # Tên file đầu ra
    base_name, ext = os.path.splitext(input_filename)
    output_filename = f"{base_name}_lab_ready{ext}"

    print(f"Đang xử lý: {input_filename}...")
    
    with open(input_filename, 'rb') as f:
        data = f.read()

    output_data = bytearray()
    pos = 0
    frame_count = 0
    
    # Marker JPEG chuẩn
    SOI = b'\xff\xd8' # Start of Image
    EOI = b'\xff\xd9' # End of Image

    while True:
        # 1. Tìm điểm bắt đầu frame (FF D8)
        start_pos = data.find(SOI, pos)
        if start_pos == -1:
            break # Không còn frame nào

        # 2. Tìm điểm kết thúc frame (FF D9)
        # Lưu ý: Tìm EOI bắt đầu từ ngay sau SOI
        end_pos = data.find(EOI, start_pos)
        if end_pos == -1:
            print("Cảnh báo: Frame không có kết thúc. Dừng lại.")
            break
        
        # EOI marker dài 2 byte, nên phải cộng thêm 2
        end_pos += 2 
        
        # 3. Trích xuất dữ liệu frame
        frame = data[start_pos:end_pos]
        length = len(frame)
        
        # 4. Tạo Header 9-byte (Chuỗi số ASCII)
        # zfill(9) giúp thêm số 0 vào trước cho đủ 9 ký tự
        header = str(length).zfill(9).encode('utf-8')
        
        # Kiểm tra giới hạn (Header chỉ hỗ trợ 5 số, max 99999 bytes ~ 97KB)
        if length > 999999999:
            print(f"Cảnh báo: Frame {frame_count} quá lớn ({length} bytes). Header có thể bị sai.")

        # 5. Ghép Header + Frame vào dữ liệu đầu ra
        output_data.extend(header)
        output_data.extend(frame)
        
        frame_count += 1
        pos = end_pos # Di chuyển con trỏ đến phần tiếp theo

    # Ghi ra file mới
    with open(output_filename, 'wb') as f_out:
        f_out.write(output_data)

    print("-" * 30)
    print(f"Hoàn tất! Đã chuyển đổi {frame_count} frame.")
    print(f"File mới: {output_filename}")
    print("Bạn hãy dùng file này trong ClientLauncher.py")

if __name__ == "__main__":
    # Cách dùng: python convert_mjpeg.py <tên_file>
    if len(sys.argv) < 2:
        print("Cách dùng: python convert_mjpeg.py <ten_file_video.mjpeg>")
    else:
        convert_to_lab_format(sys.argv[1])