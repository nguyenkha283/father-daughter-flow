# Kế hoạch triển khai: hệ thống tự động dựng & phát hành Shorts
**Kênh:** khoảnh khắc bình yên của cha và con gái · phong cách hoạt hình 2D
**Cấu hình đã chốt:** Shorts 9:16 30–60s · hybrid ảnh AI + I2V ngắn · chạy trên máy cá nhân (NVIDIA <12GB) + Colab Free T4 · không lời thoại, thị trường toàn cầu · 1 video/ngày

---

## 0. Hai ràng buộc phải xử lý ngay ngày đầu

**1. YouTube API: video upload bị khóa `private` cho tới khi qua audit.**
Project Google Cloud tạo sau 28/07/2020 mà chưa qua *API compliance audit* thì mọi video upload qua `videos.insert` bị buộc trạng thái private, không thể public bằng API. Audit mất vài tuần, có báo cáo tới 3 tháng. Quyền truy cập còn có thể bị thu hồi nếu 90 ngày không dùng API.

→ **Hành động ngày 1:** tạo GCP project + bật YouTube Data API v3 + submit audit ngay, trước khi viết dòng code nào. Trong lúc chờ, chạy chế độ **hybrid publish**: API upload lên dạng private kèm đầy đủ metadata, bạn vào YouTube Studio bấm schedule/public (30 giây/ngày). Khi audit xong, bật cờ `YT_FULL_AUTO=true` là tự động hoàn toàn, không phải sửa code.

**2. X API không còn free tier.** Free tier đóng với dev mới từ 02/2026, chuyển sang pay-per-use mua credit trước. Giá ~$0.015/post, nhưng **post có chứa URL bị tính ~$0.20**.
→ Thiết kế: luôn đăng **video native** không kèm link trong post gốc; link kênh đặt ở reply hoặc bỏ hẳn. 30 post/tháng ≈ $0.5–1.
→ Lưu ý kỹ thuật: media upload theo luồng INIT / APPEND / FINALIZE, hiện vẫn cần ký OAuth 1.0a bên cạnh OAuth 2.0.

**3. Facebook Groups: không có API.** Chỉ đăng được vào **Page bạn làm admin** (Reels qua `rupload.facebook.com` + `/{page-id}/video_reels`). Vì chỉ đăng lên Page của chính mình nên **không cần App Review** — Standard Access với user có role trong app là đủ. Groups xử lý bằng *share pack* bán tự động (mục 5).

---

## 1. Kiến trúc tổng thể

```
                  ┌─────────────────────────────────────┐
  bạn đưa logline │  Claude Code (local)  = hạt nhân    │
  ───────────────►│  đọc repo, chạy stage, QC, viết copy│
                  └───────────────┬─────────────────────┘
                                  │ gọi các stage CLI (python)
   ┌──────────────────────────────┼──────────────────────────────┐
   ▼              ▼               ▼              ▼               ▼
 brief          stills         animate       assemble        publish
 logline→     SDXL+LoRA      A) 2.5D local  ffmpeg: cut,   YT / FB Page
 shotlist     (máy bạn)      B) LTX I2V     nhạc, grade,   / X / share-pack
                             (Colab T4)     text, loudness
                                  ▲
                      Google Drive bridge (rclone)
                      inbox/ ─► notebook ─► outbox/
```

**Nguyên tắc thiết kế quan trọng nhất:** mỗi video là một **thư mục job** có `job.yaml` + `state.json`. Mọi stage đều **idempotent** và ghi checkpoint từng shot. Colab Free bị ngắt giữa đường là chuyện bình thường — chạy lại notebook thì nó bỏ qua shot đã `done` và tiếp tục. Không có tính chất này thì pipeline không sống được trên Colab Free.

```
jobs/2026-11-10_firefly-jar/
  job.yaml        # logline, shotlist, prompt từng shot, nhạc, caption
  state.json      # stage nào xong, shot nào xong
  stills/         # shot_01.png ... shot_08.png  (832x1472)
  clips/          # shot_01.mp4 ...
  audio/
  out/final.mp4 + thumb.jpg + captions/{yt,fb,x}.txt
```

---

## 2. Character bible — việc quan trọng nhất, làm trước tiên

