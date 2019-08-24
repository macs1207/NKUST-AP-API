import datetime
import json
import time

import execjs
import requests

from utils import config, error_code

with open('crawler/bus.js', 'r') as bus_read:
    js_function = bus_read.read()

# Bus url setting
BUS_URL = "http://bus.kuas.edu.tw"
BUS_SCRIPT_URL = "http://bus.kuas.edu.tw/API/Scripts/a1"
BUS_API_URL = "http://bus.kuas.edu.tw/API/"
BUS_LOGIN_URL = BUS_API_URL + "Users/login"
BUS_FREQ_URL = BUS_API_URL + "Frequencys/getAll"
BUS_RESERVE_URL = BUS_API_URL + "Reserves/getOwn"
BUS_BOOK_URL = BUS_API_URL + "Reserves/add"
BUS_UNBOOK_URL = BUS_API_URL + "Reserves/remove"
BUS_FINE_URL = BUS_API_URL + "Illegals/getOwn"

# Bus timeout setting
BUS_TIMEOUT = 4.0


def js_init(session):
    session.head(BUS_URL)
    script_content = session.get(BUS_SCRIPT_URL).text

    js = execjs.compile(js_function + script_content)

    return js


def _get_real_time(timestamp):
    return datetime.datetime.fromtimestamp(int(timestamp) / 10000000 - 62135596800).isoformat()


def login(session, username, password):
    """"Login to NKUST bus system. (Only for kuas students.)

    Args:
        session ([request.session]): requests session
        username ([str]): username of NKUST ap system, actually your NKUST student id.
        password ([str]): password of NKUST ap system.

    Returns:
        [dict]: Login success, return user data.
        [int]: BUS_JS_ERROR(601)
               BUS_USER_WRONG_CAMPUS_OR_NOT_FOUND_USER(602)
               BUS_WRONG_PASSWORD(603)
               BUS_TIMEOUT_ERROR(604)
               BUS_ERROR(605)
    """

    data = {'account': username, 'password': password}

    try:
        js = js_init(session)
        data['n'] = js.call('loginEncryption', str(username), str(password))
    except Exception as e:
        print(e)
        return error_code.BUS_JS_ERROR

    try:
        content = session.post(BUS_LOGIN_URL,
                               data=data,
                               timeout=BUS_TIMEOUT
                               )

        if content.status_code == 200:
            content = content.json()
            if content['success']:
                return content
            elif content['code'] == 400:
                return error_code.BUS_USER_WRONG_CAMPUS_OR_NOT_FOUND_USER
            elif content['code'] == 302:
                return error_code.BUS_WRONG_PASSWORD
    except requests.exceptions.Timeout:
        return error_code.BUS_TIMEOUT_ERROR
    except Exception as e:
        return error_code.BUS_ERROR

    return error_code.BUS_ERROR


def query(session, year, month, day):
    """query bus timetable.

    Args:
        session ([request.session]): requests session
        year ([int]): year, common era.
        month ([int]): month.
        day ([int]): day.

    Returns:
        [list]: timetable list.

        [int]: BUS_USER_WRONG_CAMPUS_OR_NOT_FOUND_USER(602)
               BUS_TIMEOUT_ERROR(604)
               BUS_ERROR(605)
    """

    data = {
        'data': '{"y": "%s","m": "%s","d": "%s"}' % (year, month, day),
        'operation': "全部",
        'page': 1,
        'start': 0,
        'limit': 90
    }

    try:
        resp = session.post(BUS_FREQ_URL, data=data, timeout=BUS_TIMEOUT)
        resource = resp.json()
    except requests.exceptions.Timeout:
        return error_code.BUS_TIMEOUT_ERROR
    except Exception as e:
        return error_code.BUS_ERROR

    if resource['code'] == 400:
        return error_code.BUS_USER_WRONG_CAMPUS_OR_NOT_FOUND_USER

    result = []

    if not resource['data']:
        return []
    for i in resource['data']:
        Data = {}
        Data['endEnrollDateTime'] = _get_real_time(i['EndEnrollDateTime'])
        Data['departureTime'] = _get_real_time(i['runDateTime'])
        Data['startStation'] = i['startStation']
        Data['busId'] = i['busId']
        Data['reserveCount'] = int(i['reserveCount'])
        Data['limitCount'] = int(i['limitCount'])
        Data['isReserve'] = bool(int(i['isReserve']) + 1)
        Data['specialTrain'] = i['SpecialTrain']
        Data['discription'] = i['SpecialTrainRemark']
        Data['homeCharteredBus'] = False

        if i['SpecialTrain'] == '1':
            Data['homeCharteredBus'] = True

        result.append(Data)

    return result
