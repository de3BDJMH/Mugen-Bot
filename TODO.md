# TODO

## 高优先级

### 签到事务一致性
- [ ] 新增 `perform_checkin()`，将一次签到放入同一个 SQLite transaction
- [ ] 签到记录插入成功后再发放奖励
- [ ] 用户 Data、签到次数、日志、物品奖励必须一起提交或一起回滚
- [ ] 处理并发重复签到问题

当前问题：
- `update_user()`、`add_checkin()`、`add_log()` 等分别建立连接并 `commit`
- `INSERT OR IGNORE` 只能阻止重复签到记录，不能阻止奖励逻辑重复执行

## 优化
- [x] 日历查询改为单次 SQL
- [x] logs 增加 `(user_id,created_at)` 索引
- [x] 数据库初始化和版本迁移
- [x] 迁移脚本防重复执行
- [x] 修复抽奖首个物品无法抽中的旧问题
- [ ] 补签到/抢劫自动化测试