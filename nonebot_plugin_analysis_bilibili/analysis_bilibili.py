import re
import json
import aiohttp
import asyncio
import lxml.html
import urllib.parse
from datetime import datetime
import traceback

analysis_stat = {}   # analysis_stat: video_url(vurl)

async def bili_keyword(group_id, text):
    try:
        # 提取url
        url = await extract(text)
        # 如果是小程序就去搜索标题
        if not url:
            pattern = re.compile(r'"desc":".*?"')
            desc = re.findall(pattern,text)
            i = 0
            while i < len(desc):
                title_dict = "{"+desc[i]+"}"
                title = eval(title_dict)
                vurl = await search_bili_by_title(title['desc'])
                if vurl:
                    url = await extract(vurl)
                    break
                i += 1
        
        # 获取视频详细信息
        if "bangumi" in url[0]:
            msg,vurl = await bangumi_detail(url)
        elif "live.bilibili.com" in url[0]:
            msg,vurl = await live_detail(url[0])
        elif "article" in url[0]:
            msg,vurl = await article_detail(url)
        else:
            msg,vurl = await video_detail(url[0])
        
        # 避免多个机器人解析重复推送
        if group_id not in analysis_stat:
            analysis_stat[group_id] = vurl
            last_vurl = ""
        else:
            last_vurl = analysis_stat[group_id]
            analysis_stat[group_id] = vurl
        if last_vurl == vurl:
            return
    except Exception as e:
        msg = f"Error: {type(e)}"
    return msg

async def b23_extract(text):
    try:
        b23 = re.compile(r'(b23.tv|bili(22|23|33|2233).cn)(\\)?/(\w+)', re.I).search(text)
        r=""
        if re.match(r'^(av|bv|ep|ss)', b23[4], re.I):
            r = b23[4]
        else:
            async with aiohttp.request('GET', f'https://bili2233.cn/{b23[4]}', timeout=aiohttp.client.ClientTimeout(10)) as resp:
                r = str(resp.url)
    except:
        r = text
    return r

async def extract(text:str):
    try:
        aid = re.compile(r'av\d+', re.I).search(text)
        bvid = re.compile(r'BV(\w){10}', re.I).search(text)
        epid = re.compile(r'ep\d+', re.I).search(text)
        ssid = re.compile(r'ss\d+', re.I).search(text)
        mdid = re.compile(r'md\d+', re.I).search(text)
        room_id = re.compile(r"live.bilibili.com/(blanc/|h5/)?(\d+)", re.I).search(text)
        cvid = re.compile(r'cv\d+', re.I).search(text)
        getid = ""
        if bvid:
            url = [f'https://api.bilibili.com/x/web-interface/view?bvid={bvid[0]}',f'https://www.biliplus.com/api/view?id={bvid[0]}']
        elif aid:
            url = [f'https://api.bilibili.com/x/web-interface/view?aid={aid[0][2:]}',f'https://www.biliplus.com/api/view?id={aid[0][2:]}']
        elif epid:
            url = f'https://bangumi.bilibili.com/view/web_api/season?ep_id={epid[0][2:]}'
            getid = epid[0][2:]
        elif ssid:
            url = f'https://bangumi.bilibili.com/view/web_api/season?season_id={ssid[0][2:]}'
        elif mdid:
            url = f'https://bangumi.bilibili.com/view/web_api/season?media_id={mdid[0][2:]}'
        elif room_id:
            url = f'https://api.live.bilibili.com/xlive/web-room/v1/index/getInfoByRoom?room_id={room_id[2]}'
        elif cvid:
            url = f"https://api.bilibili.com/x/article/viewinfo?id={cvid[0][2:]}&mobi_app=pc&from=web"
            getid = cvid[0][2:]
        return url,getid
    except:
        return None

async def search_bili_by_title(title: str):
    brackets_pattern = re.compile(r'[()\[\]{}（）【】]')
    title_without_brackets = brackets_pattern.sub(' ', title).strip()
    search_url = f'https://search.bilibili.com/video?keyword={urllib.parse.quote(title_without_brackets)}'

    try:
        async with aiohttp.request('GET', search_url, timeout=aiohttp.client.ClientTimeout(10)) as resp:
            text = await resp.text(encoding='utf8')
            content: lxml.html.HtmlElement = lxml.html.fromstring(text)
    except asyncio.TimeoutError:
        return None

    for video in content.xpath('//li[@class="video-item matrix"]/a[@class="img-anchor"]'):
        if title == ''.join(video.xpath('./attribute::title')):
            url = ''.join(video.xpath('./attribute::href'))
            break
    else:
        url = None
    return url

