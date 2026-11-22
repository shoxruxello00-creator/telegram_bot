# 🎓 English C2 Quiz Bot — Multilingual & Autonomous AI Vocabulary

Uch tilda (**🇺🇿 O‘zbekcha**, **🇷🇺 Русский**, **🇬🇧 English**) to‘liq ishlaydigan, har kuni avtomatik ravishda **10 ta yangi va hech qachon takrorlanmaydigan C1–C2** darajadagi inglizcha so‘z, phrasal verb, idiom hamda collocation yaratib o‘rgatadigan professional Telegram bot (`python-telegram-bot 22.3` + `PostgreSQL`).

---

## ✨ Asosiy Imkoniyatlar

1. **Uch tilli interfeys (`uz`, `ru`, `en`)**:
   - `/start` bosilganda til tanlash oynasi chiqadi: `🇺🇿 O‘zbekcha | 🇷🇺 Русский | 🇬🇧 English`.
   - Barcha menyular, tugmalar, dars kartochkalari, quiz savollari va izohlari, statistika, reyting hamda kechki eslatmalar foydalanuvchi tanlagan tilda ishlaydi.
   - Til `⚙️ Sozlamalar` bo‘limidan o‘zgartirilganda barcha o‘rganilgan so‘zlar, XP, streak va statistika saqlab qolinadi.
   - Barcha interfeys matnlari `locales/uz.json`, `locales/ru.json`, `locales/en.json` fayllarida joylashgan.

