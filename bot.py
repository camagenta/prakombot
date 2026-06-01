#!/usr/bin/env python3
"""
Telegram bot for join request verification.
6-step conversation: NAMA → NIP → INSTANSI → JENJANG → BUKTI → KONFIRMASI
Auto-approves on valid submission, declines on failure.
Admin commands: /stats, /pending, /approve <user_id>, /reject <user_id>
"""

import logging
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ChatJoinRequestHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import Config
from database import get_verification_by_user, init_db, save_verification, update_status

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

NAMA, NIP, INSTANSI, JENJANG, BUKTI, KONFIRMASI = range(6)

JENJANG_OPTIONS = ["Terampil", "Mahir", "Penyelia"]
VALID_EXTENSIONS = (".jpg", ".jpeg", ".png", ".pdf")


def is_admin(user_id: int) -> bool:
    return user_id in Config().admin_ids


# ── Conversation: /start → verification flow ─────────────────────────────────


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    args = context.args

    # If user came from deep link with start=verify, go straight to verification
    if args and args[0] == "verify":
        return await _start_verification(update, context)

    # Regular start
    await update.message.reply_text(
        f"Selamat datang, {user.first_name}! 👋\n\n"
        "Gunakan /verify untuk memulai verifikasi dan bergabung ke grup Prakom.\n"
        "Gunakan /cancel kapan saja untuk membatalkan."
    )
    return ConversationHandler.END


async def verify_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _start_verification(update, context)


