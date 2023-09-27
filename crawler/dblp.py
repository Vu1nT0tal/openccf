import json
import time
import asyncio
import requests
from bs4 import BeautifulSoup

from utils import *
from crawler.scholar import *


def get_dblp_data(url: str, start_year: str, end_year: str):
    dblp_key = '/'.join(url.split('/')[-3:-1])
    dblp_file = dblp_path.joinpath(f'{dblp_key.replace("/", "_")}.json')

    old_data = json.loads(dblp_file.read_text()) if dblp_file.exists() else {}
    all_data, new_data, update_data = get_dblp(dblp_key, old_data, start_year, end_year)

    # 只更新start_year到end_year的数据
    for year, year_data in all_data.items():
        old_data[year] = year_data

    with open(dblp_file, 'w') as f:
        json.dump(old_data, f, indent=4, ensure_ascii=False)

    return url, all_data, new_data, update_data


def get_dblp(key: str, old_data: dict, start_year: str, end_year: str):
    # 期刊/会议主页
    url = f'https://dblp.uni-trier.de/db/{key}/index.html'
    console.print(url, style='bold yellow')
    while True:
        try:
            r = requests.get(url, timeout=30)
            break
        except Exception:
            time.sleep(1)
            print('Retrying...')

    soup = BeautifulSoup(r.content, 'html.parser')
    href_list = []
    tasks = []
    all_papers_dict = {}
    new_papers_dict = {}
    update_papers_dict = {}
    loop = asyncio.new_event_loop()

    old_dict = {}
    for year_data in old_data.values():
        for item in year_data:
            for paper in item['papers']:
                old_dict[paper['title']] = paper

    # 遍历所有年份的所有文章
    if '/journals/' in url:
        href_list = parse_journals_index(soup, start_year, end_year)

        print(href_list)
        for year, href in href_list:
            task = asyncio.ensure_future(parse_journals(year, href, old_dict), loop=loop)
            tasks.append(task)

        console.print(f'tasks: {len(tasks)}\n', style='bold yellow')

    elif '/conf/' in url:
        href_list = parse_conf_index(soup, start_year, end_year)

        print(href_list)
        for year, href in href_list:
            task = asyncio.ensure_future(parse_conf(year, href, old_dict), loop=loop)
            tasks.append(task)

        console.print(f'tasks: {len(tasks)}\n', style='bold yellow')

    if tasks:
        try:
            done, pending = loop.run_until_complete(asyncio.wait(tasks))
            print(f'done: {len(done)}\t pending: {len(pending)}\n')
            for task in done:
                ret = task.result()
                year, all_papers, new_papers, update_papers = ret

                all_papers_dict.setdefault(year, []).append(all_papers)
                new_papers_dict.setdefault(year, []).append(new_papers)
                update_papers_dict.setdefault(year, []).append(update_papers)
        except ValueError:
            console.print(f'ValueError: {ret}', style='bold red')
        except Exception:
            console.print_exception()
        finally:
            loop.close()

    # 按会议排序
    for year in all_papers_dict:
        all_papers_dict[year].sort(key=lambda x: x['dblp_url'])

    return all_papers_dict, new_papers_dict, update_papers_dict


async def parse_journals(year: str, url: str, old_dict: dict):
    """获取一年的所有文章"""
    # 获取网页数据
    data = await fetch(url)
    if not data:
        return url

    try:
        soup = BeautifulSoup(data, 'html.parser')
        # 期刊
        journals_title = soup.select_one('h1').text

        # 文章
        all_papers = []
        new_papers = []
        update_papers = []
        article = soup.select('li.entry.article')
        for a in article:
            new_flag = False
            update_flag = False

            paper = {'url': a.select_one('li.drop-down').select_one('a').attrs.get('href')}
            paper['title'] = a.select_one('span.title').text.strip('.')
            paper['authors'] = ', '.join([a.text for a in a.select('span[itemprop="name"]')[:-1]])

            # 用旧数据补充
            if paper['title'] in old_dict:
                paper = old_dict[paper['title']]
            else:
                new_flag = True

            # 获取新数据补充
            if not paper.get('abstract'):
                paper = await get_scholar(paper)
                if paper['abstract'] and not new_flag:
                    update_flag = True

            all_papers.append(paper)
            if new_flag:
                new_papers.append(paper)
            if update_flag:
                update_papers.append(paper)

            await asyncio.sleep(1)

        result_all = {'dblp_url': url, 'journals_title': journals_title, 'papers': sorted(all_papers, key=lambda x: x['url'])}
        result_new = {'dblp_url': url, 'journals_title': journals_title, 'papers': new_papers}
        result_update = {'dblp_url': url, 'journals_title': journals_title, 'papers': update_papers}

        print(f'{journals_title}\n{url}\nAll Papers: {len(all_papers)}\tNew Papers: {len(new_papers)}\tUpdate Papers: {len(update_papers)}\n')
        return year, result_all, result_new, result_update
    except Exception:
        console.print(url, style='bold red')
        console.print_exception()
        return url


