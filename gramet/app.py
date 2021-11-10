# this file is deployed from github on push

from urllib.parse import urlsplit
from hashlib import sha1
import base64
import json
import re
import requests
import time

def aws_error(status=400, body='invalid request'):
    return {
        'statusCode': status,
        'body': json.dumps(body)
    }

def fetch_image(url, etag):
    url_object = urlsplit(url)
    try:
        r = requests.get(url, timeout=30)
    except requests.exceptions.Timeout:
        return aws_error(body="ogimet gramet TimeOut", status="408 ogimet gramet TimeOut")
    data = r.text
    if not data:
        return aws_error(body="gramet not found", status="404 gramet not found")
    if data.find('No grib data available') >=0 :
        return aws_error(body='no grib data', status="503 no grib data")
    if data.find('Sorry, OGIMET is overloaded. Try again in few minutes')>=0 :
        return aws_error(body='OGIMET is overloaded', status="404 OGIMET is overloaded")
    m = re.search(r'gramet_lee_rutind: Error, no se han encontrado datos de (.+)', data)
    if m:
        return aws_error(body=m.group(1), status="409 " + m.group(1) + " unknown wmo") # wmo non reconnu
    m = re.search(r'<img src="([^"]+/gramet_[^"]+)"', data)
    if not m:
        return aws_error(body="gramet image not found", status="404 gramet image not found")
    img_src = "{url.scheme}://{url.netloc}{path}".format(
        url=url_object, path=m.group(1))
    ogimet_serverid = r.cookies.get('ogimet_serverid', None)
    try:
        if ogimet_serverid:
            response = requests.get(img_src, cookies=dict(ogimet_serverid=ogimet_serverid), timeout=25)
        else:
            response = requests.get(img_src, timeout=25)
    except requests.exceptions.Timeout:
        return aws_error(body="ogimet fetch image TimeOut", status="504 ogimet fetch image TimeOut")
    except KeyError:
        return aws_error(body="no ogimet_serverid cookie", status="404 OGIMET not responding")
    content_type=response.headers.get('content-type')
    mimetype, _, _ = content_type.partition(';')
    if response.status_code != 200:
        return aws_error(body='ogimet returns with status %s' % response.status_code, status=response.status_code)
    if not mimetype.startswith("image/"):
        return aws_error(body='gramet is not an image', status="406 gramet is not an image")

    return {
        'headers': {
            "Content-Type": content_type,
            "ETag": 'W/"{etag}"'.format(etag=etag),
            "X-ETag": etag,
        },
        'statusCode': response.status_code,
        'body': base64.b64encode(response.content).decode('utf-8'),
        'isBase64Encoded': True
    }

def lambda_handler(event, context):
    path_parameters = event.get('pathParameters', {})
    conditional_etag = event.get('headers', {}).get('if-none-match', None)
    match = re.search(r'^(?P<hini>[^-]+)-(?P<tref>[^-]+)-(?P<hfin>[^-]+)-(?P<fl>[^-]+)-(?P<wmo>[^-]+)__(?P<name>.+)$', path_parameters.get('data', ''))
    if not match:
        return aws_error()

    hini = int(match.group('hini'))
    tref = int(match.group('tref'))
    hfin = int(match.group('hfin'))
    fl = int(match.group('fl'))
    wmo = match.group('wmo')
    name = match.group('name')

    now_ts = int(time.time())
    max_age = min(3600, tref - now_ts)
    ogimet_tref = tref // 3600
    seconds = tref % 3600
    if now_ts > tref:
        ogimet_tref = now_ts // 3600
        seconds = now_ts % 3600
        if (seconds) > 1800:
            max_age = 3600 - seconds
        else:
            max_age = 1800 - seconds
    if (seconds) > 1800:
        ogimet_tref += 1
    OGIMET_URL = "http://www.ogimet.com/display_gramet.php?" \
                 "lang=en&hini={hini}&tref={tref}&hfin={hfin}&fl={fl}" \
                 "&hl=3000&aero=yes&wmo={wmo}&submit=submit"
    url = OGIMET_URL.format(hini=hini, tref=ogimet_tref*3600, hfin=hfin, fl=fl, wmo=wmo)
    etag_src = "{hini}&tref={tref}&hfin={hfin}&fl={fl}&wmo={wmo}".format(hini=hini, tref=ogimet_tref, hfin=hfin, fl=fl, wmo=wmo)
    etag = sha1(etag_src.encode('utf-8')).hexdigest()
    response_dict = {}
    if ('W/"{etag}"'.format(etag=etag) == conditional_etag):
        response_dict = {
            'headers': {
                "ETag": 'W/"{etag}"'.format(etag=etag),
                "X-ETag": etag,
            },
            'statusCode': 304,
        }
        print("304 Not modified")
    else:
        response_dict = fetch_image(url, etag)

    # add CORS headers (on amazon lambda this is already set in the API Gateway/CORS)
    headers = response_dict.get('headers', {})
    headers['Access-Control-Allow-Origin'] = '*'
    headers["Access-Control-Allow-Headers"] = "X-Requested-With"
    headers["Access-Control-Expose-Headers"] = "ETag, X-ETag, X-ofp2map-status"
    if (response_dict['statusCode'] == 200 or response_dict['statusCode'] == 304):
         headers['Cache-Control'] = "max-age={}".format(max_age)
         if (response_dict['statusCode'] == 304):
             print(name.replace('Route_', 'Cache_'))
         else:
             print(name)
         print(response_dict['statusCode'])
    else:
        headers['Cache-Control'] = "max-age=0"
        headers['X-ofp2map-status'] = response_dict['statusCode']
        print(name)
        print(response_dict['statusCode'])
    if not isinstance(response_dict['statusCode'], int):
        try:
            response_dict['statusCode'] = int(response_dict['statusCode'].split()[0])
        except ValueError:
            response_dict['statusCode'] = 500
    response_dict['headers'] = headers
    return response_dict