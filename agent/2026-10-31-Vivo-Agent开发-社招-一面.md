# Vivo agent开发一面简单记记

> Vivo · Agent开发 · 社招一面 · 发帖 2026-10-31 · 作者 生气 · 来源：[小红书](https://www.xiaohongshu.com/explore/6ae5d9130000000006023ff5)

## 速览

- **重点**：规划模型选择，Plan-and-Execute 加 ReAct 的 multi-agent，100+ 工具和可观测指标，以及 RAG 的并集、线性加权和 RRF。
- **难度**：社招一面。
- **题量**：正文编号至第 7 问，后补测评、上线指标和 RAG 融合说明。

## 面经正文

1、模型选择,规划用什么模型
2、clawcode+openclaw
3、模型内部采用那种模式?
Plan-and-Execute（顶层 Supervisor） + ReAct（每个子 Agent 内部）
4、有多少工具,为什么要用multi-agent的架构
5、为什么要采用multi-agent架构,为什么?
6、评估怎么评估的,关注哪些指标
可观测性构建:
应该关注指标:平均步数、最大执行时间、工具调用次数、工具调用结果接口时延、接口相应、token消耗
7、工具有多少?
100+

对于开放性、多维度的复杂问题，单个 Agent 由于 context 限制和顺序推理的天性，无法做到"广度优先"的全面探索。Multi-Agent 系统让每个子 Agent 独立探索一个子问题，最终合并结果，可以达到单 Agent 无法企及的研究深度和广度。

测评和评估是怎么做的?
最终上线后,指标是怎么评估的?有没有其他因素影响

RAG相关:
RAG算法、召回策略、reranker

● 简单并集：两路结果取并集后排序
● 线性加权：Score = α × BM25分 + (1-α) × Dense分
● RRF（Reciprocal Rank Fusion）：Score = 1/(k+rank1) + 1/(k+rank2)，无需调权重，业界主流

---

收录于 2026-11-12 · 题目按原文顺序整理，版权归原作者所有，如有侵权请提 Issue 删除。
