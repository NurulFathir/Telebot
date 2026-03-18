import logging
import sqlite3
import re
import os
from datetime import datetime, timedelta
import pytz
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Setup Database SQLite (Support Railway Volume)
db_path = os.getenv('DB_PATH', 'tugas.db')
conn = sqlite3.connect(db_path, check_same_thread=False)
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

# Kamus bulan
BULAN_IND = {
    'januari': 1, 'jan': 1, 'februari': 2, 'feb': 2, 'maret': 3, 'mar': 3,
    'april': 4, 'apr': 4, 'mei': 5, 'juni': 6, 'jun': 6, 'juli': 7, 'jul': 7,
    'agustus': 8, 'agu': 8, 'agus': 8, 'september': 9, 'sep': 9, 'sept': 9,
    'oktober': 10, 'okt': 10, 'november': 11, 'nov': 11, 'desember': 12, 'des': 12
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_msg = (
        "Halo ngab! Bot reminder tugas siap jalan 🫡\n\n"
        "Command:\n"
        "/tambah [nama tugas] [DD Bulan YYYY] [HH:MM opsional]\n"
        "/edit [ID] [nama tugas] [DD Bulan YYYY] [HH:MM opsional]\n"
        "/list - Liat urutan & ID tugas\n"
        "/hapus - Hapus SEMUA tugas"
    )
    await update.message.reply_text(welcome_msg)

async def tambah(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text

    pattern = r'^/tambah\s+(.+?)\s+(\d{1,2})\s+([a-zA-Z]+)\s+(\d{4})(?:\s+(\d{2}:\d{2}))?$'
    match = re.match(pattern, text)
    
    if not match:
        await update.message.reply_text(
            "Format salah ngab! Coba input ulang pake format ini:\n"
            "`/tambah [nama tugas] [Tanggal] [Bulan] [Tahun] [Jam opsional]`",
            parse_mode='Markdown'
        )
        return

    nama_tugas = match.group(1).strip()
    tanggal_str, bulan_str, tahun_str, waktu_str = match.group(2), match.group(3).lower(), match.group(4), match.group(5)
    
    if bulan_str not in BULAN_IND:
        await update.message.reply_text("Typo nama bulan tuh ngab.")
        return
        
    bulan_angka = BULAN_IND[bulan_str]
    jam_menit = waktu_str if waktu_str else "23:59"

    try:
        deadline_str = f"{tahun_str}-{bulan_angka:02d}-{int(tanggal_str):02d} {jam_menit}"
        deadline_dt = datetime.strptime(deadline_str, "%Y-%m-%d %H:%M")
        deadline_dt = timezone.localize(deadline_dt)
    except ValueError:
        await update.message.reply_text("Tanggalnya nggak valid nih ngab.")
        return

    if deadline_dt < datetime.now(timezone):
        await update.message.reply_text("Waduh, masa deadline-nya di masa lalu?")
        return

    cursor.execute("INSERT INTO tugas (chat_id, nama_tugas, deadline) VALUES (?, ?, ?)",
                   (chat_id, nama_tugas, deadline_dt.isoformat()))
    conn.commit()

    await update.message.reply_text(f"Sip! Tugas '{nama_tugas}' aman disimpen.\nDeadline: {tanggal_str} {bulan_str.capitalize()} {tahun_str} jam {jam_menit} WIB.")

# FITUR EDIT BARU
async def edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text

    # Regex nangkep ID, Nama Tugas, Tanggal, Bulan, Tahun, Jam
    pattern = r'^/edit\s+(\d+)\s+(.+?)\s+(\d{1,2})\s+([a-zA-Z]+)\s+(\d{4})(?:\s+(\d{2}:\d{2}))?$'
    match = re.match(pattern, text)
    
    if not match:
        await update.message.reply_text(
            "Format salah ngab! Pake format ini yak:\n"
            "`/edit [ID Tugas] [Nama Tugas Baru] [Tanggal] [Bulan] [Tahun] [Jam opsional]`\n\n"
            "Cek ID Tugas dari command /list. Contoh:\n"
            "`/edit 5 Laporan Elektro 20 maret 2026 15:00`",
            parse_mode='Markdown'
        )
        return

    tugas_id = match.group(1)
    nama_tugas = match.group(2).strip()
    tanggal_str, bulan_str, tahun_str, waktu_str = match.group(3), match.group(4).lower(), match.group(5), match.group(6)
    
    if bulan_str not in BULAN_IND:
        await update.message.reply_text("Typo nama bulan tuh ngab.")
        return
        
    bulan_angka = BULAN_IND[bulan_str]
    jam_menit = waktu_str if waktu_str else "23:59"

    try:
        deadline_str = f"{tahun_str}-{bulan_angka:02d}-{int(tanggal_str):02d} {jam_menit}"
        deadline_dt = datetime.strptime(deadline_str, "%Y-%m-%d %H:%M")
        deadline_dt = timezone.localize(deadline_dt)
    except ValueError:
        await update.message.reply_text("Tanggalnya nggak valid nih ngab.")
        return

    if deadline_dt < datetime.now(timezone):
        await update.message.reply_text("Masa diubah ke masa lalu? Coba masukin waktu yang bener ngab.")
        return

    # Cek ID tugas beneran ada di grup ini nggak
    cursor.execute("SELECT id FROM tugas WHERE id = ? AND chat_id = ?", (tugas_id, chat_id))
    if not cursor.fetchone():
        await update.message.reply_text(f"ID tugas {tugas_id} nggak ketemu ngab. Cek lagi pake /list.")
        return

    # Update data & reset status reminder biar diingetin ulang
    cursor.execute(
        """UPDATE tugas 
           SET nama_tugas = ?, deadline = ?, reminded_24h = 0, reminded_6h = 0 
           WHERE id = ? AND chat_id = ?""",
        (nama_tugas, deadline_dt.isoformat(), tugas_id, chat_id)
    )
    conn.commit()

    await update.message.reply_text(f"Mantap! Tugas ID {tugas_id} udah di-update jadi '{nama_tugas}'.\nDeadline baru: {tanggal_str} {bulan_str.capitalize()} {tahun_str} jam {jam_menit} WIB.")

# UPDATE LIST BIAR NAMPILIN ID TUGAS
async def list_tugas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    cursor.execute("SELECT id, nama_tugas, deadline FROM tugas WHERE chat_id = ? ORDER BY deadline ASC", (chat_id,))
    tugas_list = cursor.fetchall()
    
    if not tugas_list:
        await update.message.reply_text("Aman ngab, lagi nggak ada tugas! Santuy dulu aja ☕")
        return

    msg = "📋 **Daftar Tugas:**\n*(Pake ID buat ngedit tugas)*\n\n"
    for tugas in tugas_list:
        tugas_id, nama, deadline_iso = tugas
        dt = datetime.fromisoformat(deadline_iso)
        waktu_format = dt.strftime("%d %B %Y - %H:%M WIB")
        msg += f"**ID: {tugas_id}** | {nama}\n⏳ {waktu_format}\n\n"
        
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
            
        # Hapus otomatis kalau deadline udah lewat 7 hari (604800 detik)
        elif sisa_waktu.total_seconds() < -604800:
            cursor.execute("DELETE FROM tugas WHERE id = ?", (tugas_id,))
            conn.commit()

if __name__ == '__main__':
    TOKEN = os.getenv('TOKEN') 
    
    if not TOKEN:
        print("Tokennya belum di-set di environment variable ngab!")
        exit(1)
        
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('tambah', tambah))
    app.add_handler(CommandHandler('edit', edit)) # Daftarin command edit
    app.add_handler(CommandHandler('list', list_tugas))
    app.add_handler(CommandHandler('hapus', hapus))
    
    job_queue = app.job_queue
    job_queue.run_repeating(cek_reminder, interval=60, first=10)
    
    print("Bot nyala ngab! Tekan Ctrl+C buat matiin.")
    app.run_polling()
