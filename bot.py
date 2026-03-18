import json
import os
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import asyncio

TOKEN = os.getenv("TOKEN")
FILE = "tugas.json"

# ================== DATA ==================

def load_data():
    try:
        with open(FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_data(data):
    with open(FILE, "w") as f:
        json.dump(data, f, indent=4)

# ================== COMMAND ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # jalankan scheduler
    context.job_queue.run_repeating(
        cek_deadline,
        interval=60,   # cek tiap 60 detik
        first=10,
        chat_id=chat_id
    )

    await update.message.reply_text("Bot aktif di chat ini 🔥")

# tambah tugas
async def tambah(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        nama = context.args[0]
        tanggal = context.args[1]
        waktu = context.args[2]

        deadline = f"{tanggal} {waktu}"

        data = load_data()
        data.append({
            "nama": nama,
            "deadline": deadline,
            "reminded_1d": False,
            "reminded_6h": False
        })

        save_data(data)

        await update.message.reply_text(f"Tugas '{nama}' ditambahkan ✅")

    except:
        await update.message.reply_text(
            "Format:\n/tambah nama_tugas YYYY-MM-DD HH:MM"
        )

# hapus semua
async def hapus_semua(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_data([])
    await update.message.reply_text("Semua tugas berhasil dihapus 🗑️")

# list tugas
async def list_tugas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()

    if not data:
        await update.message.reply_text("Tidak ada tugas 😎")
        return

    now = datetime.now()

    data_baru = []
    for t in data:
        dl = datetime.strptime(t["deadline"], "%Y-%m-%d %H:%M")
        if now <= dl + timedelta(days=7):
            data_baru.append(t)

    save_data(data_baru)

    data_baru.sort(key=lambda x: x["deadline"])

    pesan = "📋 Daftar Tugas:\n\n"
    for t in data_baru:
        pesan += f"- {t['nama']} → {t['deadline']}\n"

    await update.message.reply_text(pesan)

# ================== REMINDER ==================

async def cek_deadline(context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    now = datetime.now()
    updated = False

    for t in data:
        dl = datetime.strptime(t["deadline"], "%Y-%m-%d %H:%M")
        selisih = dl - now

        # ⏰ H-1 hari
        if (not t.get("reminded_1d") and 
            timedelta(hours=23, minutes=59) < selisih <= timedelta(days=1)):

            await context.bot.send_message(
                chat_id=context.job.chat_id,
                text=f"📅 Besok deadline: {t['nama']}!"
            )
            t["reminded_1d"] = True
            updated = True

        # ⏰ H-6 jam
        if (not t.get("reminded_6h") and 
            timedelta(hours=5, minutes=59) < selisih <= timedelta(hours=6)):

            await context.bot.send_message(
                chat_id=context.job.chat_id,
                text=f"⏰ 6 jam lagi: {t['nama']}!"
            )
            t["reminded_6h"] = True
            updated = True

    if updated:
        save_data(data)

# ================== MAIN ==================

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("tambah", tambah))
app.add_handler(CommandHandler("list", list_tugas))
app.add_handler(CommandHandler("hapus_semua", hapus_semua))

print("Bot jalan...")
app.run_polling()