async def video_detail(url):
    try:
        async with aiohttp.request('GET', url[0], timeout=aiohttp.client.ClientTimeout(10)) as resp:
            res = await resp.json()
        if not res['code']:
            res = res['data']
            title = f"{res['title']}\n"
            if res['rights']['is_cooperation']:
                CZTD=f"\n创作团队({len(res['staff'])}人)：\n"
                for i in res['staff']:
                    CZTD = f"{CZTD}{i['title']}：{i['name']}(https://space.bilibili.com/{i['mid']})\n"
                CZTD = f"{CZTD}\n"
            else:
                CZTD = f"UP主：{res['owner']['name']}(https://space.bilibili.com/{res['owner']['mid']})\n"
            try:
                RU = res['redirect_url']
            except:
                RU = f"https://www.bilibili.com/video/av{res['aid']}\nhttps://www.bilibili.com/video/{res['bvid']}"
            TGSJFQ = f"投稿时间：{datetime.fromtimestamp(res['pubdate']).strftime('%Y-%m-%d %H:%M:%S')}\n投搞分区：{res['tname']}"
            activity=""
            try:
                async with aiohttp.request('GET', f"https://api.bilibili.com/x/activity/subject/info?sid={res['mission_id']}") as resp:
                    activityr = await resp.json()
                if not activityr['code']:
                    activity = f"\n投稿活动：{activityr['data']['name']}"
                    if activityr['data']['act_url']:
                        activity = f"{activity}({activityr['data']['act_url']})"
            except:
                pass
            tag=""
            async with aiohttp.request('GET', f"https://api.bilibili.com/x/web-interface/view/detail/tag?aid={res['aid']}") as resp:
                atag = await resp.json()
            if not atag['code'] and atag['data']:
                tag=f"\n标签({len(atag['data'])}条)："
                for i in atag['data']:
                    if i['tag_type'] == "new_channel":
                        tag_type = "频道"
                    else:
                        tag_type = ""
                    tag = f"{tag}{tag_type}#{i['tag_name']}# "
            other = ""
            if res['stat']['view']:
                other += f"\n播放：{res['stat']['view']}"
            if res['stat']['danmaku']:
                other += f"\n弹幕：{res['stat']['danmaku']}"
            if res['stat']['like']:
                other += f"\n点赞：{res['stat']['like']}"
            if res['stat']['coin']:
                other += f"\n硬币：{res['stat']['coin']}"
            if res['stat']['favorite']:
                other += f"\n收藏：{res['stat']['favorite']}"
            if res['stat']['share']:
                other += f"\n分享：{res['stat']['share']}"
            if res['stat']['reply']:
                other += f"\n评论：{res['stat']['reply']}"
            msg = f"{title}{CZTD}{TGSJFQ}{activity}{tag}{other}\n{RU}"
            return msg, f"https://www.bilibili.com/video/av{res['aid']}"
        elif res['message']=="啥都木有" or res['message']=="稿件不可见":
            t = await video_detail2(url[1])
            if t=="获取失败，请稍后再试":
                msg = t
            elif t in ["啥都木有","稿件不可见","请求错误"]:
                msg = f"查询失败({t})"
            else:
                msg = f"此信息仅供参考\n{t}"
            return msg, None
    except Exception as e:
        msg = f"视频解析出错--Error: {type(e)}"
        return msg, None

