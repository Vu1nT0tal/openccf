#!/usr/bin/python3

import os
import json
import json5
import argparse
import pyfiglet
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor
from pyrate_limiter import Duration, Rate, InMemoryBucket, Limiter

from utils import *
from bots import *
from crawler import *
from crawler.libpaper import *


def make_bitable(data) -> dict:
    """将数据转换为多维表格格式"""
    def format_fields(data):
        """构建一条数据"""
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
            '总结': data['tldr_zh'] or data['tldr'],
            '网址': {'text': data['url'], 'link': data['url']},
        }
        if pdf_url := data['files']['openAccessPdf']:
            fields['文件'] = {'text': pdf_url, 'link': pdf_url}

        return fields

    result = {'records': []}
    for item in data:
        result['records'].append({
            'fields': format_fields(item)
        })
    return result


def make_database(data) -> dict:
    """将数据转换为数据表格格式"""
    def format_fields(data):
        """构建一条数据"""
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
            '总结': data['tldr_zh'] or data['tldr'],
            '网址': data['url'],
        }
        if pdf_url := data['files']['openAccessPdf']:
            fields['文件'] = pdf_url

        return fields

    result = {'rows': []}
    for item in data:
        result['rows'].append(format_fields(item))
    return result


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
                    if paper['tldr'] and paper['tldr_zh'].isascii():
                        data[year][i]['papers'][j]['tldr_zh'] = get_translate(paper['tldr'])
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
        console.print(f'Wrong rule: {rule}', style='bold red')
        exit(1)

    return ccf_url


def parse_year(year: str):
    """解析年份"""
    parts = year.split(':')
    return parts[0], parts[1]


def init_bot(bot_name: str, conf: dict):
    """初始化机器人"""
    bot = None
    oper = None
    table = {}

    if bot_name == 'feishu':
        bot_conf = conf['feishu']

        # 群机器人
        if bot_key := os.getenv(bot_conf['bot']['name']) or bot_conf['bot']['key']:
            bot = feishuBot(bot_key)

        # 飞书开放平台->开发者后台
        app_id = os.getenv(bot_conf['app_id']['name']) or bot_conf['app_id']['key']
        app_secret = os.getenv(bot_conf['app_secret']['name']) or bot_conf['app_secret']['key']
        # 多维表格
        for key, value in bot_conf['bitable'].items():
            table[key] = os.getenv(value['name']) or value['key']

        if app_id and app_secret and table:
            oper = feishuOper(app_id, app_secret)

    elif bot_name == 'wolai':
        bot_conf = conf['wolai']

        # 应用设置
        app_id = os.getenv(bot_conf['app_id']['name']) or bot_conf['app_id']['key']
        app_secret = os.getenv(bot_conf['app_secret']['name']) or bot_conf['app_secret']['key']
        # 数据表格
        for key, value in bot_conf['database'].items():
            table[key] = os.getenv(value['name']) or value['key']

        if app_id and app_secret:
            oper = wolaiOper(app_id, app_secret)

    else:
        console.print('Wrong bot', style='bold red')
        exit(1)

    return bot, oper, table


def crawl_papers():
    """爬取论文"""
    # 获取CCF数据
    console.print('Getting ccf...', style='bold yellow')
    ccf_data = get_ccf_data(update=False)
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


def filter_papers(category: str, keywords: list):
    """过滤论文"""
    console.print(f'\[{category}] Filtering papers...', style='bold yellow')

    total_data = []
    category_file = data_path.joinpath(f'{category}.json')
    for file in dblp_path.glob('*.json'):
        data = json.loads(file.read_text())
        filter_data = filter_keywords(data, keywords)
        total_data += filter_data

    # 按url排序
    sorted_data = sorted(total_data, key=lambda x: x['url'])

    with open(category_file, 'w') as f:
        json.dump(sorted_data, f, indent=4, ensure_ascii=False)

    console.print(f'\[{category}] Papers: {len(sorted_data)}', style='bold yellow')
    return sorted_data


