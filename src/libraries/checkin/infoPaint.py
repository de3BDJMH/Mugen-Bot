import json
import calendar
import datetime
import pathlib
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops
from zoneinfo import ZoneInfo

from .tools import *

VOLTAGE_COLORS={
    "Steam":(170,170,170,255),
    "ULV":(255,85,85,255),
    "LV":(0,170,0,255),
    "MV":(255,170,0,255),
    "HV":(255,255,85,255),
    "EV":(85,85,85,255),
    "IV":(85,85,255,255),
    "LuV":(255,85,255,255),
    "ZPM":(85,255,255,255),
    "UV":(0,170,0,255),
    "UHV":(170,0,0,255),
    "UEV":(170,0,170,255),
    "UIV":(0,0,170,255),
    "UMV":(255,85,85,255),
    "UXV":(170,0,0,255),
    "MAX":(255,255,255,255)
}

VOLTAGE_STYLES={
    "Steam":{"bold":False,"underline":False},
    "ULV":{"bold":False,"underline":False},
    "LV":{"bold":False,"underline":False},
    "MV":{"bold":False,"underline":False},
    "HV":{"bold":False,"underline":False},
    "EV":{"bold":False,"underline":False},
    "IV":{"bold":False,"underline":False},
    "LuV":{"bold":False,"underline":False},
    "ZPM":{"bold":False,"underline":False},
    "UV":{"bold":False,"underline":True},
    "UHV":{"bold":False,"underline":True},
    "UEV":{"bold":False,"underline":True},
    "UIV":{"bold":True,"underline":True},
    "UMV":{"bold":True,"underline":True},
    "UXV":{"bold":True,"underline":True},
    "MAX":{"bold":True,"underline":True}
}

FONT_PATH=pathlib.Path(__file__).parent.parent.parent.parent/"data"/"checkin"/"font"/"RuiZiTaiKongPaoKuXiangSuJian-Shan-ChaoHei(REEJI-TaikoRunGB-Flash-Heavy)-2.ttf"
MCFONT_PATH=pathlib.Path(__file__).parent.parent.parent.parent/"data"/"checkin"/"font"/"Minecraft.ttf"
name_font = ImageFont.truetype(str(MCFONT_PATH), size=60)
title_font = ImageFont.truetype(str(FONT_PATH), size=40)
subtitle_font = ImageFont.truetype(str(FONT_PATH), size=20)
data_font_big=ImageFont.truetype(str(FONT_PATH),size=42)
data_font_small=ImageFont.truetype(str(FONT_PATH),size=24)
info_font=ImageFont.truetype(str(FONT_PATH),size=24)

