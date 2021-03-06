#!/usr/bin/env python3

# Copyright (C) 2020
# Robert Engler (rengler33@gmail.com)

import logging
import os

from dotenv import load_dotenv
from telegram import (ReplyKeyboardMarkup, ReplyKeyboardRemove, Update)  # type: ignore
from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters,  # type: ignore
                          ConversationHandler, CallbackContext)

from storages import build_uploader

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if BOT_TOKEN is None:
    logger.warning(f"No bot token provided. Exiting.")
    quit()

APPROVED_USER_IDS = os.getenv("APPROVED_USER_IDS")
if APPROVED_USER_IDS:
    APPROVED_USERS = list(map(int, APPROVED_USER_IDS.split(",")))
    logger.info(f"Approved user list restricted to {APPROVED_USERS}")
else:
    logger.info(f"No approved user restrictions supplied. All users will be approved.")

UPLOAD_TO, UPLOAD_FILE = range(2)


def _user_info_text(user):
    return f"{user.first_name} (id: {user.id})"


def start(update: Update, context: CallbackContext):
    user = update.message.from_user
    user_info = _user_info_text(user)
    logger.info(f"{user_info} initiated a conversation with '/start'")

    if user.id in APPROVED_USERS:
        reply_keyboard = [['S3', 'GDrive']]
        update.message.reply_text(
            "Choose a storage service.\nSend /cancel to stop.\n\n",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
        )
        return UPLOAD_TO
    else:
        logger.info(f"{user_info} found to be not authorized.")
        update.message.reply_text(f"{user_info} is not authorized.")
        return


def upload_to(update: Update, context: CallbackContext):
    user = update.message.from_user
    user_info = _user_info_text(user)
    upload_option = update.message.text
    context.user_data["uploader"] = build_uploader(upload_option)
    logger.info(f"{user_info} selected upload to {upload_option} option.")
    update.message.reply_text(f"I will upload files that you send me to {upload_option}. I'm ready to receive files. " +
                              "\nMake sure to send as -file attachments- so that the images/videos are not compressed.",
                              reply_markup=ReplyKeyboardRemove())

    return UPLOAD_FILE


def upload_file(update: Update, context: CallbackContext):
    """
    Receives file attachments (images or videos). Videos are received as message.video even when they are
    file attachments. Images are received as message.photo if not sent as a file attachment, which is undesirable
    because they're compressed. When sent as a file attachments, images are stored as message.document.

    :return: state for this same method to allow user to continue uploading files
    """
    user = update.message.from_user
    user_info = _user_info_text(user)

    file = None
    file_name_from_user = ""
    if update.message.document:
        file_name_from_user = update.message.document["file_name"]
        file = update.message.document.get_file()
    elif update.message.video:
        file_name_from_user = "Video file."  # message does not appear to hold the original file name of a video
        file = update.message.video.get_file()
    elif update.message.photo:
        logger.info(f"{user_info} attempted to upload a photo without attaching as a file.")
        update.message.reply_text(
            "⚠️ Photo not stored. Please only use the -file attachment- option when sending images, " +
            "otherwise they will be compressed.")
    else:  # With appropriate filters on the MessageHandler this should not happen
        update.message.reply_text("Unsupported file type.")
        logger.info(f"Unsupported file type uploaded by {user_info}: {update.message}. Check filters.")
        return UPLOAD_FILE

    if file:
        downloaded_filename = file.download()
        logger.info(f"File downloaded from {user_info}: {downloaded_filename}")
        update.message.reply_text(f'File received.\n{file_name_from_user}', reply_markup=ReplyKeyboardRemove())

        uploader = context.user_data["uploader"]
        upload = uploader.upload_file(downloaded_filename)
        if upload:
            update.message.reply_text(f"File uploaded.")

    return UPLOAD_FILE


def cancel(update: Update, context: CallbackContext):
    user = update.message.from_user
    user_info = _user_info_text(user)
    logger.info(f"User {user_info} canceled the conversation.")
    update.message.reply_text('Finished. Reply /start to start again.', reply_markup=ReplyKeyboardRemove())

    return ConversationHandler.END


def error(update: Update, context: CallbackContext):
    """Log Errors caused by Updates."""
    logger.warning(f"Update '{update}' caused error '{context.error}'")
    update.message.reply_text("I encountered an error.")


def main():
    updater = Updater(BOT_TOKEN, use_context=True)

    dp = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],

        states={
            UPLOAD_TO: [MessageHandler(Filters.regex('^(S3|GDrive)$'), upload_to)],
            UPLOAD_FILE: [MessageHandler(Filters.document.image | Filters.video | Filters.photo, upload_file)],
        },

        fallbacks=[CommandHandler('cancel', cancel)]
    )

    dp.add_handler(conv_handler)
    dp.add_error_handler(error)

    print("Bot is being polled.")
    updater.start_polling()

    updater.idle()


if __name__ == '__main__':
    main()
