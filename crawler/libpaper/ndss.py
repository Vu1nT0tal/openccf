import re
import json
import asyncio
from bs4 import BeautifulSoup

from utils import *
from .common import *


def get_ndss_data(data: dict, update: bool=False):
    data_file = paper_path.joinpath('conf_ndss.json')

    if update or not data_file.exists():
        ret_data = data_ndss(data)
        with open(data_file, 'w') as f:
            json.dump(ret_data, f, indent=4, ensure_ascii=False)
    else:
        ret_data = json.loads(data_file.read_text())

    num = sum(len(j['papers']) for i in ret_data.values() for j in i)
    console.print(f'NDSS: {num}\n', style='bold green')

    return ret_data


def data_ndss(data: dict):
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
                if 'ndss-symposium.org' in url:
                    task = asyncio.ensure_future(parse_ndss_symposium_org(paper), loop=loop)
                    tasks.append(task)
                elif 'wp.internetsociety.org' in url:
                    # 转换此类链接
                    base_url = 'https://www.ndss-symposium.org/wp-content/uploads'
                    url = f'{base_url}/{"/".join(url.split("/")[-3:])}'
                    i['papers'][idx]['url'] = url
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


async def parse_ndss_symposium_org(paper: dict):
    data = await fetch(paper['url'])
    if not data:
        paper['status'] = 'error'
        return paper

    try:
        soup = BeautifulSoup(data, 'html.parser')
        data = soup.select_one('div.paper-data')

        # authors = data.contents[1].text.strip()
        # paper['authors'] = authors.strip() if authors else ''

        abstract = data.contents[3].text.strip()
        paper['abstract'] = abstract.strip() if abstract else ''

        files = {}
        slides = {}
        video = ''
        buttons = soup.select_one('div.paper-buttons')
        for a in buttons.select('a'):
            if 'paper' in a.text.lower():
                files['Paper'] = a.attrs.get('href')
            if 'slides' in a.text.lower():
                slides['Slides'] = a.attrs.get('href')
            if 'video' in a.text.lower():
                href = a.attrs.get('href')
                try:
                    video_id = re.search(r"v=([A-Za-z0-9_-]{11})", href)[1]
                    video = f'https://www.youtube.com/watch?v={video_id}'
                except Exception:
                    video = href
        paper['files'].update(files)
        paper['slides'] = slides
        paper['video'] = video

    except Exception:
        paper['status'] = 'error'
        console.print(paper['url'], style='bold red')
        console.print_exception()
    finally:
        return paper