def paint_cell(day, day_info, cell_w=100, cell_h=140):
    """
    日历单个格子绘制
    """
    pad = 20
    cw, ch = cell_w + pad * 2, cell_h + pad * 2
    cell_img = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    x1, y1, x2, y2 = pad, pad, pad + cell_w, pad + cell_h
    
    #计算底色红绿高度
    inc_bytes = day_info[1].getBytes()
    dec_bytes = day_info[2].getBytes()
    total_bytes = inc_bytes + dec_bytes
    if total_bytes > 0:
        green_h = int(inc_bytes / total_bytes * (cell_h - 4))
        red_h = cell_h - 4 - green_h
    else:
        green_h, red_h = 0, 0

    #发光颜色
    if datetime.date.today()<datetime.date(day[0],day[1],day[2]):#这天还没到
        glow_color = (0, 0, 0, 0)
        border_color = (100, 105, 120, 255)
        text_color = (100, 105, 120, 255)
        has_glow = False
    elif day_info[3][3]:#补签
        glow_color=(180,80,255,255)#霓虹紫
        border_color=(230,170,255,255)#亮紫色边框
        text_color=(255,255,255,255)
        has_glow=True
    elif day_info[3][0]:#签到了
        glow_color = (255, 165, 0, 255)     # 闪耀金橙
        border_color = (255, 223, 0, 255)   # 亮金色实体边框
        text_color = (255, 255, 255, 255)
        has_glow = True
    else:#没签到，没data变化
        glow_color = (0, 180, 216, 255)     # 霓虹冰蓝
        border_color = (255, 255, 255, 255)
        text_color = (255, 255, 255, 255)
        has_glow = True

    #发光绘制
    if has_glow:
        #第一层强发光
        mask_core = Image.new("L", (cw, ch), 0)
        gd_core = ImageDraw.Draw(mask_core)
        gd_core.rectangle([x1, y1, x2, y2], outline=255, width=30) 
        core_glow_mask = mask_core.filter(ImageFilter.GaussianBlur(radius=5)) 

        #第二层弱发光
        mask_bloom = Image.new("L", (cw, ch), 0)
        gd_bloom = ImageDraw.Draw(mask_bloom)
        gd_bloom.rectangle([x1, y1, x2, y2], outline=255, width=50) 
        bloom_glow_mask = mask_bloom.filter(ImageFilter.GaussianBlur(radius=15)) 

        #结合
        solid_glow_color = Image.new("RGBA", (cw, ch), glow_color)
        enhanced_glow = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        enhanced_glow.paste(solid_glow_color, (0, 0), mask=bloom_glow_mask)
        enhanced_glow.paste(solid_glow_color, (0, 0), mask=core_glow_mask)

        #内部填充，只保留外发光
        ImageDraw.Draw(enhanced_glow).rectangle([x1+1, y1+1, x2-1, y2-1], fill=(0, 0, 0, 0))
        cell_img = Image.alpha_composite(cell_img, enhanced_glow)

    #格子底色绘制（红绿）
    fill_layer = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fill_layer)
    if total_bytes > 0:
        if green_h > 0: 
            fd.rectangle([x1+2, y1+2, x2-2, y1+2+green_h], fill=(0, 230, 118, 40))
        if red_h > 0:   
            fd.rectangle([x1+2, y2-2-red_h, x2-2, y2-2], fill=(255, 23, 68, 35))
    else:
        fd.rectangle([x1+2, y1+2, x2-2, y2-2], fill=(30, 34, 53, 20))
    cell_img = Image.alpha_composite(cell_img, fill_layer)

    #内阴影绘制
    shadow_layer = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow_layer)
    sd.rectangle([x1, y1, x2, y2], outline=(0, 0, 0, 64), width=8)
    blurred_shadow = shadow_layer.filter(ImageFilter.GaussianBlur(radius=2))
    
    mask = Image.new("L", (cw, ch), 0)
    md = ImageDraw.Draw(mask)
    md.rectangle([x1+2, y1+2, x2-2, y2-2], fill=255)
    
    all_shadow_layer = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    all_shadow_layer.paste(blurred_shadow, (0, 0), mask=mask)
    cell_img = Image.alpha_composite(cell_img, all_shadow_layer)

    #边框绘制
    cell = ImageDraw.Draw(cell_img)
    cell.rectangle([x1, y1, x2, y2], outline=border_color, width=2)

    #日期数字绘制
    cx = x1 + cell_w // 2
    cy = y1 + cell_h // 2
    cell.text((cx, cy), str(day[2]), fill=text_color, font=title_font, anchor="mm")

    #签到排名绘制
    if day_info[3][0]:
        try:
            rank_num = day_info[3][2]
            rank_text = f"#{rank_num}"
            rank_x = x2 - 8
            rank_y = y2 - 8
            rank_color = (255, 235, 150, 180) if border_color != (255, 255, 255, 255) else (255, 255, 255, 150)
            cell.text((rank_x, rank_y), rank_text, fill=rank_color, font=subtitle_font, anchor="rb")
        except (IndexError, TypeError):
            pass
    
    return cell_img, pad

