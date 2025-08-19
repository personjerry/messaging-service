from django.urls import path
from messaging_service.api import views

urlpatterns = [
    path("messages/sms/", views.send_sms, name="send_sms"),
    path("messages/email/", views.send_email, name="send_email"),
    path("webhooks/sms/", views.receive_sms, name="receive_sms"),
    path("webhooks/email/", views.receive_email, name="receive_email"),
    path("conversations/", views.get_conversations, name="get_conversations"),
    path("conversations/<int:conversation_id>/messages/", views.get_messages, name="get_messages"),
]

# Need this section because the reader's team didn't add trailing slashes to tests

urlpatterns += [
    path("messages/sms", views.send_sms, name="send_sms"),
    path("messages/email", views.send_email, name="send_email"),
    path("webhooks/sms", views.receive_sms, name="receive_sms"),
    path("webhooks/email", views.receive_email, name="receive_email"),
    path("conversations", views.get_conversations, name="get_conversations"),
    path("conversations/<int:conversation_id>/messages", views.get_messages, name="get_messages"),
]