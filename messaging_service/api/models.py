from django.db import models
from django.core.exceptions import ValidationError

# Create your models here.

class Participant(models.Model):
    identifier = models.CharField(max_length=255, unique=True) # email or phone number
    
    def __str__(self):
        return f"{self.identifier}"


# ========================= For reader convenience, this is boring django code to make sure WLOG you can query two users get the same conversation.
class ConversationQuerySet(models.QuerySet):
    def _normalize_participants(self, participant1, participant2):
        """Ensure consistent ordering of participants"""
        # Handle both Participant objects and IDs
        if hasattr(participant1, 'id') and hasattr(participant2, 'id'):
            if participant1.id > participant2.id:
                return participant2, participant1
        elif participant1 > participant2:  # If passing IDs directly
            return participant2, participant1
        return participant1, participant2
    
    def get_conversation(self, participant1, participant2):
        """Get conversation between two participants, handling order automatically"""
        p1, p2 = self._normalize_participants(participant1, participant2)
        return self.get(participant1=p1, participant2=p2)
    
    def filter_by_participants(self, participant1, participant2):
        """Filter conversations between two participants"""
        p1, p2 = self._normalize_participants(participant1, participant2)
        return self.filter(participant1=p1, participant2=p2)
    
    def for_participant(self, participant):
        """Get all conversations for a specific participant"""
        return self.filter(
            models.Q(participant1=participant) | models.Q(participant2=participant)
        )
    
    def by_identifier(self, identifier1, identifier2):
        """Find conversation by participant identifiers (email/phone)"""
        try:
            p1 = Participant.objects.get(identifier=identifier1)
            p2 = Participant.objects.get(identifier=identifier2)
            return self.get_conversation(p1, p2)
        except Participant.DoesNotExist:
            raise Conversation.DoesNotExist("One or both participants not found")

class ConversationManager(models.Manager):
    def get_queryset(self):
        return ConversationQuerySet(self.model, using=self._db)
    
    def get_conversation(self, participant1, participant2):
        return self.get_queryset().get_conversation(participant1, participant2)
    
    def filter_by_participants(self, participant1, participant2):
        return self.get_queryset().filter_by_participants(participant1, participant2)
    
    def for_participant(self, participant):
        return self.get_queryset().for_participant(participant)
    
    def by_identifier(self, identifier1, identifier2):
        return self.get_queryset().by_identifier(identifier1, identifier2)
    
    def create_conversation(self, participant1, participant2, **kwargs):
        """Create a conversation with normalized participant order"""
        if participant1 == participant2:
            raise ValidationError("A conversation cannot be between the same participant.")
        
        p1, p2 = self.get_queryset()._normalize_participants(participant1, participant2)
        return self.create(participant1=p1, participant2=p2, **kwargs)
    
    def get_or_create_conversation(self, participant1, participant2, **kwargs):
        """Get or create a conversation between two participants"""
        if participant1 == participant2:
            raise ValidationError("A conversation cannot be between the same participant.")
        
        p1, p2 = self.get_queryset()._normalize_participants(participant1, participant2)
        return self.get_or_create(participant1=p1, participant2=p2, **kwargs)
    
    def get_or_create_by_identifier(self, identifier1, identifier2, **kwargs):
        """Get or create conversation by participant identifiers"""
        p1, _ = Participant.objects.get_or_create(identifier=identifier1)
        p2, _ = Participant.objects.get_or_create(identifier=identifier2)
        return self.get_or_create_conversation(p1, p2, **kwargs)

# ========================= End of boring django code

class Conversation(models.Model):
    participant1 = models.ForeignKey(
        Participant, 
        on_delete=models.CASCADE, 
        related_name='conversations_as_p1'
    )
    participant2 = models.ForeignKey(
        Participant, 
        on_delete=models.CASCADE, 
        related_name='conversations_as_p2'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    objects = ConversationManager()
    
    class Meta:
        unique_together = ['participant1', 'participant2']
    
    def clean(self):
        if self.participant1 == self.participant2:
            raise ValidationError("A conversation cannot be between the same participant.")
    
    def save(self, *args, **kwargs):
        # Ensure consistent ordering (lower ID first)
        if self.participant1.id > self.participant2.id:
            self.participant1, self.participant2 = self.participant2, self.participant1
        self.full_clean()
        super().save(*args, **kwargs)
    
    def get_other_participant(self, participant):
        """Get the other participant in the conversation"""
        if self.participant1 == participant:
            return self.participant2
        elif self.participant2 == participant:
            return self.participant1
        else:
            raise ValueError("Participant is not part of this conversation")
    
    def __str__(self):
        return f"Conversation between {self.participant1} and {self.participant2}"

    class Meta: 
        ordering = ['-created_at']
    
class MessageStatus(models.Model):
    send_attempts = models.IntegerField(default=0)
    send_success = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)
    last_http_status_code = models.IntegerField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.id}: Send Attempt {self.send_attempts}. Success: {self.send_success}. Error Message: {self.error_message}"


class Message(models.Model):
    # existence of status implies it's outbound
    outbound_status = models.OneToOneField(MessageStatus, on_delete=models.CASCADE, blank=True, null=True)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    to_participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name='messages_to')
    from_participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name='messages_from')
    body = models.TextField()
    timestamp = models.DateTimeField()
    type = models.CharField(max_length=255)
    messaging_provider_id = models.CharField(max_length=255)
    additional_data = models.JSONField(default=dict)

    def __str__(self):
        return f"{self.id}: {self.body} from {self.from_participant} to {self.to_participant} at {self.timestamp}. Type: {self.type}. Messaging Provider ID: {self.messaging_provider_id}. Outbound: {self.outbound_status is not None}. Send Attempts: {self.outbound_status.send_attempts if self.outbound_status else 0}. Additional Data: {self.additional_data}"

    class Meta: 
        ordering = ['-timestamp']

class Attachment(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='attachments')
    url = models.URLField()






# Just in case, preparing for your questions in advance:
import secrets
from django.conf import settings

class APIToken(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    token = models.CharField(max_length=40, unique=True)
    created = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_hex(20)
        super().save(*args, **kwargs)