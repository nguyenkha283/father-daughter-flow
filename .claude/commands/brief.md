---
description: Bien logline thanh job.yaml dat chuan World Bible
---

Tao mot job video moi tu logline: **$ARGUMENTS**

Quy trinh bat buoc:

1. Doc `WORLD-BIBLE.md`. Day la rang buoc cung, khong phai goi y.
2. Doc `pipeline/schema.py` de lay danh sach hop le cua `SETS`, `MOTIFS`,
   `SEASONS`, `TIMES`. Khong duoc bia gia tri moi.
3. Viet `jobs/<YYYY-MM-DD>_<slug>.yaml` theo dung cau truc `jobs/example.yaml`.

Rang buoc khi viet shotlist:

- **Shot dau luon la `beat: hook`, toi da 1.8s**, va nen dung `lane: i2v`.
  Day la 1.5 giay quyet dinh so phan video. Khong mo bang man den.
- **Nhip lang cuoi >= 8s** (`beat: rest` roi `end`). Day la cho cam xuc dong
  lai. Khong duoc cat ngan vi so nguoi xem luot.
- **Toi thieu 60% shot dung `lane: parallax`.** Chi dung `i2v` cho shot that
  su can vat the chuyen dong. Ngan sach T4 tinh tren 3-4 shot i2v moi video.
- **It nhat 3 dao cu motif** tu danh sach trong World Bible.
- Co ca `father` va `moonie`. Neu cho `mother` xuat hien thi shot cuoi phai
  quay ve cha-con.
- Tong thoi luong (da tru xfade) trong khoang 30-60s.
- Dung ít nhất 2 set khac nhau.

Prompt cho tung shot: tieng Anh, ta canh cu the, neu ro nguon sang va **mot
diem do nhan duy nhat**. Khong nhac ten studio hoat hinh nao.

Phan `publish`:
- `youtube.title` tieng Anh, goc nhin nguoi lon hoai niem, khong phai giong
  ke cho tre con.
- `x.text` **tuyet doi khong chua URL** (post co link bi tinh dat gap ~13 lan).
- `facebook.variants`: 4 caption **khac nhau that su**, khong phai doi emoji.
  Chung se bi kiem tra do tuong dong tu dong.

Xong thi chay `python run.py status <file>` va sua cho den khi khong con loi.
