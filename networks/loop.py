import os
import random
import re
import time
from datetime import datetime
from collections import defaultdict

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
        self.search_pages = int(config['Monitor']['search_pages'])
        self.page_interval = int(config['Defaults']['page_interval'])
        self.get_interval = int(config['Monitor']['get_interval'])
        self.morning_sleep = config['Monitor']['morning_sleep'] == 'True'
        self.monitor_key_words = config['Monitor']['monitor_key_words'] == 'True'
        self.monitor_live_key_words = config['Monitor']['monitor_live_key_words'] == 'True'
        self.with_comments = config['Defaults']['comments'] == 'True'
        self.max_hole_actions = int(config['Monitor']['max_hole_actions'])
        self.info_pid_set = set()
        self.monitoring_dict = defaultdict(int) # comments count
        self.monitoring_dict_iter = defaultdict(int) # iteration count
        self.monitoring_df = pd.DataFrame()

        if self.mode == 'monitor' and self.monitor_key_words: 
            self.monitor_key_word_init()
        if self.mode == 'monitor' and self.monitor_live_key_words:
            self.monitor_live_key_word_init()
        
        # initialize database and client
        self.client = TreeHoleClient()
        self.db = SQLDatabase(os.path.join(os.path.dirname(__file__),f"../data/{self.init_date}_holes_{self.mode}.db"))
        self.db.create_holes_table()
        self.db.create_comments_table()
        # self.db.create_comments_table()
        print(f"TreeHoleClient starting at {str(datetime.now()).split('.')[0]} as {self.mode} mode")
    
    def monitor_key_word_init(self):
        self.key_words = config['Key_Words']['key_words']
        if self.key_words.startswith('[') and self.key_words.endswith(']'):
            self.kw_parse = 'list'
            self.key_words = self.key_words[1:-1].split()
        else: self.kw_parse = 'regular'
        self.server_key = config['Key_Words']['server_key']
        self.posted_df_pool = pd.DataFrame()

    def monitor_live_key_word_init(self):
        self.live_key_words = config['Live_Key_Words']['live_key_words']
        self.live_key_words = self.live_key_words[1:-1].split()
        self.negative_live_key_words = config['Live_Key_Words']['negative_live_key_words']
        self.negative_live_key_words = self.negative_live_key_words[1:-1].split()
    
    def check_monitoring_df(self) -> None:
        # for each iteration check the monitoring_df reply count
        # if the reply count is not growing, delete the post from monitoring_df
        for pid, row in self.monitoring_df.iterrows():
            reply_num = int(row['reply'])
            if reply_num <= self.monitoring_dict[pid]: # no growing
                self.monitoring_dict_iter[pid] += 1
                if self.monitoring_dict_iter[pid] == self.max_hole_actions:
                    # delete no growing post
                    self.monitoring_df = self.monitoring_df.drop(pid)
                    del self.monitoring_dict[pid]
                    del self.monitoring_dict_iter[pid]
            else:
                self.monitoring_dict_iter[pid] = 0
                self.monitoring_dict[pid] = reply_num
    
    def print_holes_with_key_words(self) -> None:
        for pid, row in self.monitoring_df.iterrows():
            if self.monitoring_dict_iter[pid] == self.max_hole_actions-1: # to be deleted
                comments_df = self.db.get_comments_data(pid)
                row_text = row.text
                comments_df_text = row_text + comments_df.text.to_string() # combine post and comments
                if any(negative_key_word in comments_df_text for negative_key_word in self.negative_live_key_words):
                    continue
                if any(live_key_word in comments_df_text for live_key_word in self.live_key_words):
                    print("====================================")
                    print(f"{str(datetime.now()).split('.')[0]} {pid} with keyword")
                    print(f"{row.text}")
                    for cid, comment_row in comments_df.iterrows():
                        print(f"{cid}\t{comment_row['name']}\t{comment_row.text}")
    
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
            for page in range(1, self.search_pages+1):
                time.sleep(self.page_interval+random.randint(-1,1))
                page_df = self.client.get_tree_hole_data(page)
                if self.monitoring_df.empty:
                    self.monitoring_df = page_df
                else:
                    self.monitoring_df = self.monitoring_df.combine_first(page_df)
 
            if self.with_comments:
                self.check_monitoring_df() # delete no growing post
                if self.monitor_live_key_words:
                    self.print_holes_with_key_words()
                
                for pid, row in self.monitoring_df.iterrows():
                    reply_num = int(row['reply'])
                    if reply_num > 0:
                        try:
                            working_comments_df = self.client.get_comments_data(pid, reply_num)                            
                            self.db.update_comments_data(working_comments_df)

                        except:
                            print("====================================")
                            print(f"{str(datetime.now()).split('.')[0]} {pid} deleted!")
                            print(f"{row.text}")
                            # read the deleted post from the database
                            deleted_df = self.db.get_comments_data(pid)
                            if not deleted_df.empty:
                                for cid, comment_row in deleted_df.iterrows():
                                    print(f"{cid}\t{comment_row['name']}\t{comment_row.text}")
                                    
            if self.monitor_key_words:
                print(f"监控关键词 {self.key_words}")
                match_df = self.find_key_word_match_in_dataframe(self.monitoring_df)
                if not match_df.empty:
                    print(f"{str(datetime.now()).split('.')[0]} 找到匹配，正在尝试发送")
                    self.send_message_to_wechat(match_df)
                else:
                    print(f"{str(datetime.now()).split('.')[0]} 未找到匹配")
            self.db.update_holes_data(self.monitoring_df)
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

    def find_key_word_match_in_dataframe(self, df:pd.DataFrame):
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
