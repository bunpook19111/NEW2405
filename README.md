# รอดมั้ย AI น้ำอินทร์บุรี

ระบบช่วยเฝ้าระวังน้ำเจ้าพระยา อ.อินทร์บุรี แบบโพสต์อัตโนมัติไป Facebook Page ผ่าน Make.com

> หลักสำคัญ: ระบบนี้เป็น **ระบบช่วยเฝ้าระวัง** ไม่ใช่ประกาศทางราชการ และจะไม่อ้างว่าแม่น 100%

## ความสามารถ

- อ่านข้อมูลย้อนหลังอินทร์บุรีจาก `data/inburi_history.csv`
- ดึงข้อมูลสดแบบ best-effort จาก Thaiwater/HII
- วิเคราะห์ความสัมพันธ์ `ท้ายเขื่อนเจ้าพระยา C.13 → ระดับน้ำอินทร์บุรี`
- ประเมินเวลาหน่วงของมวลน้ำแบบช่วงเวลา
- คาดการณ์ 3/6/12/24/48 ชั่วโมง
- สร้างภาพ SVG แนวน่ารัก อ่านง่ายสำหรับชาวบ้านและเด็ก
- สร้าง caption สำหรับ Facebook
- ต่อ Make.com webhook เพื่อโพสต์เพจอัตโนมัติ
- Safe Mode: ถ้าข้อมูลไม่ครบหรือความเชื่อมั่นต่ำ จะไม่โพสต์เตือนเกินจริง

## วิธีรันบนเครื่อง

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python main.py --use-history-latest
```

ทดสอบสถานการณ์:

```bash
python main.py --simulate-level 12.80 --simulate-q 2200
python main.py --simulate-level 11.80 --simulate-q 1700 --target-q 2200
```

ไฟล์ผลลัพธ์จะอยู่ใน `outputs/`

## โพสต์ผ่าน Make.com

1. ตั้งค่า Make.com ตาม `docs/MAKE_COM_SETUP.md`
2. ใส่ webhook ใน `.env` หรือ GitHub Secret
3. ตั้ง `DRY_RUN=false`
4. รัน:

```bash
python main.py --post
```

## GitHub Actions

Workflow อยู่ที่ `.github/workflows/water-watch.yml`

Secret ที่ต้องมี:

- `MAKE_WEBHOOK_URL`

Variables ที่แนะนำ:

- `DRY_RUN=false` เมื่อต้องการโพสต์จริง
- `INBURI_BANK_LEVEL_MSL=13.00`

## ข้อควรระวัง

ระบบนี้ยังต้องใช้ข้อมูลย้อนหลังเพิ่มขึ้นเพื่อให้โมเดลแม่นขึ้น โดยเฉพาะ:

- ระดับน้ำอินทร์บุรีรายชั่วโมง
- เวลาที่เขื่อนปรับระบายจริง
- ปริมาณก่อน/หลังปรับ
- ฝนเหนือและฝนในพื้นที่
- สถานีกลาง เช่น สิงห์บุรี/พรหมบุรี

## โครงสร้าง

```text
inburi_ai/
  app.py        main workflow
  sources.py    live data fetchers
  history.py    historical data loader
  forecast.py   rating curve + lag model + risk
  graphics.py   friendly SVG image
  caption.py    Facebook caption
  posting.py    Make.com webhook payload
```

## อัปเกรด: Chao Phraya → Inburi Smart Water Watch

เวอร์ชันนี้เพิ่มชั้นวิเคราะห์เส้นทางน้ำโดยเน้นแม่น้ำเจ้าพระยาและพื้นที่เป้าหมาย **ต.อินทร์บุรี จ.สิงห์บุรี** เป็นหลัก

### ไฟล์ใหม่/ไฟล์สำคัญ

- `main_water.py` — ตัวรันรายงานประจำวัน 3 รอบ/วัน ใช้แทน `main.py` ได้ทันที
- `alert_water.py` — ตัวรันแจ้งเตือนด่วนทุก 30 นาที พร้อมสร้าง `outputs/inburi_alert.json`
- `infographic.html` — หน้าอินโฟกราฟิกอ่านง่ายสำหรับชาวบ้าน โหลดข้อมูลจาก `outputs/inburi_report.json`
- `inburi_ai/stations.py` — นิยามสถานีตามเส้นทางน้ำ นครสวรรค์ → ชัยนาท → สิงห์บุรี → อินทร์บุรี → อ่างทอง
- `inburi_ai/route_analysis.py` — วิเคราะห์มวลน้ำ ระยะทาง ช่วงเวลาที่น้ำจาก C.13 จะถึงอินทร์บุรี และคำอธิบายภาษาชาวบ้าน
- `inburi_ai/ai_council.py` — โครงสำหรับให้ Gemini / Claude / OpenAI ช่วยตรวจสรุปก่อนโพสต์ โดยปิดไว้เป็นค่าเริ่มต้นเพื่อความปลอดภัย

### ตัวอย่างรัน

```bash
python main_water.py --use-history-latest
python main_water.py --simulate-level 12.45 --simulate-q 2200
python alert_water.py --use-history-latest
```

### เปิดหลาย AI ช่วยวิเคราะห์

ตั้งค่า environment variables ใน GitHub Actions หรือเครื่องรันจริง:

```bash
AI_COUNCIL_ENABLED=true
GEMINI_API_KEY=...
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
```

ค่าเริ่มต้นจะใช้ deterministic fallback ก่อน เพื่อไม่ให้ระบบโพสต์มั่วเมื่อ API key หายหรือ AI ตอบไม่แน่นอน

### หมายเหตุสำคัญ

ระบบนี้เป็นระบบช่วยเฝ้าระวังชุมชน ไม่ใช่ประกาศทางราชการ การตัดสินใจภาคสนามควรเทียบกับประกาศจากกรมชลประทาน จังหวัด และหน่วยงานท้องถิ่นเสมอ

## หมายเหตุไฟล์รัน
- `main_water.py` คือ entrypoint หลักสำหรับรายงานน้ำเจ้าพระยา → อินทร์บุรี
- `main.py` คงไว้เป็น compatibility wrapper เผื่อ workflow/เครื่องเดิมเรียกชื่อเก่า
- ตั้ง `DRY_RUN=false` เฉพาะเมื่อ Make.com webhook พร้อมและทดสอบ Safe Mode แล้ว
- ตั้ง `AI_COUNCIL_ENABLED=true` พร้อม `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` เมื่อต้องการให้หลาย AI ช่วยวิจารณ์รายงานจริง
