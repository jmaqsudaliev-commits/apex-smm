# 🚀 Professional SMM Panel Telegram Bot (1M+ Foydalanuvchi uchun)

Ushbu bot **yuqori yuklamalarga (1,000,000+ foydalanuvchi)** bardosh beradigan, server o'chib yonganda ham hech qanday ma'lumot yo'qolmaydigan, asinxron arxitekturada qurilgan professional Telegram bot hisoblanadi.

---

## 🌟 Asosiy Imkoniyatlar

### 🛍 Xizmatlar Katalogi
1. **📸 Instagram** — Obunachilar (Followers), Layklar, Ko'rishlar (Views), Izohlar, Reels, Stories
2. **🎵 TikTok** — Obunachilar, Layklar, Ko'rishlar, Ulashishlar (Shares)
3. **📺 YouTube** — Obunachilar, Ko'rishlar, Layklar, Watch Time (4000 soat)
4. **✈️ Telegram** — Obunachilar (Members), Post ko'rishlar, Reaksiyalar
5. **⭐ Telegram Stars** — Stars sotib olish (50, 100, 250, 500, 1000 dona)
6. **💎 Telegram Premium** — 1 oy, 3 oy, 6 oy, 12 oylik obunalar
7. **🖼 NFT & Collectibles** — Telegram Username NFT, Virtual Nomer (+888) NFT, Custom Emoji Pack
8. **🎁 Sovg'alar** — Telegram Gifts, Tug'ilgan kun tabrik xizmati
9. **💠 TON Coin** — 10, 50, 100, 500 TON sotib olish
10. **💵 USDT** — 10$, 50$, 100$, 500$, 1000$ USDT (TRC-20) sotib olish

---

### 💳 To'lov Tizimi
- **Click** (Karta raqami admin paneldan boshqariladi)
- **Payme** (Karta raqami admin paneldan boshqariladi)
- **⭐ Telegram Stars** (Kursi admin paneldan belgilanadi)
- Screenshot yuklash orqali to'lov yuboriladi va adminga/guruhga tasdiqlash uchun boradi.

---

