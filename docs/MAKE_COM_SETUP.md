# Make.com Flow สำหรับโพสต์ Facebook Page

1. สร้าง Scenario ใหม่
2. Module แรก: **Webhooks > Custom webhook**
3. Copy URL ไปใส่ GitHub Secret ชื่อ `MAKE_WEBHOOK_URL`
4. เพิ่ม Module: **Tools > Base64 decode**
   - Input: `image_base64`
   - Filename: `image_filename`
5. เพิ่ม Module: **Facebook Pages > Create a Photo Post**
   - Page: เพจที่ต้องการ
   - Message/Caption: `caption`
   - Photo: output จาก Base64 decode
6. เปิด Scenario

แนะนำ: ช่วงแรกตั้ง `DRY_RUN=true` ใน GitHub Variables เพื่อทดสอบก่อนโพสต์จริง
เมื่อแน่ใจแล้วค่อยตั้ง `DRY_RUN=false`
