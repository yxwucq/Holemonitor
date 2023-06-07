import configparser
import os

config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(__file__),"../config.ini"),encoding="UTF-8")