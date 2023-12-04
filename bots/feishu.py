import time
import json
import requests
from pathlib import Path
from Crypto.Cipher import AES
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright

from utils import *


class feishuBot:
    """飞书群机器人
    https://open.feishu.cn/document/ukTMukTMukTM/ucTM5YjL3ETO24yNxkjN
    https://open.feishu.cn/tool/cardbuilder
    """
    URL_API = 'https://open.feishu.cn/open-apis'

    def __init__(self, key) -> None:
        self.key = key

    def make_card(self, paper: dict):
        keywords = ','.join(paper['keywords'])

        if files := paper.get('files'):
            files = "\n".join(f'{name}：{url}' for name, url in files.items() if url)
        if slides := paper.get('slides'):
            slides = "\n".join(f'{name}：{url}' for name, url in slides.items() if url)

        # 优先使用中文
        abstract = paper['abstract_zh'] or paper['abstract']

        card = {
            'header': {
                'template': 'red',
                'title': {
                    'content': paper['title'],
                    'tag': 'plain_text'
                }
            },
            'elements': [
                {
                    'tag': 'div',
                    'fields': [
                        {
                            'is_short': True,
                            'text': {
                                'content': f'**命中依据：**{keywords}',
                                'tag': 'lark_md'
                            }
                        },
                        {
                            'is_short': True,
                            'text': {
                                'content': f'**发表年份：**{paper["year"]}',
                                'tag': 'lark_md'
                            }
                        }
                    ]
                },
                {
                    'tag': 'hr'
                },
                {
                    'tag': 'div',
                    'text': {
                        'content': f'**期刊/会议**\n{paper["conf_title"]}\n{paper["dblp_url"]}\n{paper["conf_url"]}',
                        'tag': 'lark_md'
                    }
                },
                {
                    'tag': 'div',
                    'text': {
                        'content': f'**标题**\n[{paper["title"]}]({paper["url"]})',
                        'tag': 'lark_md'
                    }
                },
                {
                    'tag': 'div',
                    'text': {
                        'content': f'**作者**\n{paper["authors"]}',
                        'tag': 'lark_md'
                    }
                },
                {
                    'tag': 'div',
                    'text': {
                        'content': f'**摘要**\n{abstract}',
                        'tag': 'lark_md'
                    }
                },
                {
                    'tag': 'div',
                    'text': {
                        'content': f'**文件**\n{files or ""}',
                        'tag': 'lark_md'
                    }
                },
                {
                    'tag': 'div',
                    'text': {
                        'content': f'**幻灯片**\n{slides or ""}',
                        'tag': 'lark_md'
                    }
                },
                {
                    'tag': 'div',
                    'text': {
                        'content': f'**视频**\n{paper.get("video") or ""}',
                        'tag': 'lark_md'
                    }
                },
            ]
        }
        bottom = [
            {
                'tag': 'hr'
            },
            {
                'tag': 'action',
                'actions': [
                    {
                        'tag': 'button',
                        'text': {
                            'tag': 'plain_text',
                            'content': '安全学术论文'
                        },
                        'url': '',
                        'type': 'primary'
                    },
                    {
                        'tag': 'button',
                        'text': {
                            'tag': 'plain_text',
                            'content': '安全研究资料'
                        },
                        'url': '',
                        'type': 'primary'
                    },
                    {
                        "tag": "button",
                        "text": {
                            "tag": "plain_text",
                            "content": "关于机器人"
                        },
                        "url": "",
                        "type": "default"
                    }
                ]
            }
        ]
        card['elements'] += bottom
        return card

    def send(self, paper: dict):
        card = self.make_card(paper)

        url = f'{self.URL_API}/bot/v2/hook/{self.key}'
        headers = {'Content-Type': 'application/json; charset=utf-8'}
        data = {'msg_type': 'interactive', 'card': card}

        r = requests.post(url=url, headers=headers, data=json.dumps(data))
        if r.status_code == 200:
            console.print(f'发送成功 {paper}', style='bold green')
            return True
        else:
            console.print(f'发送失败 {paper}', style='bold red')
            print(r.text)
            return False


