from rauth import OAuth2Service
import json

nation_slug = "fakenation"
access_token_url = "http://" + nation_slug + ".nationbuilder.com/oauth/token"
authorize_url = nation_slug + ".nationbuilder.com/oauth/authorize"
service = OAuth2Service(
    client_id = "c2803fd687f856ce94a55b7f66121c79b75bf7283c467c855e82d53af07074e9",
    client_secret = "0d133e9f2b24ab3b897b4a9a216a1a8391a67b96805eb9a3c9305c0f7ac0e411",
    name = "anyname",
    authorize_url = authorize_url,
    access_token_url = access_token_url,
    base_url = nation_slug + ".nationbuilder.com")

token = "3b25a115de6b9581f567c1eba47148223203a1825c35c03df5c0b7d046e30455"
session = service.get_session(token)

response = session.get("https://" + nation_slug + ".nationbuilder.com/api/v1/people",
    params={'format': 'json'},
    headers ={'content-type':'application/json'})

person = {'first_name'=
response = session.post("https://" + nation_slug + ".nationbuilder.com/api/v1/people",
    params={'format': 'json'}, data=json.dumps({'person': {'first_name':'john', 'last_name':'doe'}}),
    headers={'content-type':'application/json'})
