import re
from .index import b23_extract, bili_keyword
from nonebot import on_regex
from nonebot.adapters import Bot, Event

#停用判断:|((\[\[)?QQ小程序(\]|&(amp;)?#93;)哔哩哔哩(\])?)
analysis_bili = on_regex(r"((b23|acg).tv)|(bili(22|23|33|2233).cn)|(live.bilibili.com)|(bilibili.com/(video|read|bangumi))|(^(av|cv|ep|ss|md)(\d+))|(^BV([a-zA-Z0-9]){10})", flags=re.I)

@analysis_bili.handle()
async def analysis_main(bot: Bot, event: Event, state: dict):
    text = str(event.message).strip()
    if re.search(r"((b23|acg).tv)|(bili(22|23|33|2233).cn)", text, re.I):
        text = await b23_extract(text)
    try:
        group_id = event.group_id
    except:
        group_id = f"i{event.user_id}"
    msg = await bili_keyword(group_id, text)
    if msg:
        try:
            await analysis_bili.send(msg)
        except:
            pass