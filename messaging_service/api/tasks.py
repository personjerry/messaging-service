from celery import shared_task
from .models import Message
from .integrations import send_sms, send_email
from requests.exceptions import RequestException

MAX_SEND_ATTEMPTS = 3
SEND_BASE_DELAY = 3

# Note that Celery making requests will block the worker from processing other tasks.
# But these requests are short-lived, so it shouldn't be a big deal.
@shared_task
def attempt_send_message(message_id):

    message = Message.objects.get(id=message_id)

    if not message.outbound_status:
        return
    
    if message.outbound_status.send_attempts >= MAX_SEND_ATTEMPTS:
        print(f"Message {message_id} failed after {MAX_SEND_ATTEMPTS} attempts. Giving up.")
        message.outbound_status.send_success = False
        message.outbound_status.error_message = f"Failed after {MAX_SEND_ATTEMPTS} attempts"
        message.save()
        return
    
    message.outbound_status.send_attempts += 1
    message.save()

    try:
        if message.type == 'sms' or message.type == 'mms':
            response = send_sms(message)
        elif message.type == 'email':
            response = send_email(message)
        else:
            raise ValueError(f"Invalid message type: {message.type}")
        
        # In theory we could add a "retry message" too but I'm already over-engineering this for this exercise
        # Basically, retry if appropriate, otherwise give up
        message.outbound_status.last_http_status_code = response.status_code
        message.save()

        if response.status_code in [200, 201, 202, 204]:
            message.outbound_status.send_success = True
            message.save()
        elif response.status_code == 429:
            retry_after = response.headers.get('Retry-After')
            if retry_after:
                retry_after = int(retry_after)
                attempt_send_message.apply_async(args=[message_id], countdown=retry_after)
            else:
                attempt_send_message.apply_async(args=[message_id], countdown=SEND_BASE_DELAY * 2**message.outbound_status.send_attempts)
        elif response.status_code in [500, 502, 503, 504]:
            attempt_send_message.apply_async(args=[message_id], countdown=SEND_BASE_DELAY * 2**message.outbound_status.send_attempts)
        elif 400 <= response.status_code < 500:
            print(f"Message {message_id} failed with status code {response.status_code}. Giving up.")
            message.outbound_status.send_success = False
            message.outbound_status.error_message = f"Failed with status code {response.status_code}"
            message.save()
        else:
            message.outbound_status.send_success = True
            message.save()
    except RequestException as e: # implies a network error, so retry
        attempt_send_message.apply_async(args=[message_id], countdown=SEND_BASE_DELAY * 2**message.outbound_status.send_attempts)
