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
        return
    return msg

async def b23_extract(text):
    r = ""
    b23 = re.compile(r'((b23|acg).tv|bili(22|23|33|2233).cn)(\\)?/(\w+)', re.I).findall(text)
    if b23:
        b23 = b23[-1]
        print(b23)
        if re.search(r'^acg.tv', b23[0], re.I):
            if re.search(r'^av', b23[-1]):
                r = b23[-1]
        else:
            if re.search(r'^(av|bv|ep|ss)', b23[-1]):
                r = b23[-1]
            else:
                b23 = f'https://{b23[0]}/{b23[-1]}'
                async with aiohttp.request('GET', b23, timeout=aiohttp.client.ClientTimeout(10)) as resp:
                    if str(resp.url) != b23:
                        r = re.sub(r'\?(.*)','',str(resp.url))
    return r

async def extract(text:str):
    try:
        getid = ""
        aid = re.compile(r'av(\d+)', re.I).findall(text)
        bvid = re.compile(r'BV([a-zA-Z0-9]{10})', re.I).findall(text)
        epid = re.compile(r'ep(\d+)', re.I).findall(text)
        ssid = re.compile(r'ss(\d+)', re.I).findall(text)
        mdid = re.compile(r'md(\d+)', re.I).findall(text)
        roomid = re.compile(r"live.bilibili.com/(blanc/|h5/)?(\d+)", re.I).findall(text)
        cvid = re.compile(r'(cv|/read/mobile(/|\?id=))(\d+)', re.I).findall(text)
        if not cvid and re.compile(r'/read/native\?id=(\d+)', re.I).findall(text):
            # app上专栏链接另外re
            cvid = re.compile(r'/read/native\?id=(\d+)', re.I).findall(text)
        if aid:
            url = [f'https://api.bilibili.com/x/web-interface/view?aid={aid[-1]}',f'https://www.biliplus.com/api/view?id={aid[-1]}']
        elif bvid:
            url = [f'https://api.bilibili.com/x/web-interface/view?bvid={bvid[-1]}',f'https://www.biliplus.com/api/view?id=BV{bvid[-1]}']
        elif epid:
            getid = epid[-1]
            url = f'https://bangumi.bilibili.com/view/web_api/season?ep_id={getid}'
        elif ssid:
            url = f'https://bangumi.bilibili.com/view/web_api/season?season_id={ssid[-1]}'
        elif mdid:
            url = f'https://bangumi.bilibili.com/view/web_api/season?media_id={mdid[-1]}'
        elif roomid:
            url = f'https://api.live.bilibili.com/xlive/web-room/v1/index/getInfoByRoom?room_id={roomid[-1][-1]}'
        elif cvid:
            getid = cvid[-1][-1]
            url = f"https://api.bilibili.com/x/article/viewinfo?id={getid}&mobi_app=pc&from=web"
        print(url)
        return url,getid
    except:
        return None

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
                RU = f"{res['redirect_url']}\n(av{res['aid']}·{res['bvid']})"
            except:
                RU = f"https://www.bilibili.com/video/{res['bvid']} (av{res['aid']})"
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
            msg = f"{title}{RU}\n{CZTD}{TGSJFQ}{activity}{tag}{other}"
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
                    ZHAV=f"av{areq['v2_app_api']['aid']}\n{areq['v2_app_api']['bvid']}"
                except:
                    if re.search(r'^(bv)', CXA, re.I):
                        ZHAV=f"{CXA}\n→av{areq['v2_app_api']['aid']}"
                    else:
                        ZHAV=f"av{areq['v2_app_api']['aid']}"
                info = f"{ZHAV}\n{RU}\n{areq['v2_app_api']['title']}(共{areq['v2_app_api']['videos']}P){CZTD}\n投稿时间：{datetime.fromtimestamp(areq['v2_app_api']['pubdate']).strftime('%Y-%m-%d %H:%M:%S')}{TGFQ}{activity}{tag}"
            else:
                if re.search(r'^(bv)', CXA, re.I):
                    ZHAV=f"{CXA}\n→av{areq['id']}"
                else:
                    ZHAV=f"av{areq['id']}"
                info = f"{ZHAV}\n{areq['title']}\nUP主：{areq['author']}(https://space.bilibili.com/{areq['mid']})\n投搞分区：{areq['typename']}"
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
        desc = f"{res['newest_ep']['desc']}"
        try:
            async with aiohttp.request('GET', f"https://api.bilibili.com/pgc/review/user?media_id={res['media_id']}") as resp:
                xres = await resp.json()
                xres = xres['result']['media']
                type_name = xres['type_name']
                title = f"{xres['title']}({type_name}·{xres['areas'][0]['name']})\n"
                desc += f" {xres['new_ep']['index_show']}\n"
        except:
            desc += "\n"
            type_name = ""
        if "season_id" in url[0]:
            vurl = f"https://www.bilibili.com/bangumi/play/ss{res['season_id']}"
        elif "media_id" in url[0]:
            vurl = f"https://www.bilibili.com/bangumi/media/md{res['media_id']}"
        elif url[1]:
            vurl = f"https://www.bilibili.com/bangumi/play/ep{url[1]}"
            for i in res['episodes']:
                if i['ep_id'] == int(url[1]):
                    index = i['index']
                    if re.search(r"^(\d+)$", index, re.I):
                        if type_name in ("番剧","国创"):
                            HJ="话"
                        else:
                            HJ="集"
                        index = f"第{index}{HJ}"
                    if i['index_title']:
                        title += f"{index} - {i['index_title']}\n"
                    elif i['index']:
                        title += f"{index}\n"
                    desc = f"更新时间：{i['pub_real_time']}\n"
                    vurl += f"\n(av{i['aid']}·{i['bvid']})"
                    break
        style = ""
        for i in res['style']:
            style += i + "、"
        style = f"\n风格：{style[:-1]}\n"
        evaluate = f"简介：{res['evaluate']}"
        msg = str(title)+str(desc)+str(vurl)+str(style)+str(evaluate)
        return msg, vurl
    except Exception as e:
        print(traceback.print_exc())
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
        vurl = purl = f"https://live.bilibili.com/{room_id}"
        if lock_status:
            lock_time = res['data']['room_info']['lock_time']
            lock_time = datetime.fromtimestamp(lock_time).strftime("%Y-%m-%d %H:%M:%S")
            title = f"(已封禁)直播间封禁至：{lock_time}\n"
        elif live_status == 1:
            title = f"[直播] {title}\n"
            purl += f"\n独立播放器：https://www.bilibili.com/blackboard/live/live-activity-player.html?enterTheRoom=0&cid={room_id}"
        else:
            title = f"[轮播/闲置] {title}\n"
        up = f"\n主播：{uname}\n当前分区："
        if parent_area_name==area_name:
            up += parent_area_name
        else:
            up += f"{parent_area_name}-{area_name}"
        up += f"\n人气上一次刷新值：{online}"
        if tags:
            tags = f"\n标签：{tags}"
        RL = ""
        try:
            async with aiohttp.request('GET', f"https://api.live.bilibili.com/xlive/web-room/v1/index/getOffLiveList?count=1&room_id={room_id}") as resp:
                OLL = await resp.json()
            if not OLL['code'] and OLL['data']['record_list']:
                if OLL['data']['record_list'][0]['title'] != res['data']['room_info']['title']:
                    RT = f"{OLL['data']['record_list'][0]['title']} ("
                else:
                    RT = "("
                RST = OLL['data']['record_list'][0]['start_time']
                if OLL['data']['record_list'][0]['rid']:
                    RU = f")\nhttps://live.bilibili.com/record/{OLL['data']['record_list'][0]['rid']}"
                elif OLL['data']['record_list'][0]['bvid']:
                    RU = f")\nhttps://www.bilibili.com/video/{OLL['data']['record_list'][0]['bvid']}"
                RL = f"\n最近回放：{RT}{RST}{RU}";
        except:
            pass
        msg = str(title)+str(purl)+str(up)+str(tags)+str(RL)
        return msg, vurl
    except Exception as e:
        #print(traceback.print_exc())
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