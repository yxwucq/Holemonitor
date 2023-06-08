from .const import TreeHoleURLs
from .config import config
import requests
import time
import re
import pandas as pd
import os
import random
from datetime import datetime

class TreeHoleClient(object):
    def __init__(self, create_new_file=True):
        self._session = requests.Session()
        self._headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36'
        }

        # read from config file
        self.user_inf = {
            'password' : config['User']['password'],
            'uid' : config['User']['uid']
        }
        self.morning_sleep = int(config['Defaults']['morning_sleep'])
        # self.auto_depth = int(config['Defaults']['auto_depth'])
        self.get_interval = int(config['Defaults']['get_interval'])
        self.pages = int(config['Defaults']['search_pages'])
        self.mode = config['Mode']['mode']
        self.init_date = str(datetime.now()).split()[0]
        self.init_time = datetime.now()

        self.user_agent_list = [
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.1.1 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:77.0) Gecko/20100101 Firefox/77.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:77.0) Gecko/20100101 Firefox/77.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36'
        ]

        # io process
        if create_new_file:
            pd.DataFrame().to_csv(os.path.join(os.path.dirname(__file__),f"../data/{self.init_date}_holes_{self.mode}.csv"))
    
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

    def get_tree_hole_data(self):
        print("---------------------------")
        print(f"{datetime.fromtimestamp(time.time())}，爬取树洞信息")
        print("---------------------------")

        # monitor mode
        if self.mode == 'monitor':
            print("监控模式运行")
            while True:
                if self.morning_sleep and datetime.fromtimestamp(time.time()).hour == 3:
                    time.sleep(5*60*60) # sleep to 8am 
                working_df = pd.DataFrame()
                for page in range(1, self.pages+1):
                    time.sleep(10+random.randint(-5,5))
                    page_df = self._get_hole_data_page(page)
                    page_df['last_retrive'] = str(datetime.now()).split('.')[0]
                    working_df = page_df.combine_first(working_df)
                self._update_csv_from_data(working_df, os.path.join(os.path.dirname(__file__),f"../data/{self.init_date}_holes_{self.mode}.csv"))
                print(f"{str(datetime.now()).split('.')[0]}爬取完成！")

                time.sleep(self.get_interval*60)

        # day mode
        elif self.mode == 'day':
            print("爬取过去24小时消息")
            page = 1
            working_df = pd.DataFrame()
            while True:                
                page_df = self._get_hole_data_page(page)
                page_df['last_retrive'] = str(datetime.now()).split('.')[0]
                working_df = page_df.combine_first(working_df)
                if page % 10 == 0:
                    print(f"{str(datetime.now()).split('.')[0]} 爬取至page{page}")
                    self._update_csv_from_data(working_df, os.path.join(os.path.dirname(__file__),f"../data/{self.init_date}_holes_{self.mode}.csv"))
                    working_df = pd.DataFrame() 
                if (self.init_time - datetime.fromtimestamp(page_df.sort_values('timestamp').iloc[0]['timestamp'])).days == 1:
                    break
                page += 1
                time.sleep(10+random.randint(-5,5))

            print(f"{str(datetime.now()).split('.')[0]}爬取完成！")

    def _get_hole_data_page(self, page):
        # print(f"reaching page {page}")
        get_dat = {
            'page': page,
            'limit': 25
        }
        # self._update_user_agent()
        resp_content = self._session.get(TreeHoleURLs.Api_content, params=get_dat, headers=self._headers)
        if resp_content.json()['success'] == False:
            print("================")
            print(f"爬取出现错误！{resp_content.json()['message']}")
            raise RuntimeError
        return pd.json_normalize(resp_content.json()['data']['data']).set_index('pid')

    def _update_csv_from_data(self, working_df, csv_path):
        # working_df.set_index('pid', inplace=True)
        working_df['time'] = working_df.timestamp.apply(datetime.fromtimestamp) 
        working_df = working_df[['text', 'type', 'time', 'reply', 'likenum', 'last_retrive']].drop_duplicates()
        holes = pd.read_csv(csv_path, index_col=0)
        working_df.combine_first(holes).to_csv(csv_path)

    def _update_user_agent(self):
        _user_agent = random.choice(self.user_agent_list)
        self._headers['User-Agent'] = _user_agent
    
