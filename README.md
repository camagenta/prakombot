# PrakomBot — Telegram Join Request Verification Bot

Bot verifikasi otomatis untuk menyeleksi pending join request di group Telegram.

## Arsitektur

```
┌─── Real-time path (saat user request join) ────────────────────────┐
│                                                                     │
│  User ──request join──► Group ──ChatJoinRequest──► bot.py           │
│                                              │                       │
│                                              ▼                       │
│                                  bot.py auto-DM (Bot API)            │
│                                  dengan link verifikasi             │
│                                              │                       │
│  User ──klik link──► /verify                                       │
│                                              │                       │
│                                              ▼                       │
│                                 6-step verification:                │
│                                 Nama → NIP → Instansi →             │
│                                 Jenjang → Bukti → Submit            │
│                                              │                       │
│                                              ▼                       │
│                              approve/decline join request          │
│                                              │                       │
│                                              ▼                       │
│                                     Admin notification              │
└─────────────────────────────────────────────────────────────────────┘

┌─── Catch-up path (untuk pending yang belum verify) ─────────────────┐
│                                                                     │
│  broadcast.py (cron job, daily)                                     │
│       │                                                             │
│       ├─► Bot API: getChatJoinRequests (ambil pending)              │
│       │                                                             │
│       └─► Telethon (akun admin): DM up to 10 user/hari              │
│              dengan link verifikasi yang sama                       │
└─────────────────────────────────────────────────────────────────────┘
```

**Dual-DM behavior**: bot.py men-DM user secara real-time begitu mereka
request join, sehingga pada praktiknya sebagian besar user tidak butuh
catch-up broadcast. broadcast.py hanya perlu mengejar user yang request
join SEBELUM bot.py sempat online (misal saat restart/maintenance), atau
yang request join lalu mengabaikan DM pertama.

## Setup

### 1. Buat Bot via BotFather
- Chat [@BotFather](https://t.me/BotFather) → `/newbot`
- Simpan **BOT_TOKEN**
- Set username bot → simpan **BOT_USERNAME**

### 2. Dapatkan API ID & API Hash (Telethon)
- Buka [my.telegram.org](https://my.telegram.org)
- Login → API Development Tools → Create App
- Simpan **API_ID** dan **API_HASH**
- Gunakan akun Telegram admin group (bukan bot)

### 3. Dapatkan Group Chat ID
- Tambahkan bot ke group sebagai **admin** (permission: Add Members, Ban Users)
- Buka `https://api.telegram.org/bot<BOT_TOKEN>/getUpdates`
- Cari `"chat":{"id":-100...}` → itu **GROUP_ID**

### 4. Install & Configure

```bash
git clone https://github.com/camagenta/prakombot.git
cd prakombot

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env dengan credentials kamu
```

### 5. File .env

```env
BOT_TOKEN=123456:ABC-DEF...
BOT_USERNAME=your_bot_username
API_ID=123456
API_HASH=your_api_hash_here
GROUP_ID=-1001234567890
ADMIN_IDS=123456789,987654321
```

## Penggunaan

### Bot (jalanin terus-menerus)

```bash
python bot.py
```

### Broadcast (cron job — jalanin berkala)

```bash
# Kirim DM ke pending users (max 10/hari)
python broadcast.py

# Lihat stats
python broadcast.py --stats

# Reset log
python broadcast.py --reset-log
```

### Cron Setup

```bash
# Jalankan broadcast setiap hari jam 9 pagi
crontab -e
0 9 * * * cd /path/to/prakombot && /path/to/venv/bin/python broadcast.py >> /var/log/prakombot.log 2>&1
```

## Flow Verifikasi

1. User request join group → Bot auto-reply DM dengan link verifikasi
2. User klik link → `/start verify` atau `/verify`
3. Bot tanya step-by-step: Nama → NIP → Instansi → Jenjang → Bukti
4. User submit → Bot approve/decline join request
5. Admin dapat notifikasi hasil verifikasi

## Admin Commands

| Command | Deskripsi |
|---------|-----------|
| `/stats` | Lihat statistik verifikasi |
| `/pending` | List verifikasi pending |
| `/approve <user_id>` | Approve user manual |
| `/reject <user_id>` | Reject user manual |

## Verifikasi Logic

- **Nama**: min 3 karakter
- **NIP**: 18 digit angka
- **Instansi**: min 3 karakter
- **Jenjang**: Terampil / Mahir / Penyelia
- **Bukti**: Foto (JPG/PNG) atau PDF
- Auto-approve jika semua data valid

## Project Structure

```
prakombot/
├── bot.py              # Main bot (ConversationHandler)
├── broadcast.py        # Telethon broadcast script
├── database.py         # SQLite async database
├── config.py           # Env config loader
├── requirements.txt
├── .env.example
└── README.md
```

## Estimate Timeline

- **Real-time (bot.py)**: instant — setiap join request yang masuk saat bot online akan langsung di-DM
- **Catch-up (broadcast.py)**: 10 DM/hari via Telethon — mengejar pending yang terlewat
- Worst case (bot offline lama + 1500 backlog): ~150 hari via broadcast saja
- Realistic case (bot online 99% waktu): broadcast hanya mengejar sisanya, biasanya selesai dalam hitungan hari

Broadcast juga otomatis me-retry user yang di-DM hari-hari sebelumnya
tetapi belum menyelesaikan verifikasi (filter scope = hari ini saja).
