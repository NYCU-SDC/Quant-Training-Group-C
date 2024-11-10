import datetime
import hmac, hashlib, base64
import requests
import json


staging_api_secret_key = "FWQGXZCW4P3V4D4EN4EIBL6KLTDA"
staging_api_key = 'sdFgbf5mnyDD/wahfC58Kw=='

def _generate_signature(data):
  key = staging_api_secret_key
  key_bytes= bytes(key, 'utf-8')
  data_bytes = bytes(data, 'utf-8')
  return hmac.new(key_bytes, data_bytes, hashlib.sha256).hexdigest()


milliseconds_since_epoch = round(datetime.datetime.now().timestamp() * 1000)
print("\n", "client_order_id=123456&order_price=0.21&order_quantity=10&order_type=LIMIT&side=BUY&symbol=SPOT_BTC_USDT|"+str(milliseconds_since_epoch), "\n")
headers = {
    'x-api-timestamp': str(milliseconds_since_epoch),
    'x-api-key': staging_api_key,
    'x-api-signature': _generate_signature("client_order_id=123456&order_price=0.21&order_quantity=10&order_type=LIMIT&side=BUY&symbol=SPOT_BTC_USDT|"+str(milliseconds_since_epoch)),
    'Content-Type': 'application/x-www-form-urlencoded',
    'Cache-Control':'no-cache'
}
data = {
  'order_price' : 0.21,
  'order_quantity': 10,
  'order_type': 'LIMIT',
  'side':'BUY',
  'symbol': 'SPOT_BTC_USDT'
}


response = requests.post('https://api.staging.woo.org/v1/order', headers=headers, data=data )
print(response.json())