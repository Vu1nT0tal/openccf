import requests

from utils import *


class wolaiOper:
    """我来应用
    https://www.wolai.com/wolai/7FB9PLeqZ1ni9FfD11WuUi
    """
    URL_API = 'https://openapi.wolai.com/v1'

    def __init__(self, app_id, app_secret) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.token = self.get_token()

    def get_token(self) -> bool:
        """创建或重置token"""
        console.print('获取token ...', style='bold yellow')

        url = f'{self.URL_API}/token'
        data = {
            'appId': self.app_id,
            'appSecret': self.app_secret
        }
        try:
            return requests.post(url, json=data).json()['data']['app_token']
        except Exception:
            console.print_exception()
            return False

    def database_get(self, id: str) -> bool:
        """获取数据表格数据"""
        url = f'{self.URL_API}/databases/{id}'
        headers = {'Authorization': self.token}
        try:
            return requests.get(url, headers=headers).json()['data']
        except Exception:
            console.print_exception()
            return False

    def database_post(self, id: str, data: dict) -> bool:
        """创建数据表格数据"""
        url = f'{self.URL_API}/databases/{id}/rows'
        headers = {'Authorization': self.token}
        try:
            r = requests.post(url, headers=headers, json=data)
            if r.status_code == 200:
                console.print('写入表格成功', style='bold green')
                return True
            else:
                console.print(f'写入表格失败:\n{data}\n{r.json()}', style='bold red')
        except Exception:
            console.print('无法访问表格', style='bold red')
            console.print_exception()

        return False
