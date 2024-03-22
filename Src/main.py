import os
import requests




# 信息分发



import requests
def send(message:str):
    url = "机器人webhook地址"
    headers = {
        "Content-Type": "application/json"
    }
    data = {
        "msgtype": "text",
        "text": {
            "content": message,
            "mentioned_list": ["@all"]
        }
    }
    response = requests.post(url, headers=headers, json=data)
    records = response.json()
    return records
def sendAll(message:str):
    url = "机器人webhook地址"
    headers = {
        "Content-Type": "application/json"
    }
    data = {
        "msgtype": "text",
        "text": {
            "content": message,
            "mentioned_list": ["@all"]
        }
    }
    response = requests.post(url, headers=headers, json=data)
    records = response.json()
    return records






print("===================================")