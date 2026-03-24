import logging
import sqlite3
import re
import os  # Tambahin ini ngab
from datetime import datetime, timedelta
import pytz
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Setup Database SQLite
conn = sqlite3.connect('tugas.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS tugas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        nama_tugas TEXT,
        deadline DATETIME,
        reminded_24h BOOLEAN DEFAULT 0,
        reminded_6h BOOLEAN DEFAULT 0
    )
''')
conn.commit()

timezone = pytz.timezone('Asia/Jakarta')

# Kamus bulan biar bot ngerti bahasa Indonesia
BULAN_IND = {
    'januari': 1, 'jan': 1,
    'februari': 2, 'feb': 2,
    'maret': 3, 'mar': 3,
    'april': 4, 'apr': 4,
    'mei': 5,
    'juni': 6, 'jun': 6,
    'juli': 7, 'jul': 7,
    'agustus': 8, 'agu': 8, 'agus': 8,
    'september': 9, 'sep': 9, 'sept': 9,
    'oktober': 10, 'okt': 10,
    'november': 11, 'nov': 11,
    'desember': 12, 'des': 12
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_msg = (
        "Halo ngab! Bot reminder tugas siap jalan 🫡\n\n"
        "Command:\n"
        "/tambah [nama tugas] [DD Bulan YYYY] [HH:MM opsional]\n"
        "/list - Liat urutan tugas\n"
        "/hapus - Hapus SEMUA tugas"
    )
    await update.message.reply_text(welcome_msg)

async def tambah(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text

    # Regex buat nangkep nama tugas (bisa pakai spasi), tanggal, bulan, tahun, dan opsional jam
    pattern = r'^/tambah\s+(.+?)\s+(\d{1,2})\s+([a-zA-Z]+)\s+(\d{4})(?:\s+(\d{2}:\d{2}))?$'
    match = re.match(pattern, text)
    
    if not match:
        await update.message.reply_text(
            "Formatnya salah ngab! Ditolak ya. Coba input ulang pake format ini:\n"
            "`/tambah [nama tugas] [Tanggal] [Bulan] [Tahun] [Jam opsional]`\n\n"
            "Contoh 1: `/tambah Laporan Kimdas 20 maret 2026`\n"
            "Contoh 2: `/tambah PR Fisika MekPan 22 april 2026 15:00`",
            parse_mode='Markdown'
        )
        return

    nama_tugas = match.group(1).strip()
    tanggal_str = match.group(2)
    bulan_str = match.group(3).lower()
    tahun_str = match.group(4)
    waktu_str = match.group(5) # Ini bisa None kalau jam nggak diisi
    
    # Cek apakah bulannya valid di kamus kita
    if bulan_str not in BULAN_IND:
        await update.message.reply_text("Typo nama bulan tuh ngab. Coba cek lagi yak (contoh: maret, april, des).")
        return
        
    bulan_angka = BULAN_IND[bulan_str]
    
    # Kalau jam nggak diisi, otomatis set ke jam 23:59
    if waktu_str:
        jam_menit = waktu_str
    else:
        jam_menit = "23:59"

    # Validasi kalender sungguhan
    try:
        deadline_str = f"{tahun_str}-{bulan_angka:02d}-{int(tanggal_str):02d} {jam_menit}"
        deadline_dt = datetime.strptime(deadline_str, "%Y-%m-%d %H:%M")
        deadline_dt = timezone.localize(deadline_dt)
    except ValueError:
        await update.message.reply_text("Tanggalnya nggak valid nih ngab. Coba cek lagi kalendernya!")
        return

    if deadline_dt < datetime.now(timezone):
        await update.message.reply_text("Waduh, masa deadline-nya di masa lalu? Coba masukin waktu yang bener ngab.")
        return

    # Masukin ke database
    cursor.execute(
        "INSERT INTO tugas (chat_id, nama_tugas, deadline) VALUES (?, ?, ?)",
        (chat_id, nama_tugas, deadline_dt.isoformat())
    )
    conn.commit()

    await update.message.reply_text(f"Sip! Tugas '{nama_tugas}' aman disimpen.\nDeadline: {tanggal_str} {bulan_str.capitalize()} {tahun_str} jam {jam_menit} WIB. Nanti gw ingetin!")

async def list_tugas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    cursor.execute("SELECT nama_tugas, deadline FROM tugas WHERE chat_id = ? ORDER BY deadline ASC", (chat_id,))
    tugas_list = cursor.fetchall()
    
    if not tugas_list:
        await update.message.reply_text("Aman ngab, lagi nggak ada tugas! Santuy dulu aja ☕")
        return

    msg = "📋 **Daftar Tugas (Urut dari yang paling mepet):**\n\n"
    for idx, tugas in enumerate(tugas_list, 1):
        nama = tugas[0]
        dt = datetime.fromisoformat(tugas[1])
        waktu_format = dt.strftime("%d %B %Y - %H:%M WIB")
        msg += f"{idx}. {nama}\n⏳ {waktu_format}\n\n"
        
    await update.message.reply_text(msg, parse_mode='Markdown')

async def hapus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    cursor.execute("DELETE FROM tugas WHERE chat_id = ?", (chat_id,))
    conn.commit()
    await update.message.reply_text("Beres ngab! Semua tugas di database grup ini udah bersih 🧹")

async def cek_reminder(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(timezone)
    cursor.execute("SELECT id, chat_id, nama_tugas, deadline, reminded_24h, reminded_6h FROM tugas")
    semua_tugas = cursor.fetchall()
    
    for tugas in semua_tugas:
        tugas_id, chat_id, nama_tugas, deadline_iso, rem_24, rem_6 = tugas
        deadline = datetime.fromisoformat(deadline_iso)
        sisa_waktu = deadline - now
        
        if timedelta(hours=6) < sisa_waktu <= timedelta(hours=24) and not rem_24:
            await context.bot.send_message(
                chat_id=chat_id, 
                text=f"⚠️ **REMINDER H-24 JAM** ⚠️\nNgab, jangan lupa kerjain tugas: *{nama_tugas}*\nDeadline: besok jam {deadline.strftime('%H:%M WIB')}!",
                parse_mode='Markdown'
            )
            cursor.execute("UPDATE tugas SET reminded_24h = 1 WHERE id = ?", (tugas_id,))
            conn.commit()
            
        elif sisa_waktu <= timedelta(hours=6) and not rem_6 and sisa_waktu.total_seconds() > 0:
            await context.bot.send_message(
                chat_id=chat_id, 
                text=f"🚨 **REMINDER MEPET (H-6 JAM)** 🚨\nGAS NGERJAIN NGAB! Tugas: *{nama_tugas}*\nDeadline: HARI INI jam {deadline.strftime('%H:%M WIB')}!",
                parse_mode='Markdown'
            )
            cursor.execute("UPDATE tugas SET reminded_6h = 1 WHERE id = ?", (tugas_id,))
            conn.commit()
            
        elif sisa_waktu.total_seconds() < -86400:
            cursor.execute("DELETE FROM tugas WHERE id = ?", (tugas_id,))
            conn.commit()

if __name__ == '__main__':
    # Token ngambil dari environment variable Railway
    TOKEN = os.getenv('TOKEN') 
    
    if not TOKEN:
        print("Waduh, tokennya belum di-set ngab!")
        exit(1)
        
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('tambah', tambah))
    app.add_handler(CommandHandler('list', list_tugas))
    app.add_handler(CommandHandler('hapus', hapus))
    
    job_queue = app.job_queue
    job_queue.run_repeating(cek_reminder, interval=60, first=10)
    
    print("Bot nyala dengan format baru ngab! Tekan Ctrl+C buat matiin.")
    app.run_polling()
