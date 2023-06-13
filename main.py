from datetime import datetime
from networks.loop import Crawler

if __name__ == '__main__':
    crawler = Crawler()
    crawler.login()
    if crawler.login_status == True:
        if crawler.mode == 'monitor':
            crawler.monitor_treehole()
        elif crawler.mode == 'day':
            crawler.craw_treehole()
    



