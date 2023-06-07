from networks.utils import TreeHoleClient
import time

if __name__ == '__main__':
    client = TreeHoleClient(create_new_file=True)
    if client.login():
        while True:
            client.get_tree_hole_data()
    