async def _start_verification(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user

    # Check if already verified
    existing = await get_verification_by_user(user.id)
    if existing and existing["status"] == "approved":
        await update.message.reply_text(
            "✅ Anda sudah terverifikasi sebelumnya. "
            "Silakan cek grup — request Anda seharusnya sudah di-approve."
        )
        return ConversationHandler.END

    await update.message.reply_text(
        f"Halo {user.first_name}! 👋\n\n"
        "Kami akan memverifikasi data Anda untuk bergabung ke grup Prakom.\n"
        "Silakan ikuti langkah-langkah berikut:\n\n"
        "1️⃣ Nama Lengkap\n"
        "2️⃣ NIP (18 digit)\n"
        "3️⃣ Instansi\n"
        "4️⃣ Jenjang Prakom\n"
        "5️⃣ Upload Bukti (foto/PDF)\n"
        "6️⃣ Review & Konfirmasi\n\n"
        "Ketik /cancel kapan saja untuk membatalkan.\n\n"
        "Silakan masukkan Nama Lengkap Anda:"
    )
    return NAMA


async def cancel(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "❌ Proses verifikasi dibatalkan.\nKetik /verify untuk memulai lagi."
    )
    return ConversationHandler.END


# ── Step handlers ─────────────────────────────────────────────────────────────


async def nama_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if len(text) < 3:
        await update.message.reply_text("Nama harus minimal 3 karakter. Silakan masukkan lagi:")
        return NAMA
    context.user_data["nama"] = text
    await update.message.reply_text(
        f"Terima kasih, {text}! 👍\n\nSekarang masukkan NIP Anda (18 digit angka):"
    )
    return NIP


async def nip_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not text.isdigit() or len(text) != 18:
        await update.message.reply_text("NIP harus 18 digit angka. Silakan masukkan lagi:")
        return NIP
    context.user_data["nip"] = text
    await update.message.reply_text("Masukkan Instansi / Organisasi Anda (minimal 3 karakter):")
    return INSTANSI


async def instansi_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if len(text) < 3:
        await update.message.reply_text("Instansi harus minimal 3 karakter. Silakan masukkan lagi:")
        return INSTANSI
    context.user_data["instansi"] = text

    keyboard = [
        [InlineKeyboardButton(j, callback_data=j)] for j in JENJANG_OPTIONS
    ]
    await update.message.reply_text(
        "Pilih Jenjang Prakom Anda:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return JENJANG


async def jenjang_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data
    if choice not in JENJANG_OPTIONS:
        keyboard = [
            [InlineKeyboardButton(j, callback_data=j)] for j in JENJANG_OPTIONS
        ]
        await query.edit_message_text(
            "Pilihan tidak valid. Silakan pilih:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return JENJANG
    context.user_data["jenjang"] = choice
    await query.edit_message_text(
        f"Jenjang: {choice} ✅\n\nSekarang upload bukti pendukung (foto JPG/PNG atau PDF):"
    )
    return BUKTI


async def bukti_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    is_photo = bool(update.message.photo)
    doc = update.message.document

    if doc:
        if not doc.file_name or not doc.file_name.lower().endswith(VALID_EXTENSIONS):
            await update.message.reply_text(
                "Format file tidak didukung. Harap upload foto (JPG/PNG) atau PDF."
            )
            return BUKTI
        file_id = doc.file_id
    elif is_photo:
        file_id = update.message.photo[-1].file_id
    else:
        await update.message.reply_text("Silakan upload file foto atau PDF.")
        return BUKTI

    context.user_data["file_id"] = file_id

    data = context.user_data
    summary = (
        "📋 Review Data Anda:\n\n"
        f"Nama: {data['nama']}\n"
        f"NIP: {data['nip']}\n"
        f"Instansi: {data['instansi']}\n"
        f"Jenjang: {data['jenjang']}\n"
        f"Bukti: Terlampir ✅\n\n"
        "Apakah data di atas sudah benar?"
    )
    keyboard = [
        [
            InlineKeyboardButton("✅ Ya, Kirim", callback_data="confirm"),
            InlineKeyboardButton("❌ Batal", callback_data="cancel"),
        ]
    ]
    await update.message.reply_text(
        summary,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return KONFIRMASI


async def confirm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "cancel":
        await query.edit_message_text("❌ Dibatalkan. Ketik /verify untuk memulai ulang.")
        context.user_data.clear()
        return ConversationHandler.END

    user = update.effective_user
    data = context.user_data
    cfg = Config()
    cfg.validate_bot()

    # Save to DB
    try:
        verif_id = await save_verification(
            user_id=user.id,
            nama=data["nama"],
            nip=data["nip"],
            instansi=data["instansi"],
            jenjang=data["jenjang"],
            file_id=data["file_id"],
        )
        logger.info("Verification saved: id=%d, user=%d", verif_id, user.id)
    except Exception as exc:
        logger.error("Failed to save verification: %s", exc)
        await query.edit_message_text("⚠️ Terjadi kesalahan sistem. Silakan coba lagi nanti.")
        context.user_data.clear()
        return ConversationHandler.END

    # Approve join request
    approved = False
    try:
        await context.bot.approve_chat_join_request(
            chat_id=cfg.group_id, user_id=user.id
        )
        approved = True
        await update_status(verif_id, "approved")
        logger.info("✅ Join request approved for user %d", user.id)
    except Exception as exc:
        logger.warning("Failed to approve join for user %d: %s", user.id, exc)
        try:
            await context.bot.decline_chat_join_request(
                chat_id=cfg.group_id, user_id=user.id
            )
            await update_status(verif_id, "rejected")
            logger.info("Join request declined for user %d", user.id)
        except Exception as inner_err:
            logger.error("Failed to decline join for user %d: %s", user.id, inner_err)

    if approved:
        await query.edit_message_text(
            "🎉 Verifikasi Berhasil!\n\n"
            "Data Anda telah diterima dan permintaan bergabung ke grup "
            "telah disetujui. Silakan cek grup.\n\n"
            "Terima kasih!"
        )
    else:
        await query.edit_message_text(
            "⚠️ Verifikasi Gagal\n\n"
            "Mohon maaf, permintaan bergabung Anda tidak dapat diproses. "
            "Silakan hubungi admin untuk informasi lebih lanjut."
        )

    # Forward to admins
    await _forward_to_admins(update, context, verif_id, approved)
    context.user_data.clear()
    return ConversationHandler.END


async def _forward_to_admins(
    update: Update, context: ContextTypes.DEFAULT_TYPE, verif_id: int, approved: bool
) -> None:
    cfg = Config()
    if not cfg.admin_ids:
        return
    data = context.user_data
    status_text = "✅ DISETUJUI" if approved else "❌ DITOLAK"
    msg = (
        f"🔔 Verifikasi Baru\n\n"
        f"ID: {verif_id}\n"
        f"User: {update.effective_user.full_name}\n"
        f"User ID: {update.effective_user.id}\n"
        f"Username: @{update.effective_user.username or '-'}\n"
        f"Nama: {data.get('nama', 'N/A')}\n"
        f"NIP: {data.get('nip', 'N/A')}\n"
        f"Instansi: {data.get('instansi', 'N/A')}\n"
        f"Jenjang: {data.get('jenjang', 'N/A')}\n"
        f"Status: {status_text}"
    )
    for admin_id in cfg.admin_ids:
        try:
            await context.bot.send_message(admin_id, msg)
            if data.get("file_id"):
                try:
                    await context.bot.send_document(admin_id, data["file_id"])
                except Exception:
                    pass
        except Exception as exc:
            logger.error("Failed to forward to admin %d: %s", admin_id, exc)


# ── Auto-reply to join requests ──────────────────────────────────────────────


async def handle_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Auto-reply when user requests to join the group."""
    join_req = update.chat_join_request
    user = join_req.from_user
    logger.info(
        "Join request from %s (ID: %d) for chat %s",
        user.full_name, user.id, join_req.chat.title,
    )

    bot_user = await context.bot.get_me()
    bot_username = bot_user.username or "bot"
    try:
        await context.bot.send_message(
            user.id,
            f"Halo {user.first_name}! 👋\n\n"
            "Kami menerima permintaan bergabung Anda ke grup Prakom.\n"
            "Untuk menyelesaikan verifikasi, silakan klik link di bawah:\n\n"
            f"https://t.me/{bot_username}?start=verify\n\n"
            "Setelah verifikasi selesai, request Anda akan di-approve otomatis.\n\n"
            "Terima kasih!",
        )
    except Exception as exc:
        logger.warning("Cannot DM user %d: %s", user.id, exc)


# ── Admin commands ────────────────────────────────────────────────────────────


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show verification stats. Admin only."""
    if not is_admin(update.effective_user.id):
        return

    import aiosqlite

    async with aiosqlite.connect("verifications.db") as db:
        db.row_factory = aiosqlite.Row

        cur = await db.execute("SELECT COUNT(*) as cnt FROM verifications")
        total = (await cur.fetchone())["cnt"]

        cur = await db.execute("SELECT COUNT(*) as cnt FROM verifications WHERE status='approved'")
        approved = (await cur.fetchone())["cnt"]

        cur = await db.execute("SELECT COUNT(*) as cnt FROM verifications WHERE status='rejected'")
        rejected = (await cur.fetchone())["cnt"]

        cur = await db.execute("SELECT COUNT(*) as cnt FROM verifications WHERE status='pending'")
        pending = (await cur.fetchone())["cnt"]

    await update.message.reply_text(
        f"📊 Statistik Verifikasi\n\n"
        f"Total: {total}\n"
        f"✅ Approved: {approved}\n"
        f"❌ Rejected: {rejected}\n"
        f"⏳ Pending: {pending}"
    )


async def admin_pending(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List pending verifications. Admin only."""
    if not is_admin(update.effective_user.id):
        return

    import aiosqlite

    async with aiosqlite.connect("verifications.db") as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT id, user_id, nama, nip, instansi, jenjang, created_at "
            "FROM verifications WHERE status='pending' ORDER BY id DESC LIMIT 20"
        )
        rows = await cur.fetchall()

    if not rows:
        await update.message.reply_text("Tidak ada verifikasi pending.")
        return

    lines = ["⏳ Verifikasi Pending (max 20 terakhir):\n"]
    for r in rows:
        lines.append(
            f"#{r['id']} | {r['nama']} | NIP: {r['nip']}\n"
            f"   Instansi: {r['instansi']} | Jenjang: {r['jenjang']}\n"
            f"   User ID: {r['user_id']} | {r['created_at']}\n"
        )

    await update.message.reply_text("\n".join(lines))


async def admin_approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Approve a user by user_id. Admin only. Usage: /approve <user_id>"""
    if not is_admin(update.effective_user.id):
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /approve <user_id>")
        return

    user_id = int(context.args[0])
    cfg = Config()
    cfg.validate_bot()

    try:
        await context.bot.approve_chat_join_request(chat_id=cfg.group_id, user_id=user_id)
        await update.message.reply_text(f"✅ User {user_id} di-approve.")
        logger.info("Admin %d approved user %d", update.effective_user.id, user_id)
    except Exception as exc:
        await update.message.reply_text(f"❌ Gagal approve: {exc}")


async def admin_reject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reject a user by user_id. Admin only. Usage: /reject <user_id>"""
    if not is_admin(update.effective_user.id):
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /reject <user_id>")
        return

    user_id = int(context.args[0])
    cfg = Config()
    cfg.validate_bot()

    try:
        await context.bot.decline_chat_join_request(chat_id=cfg.group_id, user_id=user_id)
        await update.message.reply_text(f"❌ User {user_id} di-reject.")
        logger.info("Admin %d rejected user %d", update.effective_user.id, user_id)
    except Exception as exc:
        await update.message.reply_text(f"❌ Gagal reject: {exc}")


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    cfg = Config()
    cfg.validate_bot()

    app = (
        Application.builder()
        .token(cfg.bot_token)
        .read_timeout(30)
        .write_timeout(30)
        .build()
    )

    # Conversation handler for /verify
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("verify", verify_command),
        ],
        states={
            NAMA: [MessageHandler(filters.TEXT & ~filters.COMMAND, nama_handler)],
            NIP: [MessageHandler(filters.TEXT & ~filters.COMMAND, nip_handler)],
            INSTANSI: [MessageHandler(filters.TEXT & ~filters.COMMAND, instansi_handler)],
            JENJANG: [CallbackQueryHandler(jenjang_handler)],
            BUKTI: [
                MessageHandler(
                    filters.PHOTO | filters.Document.ALL,
                    bukti_handler,
                )
            ],
            KONFIRMASI: [CallbackQueryHandler(confirm_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)

    # Auto-reply to join requests
    app.add_handler(ChatJoinRequestHandler(handle_join_request))

    # Admin commands
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler("pending", admin_pending))
    app.add_handler(CommandHandler("approve", admin_approve))
    app.add_handler(CommandHandler("reject", admin_reject))

    logger.info("🤖 Bot started. Waiting for updates...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    import asyncio

    asyncio.run(init_db())
    main()