Rủi ro số 1 của kênh dạng này **không phải** chất lượng render, mà là **nhân vật đổi mặt giữa các cảnh**. Khán giả nhận ra ngay và kênh mất cảm giác "một gia đình thật". Phải giải quyết bằng LoRA, không phải bằng prompt.

**Tuần 1 làm một lần, dùng mãi:**
1. Chốt thiết kế: tuổi con gái (gợi ý 5–6, dễ tạo khoảnh khắc nhất), kiểu tóc, màu áo cố định, dáng người cha, palette 5 màu, "thế giới" (nhà gỗ, hiên, sân, bếp, cánh đồng).
2. Sinh 60–80 ảnh thử ở style đã chốt, cherry-pick 25–30 ảnh sạch nhất cho mỗi nhân vật.
3. Train **3 LoRA** trên Colab T4 bằng kohya_ss (~40–60 phút mỗi cái): `lora_dad`, `lora_girl`, `lora_style`.
4. Từ đó mọi prompt đều gọi token cố định → nhất quán. Thêm IP-Adapter từ một frame canonical cho các shot cận mặt.

**Về style:** đừng prompt tên studio hoạt hình cụ thể — vừa là vùng xám pháp lý vừa khiến kênh phụ thuộc vào model bên thứ ba. Train `lora_style` của riêng bạn từ các ảnh bạn tự sinh và chọn; đó là tài sản của kênh.

---

## 3. Chọn model cho đúng cấu hình bạn có

| Việc | Chạy ở đâu | Model | Ghi chú thực tế |
|---|---|---|---|
| Sinh keyframe 9:16 | **Local, <12GB VRAM** | SDXL / Illustrious fp16 + 3 LoRA | 832×1472, ~15–25s/ảnh với medvram. 8–10 ảnh/video ≈ 4 phút |
| Depth map | Local | Depth-Anything v2 small | nhẹ, cho lane 2.5D |
| **Lane A — 2.5D parallax** | **Local, 0đ** | depth + warp + ffmpeg | drift camera, hơi thở, lá bay, ánh sáng nhấp nháy. Dùng cho **60–70% shot** |
| **Lane B — I2V thật** | **Colab T4** | **LTX-Video 0.9.x** (fp16) | Lựa chọn đúng nhất cho T4: footprint nhẹ nhất, luồng i2v sạch nhất. 3–4s/clip |
| (dự phòng chất lượng cao) | Colab T4 | Wan 2.2 14B I2V GGUF Q4_K_S | fit được nhưng ~18 phút/video, chỉ dùng cho shot mở đầu |

Lưu ý: **T4 là Turing, không hỗ trợ bf16 và không có FlashAttention-2.** Mọi model phải chạy fp16 hoặc GGUF, cần custom node `ComfyUI-GGUF` nếu dùng quant. Đừng kỳ vọng LTX-2.x chạy được trên T4.

**Vì sao hybrid 2 lane là lựa chọn đúng cho chủ đề này:** "khoảnh khắc bình yên" cần chuyển động *chậm và tối giản* — một tách trà bay hơi, tóc lay, màn cửa phất. 2.5D parallax làm những thứ đó tốt gần bằng I2V mà miễn phí và nhất quán 100%. Chỉ 3–4 "hero shot" mỗi video cần I2V thật.

**Ngân sách GPU thực tế:** ~4 hero clip/video × ~3 phút = ~15 phút Colab/video → **10 video ≈ 2.5 giờ**, vừa 1–2 session Colab Free mỗi tuần. 1 video/ngày là khả thi với điều kiện bạn **render dồn và đệm sẵn 7–10 video**, không render-trong-ngày.

---

## 4. Âm thanh — chỗ dễ làm chết kênh nhất

Không lời thoại nghĩa là nhạc gánh toàn bộ cảm xúc, và nhạc là nguồn rủi ro Content ID lớn nhất.

- **Khuyến nghị:** thuê thư viện có license đa nền tảng (Epidemic Sound hoặc Artlist, ~$10–20/tháng), whitelist kênh YouTube. Bắt buộc nếu bạn đăng cùng nội dung lên FB và X.
- **Không dùng** YouTube Audio Library cho bản đăng FB/X — license thực tế bó trong YouTube.
- **Chưa nên dùng** Suno/Udio cho kênh thương mại tới khi bạn tự xác nhận điều khoản bản quyền đầu ra.
- Tự dựng thêm lớp **ambient SFX** (ve kêu, lửa tí tách, mưa hiên nhà) — đây là thứ tạo cảm giác "bình yên" nhiều hơn cả nhạc, và SFX free license dễ tìm hơn nhạc.
- Chuẩn hóa **-14 LUFS**, duck ambient dưới nhạc 6dB.

