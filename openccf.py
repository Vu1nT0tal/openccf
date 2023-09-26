#!/usr/bin/python3

import os
import json
import argparse
import pyfiglet
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor

from utils import *
from feishu import *
from crawler import *
from crawler.libpaper import *


def make_bitable_records(data) -> dict:
    """将数据转换为多维表格格式"""
    def format_fields(data):
        if title_zh := data['title_zh']:
            title = f'{data["title"]}\n\n{title_zh}'
        else:
            title = data['title']

        fields = {
            '标题': title,
            '年份': data['year'],
            '刊物': data['dblp_url'].split('/')[-2],
            '标签': data['keywords'],
            '摘要': data['abstract_zh'] or data['abstract'],
            '网址': {'text': data['url'], 'link': data['url']},
        }
        if pdf_url := data['files']['openAccessPdf']:
            fields['文件'] = {'text': pdf_url, 'link': pdf_url}

        return fields

    records = {'records': []}
    for item in data:
        records['records'].append({
            'fields': format_fields(item)
        })

    return records


def translate_all_empty():
    """将空的中文摘要和标题全部翻译"""
    console.print('Translating...', style='bold yellow')

    for file in dblp_path.glob('*.json'):
        empty_num = 0
        data = json.loads(file.read_text())
        for year, year_data in data.items():
            for i, item in enumerate(year_data):
                for j, paper in enumerate(item['papers']):
                    if paper['title'] and paper['title_zh'].isascii():
                        data[year][i]['papers'][j]['title_zh'] = get_translate(paper['title'])
                        empty_num += 1
                    if paper['abstract'] and paper['abstract_zh'].isascii():
                        data[year][i]['papers'][j]['abstract_zh'] = get_translate(paper['abstract'])
                        empty_num += 1

        if empty_num:
            print(file.name, empty_num)

            with open(file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)


def func_broker(url: str):
    """选择解析函数"""
    dblp_key = '/'.join(url.split('/')[-3:-1])
    func_map = {
        'conf/sp': get_sp_data,
        'conf/ccs': get_ccs_data,
        'conf/ndss': get_ndss_data,
        'conf/uss': get_usenix_data,
    }
    return func_map.get(dblp_key)


def parse_rule(ccf_data: dict, rule: str='all:all:all:all'):
    """规则解析"""
    try:
        ccf_field, ccf_type, ccf_rank, ccf_name = rule.split(':')

        ccf_field = FIELDS if ccf_field == 'all' else ccf_field.split(',')
        ccf_type = ['journals', 'conf'] if ccf_type == 'all' else ccf_type.split(',')
        ccf_rank = ['A', 'B', 'C'] if ccf_rank == 'all' else ccf_rank.split(',')
        ccf_name = ['all'] if ccf_name == 'all' else ccf_name.split(',')

        ccf_url = []
        for a in ccf_field:
            for b in ccf_type:
                for c in ccf_rank:
                    if ccf_name[0] == 'all':
                        ccf_url.extend(e['address'] for e in ccf_data[a][b][c])
                    else:
                        for d in ccf_name:
                            ccf_url.extend(e['address'] for e in ccf_data[a][b][c] if d == e['name'])
        print(f'dblp url: {len(ccf_url)}\n{ccf_url}\n')
    except Exception:
        console.print(f'wrong rule: {rule}', style='bold red')
        exit(1)

    return ccf_url


def parse_year(year: str):
    """解析年份"""
    parts = year.split(':')
    return parts[0], parts[1]


def parse_args():
    """参数解析"""
    start_year = datetime.now().year
    end_year = start_year - 5
    parser = argparse.ArgumentParser()
    parser.add_argument('--year', type=str, metavar='start:end', default=f'{start_year}:{end_year}', help='e.g. 2020:2015')
    parser.add_argument('--rule', type=str, metavar='field:type:rank:name', default='all:all:all:all', help='e.g. NIS:conf:A,B:all')
    parser.add_argument('--keywords', type=str, metavar='keywords', default='', help='e.g. keyword1,keyword2')
    return parser.parse_args()


