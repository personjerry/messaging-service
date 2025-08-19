from django.http import HttpResponse
def send_sms(message):
    print(f"Sending SMS (pretend integrations would be implemented here). Data dump:")
    print("Message:")
    print(message)
    print("Attachments:")
    print("\n".join([attachment.url for attachment in message.attachments.all()]))
    print()
    return HttpResponse(status=200)

def send_email(message):
    print(f"Sending Email (pretend integrations would be implemented here). Data dump:")
    print("Message:")
    print(message)
    print("Attachments:")
    print("\n".join([attachment.url for attachment in message.attachments.all()]))
    print()
    return HttpResponse(status=200)