async def parse_conf(year: str, url: str, old_dict: dict):
    """获取一年的所有文章"""
    # 获取网页数据
    data = await fetch(url)
    if not data:
        return url

    try:
        soup = BeautifulSoup(data, 'html.parser')
        # 会议
        conf_title = soup.select_one('h1').text
        if '404' in conf_title:
            print(f'{conf_title}\n{url}\npapers: 0\n')
            return url

        editor = soup.select_one('li.entry.editor')
        conf_url = editor.select_one('li.drop-down').select_one('a').attrs.get('href')
        # conf_title = editor.select_one('span.title').text

        # 文章
        all_papers = []
        new_papers = []
        update_papers = []
        inproceedings = soup.select('li.entry.inproceedings')
        for i in inproceedings:
            new_flag = False
            update_flag = False

            paper = {'url': i.select_one('li.drop-down').select_one('a').attrs.get('href')}
            paper['title'] = i.select_one('span.title').text.strip('.')
            paper['authors'] = ', '.join([a.text for a in i.select('span[itemprop="name"]')[:-1]])

            # 用旧数据补充
            if paper['title'] in old_dict:
                paper = old_dict[paper['title']]
            else:
                new_flag = True

            # 获取新数据补充
            if not paper.get('abstract'):
                paper = await get_scholar(paper)
                if paper['abstract'] and not new_flag:
                    update_flag = True

            all_papers.append(paper)
            if new_flag:
                new_papers.append(paper)
            if update_flag:
                update_papers.append(paper)

            await asyncio.sleep(1)

        result_all = {'dblp_url': url, 'conf_title': conf_title, 'conf_url': conf_url, 'papers': sorted(all_papers, key=lambda x: x['url']))}
        result_new = {'dblp_url': url, 'conf_title': conf_title, 'conf_url': conf_url, 'papers': new_papers}
        result_update = {'dblp_url': url, 'conf_title': conf_title, 'conf_url': conf_url, 'papers': update_papers}

        print(f'{conf_title}\n{url}\nAll Papers: {len(all_papers)}\tNew Papers: {len(new_papers)}\tUpdate Papers: {len(update_papers)}\n')
        return year, result_all, result_new, result_update
    except Exception:
        console.print(url, style='bold red')
        console.print_exception()
        return url


def parse_journals_index(soup, start_year: str, end_year: str):
    """解析期刊首页"""
    results = []
    section = soup.select_one('div#info-section')
    ul = section.find_next_siblings('ul')
    for u in ul:
        for li in u.select('li'):
            aa = li.select('a')
            for a in aa:
                a_text = a.text.strip()
                if len(li.contents) == 1:
                    if ',' in a_text or ':' in a_text:
                        v, year = [i.strip() for i in a_text.replace(',', ':').split(':')]
                    elif ' ' not in a_text:
                        year = a_text
                    else:
                        v, year = a_text.split(' ')
                    # title = f'{v}: {year}'
                else:
                    year, v = [i.strip() for i in li.contents[0].split(':')]
                    # title = f'{v} {a_text}: {year}'

                href = a.attrs.get('href')
                year = year.split('/')[-1] if '/' in year else year
                if year and end_year >= year >= start_year:    # 筛选年份
                    results.append((year, href))
    return results


def parse_conf_index(soup, start_year: str, end_year: str):
    """解析会议首页"""
    results = []

    # conf/ccs
    if workshops := soup.select_one('p:-soup-contains("Workshops:")'):
        ul = workshops.find_next('ul')
        for li in ul.select('li'):
            try:
                title = li.contents[0].strip()
                aa = li.select('a')
            except Exception:
                title = li.find_next('a').text.strip() + li.contents[1]
                aa = li.select('a')[1:]
            title = title.strip().strip(':').replace('\n', ' ')

            for a in aa:
                year = a.text.strip()
                href = a.attrs.get('href')
                if year and end_year >= year >= start_year:
                    results.append((year, href))

    for h2 in soup.select('header.h2'):
        year = h2.select_one('h2').attrs.get('id')
        # 筛选年份，示例：'2016' < '2016a' < '2017'
        if year and end_year >= year >= start_year:
            if n := h2.next_sibling:
                if n.name == 'ul':
                    toc = n.select('li.entry.editor.toc')
                    for t in toc:
                        href = t.select_one('li.drop-down').select_one('a').attrs.get('href')
                        results.append((year, href))

                    workshop = n.next_sibling
                    if 'workshop' in workshop.text.lower():
                        for a in workshop.select('a'):
                            title = a.text.strip()
                            href = a.attrs.get('href')
                            results.append((year, href))
                # elif n.name == 'p':
                #     a = n.select_one('a')
                #     title = a.text.strip()
                #     href = a.attrs.get('href')
                #     results.append((year, href))

    return results
