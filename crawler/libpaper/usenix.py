import re
import json
import asyncio
import bibtexparser
from bs4 import BeautifulSoup

from utils import *
from .common import *


def get_usenix_data(data: dict, update: bool=False):
    data_file = paper_path.joinpath('conf_uss.json')

    if update or not data_file.exists():
        ret_data = get_usenix(data)
        with open(data_file, 'w') as f:
            json.dump(ret_data, f, indent=4, ensure_ascii=False)
    else:
        ret_data = json.loads(data_file.read_text())

    num = sum(len(j['papers']) for i in ret_data.values() for j in i)
    console.print(f'USENIX: {num}\n', style='bold green')

    return ret_data


def get_usenix(data: dict):
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
                if 'usenix.org' in url:
                    task = asyncio.ensure_future(parse_usenix_org(paper), loop=loop)
                    tasks.append(task)
                elif 'doi.org' in url:
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


async def parse_usenix_org(paper: dict):
    data = await fetch(paper['url'])
    if not data:
        paper['status'] = 'error'
        return paper

    try:
        soup = BeautifulSoup(data, 'html.parser')
        paper['bibtex'] = ''
        if bibtex := soup.select_one('div.bibtex-text-entry.bibtex-accordion-text-entry'):
            paper['bibtex'] = bibtex.text.strip()
            bibtex = bibtexparser.loads(bibtex.text)

        # authors = ''  # 目前是使用dblp的作者
        abstract = ''
        label = soup.select('div.field-label')
        for l in label:
            # if 'Authors' in l.text:
            #     authors = l.find_next('div', class_='field-item odd').text
            if 'Abstract' in l.text:
                abstract = l.find_next('div', class_='field-item odd').text

        # if not authors:
        #     odd = soup.select('div.field-item.odd')
        #     for o in odd:
        #         if o.text and o.text == abstract:
        #             if tmp := o.find_previous('div', class_='field-item odd'):
        #                 authors = tmp.text
        #             break
        #     if not authors:
        #         authors = bibtex.entries[0].get('author') if bibtex else ''
        # paper['authors'] = authors.strip() if authors else ''
        paper['abstract'] = abstract.strip() if abstract else ''

        files = {}
        file = soup.select('span.file')
        for f in file:
            if a := f.select_one('a'):
                files[a.text.strip()] = a.attrs.get('href')

        slides = {}
        slide = soup.select('div.usenix-schedule-slides')
        for s in slide:
            if a := s.select_one('a'):
                slides[a.text.strip()] = a.attrs.get('href')

        if not files or not slides:
            label = soup.select('div.field-label')
            for l in label:
                if 'paper' in l.text.lower():
                    files['Paper'] = l.find_next('div', class_='field-item odd').text
                if 'slides' in l.text.lower():
                    slides['Slides'] = l.find_next('div', class_='field-item odd').text
        paper['files'].update(files)
        paper['slides'] = slides

        video = ''
        if player := soup.select_one('div.player'):
            src = player.find_next().attrs.get('src')
            video_id = re.search(r"embed/(.+)\?", src)[1]
            video = f'https://www.youtube.com/watch?v={video_id}'
        elif player := soup.select_one('video'):
            video = player.find_next('source').attrs.get('src')
        paper['video'] = video

    except Exception:
        paper['status'] = 'error'
        console.print(paper['url'], style='bold red')
        console.print_exception()
    finally:
        return paper