if __name__ == '__main__':
    print(pyfiglet.figlet_format('OpenCCF'))
    args = parse_args()
    conf = json.loads(Path('config.json').read_text())
    proxy_url = conf['proxy']

    # 设置API Key
    secrets = conf['openai']['secrets']
    openai_key = os.getenv(secrets) or conf['openai']['key']
    os.environ[secrets] = openai_key

    secrets = conf['s2api']['secrets']
    s2api_key = os.getenv(secrets) or conf['s2api']['key']
    os.environ[secrets] = s2api_key

    # 飞书机器人
    feishu_conf = conf['keywords']
    feishu_bot_key = os.getenv(feishu_conf['secrets']) or feishu_conf['key']
    feishu_bot = feishuBot(feishu_bot_key)

    if args.keywords:
        keywords = args.keywords.split(',')
    else:
        keywords = [j for i in feishu_conf['keywords'].values() for j in i if j.isascii()]

    year = args.year or conf['year']
    rule = args.rule or conf['rule']
    start_year, end_year = parse_year(year)

    # 获取CCF数据
    console.print('Getting ccf...', style='bold yellow')
    ccf_data = get_ccf_data(update=True)
    urls = parse_rule(ccf_data, rule)

    # 获取全量论文
    total_num = 0
    total_new_num = 0
    total_update_num = 0
    total_data = []
    total_new_data = []
    total_update_data = []

    # 获取基础数据及网址
    console.print('Getting papers...', style='bold yellow')
    executor = ProcessPoolExecutor(os.cpu_count()-1)
    tasks = [executor.submit(get_dblp_data, url, start_year, end_year) for url in urls]
    executor.shutdown(wait=True)

    for task in tasks:
        url, all_data, new_data, update_data = task.result()

        all_num = sum(len(j['papers']) for i in all_data.values() for j in i)
        new_num = sum(len(j['papers']) for i in new_data.values() for j in i)
        update_num = sum(len(j['papers']) for i in update_data.values() for j in i)
        console.print(f'{url}\nAll Papers: {all_num}\tNew Papers: {new_num}\tUpdate Papers: {update_num}\n', style='bold green')

        total_num += all_num
        total_new_num += new_num
        total_update_num += update_num
        # total_data.append(all_data)
        # total_new_data.append(new_data)
        # total_update_data.append(update_data)

        # 从论文网址获取补充数据
        # if get_paper_data := func_broker(url):
        #     paper_data = get_paper_data(all_data)

    console.print(f'All Papers: {total_num}\tNew Papers: {total_new_num}\tUpdate Papers: {total_update_num}', style='bold yellow')

    # 翻译摘要和标题
    translate_all_empty()

    # 过滤论文
    console.print('Filtering papers...', style='bold yellow')
    total_vehicle_data = []
    vehicle_file = data_path.joinpath('vehicle.json')
    for file in dblp_path.glob('*.json'):
        data = json.loads(file.read_text())
        vehicle_data = filter_vehicle(data, keywords)
        total_vehicle_data += vehicle_data

    with open(vehicle_file, 'w') as f:
        json.dump(total_vehicle_data, f, indent=4, ensure_ascii=False)

    # 发送新论文
    bot_data = []
    bitable_data = []
    bitable_data_temp = []

    bitable_history_file = data_path.joinpath('bitable_history.txt')
    bitable_history_data = bitable_history_file.read_text().splitlines() if bitable_history_file.exists() else []
    bot_history_file = data_path.joinpath('bot_history.txt')
    bot_history_data = bot_history_file.read_text().splitlines() if bot_history_file.exists() else []

    console.print('Sending bot...', style='bold yellow')
    for data in total_vehicle_data:
        title = data['title']

        # 发送飞书消息
        if title not in bot_history_data and feishu_bot.send(data):
            bot_data.append(title)

        # 多维表格临时数据
        if title not in bitable_history_data:
            bitable_data_temp.append(data)

    # 更新多维表格
    console.print('Updating bitable...', style='bold yellow')
    # 飞书开放平台->开发者后台
    app_id = 'cli_a42a42b995f9d00e'
    app_secret = os.getenv('APP_SECRET') or ''
    # 多维表格应用
    app_token, table_id = (os.getenv('BITABLE_TOKEN') or '').split(':')

    feishu_oper = feishuOper(app_id, app_secret)
    if feishu_oper.check_access_valid(feishuOper.TOKEN_TENANT):
        split_list = [bitable_data_temp[i:i+100] for i in range(0, len(bitable_data_temp), 100)]
        for split_data in split_list:
            # 每组100条数据
            data = make_bitable_records(split_data)
            if feishu_oper.bitable_batch_create(app_token, table_id, data):
                bitable_data += [i['title'] for i in split_data]
    else:
        console.print('权限验证失败', style='bold red')

    with open(bot_history_file, 'w') as f:
        f.write('\n'.join(bot_history_data + bot_data))

    with open(bitable_history_file, 'w') as f:
        f.write('\n'.join(bitable_history_data + bitable_data))

    console.print(f'Vehicle Papers: {len(total_vehicle_data)}\tSend Papers: {len(bot_data)}\tUpdate Papers: {len(bitable_data)}', style='bold yellow')
