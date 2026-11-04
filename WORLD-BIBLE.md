# World Bible v0.1 — "Father and Daughter"
Chung cư Hà Nội · 2D hoạt hình · không lời thoại · Shorts 9:16, 30–60s

> Đây là bản nháp để bạn sửa. Mọi thứ trong file này sẽ được nạp vào mọi prompt, nên **sửa bây giờ rẻ, sửa sau khi train LoRA là phải train lại.**

---

## 1. Nhân vật

| | Mô tả | Token LoRA |
|---|---|---|
| **Father** | ~32 tuổi, cao hơi gầy, tóc ngắn hơi rối, râu lún phún, áo thun cổ tròn xám hoặc xanh than, quần short ở nhà, chân trần. Luôn có khăn sữa kẻ ô vắt vai. | `f4thr_man` |
| **Moonie** | 2 tuổi, tóc tơ ngắn buộc một chỏm nhỏ trên đỉnh, má phúng phính, mắt to tròn, yếm hoặc áo cotton vàng bơ, quần đùi. | `m00nie_girl` |
| **Mother** | ~30 tuổi, tóc búi thấp, áo sơ mi linen sáng, quần vải. Vai phụ. | `m0ther_woman` |

**Luật về mẹ:** xuất hiện ở khoảng **30% số video**, luôn ở vai phụ, và khung hình luôn quay về cha–con trước khi kết. Tên kênh là *Father and Daughter* nên tiêu điểm không được dịch chuyển. Mẹ có mặt để gia đình **trọn vẹn**, không để chia đôi sự chú ý.

**Khoá tuyệt đối trong 3 tháng đầu:** kiểu tóc, màu áo, dáng người. 2 tuổi là độ tuổi model dễ trượt lên 4–5 nhất, nên mọi tín hiệu tuổi phải được neo cứng: tỉ lệ đầu/thân ~1:3.5, bước đi chưa vững, luôn cần người đỡ khi lên bậc.

---

## 2. Style

2D hoạt hình, nét viền mảnh không đều, màu phẳng phủ texture giấy nhẹ, bóng đổ mềm không có ranh giới cứng. **Ánh sáng là nhân vật chính** — mọi cảnh phải có một nguồn sáng rõ và một mảng tối để thở.
Token: `cozyhn_style`. Train LoRA style riêng, **không prompt tên studio nào**.

---

## 3. Palette

| Tên | Hex | Dùng ở |
|---|---|---|
| Nắng nghệ | `#F2C879` | ánh sáng chính, giờ vàng |
| Tường kem cũ | `#EDE4D3` | nền, tường căn hộ |
| Xanh rêu nhạt | `#7A9A8B` | cửa, tủ, cây |
| Nâu gỗ ấm | `#8A5A3B` | bàn ghế, sàn |
| Xám kính bê tông | `#9AA5AD` | cửa nhôm kính, nhà đối diện, trời |
| Đỏ nhấn | `#C9513E` | ghế nhựa, bao lì xì, một điểm duy nhất mỗi khung |

Luật: mỗi khung hình chỉ **một** điểm đỏ nhấn. Đó là thứ dẫn mắt người xem trong 1.5 giây đầu.

---

## 4. Tám set cố định (mỗi set 3 góc máy chuẩn)

1. **Ban công** — lưới an toàn, giàn phơi, máy giặt cửa trên, 3 chậu cây, nhìn ra rừng chung cư
2. **Bếp mở nối bàn ăn** — bếp từ, giá bát inox, tủ lạnh dán nam châm hoa quả
3. **Phòng khách** — sofa nỉ xám, quạt cây, chiếu trúc trải sàn, cửa nhôm kính lớn
4. **Phòng Moonie** — giường thấp có chắn, đèn ngủ vàng, rổ thú bông
5. **Phòng bố mẹ** — giường, tủ gỗ, cửa sổ nhỏ
6. **Nhà tắm** — bình nóng lạnh, chậu tắm nhựa xanh, gương mờ hơi nước
7. **Hành lang & cửa sắt** — thảm chùi chân, đôi dép xếp, ánh đèn hành lang trắng lạnh (đối lập với trong nhà ấm)
8. **Góc làm việc của bố** — bàn gỗ sát tường, laptop, cốc sứ sứt miệng

Tám set này là **toàn bộ thế giới**. Không thêm địa điểm mới trong 3 tháng đầu. Hạn chế này là tài sản, không phải giới hạn: nó tạo cảm giác "nhà" và cho phép tái dùng asset.

---

## 5. Mười đạo cụ motif

Khán giả nhận ra **đồ vật trước khi nhận ra khuôn mặt**. Đây là lớp nhất quán mạnh hơn cả LoRA.

