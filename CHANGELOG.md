# Changelog

## 2.8.0 (2026-10-26)

### สิ่งที่ผู้ใช้จะเห็น

- เบราว์เซอร์กำลังเลิกรองรับ XSLT ซึ่งเป็นตัวที่ทำให้ไฟล์ sitemap.xml เปิดดูแล้วเป็นตารางสวย Chrome หยุดทำงานวันที่ 17 พฤศจิกายน 2026
  และ Firefox กับ Safari จะทำตาม **เรื่องนี้ไม่กระทบ SEO เลย** เพราะบอทค้นหาไม่เคยรัน stylesheet อยู่แล้ว มันอ่าน XML ข้างใต้ตรง ๆ
  สิ่งเดียวที่เปลี่ยนคือภาพที่คนเห็นตอนเปิดไฟล์ในเบราว์เซอร์ จากตารางกลายเป็น XML ดิบ
- สกิล sitemap เปลี่ยนคำแนะนำหลักเป็นหน้า HTML sitemap คือหน้าเว็บธรรมดาที่ URL ของตัวเอง ที่ลิสต์หน้าของเว็บออกมาเป็นลิงก์จริง
  มันอยู่รอดทุกการเปลี่ยนของเบราว์เซอร์ และพาลิงก์ภายในได้ซึ่ง XML sitemap ทำไม่ได้
  มาพร้อมกฎว่าลิสต์อะไร จัดกลุ่มยังไง ใหญ่ได้แค่ไหน และเมื่อไหร่ที่ไม่ควรทำเลย
- เราไม่ถอดคำสั่ง stylesheet ออกจาก sitemap ที่ทำไว้แล้ว เพราะคำสั่งที่เบราว์เซอร์ไม่รองรับไม่มีผลอะไรทั้งนั้น
  ไฟล์ยังถูกต้องและบอทเห็นข้อมูลเดิมทุกไบต์ ส่วนเบราว์เซอร์ที่ยังรองรับก็ยังแสดงตารางให้อ่านต่อไป

### Under the hood

- `sitemap-architecture-lite`: the Thai "XSL stylesheet" section is replaced by a new
  "human-readable view" section, mirroring the full edition at 3.22.0 (roadmap DP-017). It carries
  the dated Chrome removal timeline (143 deprecation, 146 Enterprise Policy, 152 Origin Trial, 158
  removal on 17 Nov 2026, 176 end of both escape hatches on 17 Aug 2027) and records that the
  Chrome Platform Status entry still read "Proposed" on 2026-10-25 while the article carries firm
  dates. Gecko and WebKit positions are both positive.
- The no-SEO-impact claim is labelled by strength, not asserted: no search engine has published a
  statement that it ignores `<?xml-stylesheet?>`, so the claim rests on XML 1.0 (a processing
  instruction is an instruction to applications) and on the absence of any presentational
  requirement in Google's sitemap documentation and the sitemaps.org protocol.
- Decision stated in the skill: keep the `<?xml-stylesheet?>` line and `sitemap.xsl`, because an
  unsupported processing instruction is inert and the XML a crawler reads is unchanged.
- New client-facing rules for an HTML sitemap page, plus the four real continuity options with
  their costs (server-side transform at a second URL, the CSS stylesheet Yoast chose which cannot
  create links, the Chrome extension, and Origin Trial or Enterprise Policy).
- New prohibitions: never change the bytes a crawler reads, never inject the polyfill `<script>`
  into a sitemap, never branch on User-Agent, and never use `Accept` as the loophole, because
  crawlers send HTML-preferring `Accept` headers.
- `references/framework-notes.md` and `assets/sitemap.xsl` mirrored from the full edition, keeping
  this edition's own layout example and compression wording.
- Version 2.8.0: the image-spec branch takes this repo from 2.3.1 through 2.4.0 (DP-015) and
  2.5.0 to 2.7.0 (DP-016), and merges first, so the sitemap release follows it.

## 2.3.1 (2026-10-13)

- Repository moved to biqdaddy-dev: the manifests, the marketplace entry and the README
  install commands use https://github.com/biqdaddy-dev/rainmojo-so-lite (was biqdaddy/rainmojo-so-lite).
