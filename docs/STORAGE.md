# Mugen-Bot 存储结构

用于快速查询各模块数据库、表名和字段名。

---

# Checkin

数据库：

```text
data/checkin/data/checkin.db
```

代码：

```text
src/storage/checkin.py
```

## users

用户基础信息、签到状态和 Data。

| 字段 | 说明 |
|---|---|
| `user_id` | 用户 QQ，主键 |
| `nickname` | 昵称 |
| `last_checkin` | 最后签到日期 |
| `total` | 总签到次数 |
| `consecutive` | 当前连续签到 |
| `max_consecutive` | 最大连续签到 |
| `data_base` | Data base |
| `data_addition` | Data addition |
| `data_zero` | Data 是否为 0 |
| `rob_rate` | 抢劫成功率 |
| `last_rob` | 最后抢劫时间 |

主键：

```text
user_id
```

---

## user_items

用户拥有的签到物品。

| 字段 | 说明 |
|---|---|
| `user_id` | 用户 QQ |
| `item_id` | 物品 ID |
| `item_name` | 物品名称 |
| `count` | 数量 |

主键：

```text
(user_id, item_id)
```

---

## rob_records

用户之间的抢劫统计。

| 字段 |
|---|
| `user_id` |
| `target_user_id` |
| `success_times` |
| `fail_times` |
| `success_data_base` |
| `success_data_addition` |
| `success_data_zero` |
| `fail_data_base` |
| `fail_data_addition` |
| `fail_data_zero` |

主键：

```text
(user_id, target_user_id)
```

---

## checkin_time

签到时间记录。

| 字段 | 说明 |
|---|---|
| `user_id` | 用户 QQ |
| `checkin_date` | 签到日期 |
| `checkin_at` | 签到时间 |

主键：

```text
(user_id, checkin_date)
```

---

## logs

统一操作日志。

| 字段 | 说明 |
|---|---|
| `id` | 日志 ID |
| `user_id` | 用户 QQ |
| `operation` | 操作类型 |
| `change_type` | `+` / `-` 等变化 |
| `related_user_id` | 相关用户 |
| `data_base` | Data 变化 |
| `data_addition` | Data 变化 |
| `data_zero` | Data zero |
| `item_id` | 物品 ID |
| `item_count` | 物品数量变化 |
| `detail` | 附加信息字符串 |
| `created_at` | 创建时间 |

常见 `operation`：

```text
checkin
rob
gacha    # Watchice 抽卡消费
```

`detail` 是通用日志字段。

Watchice 抽卡可以将 `request_id` 写入 `detail` 方便查账，但抽卡业务约束仍由 Watchice 自己负责。

---

# Watchice

数据库：

```text
data/watchice/database/watchice.db
```

数据目录：

```text
data/watchice/
```

代码：

```text
src/storage/watchice.py
```

---

## members

群友基础信息。

| 字段 | 说明 |
|---|---|
| `slug` | 群友唯一标识，主键 |
| `visibility` | 群友权限 |
| `enabled` | 是否启用 |

`visibility`：

```text
public
authenticated
allowlist
```

---

## member_aliases

群友别名。

| 字段 | 说明 |
|---|---|
| `member_slug` | 群友 slug |
| `alias` | 别名 |

主键：

```text
(member_slug, alias)
```

约束：

```text
alias UNIQUE
```

---

## images

图片核心索引。

| 字段 | 说明 |
|---|---|
| `image_id` | 全局图片 ID |
| `member_slug` | 所属群友 |
| `legacy_id` | 旧版局部图片 ID |
| `relative_path` | 图片相对路径 |
| `mime_type` | MIME |
| `width` | 宽度 |
| `height` | 高度 |
| `file_size` | 文件大小 |
| `sha256` | 文件 SHA-256 |
| `is_animated` | 是否动图 |
| `uploaded_at` | 上传时间 |
| `uploader_qq` | 上传者 QQ |
| `visibility` | 单图权限 |
| `status` | 图片状态 |

主键：

```text
image_id
```

唯一：

```text
(member_slug, legacy_id)
```

`visibility`：

```text
inherit
authenticated
allowlist
```

`status`：

```text
active
deleted
```

### 抽卡计划新增

| 字段 | 说明 |
|---|---|
| `collectible` | 是否可以抽到 |
| `rarity` | 卡片稀有度 |
| `draw_weight` | 单图抽取权重 |

`rarity` 第一版：

```text
normal
rare
```

---

## member_allowed_users

member 权限白名单。

| 字段 |
|---|
| `member_slug` |
| `user_qq` |

主键：

```text
(member_slug, user_qq)
```

---

## image_allowed_users

单图权限白名单。

| 字段 |
|---|
| `image_id` |
| `user_qq` |

主键：

```text
(image_id, user_qq)
```

---

## ratings

图片评分。

| 字段 |
|---|
| `image_id` |
| `user_id` |
| `score` |
| `created_at` |
| `updated_at` |

主键：

```text
(image_id, user_id)
```

---

## comments

图片评论。

| 字段 |
|---|
| `id` |
| `image_id` |
| `user_id` |
| `content` |
| `created_at` |
| `status` |

主键：

```text
id
```

`status`：

```text
visible
deleted
```

---

# Watchice 抽卡（计划）

以下结构尚未全部实现。

## user_cards

用户当前拥有的卡。

| 字段 | 说明 |
|---|---|
| `user_qq` | 用户 QQ |
| `image_id` | 图片 ID |
| `owned_count` | 拥有数量 |
| `first_obtained_at` | 第一次获得时间 |
| `last_obtained_at` | 最近获得时间 |

主键：

```text
(user_qq, image_id)
```

---

## gacha_draws

一次抽卡请求。

| 字段 | 说明 |
|---|---|
| `draw_id` | 抽卡 ID |
| `user_qq` | 用户 QQ |
| `request_id` | 幂等请求 ID |
| `count` | 抽卡数量 |
| `created_at` | 抽卡时间 |

主键：

```text
draw_id
```

唯一：

```text
(user_qq, request_id)
```

---

## gacha_draw_items

一次抽卡中具体获得的卡。

| 字段 | 说明 |
|---|---|
| `draw_id` | 对应 `gacha_draws.draw_id` |
| `position` | 本次抽卡顺序 |
| `image_id` | 图片 ID |
| `rarity` | 抽到时的稀有度 |

主键：

```text
(draw_id, position)
```

---

## gacha_config

抽卡配置。

计划字段：

| 字段 |
|---|
| `enabled` |
| `single_cost` |
| `ten_cost` |
| `normal_rate` |
| `rare_rate` |

---

# 跨模块关系

```text
Checkin
└── users
    └── Data

Checkin
└── logs
    └── 记录 gacha 消耗

Watchice
├── images
├── user_cards
├── gacha_draws
└── gacha_draw_items
```

职责：

```text
Checkin  → Data 与 Data 日志
Watchice → 抽卡、卡片、抽卡幂等和抽卡历史
```

`checkin.db` 与 `watchice.db` 为两个独立 SQLite 数据库。

涉及两边同时修改的数据操作，需要特别考虑跨数据库事务。