### 👑 Admin Panel & Sozlamalar Boshqaruvi (`/admin`)
Barcha muhim parametrlar botning o'zidan o'zgartiriladi:
- 📊 **Statistika** — Foydalanuvchilar soni, umumiy aylanma, buyurtmalar soni
- 👥 **Foydalanuvchilar boshqaruvi** — ID/Username bo'yicha qidirish, balans qo'shish/ayirish, ban/unban qilish
- 🛍 **Xizmatlar boshqaruvi** — Yangi xizmat/kategoriya qo'shish, istalgan xizmat narxini va nomini o'zgartirish, yoqish/o'chirish
- 💳 **To'lovlarni tasdiqlash** — Screenshotni ko'rib bitta tugma bilan ✅ Tasdiqlash / ❌ Rad etish
- 📢 **Xabar yuborish (Broadcast)** — Barcha foydalanuvchilarga rasm, video yoki matnli e'lon yuborish (progress bar bilan)
- ⚙️ **Bot Sozlamalari**:
  - **Referal bonus foizi** (masalan: 5%)
  - **Minimum to'lov summasi** (masalan: 5000 so'm)
  - **Telegram Stars kursi** (masalan: 1 Star = 1500 so'm)
  - **Click karta raqami va egasi**
  - **Payme karta raqami**
  - **Qo'llab-quvvatlash (@username)**
  - **Majburiy obuna kanallari** (masalan: `kanal1,kanal2`)
  - **Buyurtmalar guruhi ID si** (`order_group_id`)

---

### 📢 Admin Guruh Integratsiyasi
- Yangi buyurtma tushganda, bot **maxsus admin guruhga** buyurtma haqida xabar yuboradi:
  - Mijoz ismi, username, ID si
  - Xizmat nomi va havolasi
  - Miqdor va summa
- Guruh ichidan turib admin tugmalar orqali boshqaradi:
  - `✅ Bajarildi` — Mijozga tabrik va buyurtma tayyorligi haqida xabar boradi
  - `🔄 Jarayonda` — Mijozga buyurtma ishlanayotgani bildiriladi
  - `❌ Rad etish` — Buyurtma bekor qilinadi va mijozning puli **avtomatik tarzda balansiga qaytariladi**!

---

### 🔒 1M+ Foydalanuvchi va Barqarorlik Kafolati
1. **Asinxron Arxitektura:** `aiogram 3.x` va `SQLAlchemy 2.0 (AsyncIO)` barcha so'rovlarni no-blocking tarzda bajaradi.
2. **PostgreSQL Connection Pooling:** Bir vaqtning o'zida yuz minglab ulanishlarni oson ko'taradi.
3. **Redis AOF (Append Only File):** Server kutilmaganda o'chib yonsa ham foydalanuvchilarning to'lov yoki buyurtma jarayonidagi holatlari (FSM) 100% saqlanadi.
4. **Persistent Volumes:** Baza ma'lumotlari (`postgres_data`, `redis_data`) konteyner tashqarisida diskda saqlanadi. Server restart bo'lganda `restart: always` orqali bot avtomatik ishga tushadi.
5. **Anti-Spam Throttling:** Har bir foydalanuvchiga rate-limit qo'yilgan bo'lib, botni server resurslarini to'ldirib yuborishdan (DDoS) himoya qiladi.

---

## 🛠 O'rnatish va Ishga Tushirish

### 1-usul: Docker bilan (Tavsiya qilinadi — Production)
Faqat bitta buyruq bilan PostgreSQL, Redis va Bot birgalikda ishga tushadi:

```bash
docker compose up -d --build
```

Loglarni ko'rish:
```bash
docker compose logs -f bot
```

To'xtatish:
```bash
docker compose down
```

---

### 2-usul: Lokal Ishga Tushirish (Python bilan)

1. Virtual muhit yaratish va faollashtirish:
```bash
python -m venv venv
# Windows uchun:
.\venv\Scripts\activate
# Linux/Mac uchun:
source venv/bin/activate
```

2. Bog'liqliklarni o'rnatish:
```bash
pip install -r requirements.txt
```

3. `.env` faylini to'ldirish:
`.env` faylini oching va bot tokeningiz hamda admin ID laringizni kiriting:
```env
BOT_TOKEN=8721599901:AAGTu4siikElZPkBqgQvGPZEQrvEzZ_ZSSM
ADMIN_IDS=SIZNING_TELEGRAM_ID
ORDER_GROUP_ID=-100XXXXXXXXXX
```

4. Botni ishga tushirish:
```bash
python bot.py
```

---

## 🌐 Render.com ga Joylash (Ma'lumotlar 100% O'chmaydi!)

Loyiha uchun maxsus [`render.yaml`](file:///c:/Users/Rayimjonov/Desktop/smm%20bot/render.yaml) (Blueprint) tayyorlandi. Bu fayl Renderda:
1. **Doimiy PostgreSQL 16** bazasini avtomatik yaratadi.
2. Botni doimiy **Worker** sifatida ishga tushiradi va bazaga ulaydi.
3. Server qayta yonganda yoki yangi versiya yuklanganda ham **barcha balanslar, buyurtmalar va sozlamalar 100% saqlanadi**!

### Qadamlar:
1. Loyihani GitHub repozitoriyangizga yuklang:
   ```bash
   git remote add origin https://github.com/SIZNING_USERNAME/SIZNING_REPO.git
   git branch -M main
   git push -u origin main
   ```
2. **[Render.com](https://dashboard.render.com)** ga kiring.
3. **"New +"** tugmasini bosing va **"Blueprint"** ni tanlang.
4. GitHub repozitoriyangizni tanlang.
5. Render avtomatik ravishda `render.yaml` ni o'qiydi va quyidagilarni so'raydi:
   - `BOT_TOKEN` — `8721599901:AAGTu4siikElZPkBqgQvGPZEQrvEzZ_ZSSM`
   - `ADMIN_IDS` — `8809344628`
   - `ORDER_GROUP_ID` — Buyurtmalar guruhi ID si (ixtiyoriy)
6. **"Apply"** tugmasini bosing.
7. **Bo'ldi!** Render avtomatik ravishda PostgreSQL bazani ishga tushiradi, jadvallarni yaratadi va botni to'xtovsiz yurgizib qo'yadi!
