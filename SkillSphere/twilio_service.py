# Download the helper library from https://www.twilio.com/docs/python/install

import os

from twilio.rest import Client

from SkillSphere.settings import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN

# Find your Account SID and Auth Token at twilio.com/console

# and set the environment variables. See http://twil.io/secure

account_sid = os.environ[TWILIO_ACCOUNT_SID]

auth_token = os.environ[TWILIO_AUTH_TOKEN]

client = Client(account_sid, auth_token)

service = client.messaging.v1.services.create(friendly_name="FriendlyName")

print(service.sid)