---

## 5. Phát hành

| Nền tảng | Cách làm | Mức tự động |
|---|---|---|
| **YouTube Shorts** | Data API v3, OAuth `youtube.upload`, resumable upload | Private-rồi-publish-tay tới khi qua audit → sau đó full auto |
| **Facebook Page / Reels** | Graph API, 3 bước rupload + `/{page-id}/video_reels`, quyền `pages_manage_posts` + `pages_read_engagement` + `pages_show_list` | **Full auto** (Page của bạn, không cần App Review) |
| **X** | pay-per-use, media INIT/APPEND/FINALIZE, post native **không chèn URL** | Full auto |
| **Facebook Groups** | **Share pack bán tự động** | Bạn bấm paste |

**Share pack** — cách xử lý groups mà không vi phạm ToS: sau khi video lên, hệ thống sinh `out/share-pack.md` chứa 3–5 biến thể caption **khác nhau thật sự** (không phải đổi emoji), kèm link, kèm ảnh cover đã export, và một thứ tự group kèm giờ gợi ý. Bạn mở file, copy, paste. Mất ~3 phút/ngày.
Giới hạn tự đặt: **tối đa 3–5 group/ngày, mỗi group caption riêng**. Paste cùng một đoạn vào 20 group là con đường ngắn nhất tới việc bị Facebook hạ reach và khóa tài khoản — và nó cũng không hiệu quả.

**Mở rộng về sau (không nằm trong phạm vi lần này):** Instagram Reels dùng chung Meta app, là kênh viral mạnh nhất cho niche này; TikTok có Content Posting API. Khi pipeline chạy trơn thì thêm mỗi cái ~1 ngày việc.

---

## 6. Vòng lặp chất lượng

**QC tự động** chặn trước khi publish: đúng 9:16, 30–60s, loudness đạt, không có text ngoài safe area, frame đầu không đen, không có artifact tay/mặt ở các frame cận. Fail → job về trạng thái `needs_review`.

**QC bằng Claude:** xuất contact sheet 12 frame + waveform, Claude xem và cho verdict theo rubric (nhất quán nhân vật, nhịp 3 nhịp cảm xúc, hook 1.5s đầu). Đây là chỗ Claude có giá trị nhất, không phải chỗ render.

**Metrics loop:** mỗi ngày pull YouTube Analytics (retention, % xem hết, swipe-away) vào `metrics.sqlite`. Mỗi tuần Claude đọc 7 video gần nhất, đối chiếu retention với đặc điểm shotlist, và điều chỉnh brief template. Đây mới là cơ chế "viral" thật — tự động hóa chỉ mang lại *phân phối*, còn cái quyết định viral là 1.5 giây đầu và nhịp cảm xúc, tức là **stage brief**, không phải stage render.

---

## 7. Lộ trình 4 tuần

**Tuần 1 — nền móng & giấy tờ (không code pipeline)**
- Ngày 1: tạo GCP project, bật YouTube Data API, **submit compliance audit**. Tạo Meta app + Facebook Page. Tạo X dev account, nạp credit tối thiểu.
- Chốt character bible, sinh ảnh, train 3 LoRA.
- Dựng **1 video hoàn toàn bằng tay** từ đầu tới cuối. Mục đích: biết "đạt" trông và nghe như thế nào, trước khi tự động hóa.

**Tuần 2 — pipeline sản xuất**
- Repo + stage `brief`, `stills`, `animate` (lane A), `assemble`. ComfyUI headless API ở local.
- Ra 3 video chỉ bằng lane A 2.5D. Nếu 3 video này đã "đủ bình yên" thì lane B thành optional, tiết kiệm lớn.

**Tuần 3 — Colab worker + publish**
- Notebook LTX I2V dạng worker: đọc `inbox/`, checkpoint từng shot, ghi `outbox/`. rclone bridge.
- Stage `publish`: YouTube (private-mode), FB Reels, X. Share pack.

