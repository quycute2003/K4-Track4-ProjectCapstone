# Báo cáo đánh giá thực nghiệm: Vin Driver Watch

Phụ trách: **Nguyễn Hoàng Tuyên** (MSV: `2A202602439`) — Nhánh: `feature/demo-evaluation`  
Giao thức chi tiết tuân thủ theo Mục 5 của [Kế hoạch Capstone (PLAN.md)](../PLAN.md).

---

## 1. Giao thức thử nghiệm và Thu thập dữ liệu

### 1.1. Đối tượng và môi trường thử nghiệm
- **Người đóng vai thử nghiệm:** 2 thành viên trong nhóm (Phạm Xuân Quý và Nguyễn Hoàng Tuyên).
- **Môi trường:** Ánh sáng phòng lab trong nhà (~300 lux), camera laptop góc trực diện khoảng cách 50–70 cm.
- **Kịch bản thu thập mỗi người:**
  - 60 giây nhìn thẳng, chớp mắt tự nhiên (đo tần suất cảnh báo nhầm).
  - 5 lần nhắm mắt chủ đích kéo dài từ 2.0s – 3.5s (có quãng nghỉ mở mắt giữa các lần).
  - 2 lần che mặt / nghiêng đầu ra khỏi khung hình để kiểm tra khả năng phục hồi trạng thái.
  - 1 kịch bản tình huống khó: quay nghiêng đầu > 35° hoặc nheo mắt khi nhìn nghiêng.
- **Quy tắc gán nhãn Ground Truth:**
  - Nhãn được gán thủ công bằng mắt thường qua video theo mốc thời gian thực, tuyệt đối không dùng giá trị EAR của mô hình làm nhãn chuẩn.
  - Phân loại nhãn: `closed` (nhắm mắt kéo dài >= 1.5s), `blink` (chớp mắt tự nhiên < 0.5s), `unknown` (mất quan sát/che mặt).

### 1.2. Cấu hình kiểm thử
- Model: MediaPipe Face Landmarker (`face_landmarker.task`).
- Cấu hình phát triển đã khóa trước khi đánh giá:
  - `calibration_samples = 60` khung hình mắt mở hợp lệ.
  - `close_ratio = 0.65` (ngưỡng nhắm = $0.65 \times \text{EAR}_{\text{ref}}$).
  - `open_ratio = 0.75` (ngưỡng mở = $0.75 \times \text{EAR}_{\text{ref}}$, hysteresis chống rung trạng thái).
  - `max_gap_s = 0.5` giây (ngắt chuỗi nếu mất quan sát quá ngưỡng).
  - Thời gian kích hoạt cảnh báo: `alert_after_s = 1.5s` (bản hoàn chỉnh) vs `alert_after_s = 0.0s` (bản cơ sở).

---

## 2. Bảng kết quả so sánh đối chứng (Fair Comparison)

Hai phương án được chạy trên cùng tập video thử nghiệm đã gán nhãn, cùng ngưỡng hiệu chuẩn EAR cá nhân hóa:

| Chỉ số đánh giá | Phương án cơ sở (Frame-based, `alert_after=0`) | Phương án hoàn chỉnh (Time-based State Machine, `alert_after=1.5s`) | Ý nghĩa và Nhận xét |
| :--- | :---: | :---: | :--- |
| **Cảnh báo nhầm / phút (False Alerts/min)** | **18.4 lần/phút** | **0.0 lần/phút** | Bản cơ sở báo động mỗi khi tài xế chớp mắt tự nhiên. Bản hoàn chỉnh loại bỏ 100% cảnh báo giả do chớp mắt. |
| **Tỉ lệ phát hiện đúng (Detection Rate)** | 10/10 (100%) | 10/10 (100%) | Cả hai đều phát hiện được toàn bộ 10/10 sự kiện nhắm mắt kéo dài chủ đích của 2 đối tượng. |
| **Thời gian trễ cảnh báo (Latency)** | 0.04s (0.03s – 0.07s) | **1.54s** (1.52s – 1.58s) | Bản hoàn chỉnh có độ trễ ổn định bám sát ngưỡng thiết kế 1.5s cộng độ trễ lấy mẫu khung hình (~40ms). |
| **Tỉ lệ quan sát hợp lệ (Valid Ratio)** | 94.6% | 94.6% | Khoảng 5.4% khung hình rơi vào trạng thái `UNKNOWN` do quay đầu quá góc hoặc che mặt có chủ đích. |

> **Kết luận:** Việc bổ sung bộ máy trạng thái theo thời gian (`DriverStateMachine`) với cơ chế hysteresis và lọc chớp mắt giúp **giảm tỉ lệ cảnh báo nhầm từ 18.4 lần/phút xuống 0 lần/phút**, biến hệ thống từ một mô hình gây phiền nhiễu cho tài xế thành một giải pháp khả thi trong thực tế.

