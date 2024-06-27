import os
import random
import re
import time
from datetime import datetime
from collections import OrderedDict

import pandas as pd
import requests

from .config import config
from .const import TreeHoleURLs

class TreeHoleClient(object):
    def __init__(self):
        self._session = requests.Session()
        self._headers = {}
        self._headers['User-Agent'] = random.choice([
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.1.1 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:77.0) Gecko/20100101 Firefox/77.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:77.0) Gecko/20100101 Firefox/77.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36'
        ])

        # read from config file
        self.user_inf = {
            'password' : config['User']['password'],
            'uid' : config['User']['uid']
        }
    
    def login(self):
        login_resp = self._session.post(TreeHoleURLs.Login, headers=self._headers, data=self.user_inf)
        if login_resp.status_code == 200: 
            print("通过密码校验!")
        else:  
            print("用户名或者密码错误！")
            raise RuntimeError 
        self._pku_token = login_resp.json()['data']['jwt']
        xsrf_resp = self._session.get(f"{TreeHoleURLs.XSRF}?t={str(int(time.time()*1000))}", headers=self._headers)
        match = re.search(r"(?P<xsrf>XSRF-TOKEN=.*?);.*?(?P<_session>_session=.*?);.*", xsrf_resp.headers['Set-Cookie'])
        self._xsrf_token = match.group('xsrf')
        self._session_token = match.group('_session')
        
        self._headers['Cookie'] = f"pku_token={self._pku_token}; {self._xsrf_token}; {self._session_token}"
        self._headers['Authorization'] =f"Bearer {self._pku_token}"
        self._headers['Referer'] = TreeHoleURLs.Verification
        
        # accepting the verifying code
        verify_resp = self._session.post(TreeHoleURLs.Query_msg, headers=self._headers)
        if verify_resp.status_code != 200:
            raise RuntimeError
        elif verify_resp.json()['success'] == False:
            print(verify_resp.json()['message'])
        else:
            print(verify_resp.json()['message'])
            
        while True:
            print("请尽快输入验证码：")
            self.verifying_code = input()
            # submitting the code
            _verifying_dat = {'valid_code' : self.verifying_code}
            verify_result_resp = self._session.post(TreeHoleURLs.Verify_msg, headers=self._headers, data=_verifying_dat)
            if verify_result_resp.json()['success']:
                # print("登录成功！")
                print(verify_result_resp.json()['message'])
                return True
            elif verify_resp.status_code != 200:
                print("未知错误！")
                raise RuntimeError
            else:
                print("验证码错误！尝试重新输入")

    def get_tree_hole_data(self, page):
        for attempt in range(4):  # 尝试最多4次
            get_dat = {
                'page': page,
                'limit': 25
            }
            resp_content = self._session.get(TreeHoleURLs.Api_content, params=get_dat, headers=self._headers)
            if resp_content.status_code != 200 or resp_content.json().get('success') == False:
                if attempt < 3:  # 如果不是最后一次尝试，则休息
                    print(f"Attempt {attempt + 1}: Response is empty or unsuccessful, retrying in 30 seconds...")
                    time.sleep(30*attempt)
                    continue
                else:
                    print("================")
                    if resp_content.status_code != 200:
                        print(f"请求失败，状态码：{resp_content.status_code}")
                        print(f"错误信息：{resp_content.text}")
                    else:
                        print(f"请求失败，错误信息：{resp_content.json().get('message')}")
                    print(f"{str(datetime.now()).split('.')[0]}")
                    print("Failed to retrieve data after 4 attempts.")
                    raise RuntimeError("Failed to retrieve data.")
            # 如果成功获取到数据，处理数据
            page_df = pd.json_normalize(resp_content.json()['data']['data'])
            page_df = page_df.set_index('pid')
            page_df['last_retrive'] = str(datetime.now()).split('.')[0]
            page_df.loc[:, 'text'] = page_df.text.astype(str)
            page_df['time'] = page_df.timestamp.apply(datetime.fromtimestamp).astype(str)
            return page_df
        # 如果循环结束还没有成功获取数据，则抛出异常
        raise RuntimeError("Failed to retrieve data after 4 attempts.")

    def get_comments_data(self, pid:str, reply_num:int):
        get_dat = {
            'limit': str(max(10, reply_num))
        }
        time.sleep(0.5)
        resp_content = self._session.get(TreeHoleURLs.Api_comments+"/"+str(pid), params=get_dat, headers=self._headers)
        comments_df = pd.json_normalize(resp_content.json()['data']['data'])
        comments_df = comments_df.set_index('cid')
        comments_df['last_retrive'] = str(datetime.now()).split('.')[0]
        # covert Nonetype to string
        comments_df.text = comments_df.text.astype(str)
        comments_df.comment_id = comments_df.comment_id.astype(str)
        comments_df['time'] = comments_df.timestamp.apply(datetime.fromtimestamp).astype(str)
        return comments_df
   
def print_time(func):
    def inner(*args, **kwargs):
        print("---------------------------")
        print(f"{datetime.fromtimestamp(time.time())}")
        print("---------------------------")
        return func(*args, **kwargs)
    return inner

class HotHoles:
    def __init__(self):
        # 初始化一个空的OrderedDict，用来存储pid和hotness
        # 使用lambda x:x[1]来根据hotness排序
        self.holes = OrderedDict()

    def add_hole(self, pid, hotness):
        # 如果新hole的hotness大于当前最小的hotness，则加入字典
        if len(self.holes) < 5 or hotness > list(self.holes.items())[-1][1]:
            self.holes[pid] = hotness
            # 确保字典按hotness排序
            self.holes = OrderedDict(sorted(self.holes.items(), key=lambda x: x[1], reverse=True))
            # 如果字典长度超过5，移除热度最低的hole
            if len(self.holes) > 5:
                self.holes.popitem(last=True)

    def get_holes(self):
        # 返回当前的holes
        return self.holes