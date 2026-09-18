## 通用接口

### database.py

负责日志数据库本身：
- 初始化
- 数据库连接
- 事务/原子性
- 统一管理log.db

### message.py

专门处理消息有关内容：
- messages表
- 消息写入
- 消息查询

#### 字段说明

id 内部自增ID
message_id onebot消息ID
self_id 处理消息的bot的ID(QQ号)
type 群聊(group)/私聊(private)
group_id 如果来自群聊这里会记录群号，私聊为NULL
sender_id 发送者QQ号
time 发送时间
message_json 原始消息，json格式
plain_text 解析后纯文本消息

### event.py

专门记录事件：
- events表
- event_key
- 事件写入和查询

### command.py

专门记录指令：
- commands表
- command_key
- 指令写入和查询