async def video_detail2(url2):
    try:
        info=RU = ""
        async with aiohttp.request('GET', url2, timeout=aiohttp.client.ClientTimeout(10)) as resp:
            areq = await resp.json()
        try:
            if areq['v2_app_api']['redirect_url']:
                RU = f"{areq['v2_app_api']['redirect_url'].replace('https://www.bilibili.com/bangumi/play/', '')}\n"
        except:
            pass
        try:
            if areq['ver'] == 2:
                CZTD = ""
                try:
                    if areq['v2_app_api']['rights']['is_cooperation']:
                        CZTD=f"\n\n创作团队({len(areq['v2_app_api']['staff'])}人)：\n"
                        for i in areq['v2_app_api']['staff']:
                            CZTD = f"{CZTD}{i['title']}：{i['name']}({i['follower']}粉丝,https://space.bilibili.com/{i['mid']})\n"
                    elif areq['v2_app_api']['owner']['mid']:
                        CZTD = f"\nUP主：{areq['v2_app_api']['owner']['name']}(https://space.bilibili.com/{areq['v2_app_api']['owner']['mid']})"
                except:
                    if areq['v2_app_api']['owner']['mid']:
                        CZTD = f"\nUP主：{areq['v2_app_api']['owner']['name']}(https://space.bilibili.com/{areq['v2_app_api']['owner']['mid']})"
                TGFQ = ""
                if areq['v2_app_api']['tname']:
                    TGFQ=f"\n投搞分区：{areq['v2_app_api']['tname']}"
                activity=""
                try:
                    async with aiohttp.request('GET', f"https://api.bilibili.com/x/activity/subject/info?sid={res['mission_id']}") as resp:
                        activityr = await resp.json()
                    if not activityr['code']:
                        activity = f"\n投稿活动：{activityr['data']['name']}"
                        if activityr['data']['act_url']:
                            activity = f"{activity}({activityr['data']['act_url']})"
                except:
                    pass
                tag=""
                try:
                    if areq['v2_app_api']['tag']:
                        tag=f"{tag}\n标签({len(areq['v2_app_api']['tag'])}条)："
                        for i in areq['v2_app_api']['tag']:
                            if i['tag_type'] == "new":
                                tag_type = "频道"
                            else:
                                tag_type = ""
                            tag = f"{tag}{tag_type}#{i['tag_name']}# "
                except:
                    pass
                try:
                    ZHAV=f"{areq['v2_app_api']['bvid']}\nav{areq['v2_app_api']['aid']}"
                except:
                    if re.match(r'^(bv)', CXA, re.I):
                        ZHAV=f"{CXA}\n→av{areq['v2_app_api']['aid']}"
                    else:
                        ZHAV=f"av{areq['v2_app_api']['aid']}"
                info = f"{ZHAV}\n{RU}\n{areq['v2_app_api']['title']}(共{areq['v2_app_api']['videos']}P){CZTD}\n投稿时间：{datetime.fromtimestamp(areq['v2_app_api']['pubdate']).strftime('%Y-%m-%d %H:%M:%S')}{TGFQ}{activity}{tag}\n播放：{areq['v2_app_api']['stat']['view']}\n弹幕：{areq['v2_app_api']['stat']['danmaku']}\n点赞：{areq['v2_app_api']['stat']['like']}\n硬币：{areq['v2_app_api']['stat']['coin']}\n收藏：{areq['v2_app_api']['stat']['favorite']}\n分享：{areq['v2_app_api']['stat']['share']}\n评论：{areq['v2_app_api']['stat']['reply']}"
            else:
                if re.match(r'^(bv)', CXA, re.I):
                    ZHAV=f"{CXA}\n→av{areq['id']}"
                else:
                    ZHAV=f"av{areq['id']}"
                info = f"{ZHAV}\n{areq['title']}\nUP主：{areq['author']}(https://space.bilibili.com/{areq['mid']})\n投搞分区：{areq['typename']}\n\n播放：{areq['play']}\n弹幕：{areq['video_review']}\n硬币：{areq['coins']}\n收藏：{areq['favorites']}\n评论：{areq['review']}"
        except:
            #print(traceback.print_exc())
            pass
        if not info:
            info = areq['message']
    except:
        #print(traceback.print_exc())
        info = "获取失败，请稍后再试"
    return info

