import re
import aiohttp
import asyncio
import contextlib
import translators
from pathlib import Path
from fake_useragent import UserAgent
from tenacity import retry, stop_after_attempt, wait_fixed

from rich import print
from rich.console import Console
from rich.progress import Progress, TextColumn, BarColumn, MofNCompleteColumn, TimeRemainingColumn


MAX_RETRY = 5
MAX_ROUTINE = 100
sem = asyncio.Semaphore(MAX_ROUTINE)

console = Console()

ScraperAPI = 'cf7e327977f1d6f56b77b48513422be9'

root_path = Path(__file__).parent
data_path = root_path.joinpath('data')
dblp_path = data_path.joinpath('dblp')
dblp_path.mkdir(exist_ok=True)
paper_path = data_path.joinpath('paper')
paper_path.mkdir(exist_ok=True)
history_path = data_path.joinpath('history')
history_path.mkdir(exist_ok=True)


def progress():
    """创建进度条"""
    return Progress(
        TextColumn("{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeRemainingColumn()
    )


def get_translate(text: str):
    """sogou速度较快，优先使用；google作为补充"""
    if text:
        result = ''
        with contextlib.suppress(Exception):
            result = translators.translate_text(text, translator='sogou')

        if result.isascii():
            with contextlib.suppress(Exception):
                result = translators.translate_text(text, translator='google', to_language='zh')

        if not result.isascii():
            return result

    return ''


async def fetch(url: str, headers: dict = None, params: dict=None, proxy: bool=False):
    if headers is None:
        headers = {}
    headers['User-Agent'] = UserAgent().random

    for _ in range(MAX_RETRY):
        try:
            async with sem, aiohttp.ClientSession() as session:
                if proxy and 'doi.org' in url:
                    payload = {'api_key': ScraperAPI, 'url': url}
                    async with session.get(url, headers=headers, payload=payload) as response:
                        if response.status == 200:
                            return await response.text()
                else:
                    async with session.get(url, headers=headers, params=params) as response:
                        if response.status == 200:
                            return await response.text()

            # 超出频率限制
            if response.status == 429:
                await asyncio.sleep(1)
                continue

            console.print(f'Request failed: {response.status} {url}', style='bold red')
            return None
        except Exception:
            await asyncio.sleep(1)

    if 'api.semanticscholar.org' not in url:
        console.print(f'Request failed: max {url}', style='bold red')
    return None


def get_keywords(paper: dict, keywords: list):
    """过滤关键词"""
    key_set = set()
    for key in keywords:
        pattern = re.compile(rf'\b{re.escape(key)}(?!\w)', re.IGNORECASE)

        if paper['title'] and re.search(pattern, paper['title']):
            key_set.add(key)
        elif paper['abstract'] and re.search(pattern, paper['abstract']):
            key_set.add(key)
        elif paper['tldr'] and re.search(pattern, paper['tldr']):
            key_set.add(key)

    return sorted(key_set)


def filter_keywords(data: dict, keywords: list):
    """通过关键词筛选相关论文"""
    results = []
    for year, year_data in data.items():
        for item in year_data:
            dblp_url = item['dblp_url']
            conf_title = item.get('journals_title') or item.get('conf_title') or ''
            conf_url = item.get('journals_url') or item.get('conf_url') or ''
            for paper in item['papers']:
                if key := get_keywords(paper, keywords):
                    paper.update({
                        'year': year,
                        'dblp_url': dblp_url,
                        'conf_title': conf_title,
                        'conf_url': conf_url,
                        'keywords': key
                    })
                    results.append(paper)

    return results