**Tuần 4 — khép vòng**
- QC tự động + rubric Claude. Scheduler (Task Scheduler/cron) đăng đúng giờ. Metrics loop.
- **Render đệm 10 video** để bắt đầu cadence 1/ngày mà không phụ thuộc máy bật/tắt.

---

## 8. Chi phí vận hành/tháng

| Mục | Chi phí |
|---|---|
| Colab Free | $0 (lên Pro ~$10 nếu T4 bị kiểm quá nhiều) |
| Thư viện nhạc (Epidemic/Artlist) | $10–20 |
| X API pay-per-use (~30 post, không URL) | $0.5–1 |
| YouTube / Facebook API | $0 |
| **Tổng** | **~$11–31/tháng** |

Nếu sau này muốn bỏ Colab để tự động hoàn toàn: Fal.ai/Replicate I2V ~$0.1–0.3/clip → ~$12–35/tháng cho 1 video/ngày. Đây là bước nâng cấp hợp lý khi kênh bắt đầu có doanh thu.

---

## 9. Rủi ro & cách chặn

| Rủi ro | Mức | Cách chặn |
|---|---|---|
| YouTube audit lâu/bị từ chối | **Cao** | Submit ngày 1; hybrid publish private + tay; không block pipeline |
| Nhân vật đổi mặt giữa cảnh | **Cao** | LoRA riêng cho từng nhân vật + IP-Adapter + seed khóa |
| Colab Free ngắt giữa render | Trung bình | Worker checkpoint từng shot, chạy lại là tiếp tục |
| Content ID nhạc | Trung bình | Thư viện có license đa nền tảng, whitelist kênh |
| Facebook hạ reach / khóa vì spam group | Trung bình | ≤3–5 group/ngày, caption khác nhau thật, luôn thủ công |
| YouTube gắn nhãn nội dung lặp lại ("inauthentic") | Trung bình | Mỗi video là một câu chuyện riêng, không dùng template cảnh giống nhau; đa dạng hóa nhịp và bối cảnh |
| Máy cá nhân tắt đúng giờ đăng | Thấp | Đệm sẵn 10 video + retry queue |
| X đổi giá/điều khoản lần nữa | Thấp | Publisher adapter tách rời, tắt X không ảnh hưởng YT/FB |

---

## 10. Những gì tôi cần bạn cung cấp

Chưa cần ngay — tôi sẽ dựng repo trước, rồi hướng dẫn bạn lấy từng cái. Toàn bộ nằm trong `.env` local, có `.gitignore`, không bao giờ commit, và bạn tự chạy script lấy token trên máy mình.

- **Google:** OAuth client dạng Desktop (client_id + secret) → tôi cho script lấy refresh token
- **Meta:** App ID, App Secret, Page ID, long-lived Page access token
- **X:** API key/secret + Access token/secret (OAuth 1.0a) + OAuth2 client ID/secret
- **Thư viện nhạc:** tài khoản, hoặc xác nhận bạn chọn nguồn nào
- **Google Drive:** cấu hình rclone cho Colab bridge
- **Máy bạn:** OS chính xác + model GPU (để tôi chốt flag VRAM cho ComfyUI/SDXL)

---

## 11. Cần bạn chốt tiếp (không chặn việc tuần 1)

1. Tên kênh + tên 2 nhân vật (dùng làm token LoRA, nên chốt sớm vì sửa sau là train lại)
2. Tuổi con gái và bối cảnh thế giới (nhà gỗ miền quê? ven biển? vùng tuyết?)
3. Có muốn chữ overlay trên video không — không chữ thì viral xuyên biên giới tốt hơn, có chữ thì retention thường cao hơn

---

# 12. Cập nhật v2 — kiến trúc sau khi biết cấu hình thật

**Phần cứng thật:**
- Máy 1 — Acer Nitro 5 N20C1, RAM 16GB, Windows. GPU **chờ xác nhận bằng `nvidia-smi`**.
- Máy 2 — **máy công ty**, GTX 1050 Ti **4GB VRAM thật** (12GB hiển thị là đã cộng shared RAM, không dùng được cho inference). Pascal, fp16 rất chậm. Có quyền cài đặt nhưng **phải kín đáo, không chạy GPU tải nặng kéo dài**.

## 12.1 Kiến trúc đã sửa

