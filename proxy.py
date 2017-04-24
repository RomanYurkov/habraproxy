import asyncio
import io
import re
from urllib.parse import urljoin
import aiohttp
from aiohttp import web
from bs4 import BeautifulSoup, Comment

habra_protocol = 'https://'
habra_host = 'habrahabr.ru'
habr = habra_protocol + habra_host


def modify_page(page):
    bs = BeautifulSoup(page, 'html.parser')
    comments = bs.find_all(string=lambda text:isinstance(text, Comment))
    for c in comments:
        c.extract()
    for a_html in bs.findAll('a'):
        try:
            a_html['href'] = a_html['href'].replace(
                habr, 'http://localhost:8077')
        except KeyError:
            pass
    return bs.prettify(formatter=None)



def add_tm_str(page):
    bs = BeautifulSoup(page, 'html.parser')
    for i in bs.findAll(text=True):
        tm_element = r"\1{0}".format(u"\u2122")
        add_tm = re.sub(r"(?<!-)\b(\w{6})\b(?!-)",
                        tm_element, i, flags=re.UNICODE)
        if add_tm != i:
            i.replaceWith(add_tm)
    tm_html = bs.prettify(formatter=None)
    return tm_html


async def habra_proxy(request):
    target_url = urljoin(habr, request.path)

    request_headers = dict(request.headers)
    request_headers['Host'] = habra_host

    async with aiohttp.ClientSession() as session:
        response = await session.get(target_url, headers=request_headers)
        change_str = response.content_type == 'text/html'
        exclude_headers = ('Content-Encoding', )
        proxy_response_headers = {
            k: v for k, v in response.headers.items() if k not in exclude_headers}

        proxy_response = web.StreamResponse(
            status=response.status,
            reason=response.reason,
            headers=proxy_response_headers
        )

        await proxy_response.prepare(request)

        while True:
            if change_str:
                chunk = await response.content.read()
            else:
                chunk = await response.content.read(io.DEFAULT_BUFFER_SIZE)
            if not chunk:
                break
            if change_str:
                modify_chunk = chunk.decode(response.charset)
                modify_chunk = modify_page(modify_chunk)
                modify_chunk = add_tm_str(modify_chunk)
                chunk = bytes(modify_chunk, response.charset)
            proxy_response.write(chunk)
            await proxy_response.drain()

        await proxy_response.write_eof()
        await response.release()

    return proxy_response


if __name__ == '__main__':
    proxy = web.Server(habra_proxy)

    event_loop = asyncio.get_event_loop()
    new_server = event_loop.create_server(proxy, '0.0.0.0', 8077)
    server = event_loop.run_until_complete(new_server)

    print(u'Server was started')

    try:
        event_loop.run_forever()
    except KeyboardInterrupt:
        pass

    event_loop.close()