class feishuOper:
    """服务端程序
    https://open.feishu.cn/document/ukTMukTMukTM/uQjN3QjL0YzN04CN2cDN
    """
    TOKEN_TENANT = 'tenant'
    TOKEN_APP = 'app'
    TOKEN_USER = 'user'
    URL_API = 'https://open.feishu.cn/open-apis'

    def __init__(self, app_id, app_secret, mail=None, pwd=None):
        # 可在飞书开放平台->开发者后台中获取
        self.app_id = app_id
        self.app_secret = app_secret

        # tenant
        self.tenant_access_token = False
        self.tenant_expire = float()

        # app
        self.app_access_token = False
        self.app_expire = float()

        # user
        self.login_mail = mail
        self.login_pwd = pwd

        self.user_access_token = False
        self.user_refresh_token = False
        self.user_expire = float()
        self.user_refresh_expire = float()

        # 缓存文件
        cache_path = Path(__file__).parent.absolute().joinpath('cache')
        cache_path.mkdir(exist_ok=True)
        self.access_cache_file = cache_path.joinpath('feishu_access.bin')
        if self.access_cache_file.exists():
            self.load_access_cache()

    def load_access_cache(self):
        """加载缓存"""
        with open(self.access_cache_file, 'rb') as f:
            nonce, tag, ciphertext = [f.read(x) for x in (16, 16, -1)]
            cipher = AES.new(self.app_secret.encode(), AES.MODE_EAX, nonce)
            plaintext = cipher.decrypt_and_verify(ciphertext, tag)
            access_info = json.loads(plaintext)

        self.tenant_access_token = access_info['tenant_access_token']
        self.tenant_expire = access_info['tenant_expire']
        self.app_access_token = access_info['app_access_token']
        self.app_expire = access_info['app_expire']
        self.user_access_token = access_info['user_access_token']
        self.user_refresh_token = access_info['user_refresh_token']
        self.user_expire = access_info['user_expire']
        self.user_refresh_expire = access_info['user_refresh_expire']

    def update_access_cache(self):
        """更新缓存"""
        access_info = {
            'tenant_access_token': self.tenant_access_token,
            'tenant_expire': self.tenant_expire,
            'app_access_token': self.app_access_token,
            'app_expire': self.app_expire,
            'user_access_token': self.user_access_token,
            'user_refresh_token': self.user_refresh_token,
            'user_expire': self.user_expire,
            'user_refresh_expire': self.user_refresh_expire,
        }
        with open(self.access_cache_file, 'wb') as f:
            plaintext = json.dumps(access_info).encode()
            cipher = AES.new(self.app_secret.encode(), AES.MODE_EAX)
            ciphertext, tag = cipher.encrypt_and_digest(plaintext)
            [f.write(x) for x in (cipher.nonce, tag, ciphertext)]

    def check_access_valid(self, name: str) -> bool:
        """
        检查token是否有效
        name可选值：tenant、app、user
        """
        auth_permission = False

        # 缓存文件存在
        current_time = time.time()
        if name == self.TOKEN_TENANT and current_time < self.tenant_expire:
            auth_permission = True

        elif name == self.TOKEN_APP and current_time < self.app_expire:
            auth_permission = True

        elif name == self.TOKEN_USER and current_time < self.user_expire:
            auth_permission = True

        # 缓存文件不存在，或者缓存无效，则重新获取
        if not auth_permission:
            if name == self.TOKEN_TENANT:
                auth_permission = self.get_tenant_access()

            elif name == self.TOKEN_APP:
                auth_permission = self.get_app_access()

            elif name == self.TOKEN_USER:
                if current_time < self.user_refresh_expire:
                    auth_permission = self.get_user_access(self.user_refresh_token)
                else:
                    auth_permission = self.get_user_access()

        # 更新缓存文件
        if auth_permission:
            self.update_access_cache()
        return auth_permission

    def get_tenant_access(self) -> bool:
        """有效期2小时"""
        console.print('获取tenant_access_token ...', style='bold yellow')

        try:
            url = f'{self.URL_API}/auth/v3/tenant_access_token/internal'
            headers = {'Content-Type': 'application/json; charset=utf-8'}
            data = json.dumps({
                'app_id': self.app_id,
                'app_secret': self.app_secret
            })
            r = requests.post(url, headers=headers, data=data).json()

            self.tenant_access_token = r['tenant_access_token']
            self.tenant_expire = time.time() + r['expire'] - 60
            return True
        except Exception:
            console.print_exception()
            return False

    def get_app_access(self) -> bool:
        """有效期2小时"""
        console.print('获取app_access_token ...', style='bold yellow')

        try:
            url = f'{self.URL_API}/auth/v3/app_access_token/internal'
            headers = {'Content-Type': 'application/json; charset=utf-8'}
            data = json.dumps({
                'app_id': self.app_id,
                'app_secret': self.app_secret
            })
            r = requests.post(url, headers=headers, data=data).json()

            self.app_access_token = r['app_access_token']
            self.app_expire = time.time() + r['expire'] - 60
            return True
        except Exception:
            console.print_exception()
            return False

    def get_user_access(self, token='') -> bool:
        try:
            # 先获取app_access_token
            if self.get_app_access():
                data = self.refresh_user_access_token(token) if token else self.get_user_access_token()

                self.user_access_token = data['access_token']
                self.user_refresh_token = data['refresh_token']
                self.user_expire = time.time() + data['expire_in'] - 60
                self.user_refresh_expire = time.time() + data['refresh_expires_in'] - 60
                return True
            else:
                return False
        except Exception:
            console.print_exception()
            return False

    def get_login_code(self) -> str:
        """有效期5分钟，且只能使用一次
        不支持开启短信验证，需要手动输入验证码
        """
        console.print('获取预授权码 ...', style='bold yellow')

        url = f'{self.URL_API}/authen/v1/index?app_id={self.app_id}&redirect_uri='
        p = sync_playwright().start()
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(locale='zh-CN')
        page.goto(url)

        with page.expect_navigation():
            page.locator('svg').nth(1).click()
            page.get_by_text('邮箱').click()
            page.locator('[data-test="login-mail-input"]').click()
            page.locator('[data-test="login-mail-input"]').fill(self.login_mail)
            page.get_by_label('我已阅读并同意 服务协议 和 隐私政策').check()
            page.locator('[data-test="login-phone-next-btn"]').click()
            page.locator('[data-test="login-pwd-input"]').click()
            page.locator('[data-test="login-pwd-input"]').fill(self.login_pwd)
            page.locator('[data-test="login-pwd-next-btn"]').click()

        code_url = page.url
        browser.close()
        return parse_qs(urlparse(code_url).query)['code'][0]

    def get_user_access_token(self) -> dict:
        """有效期6900秒"""
        console.print('获取user_access_token ...', style='bold yellow')

        url = f'{self.URL_API}/authen/v1/access_token'
        data = json.dumps({
            'code': self.get_login_code(),
            'grant_type': 'authorization_code'
        })
        headers = {
            'Content-Type': 'application/json; charset=utf-8',
            'Authorization': f'Bearer {self.app_access_token}',
        }

        return requests.post(url, headers=headers, data=data).json()['data']

    def refresh_user_access_token(self, token: str) -> dict:
        """有效期30天"""
        console.print('刷新user_access_token ...', style='bold yellow')

        url = f'{self.URL_API}/authen/v1/refresh_access_token'
        data = json.dumps({
            'refresh_token': token,
            'grant_type': 'refresh_token'
        })
        headers = {
            'Content-Type': 'application/json; charset=utf-8',
            'Authorization': f'Bearer {self.app_access_token}',
        }

        return requests.post(url, headers=headers, data=data).json()['data']

    def bitable_batch_create(self, table: str, data: dict) -> bool:
        """tenant_access_token 或 user_access_token"""
        app_token, table_id = table.split(':')
        url = f'{self.URL_API}/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create'
        headers = {
            'Content-Type': 'application/json; charset=utf-8',
            'Authorization': f'Bearer {self.tenant_access_token}',
        }
        try:
            result = requests.post(url, headers=headers, data=json.dumps(data)).json()
            if result['msg'] == 'success':
                console.print('写入表格成功', style='bold green')
                return True
            else:
                console.print(f'写入表格失败:\n{data}\n{result}', style='bold red')
        except Exception:
            console.print('无法访问表格', style='bold red')
            console.print_exception()

        return False
