<p align="center">
  <a href="README.md">🇨🇳 中文</a> &nbsp;|&nbsp;
  <a href="README_EN.md">🇺🇸 English</a> &nbsp;|&nbsp;
  <a href="README_JA.md">🇯🇵 日本語</a> &nbsp;|&nbsp;
  <a href="README_AR.md">🇸🇦 العربية</a>
</p>

---

# Jira Monitor Agent

> نظام مراقبة مشكلات Jira المعتمد على الإعدادات + تقارير يومية مجدولة إلى مجموعة Feishu

## ماذا يفعل؟

يقوم مديرو المشاريع بسحب الحالات من Jira يدويًا → تنسيقها → نشرها في المجموعة. عمل متكرر وعرضة للخطأ.

**هذه الأداة**: جلب من Jira → تصفية حسب قواعد مخصصة → تصنيف → دفع إلى مجموعة Feishu بموعد محدد. آلي بالكامل.

## الميزات الرئيسية

- 📋 **مدفوع بالإعدادات**: ملف `settings.json` واحد يتحكم بكل شيء
- 🔍 **تصفية مرنة**: أي تركيبة من المشروع / المسؤول / الحقول المخصصة
- 🏷️ **تصنيف ذكي**: تجميع تلقائي حسب الكلمات المفتاحية في الملخص
- ⏰ **دفع مجدول**: أوقات ثابتة يوميًا إلى مجموعة Feishu
- 🎭 **عبارات طريفة**: ملاحظات عشوائية في نهاية التقرير
- 🖥️ **عميل + خادم**: جهاز الشبكة الداخلية يجلب → الخادم السحابي يسلم

## البداية السريعة

```bash
pip install requests
cp config/settings.example.json config/settings.json
# عدّل settings.json بمعلومات Jira و Feishu
python3 server.py          # تشغيل الخادم
python3 jira_fetcher.py    # جلب من Jira
python3 send_daily.py      # اختبار الإرسال
```

## الإعدادات

```json
{
  "jira": { "url": "...", "project": "E0V", "auth": {"username":"","password":""} },
  "filter": {
    "statuses": ["已分配","分析中","修复中"],
    "categories": [
      {"name":"مرئي", "emoji":"👁️", "match":"exclude", "exclude_keyword":"فحص الصحة"},
      {"name":"صحي", "keyword":"فحص الصحة", "emoji":"💊", "match":"include"}
    ]
  },
  "feishu": { "app_id":"", "app_secret":"", "chat_id":"", "chat_type":"group" },
  "schedule": { "fetch_times": ["10:30","15:30"], "report_times": ["11:00","16:00"] }
}
```

## التقنيات المستخدمة

Python 3.9+ · إعدادات مدفوعة · Feishu Open API · Jira REST API
