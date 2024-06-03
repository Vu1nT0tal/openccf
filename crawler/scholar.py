import os
import json
import contextlib
from semanticscholar import SemanticScholar
from scholarly import scholarly, ProxyGenerator, MaxTriesExceededException

from utils import *

# pg = ProxyGenerator()
# pg.FreeProxies()
# pg.ScraperAPI(ScraperAPI)
# scholarly.use_proxy(pg, pg)


async def get_scholar(paper: dict):
    """获取补充数据"""
    paper.setdefault('files', {'openAccessPdf': ''})

    if ret := await get_semantic_scholar(paper['title']):
        paper['abstract'] = ret['abstract']
        paper['tldr'] = ret['tldr']
        paper['files']['openAccessPdf'] = ret['openAccessPdf']
    elif ret := get_semantic_scholar2(paper['title']):
        paper['abstract'] = ret['abstract']
        paper['tldr'] = ret['tldr']
        paper['files']['openAccessPdf'] = ret['openAccessPdf']
    elif ret := get_google_scholar(paper['title']):
        paper['abstract'] = ret['abstract']

    if not paper.get('title_zh'):
        paper['title_zh'] = get_translate(paper['title'])
    if not paper.get('abstract_zh'):
        paper['abstract_zh'] = get_translate(paper['abstract'])
    if not paper.get('tldr_zh'):
        paper['tldr_zh'] = get_translate(paper['tldr'])

    if not paper['abstract'] and not paper['tldr']:
        console.print(f'Abstract null: {paper["title"]}', style='bold red')

    return paper


async def get_semantic_scholar(title: str):
    """https://api.semanticscholar.org/api-docs/graph
    使用API获取Semantic Scholar数据
    无KEY：5000次/5分钟；有KEY：100次/秒
    """
    semantic_url = 'https://api.semanticscholar.org/graph/v1/paper/search'

    bad_character = ['(', ')', '/', '-', ':']
    for c in bad_character:
        title = title.replace(c, ' ')

    headers = {
        'x-api-key': os.getenv('S2API_KEY'),
    }
    params = {
        'query': title,
        'fields': 'abstract,tldr,openAccessPdf',
        'limit': 1
    }
    with contextlib.suppress(Exception):
        ret_text = await fetch(semantic_url, headers=headers, params=params)
        ret = json.loads(ret_text)['data'][0]
        return {
            'abstract': ret['abstract'] or '',
            'tldr': ret['tldr']['text'] or '',
            'openAccessPdf': ret['openAccessPdf']['url'] if ret['openAccessPdf'] else ''
        }

    return {}


def get_semantic_scholar2(title: str):
    """使用第三方库获取Semantic Scholar数据"""
    sch = SemanticScholar(api_key=os.getenv('S2API_KEY'))

    bad_character = ['(', ')', '/', '-', ':']
    for c in bad_character:
        title = title.replace(c, ' ')

    with contextlib.suppress(Exception):
        ret = sch.search_paper(title, fields=['abstract', 'tldr', 'openAccessPdf'], limit=1)[0]
        return {
            'abstract': ret['abstract'] or '',
            'tldr': ret['tldr']['text'] or '',
            'openAccessPdf': ret['openAccessPdf']['url'] if ret['openAccessPdf'] else ''
        }

    return {}


def get_google_scholar(title: str):
    """获取Google Scholar数据，摘要可能不完整"""
    result = {}
    return result
    try:
        if result := next(scholarly.search_pubs(title))['bib']['abstract']:
            result['abstract'] = result
    except MaxTriesExceededException:
        console.print(f'Google Max failed: {title}', style='bold red')
    except TimeoutError:
        console.print(f'Google Timeout failed: {title}', style='bold red')
    except Exception:
        console.print(f'Google failed: {title}', style='bold red')
        console.print_exception()
    finally:
        return result
