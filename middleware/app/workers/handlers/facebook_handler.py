"""Accumulate Messenger purchases across messages, including anonymous chats."""
from app.services.facebook_service import fetch_facebook_user_profile
from app.services.facebook_draft_service import process_message


def handle_facebook_message(data: dict):
    process_message(data, fetch_facebook_user_profile(data['sender_id']))
