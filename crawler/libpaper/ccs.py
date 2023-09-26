import json
import asyncio

from utils import *
from .common import *


def get_ccs_data(data: dict, update: bool=False):
    data_file = paper_path.joinpath('conf_ccs.json')

    if update or not data_file.exists():
        ret_data = get_ccs(data)
        with open(data_file, 'w') as f:
            json.dump(ret_data, f, indent=4, ensure_ascii=False)
    else:
        ret_data = json.loads(data_file.read_text())

    num = sum(len(j['papers']) for i in ret_data.values() for j in i)
    console.print(f'CCS: {num}\n', style='bold green')

    return ret_data


def get_ccs(data: dict):
    results = {}

    # 遍历年份
    for year, v in data.items():
        results[year] = []

        # 遍历会议
        for i in v:
            tasks = []
            loop = asyncio.new_event_loop()

            # 遍历文章
            for idx, paper in enumerate(i['papers']):
                url = paper['url']
                if 'doi.org' in url:
                    task = asyncio.ensure_future(parse_doi_org(paper), loop=loop)
                    tasks.append(task)
                else:
                    console.print(f'Unknow: {url}', style='bold red')
                    i['papers'][idx]['url'] = url

            if tasks:
                i['papers'] = []    # 清空原数据
                try:
                    done, pending = loop.run_until_complete(asyncio.wait(tasks))
                    print(f'done: {len(done)}\t pending: {len(pending)}\n')
                    for task in done:
                        i['papers'].append(task.result())
                    results[year].append(i)
                except Exception:
                    console.print_exception()
                finally:
                    loop.close()
            else:
                results[year].append(i)

    return results
