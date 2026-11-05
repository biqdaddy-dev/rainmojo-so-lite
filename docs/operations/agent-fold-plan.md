# แผนพับ agent ของ rainmojo-so-lite (LITE-005)

เขียน 2026-11-05 · สถานะ: **แผนอย่างเดียว ยังไม่แตะ agent ตัวไหน**

## เริ่มได้เมื่อไร

ห้ามเริ่มจนกว่าครบทั้งสามข้อ (DP-023, แผนส่งงาน 2026-11-02 แถว 4 e):

1. rainmojo-so ผ่าน eval ฐานของ RS-1 (DP-024, ตรวจ audit) และ RS-2 (สายผลิตเนื้อหา) แล้ว
2. rainmojo-so พับ agent ตาม RS-7 ไปแล้วอย่างน้อยหนึ่งตัวโดยคะแนนไม่ตก ใช้เป็นแบบให้รุ่น Lite ทำตาม
3. รุ่น Lite มี eval ฐานของตัวเองก่อนพับ: อย่างน้อย 10 งาน งานละ 3 รอบ เกณฑ์ให้คะแนนเขียนก่อนรัน
   (ab-bench v2 ของ plugin-optimizer, PO-1)

## สิ่งที่นับได้จริง (แก้ข้อสรุปเดิม)

ผลตรวจ 2026-11-02 ข้อ 2 เขียนว่า agent 17 ตัว "แต่ละตัวอ้าง skill ตัวเดียว เป็นตัวห่อแบบ 1 ต่อ 1"
นับจากหัวข้อ `## ลำดับการเรียกสกิล` ของแต่ละไฟล์ใน `agents/` เมื่อ 2026-11-05 แล้ว **ไม่จริง**
มีตัวเดียวที่ห่อสกิลเดียว ที่เหลือเรียก 2 ถึง 16 สกิลต่อกัน (ไม่นับ `new-workspace-lite` ซึ่งทุกตัวเรียกก่อน)

ทุกตัวไม่มีเครื่องมือสร้าง subagent (`tools` ไม่มี Agent) เรียกสกิลใน context เดียวและส่งงานต่อกันผ่านไฟล์
ใต้ `work/{domain}/` ซึ่งเป็นแบบ "loop เดียว + skills" อยู่แล้ว ปัญหาจึงอยู่ที่จำนวน agent กับขอบเขตที่ทับกัน
ไม่ใช่การแตก context

| กลุ่ม | agent | สกิลที่เรียก (ไม่นับ new-workspace-lite) | ข้อเสนอ |
|---|---|---|---|
| A ห่อสกิลเดียว | `seo-disavow-auditor-lite` | `seo-backlink-strategy-lite` แล้วชี้ไปปลั๊กอิน disavow | พับเข้าสกิล: ย้ายคำเตือน "ไม่สร้างไฟล์ disavow" กับย่อหน้าชี้ทางไปไว้ใน `seo-backlink-strategy-lite` |
| B ห่อ 2 ถึง 3 สกิลที่ทับ agent ตัวใหญ่ | `aiso-schema-audit-lite` | `aiso-schema-lite`, `seo-schema-lite` | พับเป็นขั้นในสกิล `aiso-schema-lite` (ตรวจแล้วส่งต่อให้สร้าง) |
| | `seo-offpage-lite` | `seo-competitor-lite`, `seo-backlink-strategy-lite` | พับ: ลำดับสองขั้นเขียนในสกิลได้ |
| | `aiso-platform-analysis-lite` | `aiso-platform-lite`, `aiso-crawlers-lite`, `aiso-schema-lite` | พับเข้า `aiso-platform-lite` ซึ่งอ่านผลของอีกสองตัวอยู่แล้ว |
| | `aiso-content-review-lite` | `aiso-content-lite`, `aiso-citability-lite`, `seo-content-audit-lite` | พับ หรือรวมเป็นช่วงหนึ่งของ `aiso-audit-lite` |
| | `seo-local-lite` | `seo-local-seo-lite`, `seo-schema-lite`, `aiso-brand-mentions-lite` | พับเข้า `seo-local-seo-lite` |
| | `seo-keyword-lite` | `seo-keyword-research-lite`, `seo-keyword-clustering-lite`, `seo-content-gap-analysis-lite` | พับ: เป็น pipeline สามขั้นที่ส่งไฟล์ต่อกัน เขียนเป็น workflow ในสกิลได้ |
| C ตรวจใหญ่ที่ทับกันเอง | `so-audit-lite` (16), `aiso-audit-lite` (10), `seo-audit-lite` (7), `aiso-ai-visibility-lite` (6), `seo-technical-lite` (6), `aiso-technical-audit-lite` (4), `seo-onpage-lite` (4) | ตัวเลขในวงเล็บคือจำนวนสกิลที่เรียก | รวม ไม่ใช่พับ: `so-audit-lite` เรียก `seo-audit-lite` กับ `aiso-audit-lite` แทนการไล่ 16 สกิลเอง และตัดสิน `seo-technical-lite` กับ `aiso-technical-audit-lite` ว่าเหลือตัวเดียว |
| D คุมสายลงมือ | `content-production-orchestrator-lite` (8), `remediation-orchestrator-lite` (อ่านผลตรวจ แล้วเรียกเฉพาะด้านที่ขาด) | | คงไว้: งานหลายขั้นที่ต้องคุมลำดับและมีจุดหยุดให้คนอนุมัติ ตรงกับหน้า 08 ของหลักสูตร |
| | `seo-content-lite` (5) | `seo-content-strategy-lite` ถึง `seo-topical-authority-lite` | ตัดสินหลังเห็น eval: ทับกับ `content-production-orchestrator-lite` ตรงช่วงเขียน |

## วิธีพับ (ทีละตัว ทีละ PR)

1. ใช้ขั้น `00-audit.md` ของ migration kit ตัดสินตัวนั้นว่าจะ พับ, รวม, เรียกแบบ tool หรือคงไว้ พร้อมเหตุผล
2. รัน eval ของงานที่ agent ตัวนั้นรับ ก่อนแก้ 3 รอบ เก็บคะแนน
3. แก้: ย้ายลำดับและกฎที่ยังใช้ไปไว้ในสกิลปลายทาง ลบไฟล์ agent และสำเนาใน `platforms/` (สร้างใหม่ด้วย agentpack)
   แก้ตาราง agent ใน `AGENTS.md` แล้วสร้าง `CLAUDE.md` กับ `GEMINI.md` ใหม่ให้ตรงกัน
4. รัน eval ชุดเดิม 3 รอบ ตัดได้เฉพาะเมื่อคะแนนไม่แย่กว่าเดิม ใส่ตัวเลขก่อนและหลังใน PR
5. ทดสอบการเรียก 5 คำขอ (โหลด 3 ไม่โหลด 2) ในเซสชันใหม่ ว่าคำขอเดิมยังไปถึงสกิลปลายทาง

ลำดับที่เสนอ: กลุ่ม A ก่อน (ความเสี่ยงต่ำสุด) แล้ว B ทีละตัว แล้วค่อยตัดสินกลุ่ม C
กลุ่ม D ไม่แตะจนกว่า eval บอกว่ามีปัญหา

## ข้อที่ต้องเปิดแถว roadmap ใหม่ตอนเริ่ม

ทุกตัวที่พับได้รหัส `LITE-` ของตัวเอง หมวด `agents` มีชั่วโมงและวันที่แผนก่อนเริ่ม
