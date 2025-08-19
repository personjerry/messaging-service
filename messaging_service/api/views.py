from django.shortcuts import render
from .models import Message, Conversation, Participant, Attachment, APIToken, MessageStatus
from django.http import JsonResponse
from tenacity import retry, stop_after_attempt, wait_exponential
from django.views.decorators.http import require_http_methods
import json
from .tasks import attempt_send_message
from django.core.paginator import Paginator
from django.views.decorators.csrf import csrf_exempt

# currently not used so the tests pass, but I'm anticipating we'll need it
def token_required(view_func):
    def wrapped_view(request, *args, **kwargs):
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        if not auth_header or not auth_header.startswith('Token '):
            return JsonResponse({'error': 'Authentication required'}, status=401)
        
        token = auth_header.split(' ')[1]
        try:
            api_token = APIToken.objects.get(token=token)
            request.user = api_token.user
        except APIToken.DoesNotExist:
            return JsonResponse({'error': 'Invalid token'}, status=401)
        
        return view_func(request, *args, **kwargs)
    return wrapped_view

REQUIRED_FIELDS = {'from', 'to', 'body', 'timestamp'}
OPTIONAL_FIELDS = {'messaging_provider_id', 'attachments', 'type'}

def send_entity(request, type):
    try:
      data = json.loads(request.body)
      if not all(field in data for field in REQUIRED_FIELDS):
        return JsonResponse({'error': 'Missing some required fields: ' + ', '.join(REQUIRED_FIELDS - set(data.keys()))}, status=400)
      
      if type == 'email':
        pass
      elif type == 'sms':
        if data['type'] != 'sms' and data['type'] != 'mms':
          return JsonResponse({'error': 'Type must be sms or mms'}, status=400)
        type = data['type']
      else:
        return JsonResponse({'error': 'Invalid type'}, status=400)
      

      from_participant, created = Participant.objects.get_or_create(identifier=data['from'])
      to_participant, created = Participant.objects.get_or_create(identifier=data['to'])

      conversation, created = Conversation.objects.get_or_create_conversation(from_participant, to_participant)


      additional_fields = {k: v for k, v in data.items() if k not in REQUIRED_FIELDS and k not in OPTIONAL_FIELDS}
      message = Message.objects.create(
          conversation=conversation,
          from_participant=from_participant,
          to_participant=to_participant,
          type=type,
          body=data['body'],
          timestamp=data['timestamp'],
          messaging_provider_id=data.get('messaging_provider_id', ''),
          additional_data=additional_fields,
      )
      message.outbound_status = MessageStatus.objects.create()
      message.save()

      for attachment_url in data.get('attachments', []) or []:
        Attachment.objects.create(message=message, url=attachment_url)
    except Exception as e:
      print(e)
      return JsonResponse({'error': 'Error creating message, likely invalid data'}, status=400)
        
    # this is a blocking call, a hack for the sake of the tests; actually dev defaults to CELERY_ALWAYS_EAGER=True anyway
    # in prod we'd use .delay()
    try:
      attempt_send_message.apply(args=[message.id])
    except Exception as e:
      print("Error sending message")
      raise e
    
    message.refresh_from_db()
    return JsonResponse({'message': 'Outbound message saved, send status: ' + str(message.outbound_status.last_http_status_code)}, status=message.outbound_status.last_http_status_code)



# @token_required
@csrf_exempt
@require_http_methods(["POST"])
def send_sms(request):
  return send_entity(request, 'sms')

# @token_required
@csrf_exempt
@require_http_methods(["POST"])
def send_email(request):
  return send_entity(request, 'email')

def receive_entity(request, type):
    try:
      data = json.loads(request.body)
      if not all(field in data for field in REQUIRED_FIELDS):
        return JsonResponse({'error': 'Missing some required fields: ' + ', '.join(REQUIRED_FIELDS - set(data.keys()))}, status=400)

      if type == 'email':
        pass
      elif type == 'sms':
        if data['type'] != 'sms' and data['type'] != 'mms':
          return JsonResponse({'error': 'Type must be sms or mms'}, status=400)
        type = data['type']
      else:
        return JsonResponse({'error': 'Invalid type'}, status=400)
      
      from_participant, created = Participant.objects.get_or_create(identifier=data['from'])
      to_participant, created = Participant.objects.get_or_create(identifier=data['to'])

      conversation, created = Conversation.objects.get_or_create_conversation(from_participant, to_participant)

      additional_fields = {k: v for k, v in data.items() if k not in REQUIRED_FIELDS and k not in OPTIONAL_FIELDS}
      message = Message.objects.create(
          conversation=conversation,
          from_participant=from_participant,
          to_participant=to_participant,
          type=type,
          body=data['body'],
          timestamp=data['timestamp'],
          messaging_provider_id=data.get('messaging_provider_id', ''),
          additional_data=additional_fields,
      )
      message.save()

      for attachment_url in data.get('attachments', []) or []:
        Attachment.objects.create(message=message, url=attachment_url)
    except Exception as e:
      print(e)
      return JsonResponse({'error': 'Error creating message, likely invalid data'}, status=400)

    return JsonResponse({'message': 'Inbound message received and saved'}, status=201)


# @token_required
@csrf_exempt
@require_http_methods(["POST"])
def receive_sms(request):
  return receive_entity(request, 'sms')

# @token_required
@csrf_exempt
@require_http_methods(["POST"])
def receive_email(request):
  return receive_entity(request, 'email')

CONVERSATIONS_PAGE_SIZE = 20

# @token_required
@require_http_methods(["GET"])
def get_conversations(request):
  conversations = Conversation.objects.all()
  paginator = Paginator(conversations, CONVERSATIONS_PAGE_SIZE)

  page_number = request.GET.get('page', 1)
  page = paginator.get_page(page_number)
  return JsonResponse({
    'conversations': [
      {
        'id': conversation.id,
        'participants': [conversation.participant1.identifier, conversation.participant2.identifier],
      }
      for conversation in page.object_list
    ],
    'total_pages': paginator.num_pages,
    'current_page': page.number,
    'has_next': page.has_next(),
    'has_previous': page.has_previous(),
  }, status=200)


MESSAGES_PAGE_SIZE = 20

# @token_required
@require_http_methods(["GET"])
def get_messages(request, conversation_id):
  conversation = Conversation.objects.get(id=conversation_id)
  messages = conversation.messages.all()
  paginator = Paginator(messages, MESSAGES_PAGE_SIZE)
  page_number = request.GET.get('page', 1)
  page = paginator.get_page(page_number)
  return JsonResponse({
    'messages': [
      {
        'id': message.id,
        'body': message.body,
        'timestamp': message.timestamp,
        'type': message.type,
        'from': message.from_participant.identifier,
        'to': message.to_participant.identifier,
        'status': message.outbound_status.send_success if message.outbound_status else None,
        'error_message': message.outbound_status.error_message if message.outbound_status else None,
        'last_http_status_code': message.outbound_status.last_http_status_code if message.outbound_status else None,
        'send_attempts': message.outbound_status.send_attempts if message.outbound_status else 0,
        'additional_data': message.additional_data,
        'attachments': [attachment.url for attachment in message.attachments.all()],
      }
      for message in page.object_list
    ],
    'total_pages': paginator.num_pages,
    'current_page': page.number,
    'has_next': page.has_next(),
    'has_previous': page.has_previous(),
  }, status=200)