async def bangumi_detail(url):
    try:
        async with aiohttp.request('GET', url[0], timeout=aiohttp.client.ClientTimeout(10)) as resp:
            res = await resp.json()
        if res['code'] == -404:
            msg = res['message']
            return msg, None
        res = res['result']
        title = f"{res['title']}({res['areas'][0]['name']})\n"
        desc = f"{res['newest_ep']['desc']}\n"
        if "season_id" in url:
            vurl = f"https://www.bilibili.com/bangumi/play/ss{res['season_id']}\n"
        elif "media_id" in url:
            vurl = f"https://www.bilibili.com/bangumi/media/md{res['media_id']}\n"
        elif url[1]:
            vurl = f"https://www.bilibili.com/bangumi/play/ep{url[1]}\n"
            for i in res['episodes']:
                if i['ep_id'] == int(url[1]):
                    if i['index_title']:
                        title += f"{i['index']}. {i['index_title']}\n"
                    elif i['index']:
                        title += f"{i['index']}\n"
                    desc = f"投稿时间：{i['pub_real_time']}\n"
                    break
        style = ""
        for i in res['style']:
            style += i + ","
        style = f"类型：{style[:-1]}\n"
        evaluate = f"简介：{res['evaluate']}"
        msg = str(title)+str(desc)+str(vurl)+str(style)+str(evaluate)
        return msg, vurl
    except Exception as e:
        #print(traceback.print_exc())
        msg = f"番剧解析出错--Error: {type(e)}"
        return msg, None

async def live_detail(url):
    try:
        async with aiohttp.request('GET', url, timeout=aiohttp.client.ClientTimeout(10)) as resp:
            res = await resp.json()
        if res['code'] == -400 or res['code'] == 19002000:
            msg = "直播间不存在"
            return msg, None
        uname = res['data']['anchor_info']['base_info']['uname']
        room_id = res['data']['room_info']['room_id']
        title = res['data']['room_info']['title']
        live_status = res['data']['room_info']['live_status']
        lock_status = res['data']['room_info']['lock_status']
        parent_area_name = res['data']['room_info']['parent_area_name']
        area_name = res['data']['room_info']['area_name']
        online = res['data']['room_info']['online']
        tags = res['data']['room_info']['tags']
        vurl = f"https://live.bilibili.com/{room_id}\n"
        if lock_status:
            lock_time = res['data']['room_info']['lock_time']
            lock_time = datetime.fromtimestamp(lock_time).strftime("%Y-%m-%d %H:%M:%S")
            title = f"(已封禁)直播间封禁至：{lock_time}\n"
        elif live_status:
            title = f"(直播中)标题：{title}\n"
        else:
            title = f"(未开播)标题：{title}\n"
        up = f"主播：{uname} 当前分区：{parent_area_name}-{area_name} 人气上一次刷新值：{online}"
        if tags:
            tags = f"\n标签：{tags}"
        msg = str(vurl)+str(title)+str(up)+str(tags)
        return msg, vurl
    except Exception as e:
        msg = "直播间解析出错--Error: {}".format(type(e))
        return msg, None

async def article_detail(url):
    try:
        async with aiohttp.request('GET', url[0], timeout=aiohttp.client.ClientTimeout(10)) as resp:
            res = await resp.json()
            res = res['data']
        title = f"{res['title']}\n"
        up = f"作者：{res['author_name']} (https://space.bilibili.com/{res['mid']})\n"
        zlwj = ""
        try:
            async with aiohttp.request('GET', f"https://api.bilibili.com/x/article/listinfo?id={url[1]}") as resp:
                azlwj = await resp.json()
            if not azlwj['code'] and azlwj['data']['list']:
                zlwj = f"文集：{azlwj['data']['list']['name']}(https://www.bilibili.com/read/readlist/rl{azlwj['data']['list']['id']})\n"
        except:
            pass
        other = ""
        if res['stats']['view']:
            other += f"阅读：{res['stats']['view']}\n"
        if res['stats']['favorite']:
            other += f"收藏：{res['stats']['favorite']}\n"
        if res['stats']['coin']:
            other += f"硬币：{res['stats']['coin']}\n"
        if res['stats']['share']:
            other += f"分享：{res['stats']['share']}\n"
        if res['stats']['like']:
            other += f"点赞：{res['stats']['like']}\n"
        vurl = f"https://www.bilibili.com/read/cv{url[1]}"
        msg = str(title)+str(up)+str(zlwj)+str(other)+str(vurl)
        return msg, vurl
    except Exception as e:
        msg = f"专栏解析出错--Error: {type(e)}"
        return msg, None