2. **Avtomatik C1–C2 Vocabulary va Quiz Generatsiyasi (`services/ai_vocabulary_generator.py`)**:
   - Admin qo‘lda so‘z kiritishi shart emas.
   - AI API (`OpenAI`, `Gemini`, `Anthropic` yoki OpenAI-compatible API) va ishonchli lug‘at manbalari (*Cambridge Dictionary*, *Oxford Learner's Dictionaries*, *Merriam-Webster*) asosida kunlik 10 ta C1–C2 ibora va A/B/C/D Quiz Poll savollarini avtomatik tayyorlaydi.
   - JSON Schema (`jsonschema`) va `Pydantic` orqali qat'iy validatsiya hamda tashqi kontentni xavfsiz tozalash (`sanitize_untrusted_text`) mavjud.
   - API vaqtincha ishlamay qolsa, bazada hali ishlatilmagan `data/reserve_vocabulary.json` zaxirasidan foydalanadi.

3. **So‘zlar hech qachon takrorlanmaydi (`services/normalizer.py`)**:
   - Har bir ibora uchun `normalized_expression` hisoblanadi va PostgreSQL bazasida `UNIQUE` constraint bilan himoyalanadi.
   - Bundan tashqari, `daily_lesson_items.vocabulary_id` ustunida ham `UNIQUE` constraint mavjud.
   - Katta-kichik harflar, tinish belgilari, `somebody/someone/one's`, `to/a/the` qo‘shimchalari hamda yaqin yozilish farqlari (`SequenceMatcher` + stem signature) avtomatik aniqlanadi va takrorlar rad etiladi.

4. **Avtomatik Kunlik Jadval (`Asia/Tashkent`)**:
   - `00:05` — Yangi 10 ta noyob C1–C2 iborani yaratadi, tekshiradi va PostgreSQL bazasiga saqlaydi.
   - `08:00` — Foydalanuvchilarga tanlangan tilda xayrli tong xabarini va bugungi 10 ta so‘zni yuboradi.
   - `20:00` — Quizni yakunlamaganlarga eslatma, yakunlaganlarga esa tabrik xabarini yuboradi.

5. **Interaktiv O‘quv Jarayoni**:
   - 10 ta so‘zni sahifalab (`1/10 ... 10/10`) yoki alohida xabarlar ko‘rinishida o‘qish.
   - `✅ YODLADIM` / `✅ Я ВЫУЧИЛ(А)` / `✅ I'VE MEMORIZED THEM` tugmasi.
   - 10 ta A/B/C/D savoldan iborat native Telegram **Quiz Poll** (har bir savolga 20 soniya, har bir to‘g‘ri javobga +10 XP).
   - Kunlik Streak, TOP-10 Leaderboard, Shaxsiy statistika va O‘rganilgan so‘zlar arxivi.

6. **Yangilangan Admin Panel (`/admin`)**:
   - `📢 Barcha foydalanuvchilarga xabar` — Matn, rasm, video, audio, voice, hujjat (PDF/DOCX), GIF va stickerlarni `copy_message` orqali asl formatida tarqatish, Preview, Live Progress, To‘xtatish, Tarix va Render restartdan keyin avtomatik davom ettirish.
   - `👑 Adminlar boshqaruvi` — Super Admin (Owner) va qo‘shimcha 1 ta Moderator (Admin) tizimi, server-side rol tekshiruvi bilan.
   - `🎁 Referral boshqaruvi` — Referral statistika, top referrers, berilgan mukofotlar, shubhali referrallarni rad etish va milestone qiymatlarini sozlash.
   - `🤖 AI Generator holati` — generatsiya loglari, xatolar va takrorlanish sababli rad etilgan so‘zlar statistikasi
   - `📚 Barcha vocabulary`
   - `📅 Bugungi dars`
   - `📊 Bot statistikasi`
   - `👥 Foydalanuvchilar`
   - `🔄 Yangi darsni generatsiya qilish` (bugungi darsni tasodifan ikki marta yaratib yuborishdan himoyalangan)
   - `⚙️ Sozlamalar`

7. **Professional Referral & Rewards System (`handlers/referral.py`, `services/bonus_pack_service.py`)**:
   - Shaxsiy referral havola (`https://t.me/BOT_USERNAME?start=ref_USER_ID`) va Telegram native ulashish (`https://t.me/share/url`).
   - Referral faqat yangi foydalanuvchi birinchi kunlik IELTS quizini yakunlagach `pending` -> `confirmed` holatiga o‘tadi (anti-fraud, self-referral va duplicate referral himoyasi bilan).
   - 5 ta haqiqiy ishlaydigan milestone mukofotlari (Gemini Free Tier uchun optimallashtirilgan, PostgreSQL'da umumiy `bonus_packs` sifatida saqlanadi):
     - **1 referral:** `🎁 +10 Bonus IELTS Vocabulary` (+ maxsus quiz)
     - **3 referral:** `💎 IELTS Speaking Advanced Pack` (+ maxsus quiz)
     - **5 referral:** `📚 IELTS Writing Academic Pack` (+ maxsus quiz)
     - **10 referral:** `👑 VIP IELTS 30-Day Challenge` (+ `👑 VIP` Badge)
     - **20 referral:** `🏆 IELTS Master Status` (+ `🏆 IELTS Master` Badge + eksklyuziv pack)

---

## 🚀 O‘rnatish va Ishga Tushirish (Terminal Komandalari)

### 1. Virtual muhit yaratish va kutubxonalarni o‘rnatish
```bash
python -m venv .venv

# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1

# Linux / macOS:
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

### 2. PostgreSQL bazasini yaratish
```bash
sudo -u postgres psql -c "CREATE DATABASE english_c2_bot ENCODING 'UTF8';"
```

### 3. `.env` faylini sozlash
```bash
cp .env.example .env
# .env fayliga BOT_TOKEN, ADMIN_ID, DATABASE_URL va AI_API_KEY qiymatlarini kiriting
```

### 4. Database migrationlarni ishga tushirish
```bash
python -m database.migrate
```

### 5. Testlarni tekshirish
```bash
pytest -v
```

### 6. Botni ishga tushirish
```bash
python main.py
```

---

## 🐳 Docker Compose orqali 24/7 ishga tushirish

```bash
cp .env.example .env
docker compose up -d --build
docker compose logs -f bot
```

---

## 🖥 Linux Serverda `systemd` orqali 24/7 ishga tushirish

```bash
sudo cp english_c2_bot.service /etc/systemd/system/english_c2_bot.service
sudo systemctl daemon-reload
sudo systemctl enable english_c2_bot
sudo systemctl start english_c2_bot
sudo systemctl status english_c2_bot
```
