# รายการวิดีโอ

review_by: 2027-02-12 · owner: rainmojo-so-lite maintainers · moved from SKILL.md in LITE-011 (2026-11-12)


ประกาศ `xmlns:video="http://www.google.com/schemas/sitemap-video/1.1"` บน `<urlset>`
ของไฟล์ที่มีรายการวิดีโอ **และประกาศเฉพาะไฟล์นั้น**
หนึ่ง `<video:video>` ต่อหนึ่งวิดีโอ วางซ้อนอยู่ในรายการของหน้าที่วางวิดีโอนั้น
**`<loc>` ยังเป็นหน้าที่คนดู ไม่ใช่ไฟล์สื่อ**

```xml
<url>
  <loc>https://example.com/videos/accounting-basics</loc>
  <video:video>
    <video:thumbnail_loc>https://example.com/thumbs/accounting-basics.jpg</video:thumbnail_loc>
    <video:title>Accounting basics in 10 minutes</video:title>
    <video:description>Double-entry explained for first-time founders.</video:description>
    <video:content_loc>https://example.com/media/accounting-basics.mp4</video:content_loc>
    <video:player_loc>https://example.com/embed/accounting-basics</video:player_loc>
  </video:video>
  <lastmod>2026-08-12T16:49:33+00:00</lastmod>
</url>
```

กฎของแต่ละช่อง **ให้ตัวสร้างตรวจทุกข้อก่อนเขียนไฟล์ รายการที่ผิดจะได้ทำให้ build ล้ม
แทนที่จะหลุดขึ้นเว็บไป**

- **ต้องมีต่อหนึ่งรายการ** `video:thumbnail_loc`, `video:title`, `video:description`
  และอย่างน้อยหนึ่งอย่างระหว่าง `video:content_loc` ซึ่งเป็น URL ไฟล์สื่อจริง
  กับ `video:player_loc` ซึ่งเป็น URL ตัวเล่นที่ฝังได้ **มีทั้งคู่ให้ใส่ทั้งคู่**
- `video:title` ตรงกับชื่อวิดีโอบนหน้าที่วางมันไว้ `video:description` ตรงกับคำอธิบายวิดีโอบนหน้านั้น
  และยาวไม่เกิน 2,048 ตัวอักษร
- **`video:content_loc` และ `video:player_loc` ห้ามเท่ากับ URL ของหน้าใน `<loc>`**
  ทั้งคู่ต้องวิ่งไปถึงไฟล์ที่ดึงได้จริงและคนละตัวกับหน้าที่คนดู ไม่งั้นบอทดึงไฟล์สื่อไม่ได้
- `video:thumbnail_loc` ต้องเป็นภาพปกตัวเดียวกับที่ markup บนหน้าประกาศไว้
  **ให้คำนวณทั้งสองที่จากฟังก์ชันเดียวกัน** ด้วยเหตุผลเดียวกับ hreflang
- **ถ้าวิดีโอเป็นเนื้อหาประเภทหนึ่งของเว็บจริง ๆ ให้แยกไฟล์ย่อยของมันเอง** เช่น `sitemaps/videos-th.xml`
  ภายใต้กฎการแยกและเพดานเดียวกัน namespace วิดีโอจะได้อยู่เฉพาะที่ที่ใช้จริง
  ส่วนวิดีโอตัวเดียวบนหน้าธรรมดา ให้อยู่ในรายการของหน้านั้นตามปกติ

ข้อกำหนดของตัววิดีโอเอง เช่นภาพปกและข้อที่ทำให้ถูกตัดสิทธิ์ อยู่ที่ `seo-video-lite`
