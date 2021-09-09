import re
from .index import b23_extract, bili_keyword, bili_url
from nonebot import on_regex
from nonebot.adapters import Bot, Event
from urllib import parse

analysis_bili = on_regex(r"((b23|acg).tv)|(bili(22|23|33|2233).cn)|(bilibili)|(^(av|cv|ep|ss|md|BV))", flags=re.I)

@analysis_bili.handle()
async def analysis_main(bot: Bot, event: Event, state: dict):
    text = str(event.message).replace(' ','')
    msg = ""
    if re.search(r"((b23|acg).tv)|(bili(22|23|33|2233).cn)", text, re.I):
        text = await b23_extract(text)
    elif re.search(r"bilibili(://|%3A%2F%2F)", text, re.I):
        text = await bili_url(parse.unquote(text))
    if text:
        try:
            group_id = event.group_id
        except:
            group_id = f"i{event.user_id}"
        text = re.sub(r'(?i)live.bilibili.com','live.bilibili.com', text)
        if re.search(r"(live.bilibili.com/(blanc|h5))|(bilibili.com/(video|read|bangumi))|(^(av|cv|ep|ss|md)(\d+))|(^BV([a-zA-Z0-9]){10})", text, re.I):
            msg = await bili_keyword(group_id, text)
        elif str(group_id).startswith("i") and re.search(r"live.bilibili.com/", text, re.I):
            msg = await bili_keyword(group_id, text)
        else:
            print(text)
    if msg:
        await analysis_bili.finish(msg)