def send_papers(category: str, total_data: list):
    """发送论文"""
    bot_data = []
    table_data = []
    table_data_temp = []

    if args.bot == 'feishu':
        bitable_history_file = history_path.joinpath(f'feishu_bitable_{category}.txt')
        bitable_history_data = bitable_history_file.read_text().splitlines() if bitable_history_file.exists() else []
        bot_history_file = history_path.joinpath(f'feishu_bot_{category}.txt')
        bot_history_data = bot_history_file.read_text().splitlines() if bot_history_file.exists() else []

        console.print(f'\[{category}] Sending bot...', style='bold yellow')
        rates = [Rate(100, Duration.MINUTE)] # 频率限制，100条/分钟
        bucket = InMemoryBucket(rates)
        limiter = Limiter(bucket, max_delay=Duration.MINUTE.value)
        for data in total_data:
            limiter.try_acquire('identity')
            title = data['title']

            # 发送机器人消息
            if title not in bot_history_data and bot.send(data):
                bot_data.append(title)

            # 多维表格临时数据
            if title not in bitable_history_data:
                table_data_temp.append(data)

        # 更新多维表格
        console.print(f'\[{category}] Updating bitable...', style='bold yellow')
        if oper.check_access_valid(feishuOper.TOKEN_TENANT):
            # 每组100条数据
            split_list = [table_data_temp[i:i+100] for i in range(0, len(table_data_temp), 100)]
            for split_data in split_list:
                data = make_bitable(split_data)
                if oper.bitable_batch_create(table[category], data):
                    table_data += [i['title'] for i in split_data]
        else:
            console.print(f'\[{category}] 权限验证失败', style='bold red')

        with open(bot_history_file, 'w') as f:
            f.write('\n'.join(bot_history_data + bot_data))

        with open(bitable_history_file, 'w') as f:
            f.write('\n'.join(bitable_history_data + table_data))

    elif args.bot == 'wolai':
        database_history_file = history_path.joinpath(f'wolai_database_{category}.txt')
        database_history_data = database_history_file.read_text().splitlines() if database_history_file.exists() else []

        # 更新数据表格
        console.print(f'\[{category}] Updating database...', style='bold yellow')
        table_data_temp = [
            data
            for data in total_data
            if data['title'] not in database_history_data
        ]
        # 每组20条数据
        split_list = [table_data_temp[i:i+20] for i in range(0, len(table_data_temp), 20)][:1]
        for split_data in split_list:
            data = make_database(split_data)
            if oper.database_post(table[category], data):
                table_data += [i['title'] for i in split_data]

        with open(database_history_file, 'w') as f:
            f.write('\n'.join(database_history_data + table_data))

    console.print(f'\[{category}] Papers: {len(total_data)}\tSend Papers: {len(bot_data)}\tUpdate Papers: {len(table_data)}', style='bold yellow')


def parse_args():
    """参数解析"""
    start_year = datetime.now().year
    end_year = start_year - 5
    parser = argparse.ArgumentParser()
    parser.add_argument('--year', type=str, metavar='start:end', default=f'{start_year}:{end_year}', help='e.g. 2020:2015')
    parser.add_argument('--rule', type=str, metavar='field:type:rank:name', default='all:all:all:all', help='e.g. NIS:conf:A,B:all')
    parser.add_argument('--category', type=str, metavar='category', default='', help='e.g. vehicle,android,linux')
    parser.add_argument('--keywords', type=str, metavar='keywords', default='', help='e.g. keyword1,keyword2')
    parser.add_argument('--bot', type=str, metavar='bot', default='feishu', help='e.g. feishu')
    return parser.parse_args()


if __name__ == '__main__':
    if Path('.env').exists():
        from dotenv import load_dotenv
        load_dotenv('.env')
    print(pyfiglet.figlet_format('OpenCCF'))

    # 参数解析
    args = parse_args()
    conf = json5.loads(Path('config.json5').read_text())
    proxy_url = conf['proxy']

    secrets = conf['openai']['name']
    openai_key = os.getenv(secrets) or conf['openai']['key']
    os.environ[secrets] = openai_key

    secrets = conf['s2api']['name']
    s2api_key = os.getenv(secrets) or conf['s2api']['key']
    os.environ[secrets] = s2api_key

    if args.category:
        category_list = args.category.split(',')
    else:
        category_list = conf['keywords'].keys()

    keywords_dict = {}
    if args.keywords:
        keywords_dict = {i: args.keywords.split(',') for i in category_list}
    else:
        for category in category_list:
            keywords_dict[category] = [
                j
                for i in conf['keywords'][category].values()
                for j in i
                if j.isascii()
            ]

    year = args.year or conf['year']
    rule = args.rule or conf['rule']
    start_year, end_year = parse_year(year)

    # 初始化机器人
    bot, oper, table = init_bot(args.bot, conf)

    # 爬取论文
    crawl_papers()

    for category, keywords in keywords_dict.items():
        # 过滤论文
        total_data = filter_papers(category, keywords)

        # 发送论文
        # send_papers(category, total_data)
