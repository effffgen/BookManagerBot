from cloudant import Cloudant
import os
import json

user_state_db_name = 'users'
book_db_name = 'books'
client = None
user_state_db = None
book_db = None
# Initialization for usage on IBM servers
# Cloudant DB connects automatically, Telegram bot token must be added on the management panel manually
if 'VCAP_SERVICES' in os.environ:
    vcap = json.loads(os.getenv('VCAP_SERVICES'))
    print('Found VCAP_SERVICES')
    if 'cloudantNoSQLDB' in vcap:
        creds = vcap['cloudantNoSQLDB'][0]['credentials']
        user = creds['username']
        password = creds['password']
        url = 'https://' + creds['host']
        client = Cloudant(user, password, url=url, connect=True)
        book_db = client.get(book_db_name, remote=True)
        user_state_db = client.get(user_state_db_name, remote=True)
# Initialization for the local usage
# Cloudant credentials are stored in the file 'vcap-local.json', token - in the 'token.json' file
elif os.path.isfile('vcap-local.json'):
    with open('vcap-local.json') as f:
        vcap = json.load(f)
        print('Found local VCAP_SERVICES')
        creds = vcap['cloudantNoSQLDB'][0]['credentials']
        user = creds['username']
        password = creds['password']
        url = 'https://' + creds['host']
        client = Cloudant(user, password, url=url, connect=True)
        book_db = client.get(book_db_name, remote=True)
        user_state_db = client.get(user_state_db_name, remote=True)
if 'token' in os.environ:
    token = os.getenv('token')
elif os.path.isfile('config.json'):
    with open('config.json') as f:
        token = json.load(f)['token']
        print('Found local token')
        print(token)

# Perform primary initialization (synchronize local version of db with remote one)
# TODO:Fix this shit later
for user in user_state_db:
    pass
for book in book_db:
    pass
