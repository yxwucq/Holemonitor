from networks.utils import TreeHoleClient
from datetime import datetime

if __name__ == '__main__':
    client = TreeHoleClient(create_new_file=True)
    print(f"TreeHoleClient starting at {str(datetime.now()).split('.')[0]} as {client.mode} mode")
    if client.login():
        client.get_tree_hole_data()
    



