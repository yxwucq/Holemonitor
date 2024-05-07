import os
import random
import re
import time
from datetime import datetime

import pandas as pd
import requests

from .config import config
from .const import TreeHoleURLs
from .database import SQLDatabase
from .utils import TreeHoleClient, print_time

class Crawler(object):
    def __init__(self):
        self.init_date = str(datetime.now()).split()[0]
        self.init_time = datetime.now()
        self.login_status = False
        self.mode = config['Mode']['mode']
        self.num_days = int(config['Day']['num_days'])
        self.pages = int(config['Monitor']['search_pages'])
        self.page_interval = int(config['Defaults']['page_interval'])
        self.get_interval = int(config['Monitor']['get_interval'])
        self.morning_sleep = config['Monitor']['morning_sleep'] == 'True'
        self.monitor_key_words = config['Monitor']['monitor_key_words'] == 'True'
        self.with_comments = config['Defaults']['comments'] == 'True'

        if self.mode == 'monitor' and self.monitor_key_words: 
            self.monitor_key_word_init()
        
        # initialize database and client
        self.client = TreeHoleClient()
        self.db = SQLDatabase(os.path.join(os.path.dirname(__file__),f"../data/{self.init_date}_holes_{self.mode}.db"))
        self.db.create_holes_table()
        self.db.create_comments_table()
        # self.db.create_comments_table()
        print(f"TreeHoleClient starting at {str(datetime.now()).split('.')[0]} as {self.mode} mode")
    
    @print_time
    def login(self):
        print("开始登录")
        self.login_status = self.client.login()

    @print_time
    def monitor_treehole(self):
        print(f"以监控模式运行")
        while True:
            if self.morning_sleep and datetime.fromtimestamp(time.time()).hour == 3:
                time.sleep(5*60*60) # sleep to 8am 
            working_df = pd.DataFrame()
            for page in range(1, self.pages+1):
                time.sleep(self.page_interval+random.randint(-1,1))
                page_df = self.client.get_tree_hole_data(page)
                working_df = page_df.combine_first(working_df)
            # working_df['time'] = working_df.timestamp.apply(datetime.fromtimestamp).astype(str)
            if self.with_comments:
                comments_df = pd.DataFrame()
                for pid, row in working_df.iterrows():
                    reply_num = int(row['reply'])
                    if reply_num > 0:
                        try:
                            comments_df = self.client.get_comments_data(pid, reply_num).combine_first(comments_df)
                        except:
                            print(f"{pid} deleted!")
                self.db.update_comments_data(comments_df)
            if self.monitor_key_words:
                print(f"监控关键词 {self.key_words}")
                match_df = self.find_match_in_dataframe(working_df)
                if not match_df.empty:
                    print(f"{str(datetime.now()).split('.')[0]} 找到匹配，正在尝试发送")
                    self.send_message_to_wechat(match_df)
                else:
                    print(f"{str(datetime.now()).split('.')[0]} 未找到匹配")
            self.db.update_holes_data(working_df)
            time.sleep(self.get_interval*60)
    
    @print_time
    def craw_treehole(self):
        print(f"爬取过去{str(self.num_days)}天消息")
        page = 1
        working_df = pd.DataFrame()
        while True:
            page_df = self.client.get_tree_hole_data(page)
            working_df = page_df.combine_first(working_df)
            if page % 10 == 0:
                print(f"{str(datetime.now()).split('.')[0]} 爬取至page{page}")
                # working_df['time'] = working_df.timestamp.apply(datetime.fromtimestamp).astype(str)
                if self.with_comments:
                    comments_df = pd.DataFrame()
                    for pid, row in working_df.iterrows():
                        reply_num = int(row['reply'])
                        if reply_num > 0:
                            comments_df = self.client.get_comments_data(pid, reply_num).combine_first(comments_df)
                    self.db.update_comments_data(comments_df)
                self.db.update_holes_data(working_df)
                working_df = pd.DataFrame() 
            if (self.init_time - datetime.fromtimestamp(page_df.sort_values('timestamp').iloc[0]['timestamp'])).days == self.num_days:
                    break
            page += 1
            time.sleep(self.page_interval+random.randint(-1,1))            
        print(f"{str(datetime.now()).split('.')[0]}爬取完成！")
        self.db.get_statistics('holes')
        self.db.get_statistics('comments')

    def monitor_key_word_init(self):
        self.key_words = config['Key_Words']['key_words']
        if self.key_words.startswith('[') and self.key_words.endswith(']'):
            self.kw_parse = 'list'
            self.key_words = self.key_words[1:-1].split()
        else: self.kw_parse = 'regular'
        self.server_key = config['Key_Words']['server_key']
        self.posted_df_pool = pd.DataFrame()

    def send_message_to_wechat(self, df:pd.DataFrame):
        desp = ''
        it = df.iterrows()
        resp = ''
        for index, i in it:
            resp += f"pid: {index}\n"
            resp += f"time: {i.time}\n"
            resp += f"text: {i.text}\n"
            resp += "\n"

        _send_data = {
            "title": f"Holemonitor: 找到匹配，共有{len(df)}条记录",
            "desp": resp
        }
        send_resp = requests.post(f"https://sctapi.ftqq.com/{self.server_key}.send", data=_send_data)
        if send_resp.status_code == 200:
            print("通知发送成功")
        else:
            print("发送失败，检查server Chan接口")

    def find_match_in_dataframe(self, df:pd.DataFrame):
        if self.kw_parse == 'list':
            for string in self.key_words:
                df = df[df.text.apply(lambda x: string in x)]
                if len(df)==0: return df
        elif self.kw_parse == 'regular':
            df = df[df.text.str.match(self.key_words, flags=re.DOTALL)]
        df = df[~df.index.isin(self.posted_df_pool.index)]
        if not df.empty:
            self.posted_df_pool = pd.concat([self.posted_df_pool, df])
        return df
