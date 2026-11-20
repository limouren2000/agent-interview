# 上海AI Lab AI4S方向 Agent开发凉经

> 上海AI Lab · Agent开发（AI4S方向） · 凉经 · 发帖 2026-10-13 · 作者 比比拉波 · 来源：[小红书](https://www.xiaohongshu.com/explore/6acd1bbf000000000b0073da)

## 速览

- **重点**：题目从电商客服 Agent 基模、DeepSeek API、Harness/Cordis，问到 Agent 框架（LangGraph、AutoGen）、项目图节点与条件边、多 Agent 分发、意图识别与 Embedding、LangGraph checkpoint 续跑，以及 Skill、Harness、vibe coding。第 10–15 题（意图识别）作者写明先不写答案。岗位是 Agent 开发（AI4S 方向），按岗位归入 agent/。
- **难度**：上海 AI Lab Agent 开发凉经。结果按标题写凉经；文末面试官称「只有他这一面过了就可以入职」，与凉经并存，不另推测最终录取结果。轮次和面试日期未注明。正文与主页均未写招聘类型，文末「明天还要面试一个 skill 实习的岗位」不据此标注本场。发帖日按笔记 ID 为 10 月 13 日 01:41（Asia/Shanghai），页面显示 10-13。封面图为标题卡，长图中的架构图和流程图按转写整理成文字，原文错字与「吸性能」保持原样。评论区无作者补充。
- **题量**：23 问，其中第 10–15 题作者暂未写答案。

## 面经正文

上海AI Lab AI4S方向 Agent开发凉经
全文4691字 | 阅读需15分钟

1、Q:电商客服系统中用的Agent基模是什么？

2、Q:既然用了DeepSeek的Api，那么具体用的是哪个版本的Api？有什么区别吗？

项目中用的是DeepSeek V4.1 Flash模型的Api，和DeekSeek-V4-pro的区别是，flash更快更高效且支持对图像的理解，pro则吸性能更高，能处理更复杂任务但不支持图像。

模型名称（model 参数） | 对应的模型版本 | 核心定位
deepseek-flash | DeepSeek-V4.1-Flash | 高速、低成本，支持图像理解，适合对响应速度和成本敏感的场景
deepseek-v4-pro | DeepSeek-V4-Pro-0813 | 高性能，不支持图像理解，适合需要最强推理能力的复杂任务

但是与DeepSeek对话可得，用户访问 deepseek-v4-pro 的请求将全部路由到 V4.1 Flash，并按 V4.1 Flash 单价计费。所以，实际上如果用DeepSeek的api的话，是只有一个flash版本可以选择。

3、Q:讲一讲DeepSeek Harness(架构深度解析)?

DeepSeek和其他产品的区别：

DeepSeek 是一个类似于Claude Code、Codex的产品，本身就是一个可以使用的agent，而不是可以被其他Agent调用的底层harness库。

区别:DSH不像Codex这股产品本身足够完整，更强调开源、模块化和可重新组合，类似于vsc的插件思想。

整体框架图:

（架构图，作者标注：「就这些都是没有画出来的都是光这一块」，黄框圈出 Main Agent Loop / Child Agent Loop）
图题：试真题深度解析
Boot-time: Profiles + Bundles + Patches → Plugin Composition (startup only)
外框：Cordis Runtime / Shared Context
Global plugin runtime that coordinates all Services, Typed Events, Scopes, Effects and Lifecycle. Not a step in the request flow.
左侧 Gateway / Entry Adapters：Web (HTTP / WebSocket)、ACP (JSON-RPC / stdio)、SDK (JSON-RPC / NDJSON)、CLI (argv / stdio)
中心黄框 Main Agent Loop：1. Inbox → 2. Prompt Assembly → 3. LLM → 4. Tool Call (I/T) → 5. Tools（含 Subagent Tool）→ 6. Tool Result → 7. LLM → Final Response；旁有 Child Agent Loop (Subagent)
右侧 Plugin loading & DI：Service Registry, Typed Events / Waterfall, Scopes & Context, Effects & Lifecycle, Dynamic load / unload / recompose
右侧 Output Adapters：WebSocket (session / event)、ACP (event / update)、SDK (session-event)、stdout (final output)
右侧人物：User / Client (Human / App)
底部 Session Event Log：ctx.sessions，Events, Append-only Log, Durable Store, user message, assistant message, tool result, step / turn events, lifecycle events

一切即插件:Cordis是什么？

Cordis是一个插件运行框架，并不专门为DSH编写的Agent框架，它负责插件加载、服务注册、依赖解析、作用域隔离、生命周期管理和资源清理(感觉面试时倒是不用答这么细致)，并配合HMR(HMR 是 Hot Module Replacement（热模块替换）的缩写。它是一种开发时技术，允许你在不重启整个应用的情况下，动态替换、添加或删除正在运行的模块，同时尽可能保留应用状态)实现运行时更新。

所以DSH的做法是把自己的各项Agent能力按照Cordis插件规范实现，然后交给Cordis统一组织。

DeepSeek的核心理念:

第一个是 Everything is a Plugin（一切皆插件）。DSH 不是在一个固定 Agent 核心外面增加少量工具，而是把模型适配器、工具系统、文件与进程能力、Session、存储、权限、Sandbox、子Agent、Agent Loop，甚至 Web UI 都放进 Cordis 插件体系。Profile 和 cordis.patch.yml 决定当前系统加载哪些插件，Cordis 则使用 Loader、Registry、Context、Fiber 和 Effect 管理插件的加载、依赖、作用域、运行状态与资源清理。这样，同一套运行底座可以按场景组装出 Web、Headless 或其他 Agent 形态，具体能力也可以独立增加、禁用或替换。

第二个是 append-only Session Event Log。DSH 将用户消息、模型输出、工具调用、工具结果和其他运行事实记录为只能追加的类型化事件，不原地修改已经发生的历史。这份日志不是额外保存的审计副本，而是会话的唯一事实来源；LLM 消息历史、Trajectory、恢复、Fork 和 Replay 都由同一事件流派生。DSH 还要求“模型可见即已记录”，即进入模型请求并影响决策的内容必须能够从日志重建。

这两个理念解决的是不同问题：Cordis 插件化让系统组件能够被组合和演进，append-only 日志让组件不断变化时，会话历史仍然保持一致、可追踪和可重建。结合起来看，DSH 更像一套开放的 Agent Runtime，而不只是一个固定工作流的 Agent 产品。

这些东西真的能背出来吗？。。。。。。

4、Q:现在DeepSeek推出的最新的模型是什么？

就是DeepSeek V4-1 Flash，面试时答不知道，结果就是这个，可能单纯想问我了不了解、追不追踪新技术。

5、Q:除了langchain、langgraph，你还了解哪些Agent开发框架？没答上来，面试官问我聊不了解AutoGen，说只知道名字，没有具体了解，pass了

AutoGen 是微软研究院在 2023 年末开源的一个多智能体协作框架，它开创性地将“群聊式对话”作为智能体协作的核心机制。尽管目前 AutoGen 已进入维护模式，其官方继任者是 Microsoft Agent Framework (MAF)。

AutoGen 的核心思想是，让多个各司其职的 AI 智能体通过自由的多轮对话来协同完成复杂任务，而不是依赖单条冗长的 Prompt 链。

* 协作范式：每个智能体（Agent）拥有独立的身份、系统提示词和工具集。它们通过消息传递来交换信息、协商分工、互相审查，形成一个类似人类团队的协作流程，最终共同达成目标。

* 涌现行为：这种设计的一个显著特点是，智能体常常会以开发者未曾预料到的方式自主分工和解决问题，展现出强大的灵活性和适应性。

AutoGen 提供了多种预设的智能体类型和群聊模式，以支持不同的协作场景。

核心智能体类型：

* AssistantAgent：核心的“大脑”，负责接收消息、调用大模型进行规划与生成。

* UserProxyAgent：代表用户，可配置为自动执行代码，或在关键节点请求人工确认。

* CodeExecutorAgent：专门负责代码执行的智能体，与生成代码的 Agent 分离，以提升安全性。

主要群聊模式：

* 轮询模式 (RoundRobinGroupChat)：智能体按固定顺序依次发言，行为可预测，适合结构化的多角色意见收集。

* 选择器模式 (SelectorGroupChat)：由一个 LLM 动态决定下一位发言者，更灵活，模拟“谁擅长谁上”的团队协作。

6、Q:LangGraph里有哪些核心组件？

LangGraph 将 Agent 工作流建模为图，其行为由三个关键组件定义：

①状态（State）：一个共享的数据结构，代表应用的当前快照。它贯穿整个图的执行过程，是所有节点都能访问的“全局内存”。状态通常使用 TypedDict、Pydantic 模型或 dataclass 来定义其模式（Schema）。

②节点（Nodes）：执行具体逻辑的函数。它们接收当前状态作为输入，执行计算或产生副作用（如调用 LLM、执行工具），然后返回一个更新后的状态。节点可以是任何 Python 函数，其内部可以包含 LLM 调用，也可以只是普通代码。

③边（Edges）：定义节点之间的执行顺序。边可以是固定转换（始终从节点 A 到节点 B），也可以是条件分支，根据当前状态动态决定下一个要执行的节点。

一个简化的关系是：节点负责工作，边负责决定下一步去哪。

7、Q:你的Agent图中有几个节点？

（流程图）
START
→ preprocess 问题预处理与意图识别
→ supervisor 生成 Agent 任务计划
→ check_information 检查信息和工具权限
　- 信息不足 → clarify 向用户追问 →（回到 check_information）
　- 信息完整 → execute_tasks 执行多种子 Agent
　　- 普通任务完成 → synthesis
　　- 生成待确认售后草稿 → await_confirmation 等待用户确认或取消
　　- 用户确认或取消 → synthesis 汇总结果并回复
→ END

当前项目的生产主图有 7 个业务节点，加上 START 和 END，共 9 个节点。

8、Q:LangGraph使用哪个Api能创建一个节点、一个条件边？(直接瞎编了，语法真的会问，我无语了)创建条件边需要写什么参数？创建节点用 StateGraph. add_node()，创建条件边用 StateGraph. add_conditional_edges()。

builder.add_node("节点名称", 节点执行函数)
builder.add_conditional_edges(
source="起始节点名称", path=路由函数, path_map={"分支值": "目标节点名称"}, )

参数 | 是否必填 | 含义
source | 必填 | 从哪个节点出发，在该节点执行完成后判断
path | 必填 | 路由函数，通常接收 state，返回分支值
path_map | 可选 | 把路由函数返回的分支值映射到目标节点

必须填起始节点，和路由函数，如果路由函数返回值为目标节点，就不用填 path_map参数。

9、Q:本项目中有多少个条件边，多Agent链路是按照什么样子的顺序去执行的？

当前生产主图有 2 组条件边，也就是调用了两次 add_conditional_edges()；展开后是 4 条条件分支

条件边起点 | 判断条件 | 下一节点
check_information | 信息不足，需要追问 | clarify
check_information | 信息完整 | execute_tasks
execute_tasks | 有待用户确认的售后草稿 | await_confirmation
execute_tasks | 无需用户确认 | synthesis

领域 Agent 的任务子图只有 START → execute_agent → END，没有注册条件边。其中模型与工具的循环由函数内的 while、if 控制。

进入 execute_tasks 后，子 Agent 的顺序由任务计划决定，没有固定的“商品 → 订单 → 售后 → 知识库”顺序：

* 单个任务：直接执行对应 Agent，再汇总。

* 多个任务且都没有依赖：使用 asyncio.gather() 并行执行，全部返回后汇总。例如商品查询与政策检索。

* 存在依赖：先执行依赖已满足的任务，再执行后续任务。例如计划中先有订单任务、后有售后任务时，售后会依赖订单结果。

（子 Agent 流程图）
execute_tasks 按任务计划分发
→ product_agent 商品 Agent
→ order_agent 订单 Agent
→ after_sales_agent 售后 Agent
→ knowledge_agent 知识库 Agent
→ general_agent 通用 Agent
→ AgentTaskResult 各任务的结构化结果
→ synthesis_agent 在主图 synthesis 节点汇总

10、Q:用户说:帮我查一下订单，顺便帮我看一下耳机怎么发货。这种跨Agent职能在项目中是怎么处理的？

11、Q:在问题10中我回答是意图识别然后经过supervisor去做，面试官问我意图识别怎么做，我说通过bge向量化再检索，面试官说DeepSeek-V4-Flash已经很好的识别用户的意图了，为什么还要通过Embedding？

12、Q:用户如果是多重query，那么Embedding能正确识别到吗？如果能，那是怎么识别到的？

13、Q:如果一句话和A意图，B意图匹配相关，但是A意图和B意图相悖，怎么处理？

14、Q:用户说了一句话，你怎么让他直接匹配到三个意图的？

15、Q:在Embedding时，意图如果很多，且都超过了阈值，这个时候该怎么办？

通过这5个问题，我感觉意图识别部分需要重做优化，这5个问题先不写答案，先暂时沉淀。

16、Q:LangGraph的checkpoint存在哪里，存了这个checkpoint，怎么让agent去续跑？

项目使用 LangGraph 的 SQLite Checkpointer，默认存放在 backend/data/checkpoints.db。构建 Graph 时把 Checkpointer 传给 compile，并用会话 ID 作为稳定的 thread_id。工作流执行到 interrupt() 时，LangGraph 会持久化当前 State 和执行位置并结束本次调用。用户确认后，后端使用相同的 thread_id 调用 graph.ainvoke(Command(resume=decision), config)，LangGraph 从 SQLite 加载最新 Checkpoint，把 decision 作为 interrupt() 的返回值，然后继续执行后续节点。Checkpoint 负责恢复工作流状态，业务会话和最终业务操作仍由业务数据库管理。

17、Q:这个项目给我带来最有价值的地方在哪？

让我学会多Agent编排、RAG全流程和评测。

18、面试官对我RAG电商客服的评价

19、对各种agent: Open Claw、Codex、豆包、Claude Code的理解:

面试官意味让我对这些架构差异都有一定了解，本菜逼当然是不了解，只从功能特点上去区分。

对我提出建议让我看一些Agent的论文综述，详细去看Agent各个组成部分。

20、平时你vibe coding时主要用什么？用Codex装了什么Skill？

21、Skill是什么？具体概念和组成？

我个人确实没有实际用过Skill，只答了Skill渐进式加载和基本概念。

22、渐进式加载是什么意思？

直接胡言乱语，根本不懂。其实之前不懂应该是问过gpt，但是忘记了，

23、Harness的具体思考和了解？

这个也是问过gpt，但是没有记完全，答得也不好

今天先这样吧，明天还要面试一个skill实习的岗位，上课时先针对今天的面经梳理skill相关所有核心概念，然后再补一下意图识别和数据库。

总体面试体验不错，面试官人很好，这个他说只有他这一面过了就可以入职，感兴趣的朋友可以直接去面试，看小红书还在招。

沉淀沉淀沉淀沉淀沉淀沉淀沉淀沉淀沉淀沉淀沉淀沉淀沉淀沉淀沉淀沉淀沉淀沉淀沉淀沉淀沉淀沉淀沉淀沉淀沉淀沉淀沉淀沉淀沉淀沉淀沉淀沉淀沉淀沉淀沉淀沉淀沉淀沉淀

---

收录于 2026-11-20 · 题目按原文顺序整理，版权归原作者所有，如有侵权请提 Issue 删除。
