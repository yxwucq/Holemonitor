from .const import TreeHoleURLs
from .config import config
import requests
import time
import re
import pandas as pd
import os
from datetime import datetime

class TreeHoleClient(object):
    def __init__(self, create_new_file=True):
        self._session = requests.Session()
        self._headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36'
        }
        self.user_inf = {
            'password' : config['User']['password'],
            'uid' : config['User']['uid']
        }
        self.get_interval = int(config['Defaults']['get_interval'])
        self.pages = int(config['Defaults']['search_pages'])
        self.init_date = str(datetime.now()).split()[0]
        if create_new_file:
            pd.DataFrame().to_csv(os.path.join(os.path.dirname(__file__),f"../data/{self.init_date}_holes.csv"))
    
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
                    print("登录成功！")
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
        
        working_df = pd.DataFrame()
        for page in range(self.pages):
            time.sleep(10)
            get_dat = {
                'page': page,
                'limit': 25
            }
            resp_content = self._session.get(TreeHoleURLs.Api_content, params=get_dat, headers=self._headers)
            working_df = pd.concat([working_df, pd.json_normalize(resp_content.json()['data']['data'])])
        working_df.set_index('pid', inplace=True)
        working_df['time'] = working_df.timestamp.apply(datetime.fromtimestamp) 
        working_df = working_df[['text', 'type', 'time', 'reply', 'likenum']]
        holes = pd.read_csv(os.path.join(os.path.dirname(__file__),f"../data/{self.init_date}_holes.csv"), index_col=0)
        working_df.combine_first(holes).to_csv(os.path.join(os.path.dirname(__file__),f"../data/{self.init_date}_holes.csv"))
        print("爬取完成！")
        
        time.sleep(self.get_interval*60)