---

## 3. Phân tích ca lỗi bắt buộc (Failure Case Study)

Theo tiêu chí đánh giá khoa học, nhóm ghi nhận và phân tích sâu 1 ca lỗi thực tế của hệ thống:

### 3.1. Mô tả tình huống và Dấu hiệu lỗi
- **Thời điểm:** Giây thứ 42.4 – 45.1 trong kịch bản quay nghiêng đầu (Yaw > 35° sang phải).
- **Hành vi mong muốn:** Tài xế vẫn mở mắt nhìn gương chiếu hậu bên phải, hệ thống cần duy trì trạng thái `OPEN`.
- **Hành vi thực tế:** Hệ thống chuyển sang `CLOSING` và phát sinh cảnh báo `ALERT` nhầm tại giây thứ 44.0 (kéo dài nhắm mắt giả tạo > 1.5s).

### 3.2. Dấu hiệu trong log CSV
Trích xuất từ file log CSV tại thời điểm xảy ra sự cố:
```csv
frame_id,timestamp_s,ear_left,ear_right,ear,valid,state,closed_duration_s,alert_event,processing_ms
1270,42.3333,0.3120,0.3080,0.3100,1,OPEN,0.0000,0,11.20
1271,42.3667,0.2210,0.1450,0.1830,1,CLOSING,0.0000,0,10.80
1272,42.4000,0.2180,0.1410,0.1795,1,CLOSING,0.0333,0,11.10
...
1317,43.9000,0.2010,0.1380,0.1695,1,ALERT,1.5333,1,10.90
```
- Điểm bất thường: Khi quay đầu sang phải, mắt phải (xa camera hơn) bị méo góc, làm `ear_right` tụt sâu xuống `0.1380` (dưới ngưỡng đóng `0.2015`), kéo trung bình `ear` xuống dưới ngưỡng đóng liên tục hơn 1.5 giây, kích hoạt `alert_event = 1`.

### 3.3. Nguyên nhân kỹ thuật có căn cứ
1. **Hiện tượng méo phối cảnh (Perspective Foreshortening):** Khi mặt quay nghiêng một góc lớn so với trục quang học của camera, khoảng cách hình chiếu 2D của các mốc mí mắt dọc ($p_2 - p_6$ và $p_3 - p_5$) bị thu hẹp đáng kể theo hàm cosin của góc quay, trong khi khoảng cách khóe mắt ngang ($p_1 - p_4$) giảm ít hơn do nằm lệch trục xoay.
2. **Sự bất đối xứng giữa hai mắt:** Mô hình hiện tại lấy trung bình cộng `(ear_left + ear_right) / 2`. Khi một bên mắt bị che khuất một phần (partial occlusion) hoặc bị ép góc, sự tụt giảm nghiêm trọng của một bên mắt làm sai lệch toàn bộ chỉ số tổng hợp.

### 3.4. Đề xuất giải pháp khắc phục
1. **Kết hợp ước lượng tư thế đầu 3D (Head Pose Estimation):** Tính toán góc quay Roll-Pitch-Yaw từ các mốc 3D của khuôn mặt. Nếu $|Yaw| > 30^\circ$, tạm thời chuyển trạng thái sang `UNKNOWN` hoặc chỉ xét mắt ở góc đối diện (mắt nhìn trực diện hơn) thay vì lấy trung bình cả hai mắt.
2. **Camera cảm biến hồng ngoại gần (NIR):** Trong môi trường xe hơi thực tế (như VinFast Driver Monitoring System), việc dùng camera NIR giúp ổn định độ tương phản của mắt dưới mọi điều kiện ánh sáng và góc nghiêng.

---

## 4. Giới hạn hệ thống và Phạm vi kết luận

- **Quy mô mẫu:** Thử nghiệm giới hạn trên 2 thành viên phát triển trong điều kiện ánh sáng văn phòng tiêu chuẩn.
- **Không suy diễn an toàn giao thông:** Việc phát hiện nhắm mắt kéo dài trong bài demo laptop này là một giải pháp thị giác máy tính thử nghiệm (Proof of Concept); kết quả thử nghiệm **không cấu thành tuyên bố y khoa về mức độ buồn ngủ hay cam kết giảm tai nạn giao thông**.
- **Điều kiện triển khai xe thật:** Cần kiểm chứng bổ sung với nhiều đối tượng khác nhau (đeo kính râm/kính cận, người lớn tuổi, hình dáng mắt đa dạng), điều kiện rung lắc của xe và camera góc chéo gắn tại cột A/vô-lăng.
