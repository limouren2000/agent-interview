# tiktok test agent开发实习面经

> TikTok · test agent开发 · 实习一面 · 过 · 面试 2026-10-01 · 发帖 2026-10-01 · 作者 Rui · 来源：[小红书](https://www.xiaohongshu.com/explore/6abe4046000000000a022ce8)

## 速览

- **重点**：七段结构完整，问基本情况、实习经历（含 RPC 和 AI Coding）、AI Agent / RAG、并发与 Redis/MySQL、测试与系统设计，以及两道 Coding。岗位按原文写 test agent 开发，归入 agent/，不写成测开或 SDET，也不因同作者后来的测开二面改判这一面。
- **难度**：TikTok test agent 开发实习一面。标题和正文均写实习，招聘类型标实习，不标秋招。结果写过：10 月 7 日通知过。面试日期为 10 月 1 日。发帖日按笔记 ID 为 10 月 1 日 19:13（Asia/Shanghai），页面显示编辑于 10-07，文件名按发帖日，不改正文日期。
- **题量**：七段，含两道手撕和反问。

## 面经正文

tiktok test agent开发实习面经
10.1一面 10.7通知过
1. 基本情况

* 自我介绍
* 硕士专业和课程方向
* 实习时间：Part-time / Full-time
* 为什么选择继续读 Master
* 未来工作地点和职业规划

2. 实习经历

* 简单介绍实习期间负责的项目
* 项目中使用了哪些技术
* RPC 的调用流程是什么？
* RPC 和 HTTP 分别适合什么场景？
* 为什么内部服务更倾向使用 RPC？
* 内部 RPC 是否还需要考虑鉴权和通信安全？
* AI Coding 是否提高了开发效率？
* AI 生成大量代码后，如何进行 Code Review？

3. AI / Agent

* 介绍一个做过的 AI Agent / RAG 项目
* 整体 Workflow 是什么？
* 为什么不直接使用大模型，而是结合 OCR / VLM？
* RAG 知识库是怎么构建的？
* 如何进行召回和排序？
* Context Window 不够怎么办？
* 如果自己设计 Agent，如何设计长期记忆和短期记忆？

4. 基础知识

* Concurrent Programming 是什么？
* Concurrency 和 Parallelism 有什么区别？
* Redis 和 MySQL 分别适合什么场景？
* Redis 为什么快？

5. 测试 / 系统设计

* 举一个使用抖音/TikTok 时遇到的 Bug
* IM 私信消息应该按 User 维度还是 Conversation 维度存储？
* 两种方案在读写方面分别有什么优缺点？
* 群聊场景下为什么 User 维度存储会产生写放大？

6. Coding

LeetCode 3：无重复字符的最长子串

* 滑动窗口 + HashMap
* 时间复杂度 O(n)

LeetCode 179：最大数

* 自定义排序
* 比较 a+b 和 b+a
* 按能够组成更大数字的顺序排列

7. 反问

* 团队主要负责什么业务？
* 测试 Agent 目前主要应用在哪些场景？
* Agent 是特定业务使用还是通用方案？
* 实习工作地点和 Full-time 时间要求？

---

收录于 2026-11-20 · 题目按原文顺序整理，版权归原作者所有，如有侵权请提 Issue 删除。
