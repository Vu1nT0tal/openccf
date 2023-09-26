from bs4 import BeautifulSoup

from utils import *


async def parse_doi_org(paper: dict):
    data = await fetch(paper['url'])
    if not data:
        paper['status'] = 'error'
        return paper

    try:
        soup = BeautifulSoup(data, 'html.parser')

        # author = soup.select('a.author-name')
        # authors = ''
        # for a in author:
        #     name = a.find_next('div', class_='author-data').text
        #     inst = a.find_next('span', class_='loa_author_inst').text
        #     authors += f'{name}, '
        # paper['authors'] = authors[:-2]

        abstract = soup.select_one('div.abstractSection.abstractInFull').text
        paper['abstract'] = abstract.strip() if abstract else ''

        files = {}
        file = soup.select('li.pdf-file')
        for f in file:
            href = f.find_next('a').attrs.get('href')
            files['Paper'] = f'https://dl.acm.org{href}'
        paper['files'].update(files)

    except Exception:
        paper['status'] = 'error'
        console.print(paper['url'], style='bold red')
        console.print_exception()
    finally:
        return paper