```
  logline ──► Claude Code (máy 1) ──► job.yaml
                                        │
        ┌───────────────────────────────┼───────────────────────────┐
        ▼                               ▼                           ▼
   MÁY 1 (cá nhân)              MÁY 2 (công ty)               COLAB T4
   ComfyUI + SDXL + 3 LoRA      depth map                     LTX-Video I2V
   train LoRA                   parallax warp                 batch, checkpoint
   keyframe 832x1472            upscale tiled                 từng shot
                                ffmpeg NVENC encode
        └───────────────┬───────────────┴───────────────────────────┘
                        ▼
              Google Drive (rclone)  ◄── kho asset chung
                        │
                        ▼
              GITHUB ACTIONS (cron)  ◄── publish YT / FB Page / X
              secrets ở GitHub Secrets, KHÔNG nằm trên máy nào
```

**Ba thay đổi so với v1:**

1. **Publish tách khỏi mọi máy, chuyển sang GitHub Actions cron.** Lý do: không để OAuth token của kênh nằm trên máy công ty, và không phụ thuộc máy nào bật đúng giờ. Publish chỉ là kéo mp4 từ Drive rồi gọi API — không cần GPU. Miễn phí, có log, chạy đúng giờ mỗi ngày.

2. **Hai máy chạy song song theo *loại việc*, không chia batch.** Máy 1 sinh ảnh cho video N+1 trong khi máy 2 dựng video N. 1050 Ti 4GB không gánh được SDXL — đó là giới hạn vật lý — nhưng ffmpeg NVENC, depth map và parallax thì thừa sức, và đó đúng là phần tốn thời gian thật trong pipeline.

3. **Job trên máy 2 phải ngắn và nhẹ.** Chia encode theo từng đoạn thay vì một job dài hàng giờ. Mặc định `--preset fast`, giới hạn GPU utilization, và không bao giờ chạy training trên máy đó.

## 12.2 Đồng bộ giữa 3 nơi

| Loại | Kênh | Lý do |
|---|---|---|
| Code, `job.yaml`, `state.json`, world bible | **Git private repo** | nhẹ, có history, Actions đọc trực tiếp |
| `stills/`, `clips/`, `out/*.mp4`, LoRA weights | **Google Drive qua rclone** | file nặng, Colab dùng chung đúng Drive này |
| Secrets | **GitHub Secrets** | không nằm trên máy công ty, không nằm trong repo |

Hai máy không cùng LAN nên **không dùng thư mục chia sẻ**, toàn bộ đi qua cloud.

## 12.3 Điểm còn chờ

`nvidia-smi` trên máy 1 quyết định một nhánh duy nhất:
- **RTX 3060 6GB trở lên** → train LoRA và chạy I2V ngay tại máy 1, Colab chỉ còn là overflow. Nhanh hơn đáng kể.
- **GTX 1650 / RTX 3050 4GB** → SDXL vẫn chạy được ở chế độ medvram, nhưng **train LoRA và I2V bắt buộc đẩy lên Colab T4**.

Mọi phần khác của kế hoạch không phụ thuộc kết quả này.

---

# 13. Nhánh T4-only (đã chốt: coi như máy 1 không gánh được GPU work)

Giả định: **toàn bộ việc cần GPU chạy trên Colab Free T4.** Hai máy Windows chỉ làm việc CPU/NVENC. Đây là kịch bản dè dặt nhất, và pipeline được thiết kế để vẫn đạt 1 video/ngày trong kịch bản đó.

## 13.1 Phân vai cuối cùng

| Nơi | Việc | Ghi chú |
|---|---|---|
| **Colab T4** | Train 3 LoRA (1 lần) · sinh keyframe SDXL · I2V LTX-Video | Toàn bộ GPU work |
| **Máy 1 (cá nhân)** | Claude Code điều phối · depth map · parallax render · ffmpeg assembly · QC · sync | Không cần GPU mạnh |
| **Máy 2 (công ty)** | Parallax render + NVENC encode, chia tải theo job ngắn | Không chứa credential |
| **GitHub Actions** | Publish YT / FB Page / X theo cron | Secrets ở GitHub Secrets |

## 13.2 Ngân sách GPU cho 1 batch 10 video

