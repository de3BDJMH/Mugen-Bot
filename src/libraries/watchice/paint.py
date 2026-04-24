import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.patheffects as path_effects
import numpy as np

plt.rcParams['font.family'] = 'SimHei'
plt.rcParams['axes.unicode_minus'] = False

def distibution(dc:dict,alias,path:str):
    # 1. 按值从大到小排序
    sorted_pairs = sorted(dc.items(), key=lambda item: item[1], reverse=True)
    sorted_labels = [item[0] for item in sorted_pairs]
    sorted_values = [item[1] for item in sorted_pairs]

    # 计算总数值和每个扇形的占比
    total = sum(sorted_values)
    percentages = [(v / total) * 100 for v in sorted_values]
    for p in range(len(sorted_values)):
        if percentages[p]<1:
            break
    sorted_labels=sorted_labels[:p]+[""]
    sorted_values=sorted_values[:p]+[sum(sorted_values[p:])]
    percentages=percentages[:p]+[sum(percentages[p:])]

    # 2. 突出效果：所有扇形向外突出0.05
    explode = [0.025] * (len(sorted_values)-1)+[0.075]

    # 3. 美观配色：使用tab20c色图
    colors = cm.tab20c(np.linspace(0, 1, len(sorted_values)))

    # 4. 创建图形并绘制环形图
    fig, ax = plt.subplots(figsize=(16, 10))

    wedges, texts, autotexts = ax.pie(
        sorted_values,
        labels=None,  # 先不添加标签，后面手动添加
        colors=colors,
        explode=explode,
        startangle=90,
        wedgeprops={
            'width': 0.5,  # 环宽 - 可调整此值改变厚度 (0-1之间)
            'edgecolor': 'none',  # 无边框
            'linewidth': 0,
            'antialiased': True
        },
        autopct='%1.1f%%',  # 显示百分比
        pctdistance=0.70,   # 百分比文字位置 (0.7=靠近圆心)
        textprops={'color': 'white', 'fontsize': 10, 'fontweight': 'bold'}
    )

    # 5. 添加ID标签（带圆角矩形底板）
    tmp=0
    for i, (wedge, label, value, percent) in enumerate(zip(wedges, sorted_labels, sorted_values, percentages)):
        # 过滤条件：只显示数量>=5的ID
        if value >= 5 and percent >= 1.0:
            # 计算标签位置（在扇形中间）
            angle = (wedge.theta1 + wedge.theta2) / 2
            angle_rad = np.deg2rad(angle)
            
            # 标签半径位置（可调整此值改变标签离圆心的距离）
            label_radius = wedge.r - (wedge.width / 2) * (0.4-(0 if percent>=2.5 else 0.05*tmp))
            if percent<2.5:
                tmp+=1
            
            x = label_radius * np.cos(angle_rad)
            y = label_radius * np.sin(angle_rad)
            
            # 智能调整文本对齐方式
            if -45 <= angle <= 45 or angle >= 135 or angle <= -135:
                ha = 'center'
            elif 45 < angle < 135:
                ha = 'left'
            else:
                ha = 'right'
                
            if -45 <= angle <= 45:
                va = 'bottom'
            elif 45 < angle < 135 or -135 <= angle <= -45:
                va = 'center'
            else:
                va = 'top'
            
            # 添加带圆角矩形底板的文本（无边框）
            ax.text(
                x, y, 
                label,
                fontsize=15,
                fontweight='bold',
                color='black',
                ha=ha,
                va=va,
                bbox=dict(
                    boxstyle="round,pad=0.3",
                    facecolor=(1, 1, 1, 0.85),  # 白色半透明底板
                    edgecolor='none',  # 无边框
                    linewidth=0
                )
            )

    # 6. 智能调整百分比文字（确保在浅色背景上清晰）
    for i, (autotext, percent, color) in enumerate(zip(autotexts, percentages, colors)):
        # 过滤条件：只显示占比>=1%的百分比
        if percent < 1.0:
            autotext.set_text('')
            continue
        
        # 计算颜色亮度
        brightness = (0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2])
        
        # 浅色背景用深色文字+白色描边，深色背景用白色文字+黑色描边
        if brightness > 0.6:  # 浅色扇形
            autotext.set_color('#111111')  # 深灰色
            autotext.set_path_effects([
                path_effects.withStroke(
                    linewidth=2.5, 
                    foreground='white'
                )
            ])
        else:  # 深色扇形
            autotext.set_color('white')
            autotext.set_path_effects([
                path_effects.withStroke(
                    linewidth=2, 
                    foreground='black'
                )
            ])
        
        autotext.set_fontsize(11)
        autotext.set_fontweight('bold')
        autotext.set_bbox(None)  # 确保百分比无底板

    # 7. 添加图例（显示所有项目）
    fewm=""
    for m in alias:
        if not m in sorted_labels:
            fewm+=f"{m}: {"、".join(alias[m][1:4])}\n"
    legend_labels = [f"{label}({value}): {"、".join(alias[label][1:4]) if label in alias else f"图片占比小于1%:\n{fewm[:-1]}"}" 
                    for label, value, percent in zip(sorted_labels, sorted_values, percentages)]
    ax.legend(
        wedges,
        legend_labels,
        title="ID(数量): 别名",
        loc="center left",
        bbox_to_anchor=(1.05, 0.5),
        fontsize=9,
        frameon=True,
        fancybox=True,
        shadow=True,
        framealpha=0.9
    )

    # 8. 添加标题和修饰
    ax.set_title('看群友图片分布图', fontsize=40, fontweight='bold', pad=50)
    ax.axis('equal')
    ax.axis('off')

    plt.tight_layout()
    plt.savefig(path)