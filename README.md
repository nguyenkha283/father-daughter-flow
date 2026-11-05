# Father and Daughter — he thong dung & phat hanh Shorts tu dong

Kenh hoat hinh 2D ve khoanh khac binh yen cua cha va con gai trong mot can ho
chung cu Ha Noi. Ban dua logline, Claude Code dieu phoi phan con lai.

**Doc truoc:** [`KE-HOACH.md`](KE-HOACH.md) (kien truc, chi phi, lo trinh) ·
[`WORLD-BIBLE.md`](WORLD-BIBLE.md) (nhan vat, set, dao cu, luat)

---

## Chay o dau

| Noi | Lam gi | Can gi |
|---|---|---|
| **May 1** (ca nhan, Windows) | Claude Code dieu phoi · depth · parallax · assemble · QC | Python 3.12, ffmpeg |
| **May 2** (cong ty, 1050 Ti) | parallax · NVENC encode, job ngan | Python 3.12, ffmpeg. **Khong credential** |
| **Colab T4** | train LoRA · keyframe SDXL · i2v LTX | Tai khoan Google |
| **GitHub Actions** | publish YouTube / FB Page / X | Secrets |

---

## Cai dat (ca hai may Windows)

```
git clone https://github.com/nguyenkha283/father-daughter-flow.git && cd father-daughter-flow
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
winget install Gyan.FFmpeg
```

Depth that (bo qua neu chi thu bang `--fallback`):

```
pip install torch --index-url https://download.pytorch.org/whl/cu121
pip install transformers
```

---

## Vong doi mot video

```
/brief "logline cua ban"              # Claude viet jobs/<ngay>_<slug>.yaml
python run.py status  jobs/<job>.yaml # kiem tra dat World Bible chua

python run.py export  jobs/*.yaml          # gom 10 job thanh 1 batch
python -m pipeline.sync push-batch        # day len Drive cho Colab
#   -> mo colab/Father_and_Daughter_Worker.ipynb, chay ~2 gio
python -m pipeline.sync pull-colab        # thu ket qua ve
python run.py import  jobs/<job>.yaml

python run.py all     jobs/<job>.yaml --encoder h264_nvenc
#   depth -> parallax -> assemble -> QC

python -m pipeline.sync push-final        # day video da qua QC len Drive
git add jobs/*/state.json && git commit -m "qc xong" && git push
```

Lan dau chay `python -m pipeline.sync check` de kiem tra rclone va tao du 5
thu muc tren Drive.

**Hai buoc cuoi deu bat buoc.** GitHub Actions lay *video* tu Drive nhung lay
*trang thai qc/publish* tu git. Thieu mot trong hai thi cron khong tim thay
gi de dang va khong bao loi gi ca.

QC pass thi GitHub Actions tu dang theo cron. Share pack cho Facebook Groups
nam o `jobs/<id>/out/share-pack.md` — ban tu paste, **toi da 5 group/ngay**.

---

## Nhung lua chon thiet ke khong hien nhien

**Khong fade-in tu man den.** 1.5 giay dau quyet dinh so phan video tren
Shorts. QC co mot check rieng chan dieu nay, va no da tung bat loi cua chinh
pipeline nay.

**Toi thieu 60% shot di qua lane parallax.** GPU la tai nguyen khan hiem khi
chay Colab Free. Parallax 2.5D chay mien phi tren CPU va voi chu de "binh yen"
— hoi tra bay, toc lay, man cua phat — no tot gan bang i2v that.
Da do: vung gan dich 23.09 px, vung xa 9.14 px, ti le 2.53x.

**Bien do dich chi 2.2% chieu rong.** Tren 3% la lo artifact o ria vat the va
mat cam giac tinh tai.

**Nhip lang >= 8s o cuoi.** Cho cam xuc dong lai. Hau het kenh tu dong cat
mat doan nay vi so nguoi xem luot.

**State machine theo tung shot.** Colab Free se bi ngat. Chay lai bat cu stage
nao cung chi lam phan con thieu.

**Credential khong bao gio nam tren may cong ty.** Publish chay tren GitHub
Actions voi Secrets.

**Bai X khong duoc chua URL.** Post co link bi tinh ~$0.20 thay vi ~$0.015.
`publish/x.py` chan cung truong hop nay.

---

## Credential

```
python scripts/get_tokens.py youtube --write    # mo trinh duyet -> refresh token
python scripts/get_tokens.py facebook --write   # token ngan han -> page token
python scripts/get_tokens.py verify             # goi thu ca 3 nen tang
python scripts/get_tokens.py secrets            # in lenh nap vao GitHub Secrets
```

X khong can script: 4 khoa lay thang o developer portal, dien vao `.env`.
Scope YouTube xin san ca `yt-analytics.readonly` de sau nay `metrics.py` dung
duoc ma khong phai dong y lai.

## Train LoRA (lam mot lan)

```
python scripts/prep_dataset.py --kind girl --src raw/moonie --out training/girl
rclone sync training gdrive:father-and-daughter/training
```

Roi mo `colab/Train_LoRA.ipynb`, train lan luot `dad` / `girl` / `style`.
~60-90 phut moi LoRA tren T4.

Script prep bat san: anh qua be, anh gan trung nhau (lam LoRA overfit), va
thieu so luong. **Moonie 2 tuoi can >= 35 anh** — mat tre nho it dac diem
rieng nen model rat de truot tuoi len 4-5.

## Vong lap cai thien

```
python -m pipeline.metrics ingest    # map video <-> job
python -m pipeline.metrics fetch     # keo YouTube Analytics
python -m pipeline.metrics report    # -> metrics-report.md cho Claude doc
```

Doi chieu % xem het voi dac diem shotlist (do dai nhip lang, ti le parallax,
lane cua hook, so set...). Voi duoi 10 video thi bao cao tu ghi ro moi ket
luan deu la doan mo.

## Test

```
python tests/test_parallax.py   # parallax co that khong
python tests/test_schema.py     # validator co bat vi pham khong
python tests/test_e2e.py        # clip -> ghep -> QC
```