def paint_progress(ratio, text1,text2,
                         color1=(255, 190, 0, 255),color2=(0, 180, 216, 32),
                         text1_color=(20, 30, 60, 192),text2_color=(255, 225, 120, 255),
                         glow_color11=(255, 100, 0, 100),glow_color12=(255, 160, 0, 180),
                         glow_color21=(0,0,0,0),glow_color22=(0,0,0,0),
                         width=790, height=14, font=None, double=False):
    """
    进度条绘制
    文字位于分割线两侧
    写的有点狗屎，这块前前后后改了很多很多次
    double是表示这个进度条是不是两段的
    color2     # 底色，double时候为右段颜色
    color1     # 左段颜色
    text1_color  # 左段文字色
    text2_color # 右段文字色
    """
    if font is None:
        font = subtitle_font

    pad = 50
    bw = width + pad * 2
    bh = height + pad * 2

    bar_img = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    draw = ImageDraw.Draw(bar_img)

    x1, y1 = pad, pad
    x2, y2 = pad + width, pad + height#进度条左上右下

    #调整绘制文字
    tmp_draw = ImageDraw.Draw(Image.new("RGBA", (bw, bh)))
    bbox = tmp_draw.textbbox((0, 0), text1, font=font)
    text_w1 = bbox[2] - bbox[0]
    bbox = tmp_draw.textbbox((0, 0), text2, font=font)
    text_w2 = bbox[2] - bbox[0]
    text_x1=x1+ratio*width-text_w1#两个文字绘制的x
    text_x2=x1+ratio*width
    if text_x1<x1:
        text2=f" {text1}/{text2} "
        text1=""
    if text_x2+text_w2>x2:
        text1=f" {text1}/{text2} "
        text2=""
        bbox = tmp_draw.textbbox((0, 0), text1, font=font)
        text_w1 = bbox[2] - bbox[0]
        text_x1=x1+ratio*width-text_w1

    fill_w = int(width * ratio)#填充长度
    divx = x1 + fill_w#分界线

    #填充进度条颜色
    if double:#两段
        draw.rectangle([x1, y1, x2, y2], fill=color2)  #整条轨道
        #左段
        draw.rectangle([x1, y1, divx, y2], fill=color1)
        #左段发光
        progress_bar = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        progress_draw = ImageDraw.Draw(progress_bar)
        progress_draw.rectangle([x1 - 2, y1 - 2, divx + 2, y2 + 2], fill=glow_color11)
        glow_blurred = progress_bar.filter(ImageFilter.GaussianBlur(radius=12))
        glow_img_core = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        glow_draw_core = ImageDraw.Draw(glow_img_core)
        glow_draw_core.rectangle([x1 - 1, y1 - 1, divx + 1, y2 + 1], fill=glow_color12)
        core_glow_blurred = glow_img_core.filter(ImageFilter.GaussianBlur(radius=4))
        bar_img = Image.alpha_composite(bar_img, glow_blurred)
        bar_img = Image.alpha_composite(bar_img, core_glow_blurred)
        #右段
        draw.rectangle([divx, y1, x2, y2], fill=color2)
        #右段发光
        progress_bar_right = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        progress_draw_right = ImageDraw.Draw(progress_bar_right)
        progress_draw_right.rectangle([divx - 2, y1 - 2, x2 + 2, y2 + 2], fill=glow_color21)
        glow_blurred_right = progress_bar_right.filter(ImageFilter.GaussianBlur(radius=12))
        glow_img_core_right = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        glow_draw_core_right = ImageDraw.Draw(glow_img_core_right)
        glow_draw_core_right.rectangle([divx - 1, y1 - 1, x2 + 1, y2 + 1], fill=glow_color22)
        core_glow_blurred_right = glow_img_core_right.filter(ImageFilter.GaussianBlur(radius=4))
        bar_img = Image.alpha_composite(bar_img, glow_blurred_right)
        bar_img = Image.alpha_composite(bar_img, core_glow_blurred_right)
    else:
        #只有左
        draw.rectangle([x1, y1, x2, y2], fill=color2)
        draw.rectangle([x1, y1, divx, y2], fill=color1)
        progress_bar = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        progress_draw = ImageDraw.Draw(progress_bar)
        progress_draw.rectangle([x1 - 2, y1 - 2, divx + 2, y2 + 2], fill=glow_color11)
        wide_glow_blurred = progress_bar.filter(ImageFilter.GaussianBlur(radius=12))
        glow_img_core = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        glow_draw_core = ImageDraw.Draw(glow_img_core)
        glow_draw_core.rectangle([x1 - 1, y1 - 1, divx + 1, y2 + 1], fill=glow_color12)
        core_glow_blurred = glow_img_core.filter(ImageFilter.GaussianBlur(radius=4))
        bar_img = Image.alpha_composite(bar_img, wide_glow_blurred)
        bar_img = Image.alpha_composite(bar_img, core_glow_blurred)

    #绘制文字
    text_mask = Image.new("L", (bw, bh), 0)
    ImageDraw.Draw(text_mask).text(
        (text_x1, y1 + height // 2), text1, font=font, fill=255, anchor="lm"
    )
    ImageDraw.Draw(text_mask).text(
        (text_x2, y1 + height // 2), text2, font=font, fill=255, anchor="lm"
    )

    #本来想做镂空的，后来发现没必要...
    if double:
        left_zone = Image.new("L", (bw, bh), 0)
        ImageDraw.Draw(left_zone).rectangle([x1, y1, divx, y2], fill=255)
        right_zone = Image.new("L", (bw, bh), 0)
        ImageDraw.Draw(right_zone).rectangle([divx, y1, x2, y2], fill=255)
        left_text_mask = ImageChops.darker(text_mask, left_zone)
        bar_img.paste(Image.new("RGBA", (bw, bh), text1_color), (0, 0), mask=left_text_mask)
        right_text_mask = ImageChops.darker(text_mask, right_zone)
        bar_img.paste(Image.new("RGBA", (bw, bh), text2_color), (0, 0), mask=right_text_mask)
    else:
        yellow_zone = Image.new("L", (bw, bh), 0)
        ImageDraw.Draw(yellow_zone).rectangle([x1, y1, divx, y2], fill=255)
        blue_zone = Image.new("L", (bw, bh), 255)
        ImageDraw.Draw(blue_zone).rectangle([0, 0, x1, bh], fill=0)
        ImageDraw.Draw(blue_zone).rectangle([x1, y1, divx, y2], fill=0)
        blue_text_mask = ImageChops.darker(text_mask, yellow_zone)
        bar_img.paste(Image.new("RGBA", (bw, bh), text1_color), (0, 0), mask=blue_text_mask)
        yellow_text_mask = ImageChops.subtract(text_mask, blue_text_mask)
        bar_img.paste(Image.new("RGBA", (bw, bh), text2_color), (0, 0), mask=yellow_text_mask)

    return bar_img, pad

def _mix_color(color,target,ratio):
    return tuple(int(color[i]*(1-ratio)+target[i]*ratio) for i in range(3))+(color[3],)

def draw_mc_voltage_text(img:Image.Image,draw:ImageDraw.ImageDraw,pos:tuple,text:str,color:tuple,font:ImageFont.FreeTypeFont,bold:bool=False,underline:bool=False)->float:
    """画名字左边的电压"""
    x,y=pos
    light=_mix_color(color,(255,255,255),0.3)
    dark=_mix_color(color,(0,0,0),0.6)

    #弱外发光
    text_mask=Image.new("L",img.size,0)
    mask_draw=ImageDraw.Draw(text_mask)
    mask_draw.text((x,y),text,font=font,fill=120,anchor="lt",stroke_width=1,stroke_fill=120)
    if bold:
        mask_draw.text((x+2,y),text,font=font,fill=120,anchor="lt",stroke_width=1,stroke_fill=120)
    glow_mask=text_mask.filter(ImageFilter.GaussianBlur(6))
    glow=Image.new("RGBA",img.size,(color[0],color[1],color[2],0))
    glow.putalpha(glow_mask.point(lambda p:int(p*0.45)))
    img.alpha_composite(glow)

    #右下阴影
    draw.text((x+4,y+4),text,fill=dark,font=font,anchor="lt")
    if bold:
        draw.text((x+6,y+4),text,fill=dark,font=font,anchor="lt")

    #左上高光
    draw.text((x-1,y-1),text,fill=light,font=font,anchor="lt")
    if bold:
        draw.text((x+1,y-1),text,fill=light,font=font,anchor="lt")

    #主体
    draw.text((x,y),text,fill=color,font=font,anchor="lt",stroke_width=1,stroke_fill=dark)
    if bold:
        draw.text((x+2,y),text,fill=color,font=font,anchor="lt",stroke_width=1,stroke_fill=dark)

    bbox=draw.textbbox((x,y),text,font=font,anchor="lt",stroke_width=1)
    text_w=bbox[2]-bbox[0]
    text_h=bbox[3]-bbox[1]
    if bold:
        text_w+=2

    #下划线
    if underline:
        uy=y+text_h+2
        uh=4
        underline_img=Image.new("RGBA",img.size,(0,0,0,0))
        ud=ImageDraw.Draw(underline_img)
        ud.rectangle([x,uy,x+text_w,uy+uh],fill=color)
        underline_blur=underline_img.filter(ImageFilter.GaussianBlur(3))
        img.alpha_composite(underline_blur)
        draw.rounded_rectangle([x,uy,x+text_w,uy+uh],radius=1,fill=color)

    return text_w

def split_data_display(text:str)->tuple[str,str,str]:
    """拆data"""
    num=""
    unit=""
    for i,ch in enumerate(text):
        if not(ch.isdigit() or ch=="."):
            num=text[:i]
            unit=text[i:]
            break
    else:
        num=text
        unit=""
    if "." in num:
        int_part,dec_part=num.split(".",1)
        dec_part="."+dec_part
    else:
        int_part=num
        dec_part=""
    return int_part,dec_part,unit

def paint(user: User,save_path):
    ###前置信息处理
    rating=user.getRating()["rating"]#用户rating
    voltage=getVoltageLevel(int(rating))#用户电压等级
    voltage_color=VOLTAGE_COLORS[voltage]#用户电压颜色
    robtimes_ranks,robbedtimes_ranks,rob_gain_data_ranks,rob_give_data_ranks=user.getRobInfo()#抢劫次数[成功，失败]，被抢次数[成功，失败]，抢到的Data[主动抢到，被送的]，失去的Data[被抢走，主动送出]
    rob_times=robtimes_ranks.get(user.id,[0,0])
    robbed_times=robbedtimes_ranks.get(user.id,[0,0])
    robtimes=rob_times[0]+rob_times[1]#抢劫次数
    robbedtimes=robbed_times[0]+robbed_times[1]#被抢劫次数
    rob_most=["",0]
    for rob_user in user.robbed:
        times=user.robbed[rob_user]["success_times"]+user.robbed[rob_user]["fail_times"]
        if times>rob_most[1]:
            rob_most=[rob_user,times]#你最喜欢抢谁
    robbed_most=["",0]
    for record in checkin_storage.get_rob_records_by_target(user.id):
        times=record["success_times"]+record["fail_times"]
        if times>robbed_most[1]:
            robbed_most=[record["user_id"],times]#最喜欢抢你的人
    total_check=user.total_check#总签到天数
    consecutive_check=user.consecutive_check#连续签到天数
    max_consecutive_check=user.max_consecutive_check#最大连续签到天数
    total_data=Data([0,0],True)#所有人data总和
    for data in checkin_storage.get_all_user_data():
        total_data=plus(total_data,Data([data["base"],data["addition"]],data["zero"]))
    self_data=user.data#自己的data
    now = datetime.datetime.now(ZoneInfo("Asia/Shanghai"))
    days = calendar.monthrange(now.year, now.month)[1]#本月天数
    month_checkinfo=[]#这个月的签到信息
    for day in range(1, days + 1):
        increase_data=Data([0,0],True)#增长的data
        decrease_data=Data([0,0],True)#减少的data
        date_str = f"{now.year}-{now.month:02d}-{day:02d}"
        logs=user.getLogsByDate(datetime.date(now.year, now.month, day))
        for log in logs:
            if log["operate"] in ["rob","checkin","send","gacha","makeup_checkin"]:
                tmp_data=Data([log["data"]["base"],log["data"]["addition"]],log["data"]["zero"])
                if log["type"]=="+":
                    increase_data=plus(increase_data,tmp_data)
                elif log["type"]=="-":
                    decrease_data=plus(decrease_data,tmp_data)
        check_info=user.getCheckInfo(datetime.date(now.year,now.month,day))
        month_checkinfo.append([date_str,increase_data,decrease_data,check_info])#日期，这天增加的data，这天减少的data，这天的签到信息（是否签到，签到时间，排名，是否为补签）

    first_weekday, days = calendar.monthrange(now.year, now.month)
    start_x, start_y = 60, 250
    col_space, row_space = 115, 160  
    cell_w = 100                     

    img = Image.new("RGBA", (900, 1440+160*((first_weekday+days)//7-4)), "#0F111A")
    draw = ImageDraw.Draw(img)

    #头像
    avatar_img=Image.open(DATA_PATH/"out"/f"avatar_{user.id}.jpg")
    avatar_size = 80 
    avatar_x = start_x
    avatar_y = 50
    
    #头像发光
    glow_size = avatar_size + 14
    glow_layer = Image.new("RGBA", (glow_size, glow_size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)
    glow_draw.ellipse((2, 2, glow_size-3, glow_size-3), outline=(255, 255, 255, 200), width=5)
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=3))
    img.paste(glow_layer, (avatar_x - 7, avatar_y - 7), mask=glow_layer)
    #圆角头像
    avatar_img = avatar_img.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
    mask = Image.new('L', (avatar_size, avatar_size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)
    
    img.paste(avatar_img, (avatar_x, avatar_y), mask=mask)
    
    #顶部信息
    text_x=avatar_x+avatar_size+30
    name_y=55
    meta_y=125

    nickname_text=getattr(user,"nickname","Mugen")
    voltage_text=f"[ {voltage} ]"
    voltage_style=VOLTAGE_STYLES.get(voltage,{"bold":False,"underline":False})

    voltage_w=draw_mc_voltage_text(
        img,draw,(text_x,name_y),voltage_text,voltage_color,name_font,
        bold=voltage_style["bold"],underline=voltage_style["underline"]
    )
    draw.text((text_x+voltage_w,name_y)," "+nickname_text,fill=(255,255,255,240),font=name_font,anchor="lt")

    rating_show=rating
    rating_text=f"RT {rating_show:.2f}"
    data_text=f"Data {self_data.display}"

    rt_label_color=(120,210,255,255)
    rt_shadow_color=(20,60,90,180)
    data_color=(50,255,180,255)
    data_shadow_color=(10,80,60,180)
    shadow_offset=3

    #RT
    draw.text((text_x+shadow_offset,meta_y+shadow_offset),rating_text,fill=rt_shadow_color,font=info_font,anchor="lt")
    draw.text((text_x,meta_y),rating_text,fill=rt_label_color,font=info_font,anchor="lt")

    #Data
    rt_w=draw.textlength(rating_text,font=info_font)
    data_x=text_x+rt_w+36
    draw.text((data_x+shadow_offset,meta_y+shadow_offset),data_text,fill=data_shadow_color,font=info_font,anchor="lt")
    draw.text((data_x,meta_y),data_text,fill=data_color,font=info_font,anchor="lt")

    #星期表头
    weeks_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    header_y = start_y - 45           
    week_text_color = (200, 235, 255, 220) 
    for c_idx, label in enumerate(weeks_labels):
        week_cx = start_x + c_idx * col_space + (cell_w // 2)
        draw.text((week_cx, header_y), label, fill=week_text_color, font=title_font, anchor="mm")

    line_y = header_y + 25
    line_start_x = start_x
    line_end_x = start_x + 6 * col_space + cell_w
    draw.line([(line_start_x, line_y), (line_end_x, line_y)], fill=(0, 180, 216, 80), width=2)

    #日历格子绘制
    for d in range(1, days + 1):
        grid_idx = first_weekday + (d - 1)
        r_idx = grid_idx // 7  
        c_idx = grid_idx % 7   
        target_x = start_x + c_idx * col_space
        target_y = start_y + r_idx * row_space
        day_info = month_checkinfo[d-1]
        cell_piece, pad = paint_cell([now.year,now.month,d], day_info, cell_w=cell_w, cell_h=140)
        img.paste(cell_piece, (target_x - pad, target_y - pad), mask=cell_piece)
    
    first_day = datetime.date(2024, 11, 6)
    ddays = (now.date() - first_day).days
    month_check_days = sum(1 for info in month_checkinfo if info[3][0])
    
    rob_gain0 = rob_gain_data_ranks[user.id][0] if user.id in rob_gain_data_ranks else Data([0,0], True)#0主动1被动
    rob_gain1 = rob_gain_data_ranks[user.id][1] if user.id in rob_gain_data_ranks else Data([0,0], True)
    rob_give0 = rob_give_data_ranks[user.id][0] if user.id in rob_give_data_ranks else Data([0,0], True)
    rob_give1 = rob_give_data_ranks[user.id][1] if user.id in rob_give_data_ranks else Data([0,0], True)

    #每行信息进度
    ratio_1 = total_check / ddays if ddays > 0 else 0.0
    ratio_2 = consecutive_check / max_consecutive_check if max_consecutive_check > 0 else 0.0
    ratio_3 = month_check_days / days if days > 0 else 0.0
    ratio_4 = self_data.getBytes() / total_data.getBytes() if total_data.getBytes() > 0 else 0.0
    ratio_5 = robtimes / (robtimes + robbedtimes) if (robtimes + robbedtimes) > 0 else 0.0
    gain_total_bytes = rob_gain0.getBytes() + rob_gain1.getBytes()
    ratio_6 = rob_gain0.getBytes() / gain_total_bytes if gain_total_bytes > 0 else 0.0
    loss_total_bytes = rob_give0.getBytes() + rob_give1.getBytes()
    ratio_7 = rob_give0.getBytes() / loss_total_bytes if loss_total_bytes > 0 else 0.0
    stats_dataset = [
        ("总签到天数", f"{total_check} ",f" {ddays} 天", ratio_1),
        ("当前/最大连续签到天数", f"{consecutive_check} ",f" {max_consecutive_check} 天", ratio_2),
        ("本月签到天数", f"{month_check_days} ",f" {days} 天", ratio_3),
        ("Data占比", f"",f" {round(self_data.getBytes()/total_data.getBytes()*100,2)} %", ratio_4),
        ("抢劫次数/被抢次数", f"{robtimes} ",f" {robbedtimes} 次", ratio_5),
        ("抢劫累计获得Data", f"{rob_gain0.display} ",f" {rob_gain1.display}", ratio_6),
        ("抢劫累计失去Data", f"{rob_give0.display} ",f" {rob_give1.display}", ratio_7)
    ]

    calendar_bottom_y = start_y + ((first_weekday + days - 1) // 7) * row_space + 140
    current_y = calendar_bottom_y + 45    
    block_gap = 75
    dx=0
    dy=0
    for l in stats_dataset:
        tmp_draw = ImageDraw.Draw(Image.new("RGBA", (1,1)))
        bbox = tmp_draw.textbbox((0, 0), l[0], font=subtitle_font)
        tmp = bbox[2] - bbox[0]
        if tmp>dx:
            dx=tmp
    dx+=20
    panel_width = 790-dx

    progress_colors = [#颜色表
        ((255, 190, 0, 255), (0, 180, 216, 32), (10, 26, 58, 255), (255, 225, 120, 255), (255, 100, 0, 100), (255, 160, 0, 180), (0, 0, 0, 0), (0, 0, 0, 0)),
        ((255, 190, 0, 255), (0, 180, 216, 32), (10, 26, 58, 255), (255, 225, 120, 255), (255, 100, 0, 100), (255, 160, 0, 180), (0, 0, 0, 0), (0, 0, 0, 0)),
        ((255, 190, 0, 255), (0, 180, 216, 32), (10, 26, 58, 255), (255, 225, 120, 255), (255, 100, 0, 100), (255, 160, 0, 180), (0, 0, 0, 0), (0, 0, 0, 0)),
        ((0, 180, 216, 255), (60, 80, 120, 32), (255, 255, 255, 255), (200, 235, 255, 255), (0, 120, 200, 100), (0, 200, 255, 180), (0, 0, 0, 0), (0, 0, 0, 0)),
        ((100, 50, 180, 255), (200, 150, 255, 255), (230, 200, 255, 255), (40, 15, 80, 255),
        (80, 20, 150, 100), (120, 60, 200, 180), (160, 100, 255, 100), (200, 130, 255, 180)),
        ((180, 60, 0, 255), (255, 160, 80, 255), (255, 200, 150, 255), (80, 20, 0, 255),
        (150, 30, 0, 100), (190, 70, 0, 180), (255, 110, 30, 100), (255, 150, 50, 180)),
        ((180, 60, 0, 255), (255, 160, 80, 255), (255, 200, 150, 255), (80, 20, 0, 255),
        (150, 30, 0, 100), (190, 70, 0, 180), (255, 110, 30, 100), (255, 150, 50, 180)),
    ]
    is_double = [False, False, False, False, True, True, True]#是否两段
    for idx, (label, text1, text2, current_ratio) in enumerate(stats_dataset):
        #左侧标题
        label_x = start_x
        label_y = current_y
        draw.text((label_x, label_y), label, fill=(200, 215, 230,192), font=subtitle_font, anchor="lt")
        current_y-=26
        #进度条
        cf, cb, ct1, ct2, g11, g12, g21, g22 = progress_colors[idx]
        bar_piece, bar_pad = paint_progress(
            ratio=current_ratio,
            text1=text1,
            text2=text2,
            color1=cf,
            color2=cb,
            text1_color=ct1,
            text2_color=ct2,
            glow_color11=g11,
            glow_color12=g12,
            glow_color21=g21,
            glow_color22=g22,
            width=panel_width,
            height=16,
            font=subtitle_font,
            double=is_double[idx]
        )
        img.paste(bar_piece, (start_x - bar_pad+dx, current_y + 26 - bar_pad+dy), mask=bar_piece)
        current_y += block_gap

    img.save(save_path)