| Việc | Đơn giá trên T4 | 10 video |
|---|---|---|
| Keyframe SDXL 832×1472, ~30 step | ~35 s/ảnh × 10 ảnh | **~60 phút** |
| I2V LTX-Video, clip 3–4 s | ~90 s/clip × 4 clip | **~50 phút** |
| **Tổng** | | **~2 giờ / 1 phiên Colab** |

Một phiên Colab Free (thực tế ~4 giờ trước khi bị ngắt) chứa trọn một batch 10 video. Nghĩa là **~2 giờ Colab mỗi tuần** là đủ cho cadence 1 video/ngày. Mức dùng đó nằm trong vùng sử dụng bình thường, không bị coi là lạm dụng.

**Bắt buộc gộp 2 stage vào CÙNG một phiên:** nạp SDXL → sinh toàn bộ keyframe cho cả 10 video → giải phóng VRAM → nạp LTX → sinh toàn bộ clip. Tách làm 2 phiên là lãng phí thời gian tải model và tăng gấp đôi rủi ro bị ngắt.

**Train LoRA (làm 1 lần):** SDXL LoRA trên T4 ở độ phân giải train 768, gradient checkpointing + 8-bit Adam + fp16, ~1500 step ≈ 60–90 phút mỗi nhân vật. Ba LoRA ≈ 3–4.5 giờ, chia 2 phiên. Nếu T4 OOM thì hạ train res xuống 640 trước khi nghĩ tới chuyện đổi sang SD 1.5 — đổi base model sẽ kéo tụt chất lượng style đáng kể.

## 13.3 Kỷ luật để sống được trên Colab Free

1. **Checkpoint từng shot ra Drive.** Bị ngắt giữa chừng, chạy lại notebook là bỏ qua shot đã `done`. Không có cái này thì pipeline không dùng được.
2. **Base model tải từ HuggingFace mỗi phiên** (có `hf_transfer`), **không** để trên Drive — Drive đọc file lớn chậm hơn đáng kể. Chỉ LoRA và asset của job mới nằm trên Drive.
3. **Không lái Colab bằng script/headless.** Vi phạm điều khoản và dễ mất tài khoản. Đây là thao tác tay ~2 giờ mỗi tuần: mở notebook, bấm chạy, để đó.
4. **Không chạy GPU dài ngày.** Batch gọn một lần mỗi tuần an toàn hơn nhiều so với chạy rải mỗi ngày.

## 13.4 Lane parallax giờ là đòn bẩy chi phí lớn nhất — đã dựng và đo xong

Vì GPU trở thành tài nguyên khan hiếm, **mọi shot không thực sự cần chuyển động vật thể đều phải đi qua lane parallax**. Tỉ lệ mục tiêu: **7–8 shot parallax / 3–4 shot I2V** mỗi video.

`pipeline/parallax.py` đã chạy được và đã kiểm chứng:

- Đo trên clip đã encode bằng phase correlation: vùng gần dịch **23.09 px**, vùng xa dịch **9.14 px** — tỉ lệ **2.53×**. Parallax là thật, không phải pan-zoom giả.
- Tốc độ trên 4 nhân CPU, libx264 preset slow: **~0.8× realtime**. Trên máy 1/máy 2 với NVENC sẽ nhanh hơn 2–4 lần. Chi phí thời gian coi như không đáng kể.
- Biên độ dịch khoá ở **2.2% chiều rộng** — cố ý rất nhỏ. Trên 3% là bắt đầu lộ artifact ở rìa vật thể và mất cảm giác tĩnh tại, trái với chủ đề kênh.
- Có 8 kiểu chuyển động: `static` `drift_left/right/up/down` `push_in` `pull_out` `float`.
- **Hơi thở nền luôn bật** (dao động zoom biên độ 0.4%) — khiến khung hình tĩnh vẫn sống mà người xem không chỉ ra được tại sao.

## 13.5 Đường thoát nếu Colab siết

Giữ nguyên kiến trúc, đổi một dòng config để chuyển I2V sang Fal.ai hoặc Replicate:

- ~$0.05–0.15/clip × 40 clip mỗi batch = **$2–6/batch**, tức **$8–25/tháng**
- Đổi lại: tự động hoàn toàn, không phải ngồi canh notebook mỗi tuần

Đây là bước nâng cấp hợp lý ngay khi kênh có doanh thu đầu tiên. Keyframe SDXL thì vẫn nên giữ trên Colab vì rẻ và nhanh.
