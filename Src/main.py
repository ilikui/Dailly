import os
import requests




def WeChatRobot(message:str):
    apiurl ='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key='
    key = os.environ["WEBHOOK_KEY"]
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


    url = apiurl + key
    
    response = requests.post(url, headers=headers, json=data)
    records = response.json()
    return records




if __name__ == '__main__':
    
    WeChatRobot('大家好，我是mimi')


    








print("===================================")