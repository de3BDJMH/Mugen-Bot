import pathlib
from PIL import Image,ImageDraw,ImageFilter,ImageFont

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

VOLTAGE_LEVELS=[
    ("Steam",0),
    ("ULV",3),
    ("LV",5),
    ("MV",7),
    ("HV",9),
    ("EV",11),
    ("IV",13),
    ("LuV",15),
    ("ZPM",17),
    ("UV",19),
    ("UHV",21),
    ("UEV",23),
    ("UIV",25),
    ("UMV",27),
    ("UXV",29),
    ("MAX",31)
]

FONT_PATH=pathlib.Path(__file__).parent.parent.parent.parent/"data"/"checkin"/"font"/"Minecraft.ttf"
name_font=ImageFont.truetype(str(FONT_PATH),size=60)
info_font=ImageFont.truetype(str(FONT_PATH),size=24)

def mix_color(color,target,ratio):
    return tuple(int(color[i]*(1-ratio)+target[i]*ratio) for i in range(3))+(color[3],)

def draw_mc_voltage_text(img,draw,pos,text,color,font,bold=False,underline=False):
    x,y=pos
    light=mix_color(color,(255,255,255),0.3)
    dark=mix_color(color,(0,0,0),0.6)

    text_mask=Image.new("L",img.size,0)
    mask_draw=ImageDraw.Draw(text_mask)
    mask_draw.text((x,y),text,font=font,fill=120,anchor="lt",stroke_width=1,stroke_fill=120)
    if bold:
        mask_draw.text((x+2,y),text,font=font,fill=120,anchor="lt",stroke_width=1,stroke_fill=120)
    glow_mask=text_mask.filter(ImageFilter.GaussianBlur(6))
    glow=Image.new("RGBA",img.size,(color[0],color[1],color[2],0))
    glow.putalpha(glow_mask.point(lambda p:int(p*0.45)))
    img.alpha_composite(glow)

    draw.text((x+4,y+4),text,fill=dark,font=font,anchor="lt")
    if bold:
        draw.text((x+6,y+4),text,fill=dark,font=font,anchor="lt")

    draw.text((x-1,y-1),text,fill=light,font=font,anchor="lt")
    if bold:
        draw.text((x+1,y-1),text,fill=light,font=font,anchor="lt")

    draw.text((x,y),text,fill=color,font=font,anchor="lt",stroke_width=1,stroke_fill=dark)
    if bold:
        draw.text((x+2,y),text,fill=color,font=font,anchor="lt",stroke_width=1,stroke_fill=dark)

    bbox=draw.textbbox((x,y),text,font=font,anchor="lt",stroke_width=1)
    text_w=bbox[2]-bbox[0]
    text_h=bbox[3]-bbox[1]
    if bold:
        text_w+=2

    if underline:
        uy=y+text_h+2
        uh=4
        underline_img=Image.new("RGBA",img.size,(0,0,0,0))
        ud=ImageDraw.Draw(underline_img)
        ud.rectangle([x,uy,x+text_w,uy+uh],fill=color)
        underline_blur=underline_img.filter(ImageFilter.GaussianBlur(3))
        img.alpha_composite(underline_blur)
        draw.rounded_rectangle([x,uy,x+text_w,uy+uh],radius=1,fill=color)
        draw.rounded_rectangle([x,uy+1,x+text_w,uy+uh+1],radius=1,outline=dark,width=1)

    return text_w

def paint():
    width=960
    row_height=96
    margin=40
    height=margin*2+row_height*len(VOLTAGE_LEVELS)

    img=Image.new("RGBA",(width,height),"#0F111A")
    draw=ImageDraw.Draw(img)

    for i,(voltage,rating) in enumerate(VOLTAGE_LEVELS):
        y=margin+i*row_height
        color=VOLTAGE_COLORS[voltage]
        style=VOLTAGE_STYLES[voltage]

        draw.rounded_rectangle(
            [30,y,930,y+78],
            radius=10,
            fill=(20,23,35,255),
            outline=(70,75,90,100),
            width=2
        )

        voltage_text=f"[ {voltage} ]"
        nickname_text="  TEST"
        x=55

        voltage_w=draw_mc_voltage_text(
            img,draw,(x,y+8),voltage_text,color,name_font,
            bold=style["bold"],underline=style["underline"]
        )
        draw.text((x+voltage_w,y+8),nickname_text,fill=(255,255,255,240),font=name_font,anchor="lt")

        info=f"RT {rating}"
        info_w=draw.textlength(info,font=info_font)
        draw.text((900-info_w,y+28),info,fill=(130,140,160,255),font=info_font,anchor="lt")

    save_path=pathlib.Path(__file__).parent/"voltage_test.png"
    img.save(save_path)
    print(f"已生成: {save_path}")

if __name__=="__main__":
    paint()