1. Cốc sứ trắng sứt một mẩu ở miệng — của bố
2. **Thỏ** — thú bông tai rủ, màu kem, một tai đã sờn
3. Chiếu trúc màu mật
4. Ghế nhựa đỏ con
5. Quạt cây cũ, cánh hơi ố vàng
6. Chuông gió ở ban công
7. Đôi dép tổ ong nhỏ màu vàng
8. Chậu húng quế trên ban công
9. Khăn sữa kẻ ô vắt vai bố
10. Nam châm hình trái cây trên cửa tủ lạnh

Luật: mỗi video phải có **ít nhất 3** đạo cụ trong danh sách này xuất hiện rõ.

---

## 6. Trục biến thiên — thay cho 4 mùa

Chung cư làm mất trục mùa tự nhiên, nên Hà Nội phải gánh bằng 5 trục chồng lên nhau. Nhân tổ hợp lại là quá đủ cho 365 video.

| Trục | Các giá trị |
|---|---|
| **Mùa** | Đông (áo len, chăn bông, cửa đóng, hơi nước đọng kính) · Nồm (tường rịn ẩm, quạt hong quần áo, sàn trơn) · Hè (quạt cây, chiếu trúc, nắng gắt 15h) · Thu (nắng hanh, cửa mở, gió lùa rèm) |
| **Giờ** | Tờ mờ sáng · nắng trưa qua rèm · chiều vàng · hoàng hôn tím sau các toà nhà · đêm đèn vàng |
| **Thời tiết** | Mưa rào · sương mù nuốt toà đối diện · nắng vỡ sau mưa |
| **Dịp** | Tết · Trung thu · sinh nhật Moonie · ngày mưa không đi đâu được |
| **Nhịp sống** | Sáng vội · trưa ngủ · chiều đón về · đêm khuya bố còn thức |

**Mùa nồm là mỏ vàng chưa ai khai thác** — tường đổ mồ hôi, quần áo hong trước quạt, sàn trơn phải bế Moonie đi — rất đặc trưng Hà Nội, rất giàu hình ảnh, và hoàn toàn dễ hiểu với người nước ngoài mà không cần giải thích.

---

## 7. Luật của thế giới

1. Chỉ ba nhân vật. Hàng xóm chỉ tồn tại qua tiếng động và bóng người sau cửa kính mờ.
2. **Không có xung đột.** Căng thẳng cao nhất được phép: Moonie mếu 2 giây rồi được dỗ. Đây là kênh "bình yên", không phải kênh kịch tính.
3. Điện thoại không bao giờ là trung tâm khung hình.
4. **Không chữ tiếng Việt cần đọc.** Chữ chỉ được phép làm texture mờ ở hậu cảnh.
5. Chất liệu địa phương, hành động phổ quát: ban công lưới, giàn phơi, ghế nhựa — giữ hết. Nhưng việc đang diễn ra phải là ăn, ngủ, tắm, dỗ con, thứ không cần giải thích văn hoá.

---

## 8. Cấu trúc 40 giây

| Giây | Việc |
|---|---|
| 0.0–1.5 | **Hook thị giác.** Một khung hình đẹp hoặc lạ ngay lập tức, có điểm đỏ nhấn. Không chữ, không logo, không intro. Đây là khúc quyết định toàn bộ số phận video. |
| 1.5–28 | **Một việc nhỏ duy nhất** diễn ra trọn vẹn. Một việc thôi — pha sữa, cắt móng tay, dỗ ngủ, hong quần áo. |
| 28–38 | **Nhịp lặng.** Camera gần như đứng yên, không có gì xảy ra. Đây là chỗ cảm xúc đọng lại, và là chỗ hầu hết kênh tự động làm hỏng vì sợ người xem lướt. |
| 38–40 | Kết bằng hình, không bằng chữ. |

---

## 9. Đóng gói: tránh nhãn "Made for Kids"

Nội dung hoạt hình có trẻ nhỏ rất dễ bị YouTube tự gắn nhãn made-for-kids → tắt bình luận, mất quảng cáo cá nhân hoá, RPM rớt mạnh, Shorts giảm đề xuất.

**Người xem mục tiêu là những ông bố 28–45 tuổi, không phải trẻ em.** Mọi thứ phải phát tín hiệu đó:
- Khai báo "Not made for kids" ngay từ video đầu, nhất quán
- Tiêu đề viết từ góc nhìn người lớn hoài niệm, không phải giọng kể cho trẻ con
- Không dùng nhạc kiểu đồ chơi, không hiệu ứng âm thanh "boing", không màu bão hoà cao
- Nhịp chậm — chính cái nhịp chậm là tín hiệu rõ nhất rằng đây là nội dung cho người lớn

---

## 10. Việc cần làm với file này

1. Bạn sửa trực tiếp mục 1, 4, 5 — nhân vật, set, đạo cụ. Đây là ba mục bạn hiểu rõ hơn tôi.
2. Chốt xong thì sinh character sheet, cherry-pick, train 3 LoRA.
3. File này được nạp vào mọi prompt sau đó, và là input cố định cho stage `brief`.
