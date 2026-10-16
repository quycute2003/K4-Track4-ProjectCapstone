# Kịch bản Demo và Thuyết trình (10 Phút): Vin Driver Watch

Phân công trình bày và quy trình ứng phó rủi ro cho Capstone Day 28 (Track 4 - Computer Vision & Robotics).

---

## 1. Phân bổ thời gian (Tổng cộng 10 phút)

| Thời lượng | Nội dung chính | Người phụ trách chính |
| :---: | :--- | :--- |
| **1 phút** | Đặt vấn đề, bối cảnh người lái VinFast/VinBus, phạm vi sản phẩm | **Quý** |
| **4 phút** | Demo trực tiếp trên Webcam: hiệu chuẩn, chớp mắt, nhắm mắt kéo dài, che mặt phục hồi | **Quý** thao tác chính, **Tuyên** hỗ trợ |
| **2 phút** | **Hai trụ cột Track 4, số đo thực nghiệm, phân tích ca lỗi, impact và giới hạn** | **Tuyên** |
| **3 phút** | Hỏi đáp (Q&A) với Ban giám khảo về toàn bộ hệ thống | **Cả hai** |

---

## 2. Kịch bản chi tiết 2 phút của Nguyễn Hoàng Tuyên

*(Sau khi Quý kết thúc phần demo trực tiếp trên webcam)*

### Lời thoại thuyết trình (Thời lượng: ~120 giây)

> **Kính thưa Ban giám khảo và các thầy cô,**
>
> Tôi là **Nguyễn Hoàng Tuyên**, phụ trách phần kiến trúc thị giác máy tính, đánh giá thực nghiệm và phân tích hiệu năng của hệ thống **Vin Driver Watch**.
>
> Để giải quyết bài toán giám sát người lái một cách tin cậy, nhóm chúng tôi đã vận dụng và kết hợp chặt chẽ **hai trụ cột cốt lõi của Track 4**:
>
> 1. **Trụ cột 1 — Biểu diễn hình học (Geometric Representation):**  
>    Thay vì phân loại ảnh thô tốn kém tài nguyên, hệ thống trích xuất 6 điểm mốc pixel cho mỗi mắt qua MediaPipe và chuẩn hóa thành chỉ số hình học **EAR (Eye Aspect Ratio)**:
>    $$\text{EAR} = \frac{\|p_2 - p_6\| + \|p_3 - p_5\|}{2 \cdot \|p_1 - p_4\|}$$
>    Chỉ số này sở hữu đặc tính toán học vượt trội: **bất biến với phép tịnh tiến, phép co giãn khoảng cách và phép xoay trong mặt phẳng**. Đồng thời, cơ chế hiệu chuẩn 60 khung hình ban đầu giúp thích ứng với kích thước mắt riêng biệt của từng tài xế.
>
> 2. **Trụ cột 2 — Suy luận và mô hình hóa theo thời gian (Temporal Reasoning):**  
>    Một hình ảnh mắt nhắm tại một khung hình đơn lẻ không có ý nghĩa cảnh báo. Chúng tôi xây dựng bộ máy trạng thái hữu hạn `DriverStateMachine` hoạt động theo trục thời gian thực độc lập với FPS. Bộ máy tích hợp:
>    - **Bộ lọc chớp mắt:** Phân biệt chớp mắt tự nhiên (100–300ms) với nguy cơ ngủ gật ($\ge 1.5\text{s}$).
>    - **Vùng trễ (Hysteresis):** Ngưỡng mở lại cao hơn ngưỡng nhắm đóng để triệt tiêu rung giật trạng thái ở vùng biên.
>    - **Bảo toàn ngữ cảnh:** Tự động hủy bộ đếm khi mất dấu mặt hoặc gián đoạn luồng xử lý $> 0.5\text{s}$, tuyệt đối không ghép nối sai hai sự kiện độc lập.
>
> **Về kết quả thực nghiệm:**  
> Khi so sánh đối chứng trên cùng tập video, phương án có xét thời gian của chúng tôi đã **giảm tỉ lệ cảnh báo nhầm từ 18.4 lần/phút xuống 0 lần/phút**, trong khi vẫn **đạt tỉ lệ phát hiện đúng 100%** đối với các sự kiện ngủ gật chủ đích, với độ trễ cảnh báo cực kỳ ổn định ở mức **1.54 giây**.
>
> **Ca lỗi điển hình và Giới hạn:**  
> Chúng tôi cũng ghi nhận một ca lỗi khi tài xế quay đầu góc lớn ($Yaw > 35^\circ$). Hiện tượng méo phối cảnh làm mí mắt xa camera bị ép dẹp, khiến EAR tụt giả và gây báo nhầm. Hướng khắc phục tiếp theo là kết hợp ước lượng tư thế đầu 3D (Head Pose Estimation) và camera hồng ngoại gần NIR.
>
> **Về giá trị thực tiễn (Impact):**  
> Hệ thống giúp tiết kiệm hàng trăm giờ rà soát video an toàn của đội xe VinBus bằng cách chuyển đổi từ việc xem thủ công toàn bộ luồng video sang việc chỉ rà soát có mục tiêu các sự kiện cảnh báo được đánh dấu tự động trong log CSV.
>
> Xin cảm ơn Ban giám khảo, sau đây nhóm xin sẵn sàng nhận các câu hỏi phản biện!

---

## 3. Checklist chuẩn bị trước giờ Demo

- [x] Laptop và camera đã kiểm tra ánh sáng và cấp quyền truy cập.
- [x] Model `face_landmarker.task` đã có sẵn tại thư mục `models/` (đã kiểm tra SHA256).
- [x] Chạy ứng dụng mượt mà không lỗi:
  ```bash
  python app.py --camera 0
  ```
- [x] Kiểm tra hiển thị giao diện HUD mới ([`src/overlay.py`](../src/overlay.py)) với viền đỏ khi ALERT và bảng thông số rõ nét.
- [x] Chuẩn bị sẵn file video dự phòng tại `data/videos/backup_demo.mp4`.
- [x] Cả hai thành viên nắm vững cấu trúc `DriverStateMachine` và cách giải thích số đo.

---

## 4. Kịch bản ứng phó sự cố (Contingency Plan)

Nếu webcam gặp sự cố kỹ thuật hoặc phòng thi không cấp quyền camera:
1. Bình tĩnh thông báo cho Ban giám khảo: *"Do sự cố camera phần cứng, nhóm xin phép chuyển sang chế độ phát lại video dự phòng đã thu thập từ luồng chạy thật của hệ thống"*.
2. Chạy ngay lệnh sau trong terminal:
   ```bash
   python app.py --video data/videos/backup_demo.mp4
   ```
3. Tiếp tục bài thuyết trình bình thường, chỉ rõ các trạng thái `CALIBRATING` $\rightarrow$ `OPEN` $\rightarrow$ `CLOSING` $\rightarrow$ `ALERT` hiển thị trên màn hình.
