from django.contrib import admin

# Register your models here.
from .models import Conversation, Message, MessageStatus, Participant, Attachment

admin.site.register(Conversation)
admin.site.register(Message)
admin.site.register(MessageStatus)
admin.site.register(Participant)
admin.site.register(Attachment)