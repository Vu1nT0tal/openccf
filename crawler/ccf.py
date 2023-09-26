import contextlib
import json
import requests
from bs4 import BeautifulSoup

from utils import *

"""
ARCH_DCP_SS 计算机体系结构/并行与分布计算/存储系统
CN          计算机网络
NIS         网络与信息安全
TCSE_SS_PDL 软件工程/系统软件/程序设计语言
DM_CS       数据库/数据挖掘/内容检索
TCS         计算机科学理论
CGAndMT     计算机图形学与多媒体
AI          人工智能
HCIAndPC    人机交互与普适计算
Cross_Compre_Emerging   交叉/综合/新兴
"""

FIELDS = ['ARCH_DCP_SS', 'CN', 'NIS', 'TCSE_SS_PDL', 'DM_CS', 'TCS', 'CGAndMT', 'AI', 'HCIAndPC', 'Cross_Compre_Emerging']

def get_ccf_data(update: bool=False):
    ccf_fields = FIELDS
    ccf_file = data_path.joinpath('ccf.json')

    if update or not ccf_file.exists():
        ccf_data = get_ccf(ccf_fields)
        with open(ccf_file, 'w') as f:
            json.dump(ccf_data, f, indent=4, ensure_ascii=False)
    else:
        ccf_data = json.loads(ccf_file.read_text())

    num1 = sum(len(j) for i in ccf_data.values() for j in i['journals'].values())
    num2 = sum(len(j) for i in ccf_data.values() for j in i['conf'].values())
    print(f'ccf: {ccf_fields}\njournals: {num1}\tconf: {num2}\n')

    return ccf_data


def get_ccf(fields: list=FIELDS):

    def parse_ul(ul):
        temp = []
        for li in ul.find_all('li')[1:]:
            fields = li.find_all('div')
            index = fields[0].text.strip()
            name = fields[1].text.strip()
            full_name = fields[2].text.strip()
            publisher = fields[3].text.strip()
            address = fields[4].text.strip()

            if address in temp_addr:
                console.print(f'Duplicate address: {full_name}\n{address}\n', style='bold red')

            line = {'name': name, 'full_name': full_name, 'publisher': publisher, 'address': address}
            temp.append(line)
            temp_addr.append(address)
        return temp

    results = {}
    for field in fields:
        temp_addr = []  # 同一个领域去重
        base_url = 'https://www.ccf.org.cn/Academic_Evaluation'
        r = requests.get(f'{base_url}/{field}', timeout=30)
        soup = BeautifulSoup(r.content, 'html.parser')
        ul_tags = soup.select('ul.g-ul.x-list3')

        item = {
            'journals': {
                'A': parse_ul(ul_tags[0]),
                'B': parse_ul(ul_tags[1]),
                'C': parse_ul(ul_tags[2]),
            },
            'conf': {
                'A': parse_ul(ul_tags[3]),
                'B': parse_ul(ul_tags[4]),
                'C': parse_ul(ul_tags[5]),
            }
        }
        results[field] = item

    # 特殊情况处理
    with contextlib.suppress(Exception):
        for a, b in results.items():
            for c, d in b.items():
                for e, f in d.items():
                    for idx, item in enumerate(f):
                        if item['name'] == 'AsiaCCS':
                            # 修改网址
                            item['address'] = 'https://dblp.org/db/conf/asiaccs/'
                            results[a][c][e][idx] = item

                        if item['name'] == 'PETS':
                            # 2015年开始改为PoPETs
                            temp = {
                                'name': 'PoPETs',
                                'full_name': 'Proceedings on Privacy Enhancing Technologies',
                                'publisher': item['publisher'],
                                'address': 'https://dblp.uni-trier.de/db/journals/popets/'
                            }
                            results[a]['journals'][e].append(temp)

                        if item['name'] == 'FSE':
                            # 2017年开始改为ToSC
                            temp = {
                                'name': 'ToSC',
                                'full_name': 'IACR Transactions on Symmetric Cryptology',
                                'publisher': item['publisher'],
                                'address': 'https://dblp.uni-trier.de/db/journals/tosc/'
                            }
                            results[a]['journals'][e].append(temp)

                        if item['name'] == 'CHES':
                            # 2018年开始改为TCHES
                            temp = {
                                'name': 'TCHES',
                                'full_name': 'IACR Transactions on Cryptographic Hardware and Embedded Systems',
                                'publisher': item['publisher'],
                                'address': 'https://dblp.uni-trier.de/db/journals/tches/'
                            }
                            results[a]['journals'][e].append(temp)

                        if item['name'] == 'DFRWS':
                            # 2006年开始改为DI
                            temp = {
                                'name': 'DI',
                                'full_name': 'Forensic Science International: Digital Investigation',
                                'publisher': item['publisher'],
                                'address': 'https://dblp.uni-trier.de/db/journals/di/'
                            }
                            results[a]['journals'][e].append(temp)

    return results
