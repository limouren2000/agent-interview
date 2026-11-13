# 27 届秋招 | SHEIN Java 岗一面面经

> SHEIN · Java工程师（广州）-2027届 · 秋招一面 · 面试时间 2026-09-17 · 发帖 2026-09-17 · 作者 轩辕永熙 · 来源：[小红书](https://www.xiaohongshu.com/explore/6aaba3af0000000012035cbe)

## 速览

- **重点**：HTTP 与 session/cookie、GET 能否带请求体、OSI 与 TCP/UDP 握手挥手；IOC 容器及不用 IOC 改用手写单例的追问；阅读 Claude Code 生成代码并指出问题；事务隔离级别、脏读幻读不可重复读、MySQL 8 默认隔离级别；单个接口 502（OpenResty）的排查思路。
- **难度**：SHEIN Java 工程师秋招一面，约 30 分钟。结果未注明。作者称回答时较紧张。
- **题量**：14 问加反问，另有一段代码阅读。

## 面经正文

先说下时间线：煮啵是9.7投递，9.8收到笔试，9.9完成笔试，9.14收到面试，9.17一面，投递的岗位名称是：Java工程师（广州）-2027届

面经如下 (30 min)：
先进行自我介绍
1、平时古法编程多一点还是 AICoding 多一点？
2、从 HTTP 协议跟报文的角度上，讲一下 session 和 cookie 的关系是什么？（一开始没听清楚，直接开始说它们的区别，要讲的是关联或者关系）
3、辩论一个问题，你认为 Get 请求可以带请求体吗？如果可以，你觉得可以的依据是什么？
4、HTTP 协议在 OSI 七层模型中的哪一层？
5、OSI 七层模型讲一下
6、TCP 和 UDP 在哪一层
7、口述一下 TCP 的三次握手和四次挥手
8、讲一下对 IOC 容器的理解
9、为什么需要用到 IOC 容器呢？用一种钻牛角尖的问法，不使用 IOC 容器，我写一大堆单例，好像也可以达到一样的效果，那为什么还是需要用到 IOC 容器？
10、代码理解：给一个 Claude Code 生成的代码截图(图 2)，把代码中你能够识别到的问题都说一下

```java
public class OrderService {

    private SimpleDateFormat sdf = new SimpleDateFormat("yyyy-MM-dd");

    @Transactional
    public void createOrder(Order order) {
        order.setCreateDate(sdf.format(new Date()));
        orderMapper.insert(order);
        sendCouponIfNeeded(order);          // 可能抛业务异常
        updateStock(order.getProductId(), order.getCount());
    }

    public List<Order> queryOrders(String userId, String status) {
        String sql = "SELECT * FROM orders WHERE user_id = '"
                + userId + "' AND status = '" + status + "'";
        return jdbcTemplate.query(sql, rowMapper);
    }

    public double calcDiscount(double price, double discount) {
        return price * discount;
    }

    public void processAsync(Order order) {
        new Thread(() -> orderMapper.update(order)).start();
    }
}
```

11、大概讲一下事务的隔离级别
12、脏读、幻读、不可重复读，这三个的区别是什么？
13、MySQL 8 的默认隔离级别是什么？
14、场景题：我们在去部署一个站点的时候肯定不会说起了一个 Server 直接把它暴露出去，正常来讲我们肯定是分布式部署、或者说挂一下负载均衡之类的，那么它肯定是多层的，现在生产环境有一个接口，在调用这个接口的时候出现了502，（只有这么一个接口报 502，其他接口都正常），这个502是 OpenResty 的默认报错页面，现在就只有这么个信息，如果是你的话你的排查思路会是什么？

反问环节：
1、 部门主要是做什么业务的？
2、 如何看待未来在 AI 的冲击下程序员的出路？

个人总结：
复盘下来感觉答的不是很好，主要还是太紧张了脑子有点短路空白了，希望幸运的话能给我过一面吧…

---

收录于 2026-11-13 · 题目按原文顺序整理，版权归原作者所有，如有侵权请提 Issue 删除。
