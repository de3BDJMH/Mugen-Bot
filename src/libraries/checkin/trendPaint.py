import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from matplotlib.font_manager import FontProperties
import pathlib
import matplotlib.colors as mcolors
from zoneinfo import ZoneInfo

from .tools import User, Data, plus, substract


FONT_PATH=pathlib.Path(__file__).parent.parent.parent.parent/"data"/"checkin"/"font"/"RuiZiTaiKongPaoKuXiangSuJian-Shan-ChaoHei(REEJI-TaikoRunGB-Flash-Heavy)-2.ttf"
title_font=FontProperties(fname=FONT_PATH, size=21)


def diff_change_format(prev_exp,curr_exp):
    """
    计算两个指数对应的字节差值，返回带符号和单位的字符串。
    """
    prev_base=int(prev_exp//10)*10
    prev_add=prev_exp-prev_base
    curr_base=int(curr_exp//10)*10
    curr_add=curr_exp-curr_base
    prev_data=Data([prev_base, prev_add], zero=False)
    curr_data=Data([curr_base, curr_add], zero=False)
    #比较大小，决定符号
    if curr_data.getBytes()>=prev_data.getBytes():
        diff_data=substract(curr_data, prev_data)  #当前-之前
        sign="+"
    else:
        diff_data=substract(prev_data, curr_data)  #之前-当前
        sign="-"
    if diff_data.is_zero:
        return "0 B"
    return f"{sign}{diff_data.display}"


def paint(user: User,logs: list,save_path:str):
    """
    绘制用户数据量变化趋势图

    参数：
        user: User 对象，包含当前数据量等信息
        logs: 已筛选的日志列表
    """
    ###数据预处理与逆推
    logs=sorted(logs, key=lambda x: x["time"])
    data_tmp=user.data#计算用的临时data
    times=[]#时间点，初始逆序
    data_list=[]#data列表

    now=datetime.datetime.now()#初始时间点
    times.append(now)
    data_list.append(data_tmp.base+data_tmp.addition)
    #逆推data历史记录
    for log in reversed(logs):
        log_data=log["data"]
        change_data=Data([log_data["base"], log_data["addition"]], log_data["zero"])
        log_time=datetime.datetime.strptime(log["time"], "%Y-%m-%d %H:%M:%S")
        if log["type"]=="+":# 过去增加
            data_tmp=substract(data_tmp, change_data)
        elif log["type"]=="-":# 过去减少
            data_tmp=plus(data_tmp, change_data)
        if data_tmp.is_zero:# 防止负值
            data_tmp=Data([0, 0], True)
        times.append(log_time)
        data_list.append(data_tmp.base+data_tmp.addition)
    times=list(reversed(times))#翻转为正序
    data_list=list(reversed(data_list))

    ###图表绘制
    plt.rcParams["font.sans-serif"]=["SimHei", "Segoe UI", "Arial"]
    plt.rcParams["axes.unicode_minus"]=False

    fig, ax_trend=plt.subplots(figsize=(11, 6), dpi=130)
    fig.patch.set_facecolor("#0F111A")
    ax_trend.set_facecolor("#0F111A")

    ax_plot=ax_trend.twinx()

    UP_COLOR="#00E676"#增加减少柱状图的颜色
    DOWN_COLOR="#FF1744"

    ###计算变化量及动态阈值
    change_list=[0.0]
    colors=[UP_COLOR]
    for i in range(1, len(data_list)):
        diff=data_list[i]-data_list[i-1]
        change_list.append(diff)
        colors.append(UP_COLOR if diff>=0 else DOWN_COLOR)

    change_list=np.array(change_list)
    changes_abs=np.abs(change_list[change_list!=0])
    is_neg=np.any(change_list<0)

    if len(changes_abs)>0:
        height_base=np.percentile(changes_abs, 95)#将95%分位数作为基准，在图中体现就是这个值是一个1/3上限高度的柱，以此为基准对其他data绘制不同高度
        if height_base==0:
            height_base=np.max(changes_abs)
    else:
        height_base=1.0

    ###变化柱状图高度计算
    y_min, y_max=min(data_list), max(data_list)
    y_range=y_max-y_min if y_max!=y_min else 1.0

    if is_neg:
        ax_left_bottom=y_min-y_range*0.35
        ax_left_top=y_max+y_range*0.1
        ax_trend.set_ylim(ax_left_bottom, ax_left_top)

        plot_ymax=height_base*2.5
        plot_ymin=-plot_ymax*(y_range*0.35)/(y_max+y_range*0.1-y_min)
        ax_plot.set_ylim(plot_ymin, plot_ymax)
    else:
        ax_left_bottom=y_min-y_range*0.08
        ax_left_top=y_max+y_range*0.1
        ax_trend.set_ylim(ax_left_bottom, ax_left_top)

        plot_ymax=height_base*2.5
        plot_ymin=-plot_ymax*0.08
        ax_plot.set_ylim(plot_ymin, plot_ymax)

    ###绘制趋势曲线
    point_num=len(times)
    COLOR_START="#A855F7"#趋势曲线和水平线的渐变色
    COLOR_END="#00B4D8"

    path_colors=[]
    for i in range(point_num):
        mix=i/(point_num-1) if point_num>1 else 1.0
        c_start=mcolors.to_rgb(COLOR_START)
        c_end=mcolors.to_rgb(COLOR_END)
        c_mixed=[s+(e-s)*mix for s, e in zip(c_start, c_end)]
        path_colors.append(mcolors.to_hex(c_mixed))

    #趋势曲线纵向渐变，瀑布样子的，很好看
    GRADIENT_LEVELS=65#渐变层数
    START_ALPHA=0.022#渐变初始值

    for j in range(GRADIENT_LEVELS):
        progress_y=j/GRADIENT_LEVELS
        alpha_level=START_ALPHA*(1.0-progress_y)
        y_shade_bottom=np.array(data_list)-(np.array(data_list)-y_min)*(progress_y*0.5)   # 原 y_shading_bottom
        y_shade_bottom=np.maximum(y_shade_bottom, y_min)

        ax_trend.fill_between(
            times,
            data_list,
            y_shade_bottom,
            step="post",
            color=path_colors[int(point_num*0.6)] if point_num>0 else COLOR_END,
            alpha=alpha_level,
            zorder=1
        )

    #趋势曲线横向渐变，蓝紫色渐变
    for i in range(point_num-1):
        segment_times=times[i:i+2]
        segment_data=data_list[i:i+2]
        ax_trend.plot(
            segment_times, segment_data,
            color=path_colors[i],
            linewidth=2.5,
            drawstyle="steps-post",
            zorder=3
        )

    ###绘制增减柱状图
    plot_cut=np.clip(change_list, plot_ymin*0.98, plot_ymax*0.98)

    bars=ax_plot.bar(
        times, plot_cut,
        width=datetime.timedelta(hours=2.5),
        color=colors,
        edgecolor="none",
        alpha=0.48,
        zorder=2
    )

    ###标注超界data
    TOPN=max(3,len(change_list)//20)#高度前几的data需要标注
    changed_log=[idx for idx, val in enumerate(change_list) if idx>0 and val!=0]

    if len(changed_log)>0:
        changed_log=sorted(changed_log, key=lambda idx: change_list[idx])
        top_min_change=set(changed_log[:TOPN])
        top_max_change=set(changed_log[-TOPN:])
    else:
        top_min_change=set()
        top_max_change=set()

    time_span:datetime.timedelta=max(times)-min(times)
    COLLISION_TIME=time_span*0.06#防撞时间间隔，总时长的百分比
    last_pos_time=None
    pos_overlap_level=0
    last_neg_time=None
    neg_overlap_level=0

    for i in range(1, len(change_list)):
        val=change_list[i]
        t_pos=times[i]

        is_overflow_pos=val>plot_ymax*0.95
        is_top_max=(i in top_max_change and val>0)
        if is_overflow_pos or is_top_max:
            if last_pos_time is not None and (t_pos-last_pos_time)<COLLISION_TIME:
                pos_overlap_level=(pos_overlap_level+1)%3
            else:
                pos_overlap_level=0

            if is_overflow_pos:
                text_y=plot_ymax*(0.92-pos_overlap_level*0.12)
            else:
                text_y=val*1.03
            data_text=diff_change_format(data_list[i-1], data_list[i])+" ↗"
            ax_plot.text(
                t_pos, text_y, data_text,
                color=UP_COLOR, fontsize=8, ha='center', va='bottom',
                fontweight='bold', bbox=dict(facecolor='#0F111A', edgecolor='none', alpha=0.5, pad=1)
            )
            last_pos_time=t_pos
        elif val<plot_ymin*0.95 or (i in top_min_change and val<0):
            is_overflow_neg=val<plot_ymin*0.95
            if last_neg_time is not None and (t_pos-last_neg_time)<COLLISION_TIME:
                neg_overlap_level=(neg_overlap_level+1)%3
            else:
                neg_overlap_level=0

            if is_overflow_neg:
                text_y=plot_ymin*(0.92-neg_overlap_level*0.12)
            else:
                text_y=val*1.03
            data_text=diff_change_format(data_list[i-1], data_list[i])+" ↘"
            ax_plot.text(
                t_pos, text_y, data_text,
                color=DOWN_COLOR, fontsize=8, ha='center', va='top',
                fontweight='bold', bbox=dict(facecolor='#0F111A', edgecolor='none', alpha=0.5, pad=1)
            )
            last_neg_time=t_pos

    ###水平线绘制
    GRADIENT_LEVELS_HORIZON=5#水平线渐变层数
    HORIZON_ALPHA_START=0.02#水平线渐变初始值
    plot_y_span=plot_ymax-plot_ymin if plot_ymax!=plot_ymin else 1.0

    for i in range(point_num-1):
        segment_times=times[i:i+2]
        segment_y=[0, 0]
        for j in range(GRADIENT_LEVELS_HORIZON):
            progress_h=j/GRADIENT_LEVELS_HORIZON
            alpha_h=HORIZON_ALPHA_START*(1.0-progress_h)
            glow_height=-plot_y_span*0.015*(1.0-progress_h)
            y_glow_bottom=[glow_height, glow_height]
            ax_plot.fill_between(
                segment_times,
                segment_y,
                y_glow_bottom,
                step="post",
                color=path_colors[i],
                alpha=alpha_h,
                zorder=1
            )
        ax_plot.plot(
            segment_times, segment_y,
            color=path_colors[i],
            linewidth=1,
            alpha=0.4,
            linestyle="-",
            zorder=2
        )

    ###杂项
    for spine in ax_trend.spines.values():
        spine.set_visible(False)
    for spine in ax_plot.spines.values():
        spine.set_visible(False)

    #y隐藏低于下限的刻度，上面绘制柱状会扩充下限
    def y_format(x, pos):
        if x<(y_min-1e-5):
            return ""
        base=int(x//10)*10
        addition=x-base
        # 浮点误差微调
        if addition<0 and addition>-1e-9:
            addition=0.0
        if addition>10-1e-9:
            base+=10
            addition=0.0
        data_obj=Data([base, addition], zero=False)
        return data_obj.display

    ax_trend.yaxis.set_major_formatter(plt.FuncFormatter(y_format))

    #时间轴，保留了两个方案
    TIME_AXIS_MODE='AUTO'
    total_hours=time_span.total_seconds()/3600

    if TIME_AXIS_MODE=='RELATIVE':
        def time_format(x, pos):
            dt=mdates.num2date(x).replace(tzinfo=None)
            now_t=times[-1]
            delta_seconds=(now_t-dt).total_seconds()
            if delta_seconds<60:
                return "Now"
            elif delta_seconds<3600:
                return f"-{int(delta_seconds/60)} min"
            else:
                return f"-{delta_seconds/3600:.1f} h"
        ax_trend.xaxis.set_major_formatter(plt.FuncFormatter(time_format))
    else:
        if total_hours<=24:
            ax_trend.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        else:
            ax_trend.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))

    ax_trend.tick_params(axis='x', colors='#5A6178', labelsize=9, rotation=0, pad=15, length=0)
    ax_trend.tick_params(axis='y', colors='#5A6178', labelsize=9, length=4, color='#24293E')
    ax_trend.grid(False)
    ax_plot.set_yticks([])
    ax_plot.set_ylabel("")

    #标题
    ax_trend.set_title(f"Data变化趋势 ({user.nickname})", fontproperties=title_font, pad=24, color="#6C43B9", fontweight="bold", loc="left")
    sub_title_font = FontProperties(fname=FONT_PATH, size=10) #小标题
    ax_trend.text(
        0, 0.99, # 相对位置：左上角 (0,0 是左下)
        f"记录条数: {len(logs)}\n时间范围: {min(times).strftime('%Y-%m-%d %H:%M:%S')} ~ {max(times).strftime('%Y-%m-%d %H:%M:%S')}", 
        transform=ax_trend.transAxes, 
        fontproperties=sub_title_font, 
        color="#888888" # 灰色区分主标题
    )

    plt.tight_layout()
    plt.subplots_adjust(top=0.85)
    #plt.show()
    plt.savefig(save_path)