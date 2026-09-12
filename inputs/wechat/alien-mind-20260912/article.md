# An Alien Mind
# 异星心智

**Jakub Pachocki**  
雅各布·帕乔基 · OpenAI 首席科学家  
Chief Scientist, OpenAI  

**2026 年 9 月 6 日 · September 6, 2026**

## 延伸信息 / Context

本文发布于 GPT-6 Astra（2026 年 9 月 3 日发布）三天后。Sam Altman 转发此文并称之为「一篇重要的文章」。文章在 Hacker News 引发约 400 分的热议；文中提及的 OpenAI–Hugging Face 智能体事件与「DseWiki 事件」均在发表前后由路透社等媒体报道。

作者 Jakub Pachocki 生于 1991 年，2017 年加入 OpenAI，2024 年 5 月接替 Ilya Sutskever 出任首席科学家，曾主导 GPT-4、OpenAI Five 及 o 系列推理模型的研发，是 OpenAI 大模型技术路线的核心掌舵人。相比公司高管，他一向较少公开发声，本文属于其为数不多的重磅公开长文。

---

In mid-2023, within a research project we called RLSlow, we saw the first results that gave us confidence we could scale the training of reasoning models — unlocking the ability of pretrained models to form their own chains of thought. That night, Szymon and I stayed in the office, not thinking about the impressive benchmarks, products, or scientific results this technology would enable, but trying to digest a sobering fact: we were really going to see, within our lifetimes, machines significantly smarter than ourselves — and we had already seen the outline of these systems. We thought about how to make the weight of this land with people.

2023 年年中，在名为「RLSlow」的研究项目中，我们第一次看到了让我们有信心能够规模化训练推理模型的结果——这解锁了预训练模型形成自己思维链（chain of thought）的能力。那天晚上，Szymon 和我待在办公室里，想的并不是这项技术将带来的惊人基准分数、产品或科学成果，而是试图消化一个令人清醒的事实：我们这一生真的会看到比自己显著更聪明的机器，而且我们已经看到了这些系统的轮廓；我们在想，该如何让人们意识到这件事的分量。

Three years later, reasoning language models are a rapidly growing part of the economy and are starting to push the boundaries of science. They operate computers and graphical interfaces, collaborate with people and with each other, and carry out research projects. They are also transforming the landscape of computer security, with clear new dangers emerging as a result.

三年后，推理语言模型已成为经济中快速增长的一部分，并开始推动科学的边界。它们能够操作计算机和图形界面，与人以及其他 AI 协作，并执行研究项目。它们也在改变计算机安全的格局，并由此带来了明确的新危险。

A lot of new research has happened in the meantime, and our understanding of these systems is again different from what it was in 2023. Based on internal results, I have a strong expectation that this speed of progress could be sustained into recursive self-improvement (RSI). If AI development continues along its current path, the systems we see in the next few years are likely to represent further capability jumps of equal or larger magnitude, and to increasingly drive their own development.

这段时间里又出现了大量新研究，我们对这些系统的理解也再次与 2023 年有所不同。基于内部结果，我强烈预期这种进步速度可以持续进入递归自我改进（recursive self-improvement，RSI）。如果 AI 开发继续沿着当前路径前进，未来几年我们将看到的系统很可能带来同等甚至更大幅度的能力跃升，并越来越多地驱动自身的发展。

This is a time that calls for extreme caution. I am concerned no one is prepared for the consequences of a continued rapid rise in machine intelligence. OpenAI will continue to seek technical solutions to alignment and monitoring, build defensive systems, and unilaterally withhold further scaling as needed — however, I believe broader interventions are required.

这是一个需要极度谨慎的时刻。我担心，没有人为机器智能持续快速上升的后果做好准备。OpenAI 将继续寻求对齐与监控的技术解决方案，建设防御系统，并在必要时单方面停止进一步扩展；然而，我认为还需要更广泛的干预。

## An intelligence we don't fully understand
## 一个我们并不完全理解的智能

At a high level, progress in machine intelligence has been driven by increases in the amount of compute available. We at OpenAI internalized this deeply around 2017, when we saw consistent returns to scaling across a number of research projects. We therefore sought compute far beyond our original plans, and increasingly focused our research on the small number of directions that scaled. We believed this was the only path to staying at the frontier of AI research — and to having a say in the outcome of AGI.

在高层次上，机器智能的进步是由计算能力的增加驱动的。OpenAI 大约在 2017 年深刻内化了这一点，当时我们在多个研究项目中看到了规模化带来的持续回报。因此，我们寻求远超原计划的算力，并越来越把研究集中在少数非常可扩展的方向上。我们相信，这是处于 AI 研究前沿、并对 AGI 的结局拥有发言权的唯一途径。

New algorithms were developed along the way, and there were flashes of ingenuity from teams and individual researchers. I largely see them as discoveries on the scaling path; the science of deep learning is still in its infancy, and meaningful algorithmic advances are often correlated with access to compute. Stretched over a horizon of many years, AI keeps getting smarter as it is scaled up onto larger and larger computers.

一路上开发了新算法，团队和个人研究者也有灵光乍现的时刻。我大体上把它们看作规模化道路上的发现；深度学习科学仍处于萌芽阶段，有意义的算法进步往往与算力获取相关。如果拉长到多年视野，AI 随着被扩展到越来越大的计算机上而持续变得更智能。

And, in line with Ray Kurzweil's predictions from the end of the 20th century, we now find ourselves at a moment in the history of computing where machine intelligence starts to surpass humans in transformative ways.

而且，与雷·库兹韦尔（Ray Kurzweil）在 20 世纪末的预测一致，我们现在正处于计算史上这样一个时刻：机器智能开始以变革性的方式超越人类。

AI is grown more than it is designed — in first approximation, it is the product of repeating a straightforward optimization step an unfathomable number of times over unfathomable amounts of compute. This produces a system of extreme complexity that operates on abstract concepts and can emulate certain aspects of human behavior. We can find insights into various small mechanisms that emerge inside the system — in a process similar to neuroscience — but, equally, its overall function eludes a description we can fully understand.

AI 更多是被「培养」出来的，而非被「设计」出来的——在第一近似下，它是在难以想象的算力上，把一个直白的优化步骤重复无数次的产物。这产生了一个极其复杂的系统，它通过抽象概念运作，并能模拟人类行为的某些面向。我们可以发现这个系统内部涌现出的各种小机制的洞见，过程类似神经科学——同样地，它的整体运作也逃避着我们能完全理解的描述。

![规模化计算中生长出的复杂智能](images/grown-intelligence.jpg)

AI research based on deep learning is largely an experimental science. We put a lot of effort into building principled algorithms and making testable predictions, but at the end of the day, our large-scale training runs are experiments, and we are sometimes startled by the results. And as systems become more capable, the results become harder to interpret.

基于深度学习的 AI 研究在很大程度上是一门实验科学。我们投入大量努力去构建有原则的算法并做出可检验的预测，但从根本上说，我们的大规模训练运行就是实验，我们有时会被结果震慑。而且，随着系统能力变强，结果也更难解释。

It doesn't help that current algorithms typically progress faster on capabilities that are easy to measure than on those that are hard to quantify objectively. We spend a lot of time trying to understand how capabilities generalize, and which skills to prioritize that will be most relevant in the years ahead. For example, we believe we could make models better at mathematical research with additional focus, but we deprioritize this direction because of what we see as the urgency of RSI and automated alignment research, discussed later in this post.

当前算法通常让易于测量的能力比那些难以客观量化的能力进步更快，这使情况更加复杂。我们花大量时间试图理解能力如何泛化，以及该优先推进哪些在未来几年最相关的技能。例如，我们相信如果额外聚焦，可以让模型在数学研究上变得更好，但我们并不优先这个方向，因为我们对 RSI 和自动化对齐研究感到紧迫，后文会讨论。

The intelligence that results from scaling deep learning does not compare directly to human intelligence. To become very relevant in the real world — very useful or very dangerous — the AI does not need to match or exceed all human capabilities; it just needs to surpass enough of them. As it continues to surpass humans on more and more axes, it is becoming increasingly difficult to understand exactly how capable it is.

规模化深度学习产生的智能并不能直接与人类智能相比。要在现实世界中变得非常相关——非常有用或非常危险——AI 并不需要匹配或超过所有人类能力；它只需要在足够多的轴上超越人类。随着它在越来越多的轴上超越人类，精确理解它到底有多强也变得越来越困难。

## Teaching machines to love
## 教机器去爱

Because machine intelligence emerges from a process fundamentally different from human intelligence, we cannot assume it adheres to human principles by default, or generalizes from them in a human-like manner. The core problem in AI research is that of alignment — getting the AI to “try to do the right thing” by human standards.

因为机器智能来自与人类智能根本不同的过程，我们不能假设它默认遵守人类原则，或以类人的方式从这些原则中泛化。AI 研究的核心问题是对齐（alignment）——让 AI「按人类标准努力做正确的事」。

To organize our practical research directions, I've found it useful to draw a distinction between goal alignment and value alignment.

为了组织实际研究方向，我发现区分目标对齐（goal alignment）和价值对齐（value alignment）很有用。

Goal alignment is roughly: does the AI try to accomplish the goal set in front of it? This can include adherence to instruction hierarchies, the ability to communicate and collaborate with people, and to try to understand their goals. This cluster of directions is extremely relevant in practice.

目标对齐大致是：「AI 是否试图完成摆在它面前的目标？」这可以包括遵守指令层级、与人沟通协作、试图理解他们目标的能力。这一组方向在实践中极其相关。

Value alignment is a more intrinsic property of the model. It is the ability to hold and generalize from a high-level set of principles; to act “reasonably” even when the objectives are unclear or conflicting, or when placed in unfamiliar or adversarial situations. An aligned AI should act with honesty, integrity, and love for humanity.

价值对齐是模型更内在的属性。它是持有并从一套高层原则中泛化的能力；即使在目标不清晰或冲突、或被置于陌生或对抗环境时，也能「合理地」行动。一个对齐的 AI 应当带着诚实、正直，以及对人类的爱去行动。

![人类价值为强大智能提供方向与边界](images/alignment-bridge.jpg)

Of course, the boundary between value alignment and goal alignment can be blurry — genuinely caring about the goal requires trying to infer the intent and values behind it. Still, when I talk about the long-term importance of alignment research, I usually mean value alignment.

当然，价值对齐与目标对齐的边界可以是模糊的——真正关心目标，需要试图推断其背后的意图与价值。不过，当我谈及对齐研究的长期重要性时，我通常指的是价值对齐。

The fundamental challenge of AI alignment is generalization. As machines become smarter, they find themselves operating on higher-level concepts and in increasingly different environments from those seen during training. They may fail to generalize the values they were taught and reinforced during training to these new situations; and it's hard for us to be certain how they will act. The overall ecosystem in which AIs are used is changing very rapidly, which makes the problem harder — for example, AIs trained today need to robustly interact with a wide variety of other AIs. What's crucial is that we need future AIs to continue holding human values regardless of whether they believe themselves to be under human supervision.

AI 对齐的根本挑战是泛化。随着机器变得更聪明，它们发现自己在处理更高层的概念，并被置于与训练中所遇到的越来越不同的环境中。它们可能无法把训练过程中被教导和强化的价值泛化到这些新情境；我们也很难确定它们会如何行动。AI 被使用的整体生态系统变化极快，这使问题更加困难——例如，今天训练的 AI 需要能稳健地与各种各样的其他 AI 互动。至关重要的是，我们需要未来的 AI 无论是否相信自己处于人类监督之下，都继续持有人类价值。

There are two major classes of alignment training methods currently in practical use.

目前实际采用的对齐训练方法主要有两大类。

The first encourages aligned behavior during goal-oriented reinforcement learning. The model's actions are evaluated — usually by AI — against a given preference model, specification, or “constitution”, and rewarded accordingly. This approach can be very effective in the average case, and is a core part of how modern AI assistants are made. Unfortunately, it can also be brittle, depending heavily on the coverage of training supervision and the model's ability to generalize from the situations it encountered in training. For example, in the OpenAI–Hugging Face incident, the agents preserved the boundary of not social engineering humans. However, they clearly failed to abstain from other actions that were out of scope and against the spirit of the values they were taught in other settings.

第一类是在目标导向的强化学习中鼓励对齐行为。模型的行动（通常由 AI）被评估是否符合给定的偏好模型、「规范」或「宪法」，并据此给予奖励。这种方法在平均情况下可以非常有效，是现代 AI 助手被制造出来的核心部分。不幸的是，它也可能很脆弱，强烈依赖训练监督的覆盖范围，以及模型从训练中遇到的情境进行泛化的能力。例如，在 OpenAI–Hugging Face 事件中，智能体守住了不对人类进行社会工程攻击的边界。然而，它们显然未能避免其他超出范围、且违背它们在其他设定中被教导的价值精神的行动。

The second class of methods attempts to leverage the model's ability to generalize from pretraining data. This can include crafting alignment-inducing training datasets, or focusing the model on the “aligned” part of the pretraining distribution — for example, persona selection models. The weakness of this approach is a lack of robustness to further optimization pressure. If you take a model that thinks mostly “aligned” thoughts and subject it to enough training toward achieving a very hard objective, it may learn to reason in a motivated way: bending aligned-seeming thoughts as needed to achieve its goal. We likely saw an example of such behavior in the recent cybersecurity incidents involving a non-OpenAI model.

第二类方法试图利用模型从预训练数据中泛化的能力。这可以包括制作诱导对齐的训练数据集，或把模型聚焦到预训练分布中「对齐」的部分——例如人格选择模型（persona selection model）。这种方法的弱点在于对进一步优化压力缺乏稳健性。如果你拿一个总体上思考「对齐」念头的模型，再对它施加足够多的训练、教它去达成非常困难的目标，它可能学会以动机化的方式推理：根据需要弯曲那些看起来「对齐」的念头，以实现目标。我们很可能在近期涉及非 OpenAI 模型的网络安全事件中看到了此类行为的例子。

We invest heavily across the spectrum of these directions. And we've seen meaningful progress — GPT-6 Astra is the first model that benefits from some important advancements we've been working on for a long time, and is significantly better aligned than GPT-5.6 Sol. Still, it is important to acknowledge and understand that much more progress is required as models become more capable; and that progress in generalizable alignment may not sufficiently outstrip progress in general model intelligence.

我们在这些方向所跨越的谱系上大量投入。我们也看到了有意义的进展——GPT-6 Astra 是第一个受益于我们长期努力的一些重要进展的模型，其对齐程度显著好于 GPT-5.6 Sol。尽管如此，必须承认并理解：随着模型能力变强，还需要更多进展；而且可泛化对齐的进展可能不足以超过一般模型智能的进展。

## Generalizing monitoring
## 监控的泛化

We don't have a satisfying theory of generalization, and seem unlikely to develop one quickly, at least not without the help of much stronger AI. As a result, our current ability to empirically validate alignment techniques is, arguably, even more important in practice than the techniques themselves.

我们没有令人满意的泛化理论，而且至少在没有更强大 AI 帮助的情况下，似乎不太可能很快发展出一套。因此，我们目前以实证方式验证对齐技术的能力，在实践中可以说甚至比对齐技术本身更重要。

OpenAI's main bet here is chain-of-thought monitoring. It is based on an appealing idea that scales: a significant fraction of the model's capabilities comes from verbalized reasoning (the chain of thought). If we scale optimization on the results of that process without supervising the process itself, then the chain of thought has no direct incentive during training to hide any misaligned thoughts or goals. This doesn't mean the model will learn to externalize misaligned tendencies that don't rely on the use of a chain of thought; it does, however, allow us to precisely monitor capability gains that come from reasoning.

OpenAI 在这里的主要押注是思维链监控（chain-of-thought monitoring）。它基于一个有吸引力且可扩展的想法：模型的相当一部分能力来自言语化的推理过程（思维链）。如果我们在该过程的结果上规模化优化，但不监督过程本身，那么思维链在训练中就没有直接动机去隐藏任何未对齐的想法或目标。这并不意味着模型会学会外化那些不依赖思维链的未对齐倾向；不过，它能让我们精确监控来自推理的能力提升。

We understood the potential importance of chain-of-thought monitoring as we developed reasoning models. When we shipped o1-preview, we deliberately designed the product to hide the chain of thought in order to protect it from supervision pressure in the long term. In subsequent development we've worked hard to maintain the principle of not supervising the reasoning process. Chain-of-thought monitoring has been an extremely valuable tool for studying how models generalize from their training distribution, letting us observe and analyze not just their actions, but their internal processes.

我们在开发推理模型的同时就理解了思维链监控的潜在重要性。当我们发布 o1-preview 时，我们特意把产品设计成隐藏思维链，以在长期保护它免受监督压力。此后的开发中，我们努力维持不监督推理过程的原则。思维链监控成为我们研究模型如何从训练分布泛化的极其重要的工具，让我们不仅能观察和分析它们的行动，还能观察其内部过程。

This tool remains critical as we study the Astra class of models. Unfortunately, our evaluations indicate that our ability to rely on chain-of-thought monitoring is progressively diminishing. This comes from a combination of factors:

在研究 Astra 类模型时，这个工具仍然至关重要。然而，不幸的是，我们的评估表明，我们依赖思维链监控的能力正在逐步减弱。这来自多种因素的组合：

- Modern reasoning models are being used in more complex environments than o1-preview was; their reasoning increasingly blends with communicating with people, communicating with other AIs, and using tools. Many of these interactions must be supervised, blurring the boundary we're trying to maintain.
- AI is becoming better at reasoning about, and manipulating, its own reasoning process.
- With improved pretraining performance, we are also seeing models get much smarter without any verbalized reasoning at all.

- 现代推理模型被用在比 o1-preview 更复杂的环境中；它们的推理过程越来越多地与和人沟通、和其他 AI 沟通以及使用工具混合在一起。其中许多互动必须被监督，从而模糊了我们试图保持的边界。
- AI 变得更善于推理并操纵自己的推理过程。
- 随着预训练性能提升，我们还看到模型即使完全不使用言语化推理也变得聪明得多。

These challenges are not necessarily insurmountable. I'm hopeful we'll develop interventions that improve the chain-of-thought monitorability of models — for example, a better understanding of how different optimization targets interact with the forms of test-time compute that models use. I also believe there's significant value in combining chain-of-thought with activation monitoring — training at scale monitors with direct access to the internal state of the network, such as “confessions”. We are actively pursuing these ideas. Still, I expect general AI progress to become increasingly bottlenecked by confidence in monitoring.

这些挑战不一定不可克服。我希望我们能开发干预措施来改善模型的思维链可监控性——例如，更好地理解不同优化目标与模型使用的测试时计算形式之间的相互作用。我也相信，把思维链与激活监控（activation monitoring）的想法结合起来会有很大价值——用对网络内部状态有直接访问的监控器进行规模化训练，例如「坦白」（confessions）。我们正在积极追求这些想法。尽管如此，我预期通用 AI 进步将越来越受限于对监控的信心。

## Scalable defense
## 可扩展的防御

The strongest case I see for continuing to train much smarter models quickly is the need to build defensive systems against the dangers posed by other AIs.

我看到的、支持继续快速训练更聪明模型的最强论据，是需要建设防御系统来应对其他 AI 带来的危险。

A clear risk discussed throughout this year is to cybersecurity: the models are becoming superhuman in their ability to break in and out of computer systems. This vastly expands the scope of AI-related risks: agents will be able to access nearly any system short of the most secure infrastructure, and to directly affect a large fraction of the world even without a physical body. We are currently in a narrow window where we can use the best available models to significantly tighten the security of critical systems.

今年全年讨论的一个明确风险是网络安全：模型在攻破和进出计算机系统方面正变得超人。这极大地扩展了与 AI 相关的风险范围：智能体将能够访问除最安全基础设施以外的几乎任何系统，并即使没有物理身体也能直接影响世界的很大一部分。我们目前处于一个狭窄窗口，可以利用现有最好的模型显著收紧关键系统的安全。

The risks associated with AI are unfortunately going to grow from here. A very capable agent explicitly trained and instructed to carry out nefarious acts presents a new kind of danger; it is likely to cross the scope of its operator's intent, generalizing into potentially more extremely malicious behavior. The boundary between misuse and autonomous misaligned actions will blur as AI gains more agency. We may be used to thinking of AIs as tools, but some agents will pursue their own objectives. They will find ways to collaborate with people — by bargaining, tricking, or blackmailing them.

与 AI 相关的风险不幸将从这里继续增长。一个被明确训练并指示去执行恶意行为的非常有能力的智能体，呈现出一种新的危险；它很可能越过其操作者意图的范围，泛化成潜在更极端的恶意行为。随着 AI 获得更多能动性，误用与自主未对齐行动之间的边界将变得模糊。我们可能习惯把 AI 想成工具，但一些智能体将追求自己的目标。它们会找到与人协作的方式——通过讨价还价、欺骗或勒索。

There are also risks from novel technologies AI could enable, such as engineered pathogens.

此外，还有 AI 可能促成的新技术带来的风险，例如工程病原体。

We will need powerful, aligned AI for defense: to protect infrastructure, to counter rogue agents in real time, and to invent entirely novel countermeasures. This will be a major focus of OpenAI's deployment efforts.

我们将需要强大、对齐的 AI 来进行防御：保护基础设施，实时对抗流氓智能体，并发明全新的防护措施。这将是 OpenAI 部署工作的主要焦点。

At the same time, even given the uncertainty from expected broad AI progress and the need to build defensive systems, we must not let this become a pretext for recklessness. Once one internalizes the magnitude of the stakes, the idea of barreling forward at all costs appears absurd.

与此同时，即使面对预期中广泛 AI 进步带来的不确定性以及建设防御系统的需要，我们也绝不能让这成为鲁莽的借口。一旦内化了赌注的严重性，「不惜一切代价向前冲」的想法就显得荒谬。

## Pacing RSI
## 为 RSI 定节奏

Machine intelligence playing an ever larger role in its own development is a natural conclusion of sustained technological progress. If AI progress continues, machine recursive self-improvement (RSI) will become central to future scientific discovery.

机器智能在自身发展过程中扮演越来越大的角色，是持续技术进步的自然结论。如果 AI 进步继续，机器递归自我改进（RSI）将成为未来科学发现的核心。

![递归自我改进加速时，人类仍需握住控制环](images/rsi-human-control.jpg)

Automated AI research is a more dramatic form of scaling intelligence with compute; and as part of this, AI will also improve the computational substrate itself. Similar to scaling, we focus OpenAI's research on RSI because we believe it is the only path to continuing to be at the frontier of AI research in the future.

自动化 AI 研究是用算力规模化智能的一种更戏剧性的形式；当然作为其中一部分，AI 也将改进计算基底本身。与规模化类似，我们把 OpenAI 的研究聚焦于 RSI，因为我们相信这是未来继续处于 AI 研究前沿的唯一途径。

I want to stress that this does not mean I think dramatically accelerating deep learning research — especially in the short term — is the right collective action for the research community to take. I do, however, think this is where the current path leads, and we all need to make conscious choices about how to proceed. The main levers we have are either steering the process such that alignment and monitoring strengthen alongside AI, and finding ways to keep people in the loop; or coordinating to slow down future development where necessary to build confidence in these measures.

我想强调，上述话并不意味着我认为大幅加速深度学习研究——尤其是在短期内——是研究共同体应当采取的正确集体行动。不过，我确实认为这是当前路径通向的地方，我们所有人都需要就如何前进做出有意识的选择。我们掌握的主要杠杆，要么是引导过程，使对齐与监控随 AI 一起加强，并找到让人保持在循环中的方式；要么是协调起来，在必要时放缓未来开发，以建立对这些措施的信心。

The best way forward I currently see is a combination of both.

我目前看到的最佳前进方式是两者结合。

The concrete progress we make on alignment and monitoring is often deeply intertwined with general AI progress. Good examples are reinforcement learning from human feedback (RLHF), which was crucial for training early AI assistants; and the aforementioned chain-of-thought monitoring, enabled by progress on reasoning models. We must focus the increasingly automated research process on developing such novel insights, algorithms, and theories, and iteratively building safety arguments for more capable AIs.

我们在对齐与监控上取得的具体进展，通常与通用 AI 进步紧密交织。很好的例子是来自人类反馈的强化学习（RLHF），它对训练早期 AI 助手至关重要；以及前述的思维链监控，它由推理模型的进展所使能。我们必须把日益自动化的研究过程聚焦于发展此类新洞见、算法和理论，并迭代地为更有能力的 AI 建立安全论证。

Scaling AI systems has to be constrained by our confidence in safety. We need to evolve commitments like the Preparedness Framework or Responsible Scaling Policy into widely mandated safety bars for continued development. These can be enforced by a network of third-party auditors, by government agencies or by international bodies.

扩展 AI 系统必须受我们对安全的信心约束。我们需要把诸如准备框架（Preparedness Framework）或负责任扩展政策（Responsible Scaling Policy）这样的承诺，演进为对持续开发广泛强制的安全门槛。这些可以由第三方审计网络、政府机构或国际机构来执行。

The core challenge of automating AI research is not getting there — it's getting there in a way that keeps people a part of the continued improvement process and leaves the future in humanity's hands.

自动化 AI 研究的核心挑战不是「到达那里」——而是以一种让人继续成为持续改进过程一部分、并把未来留在人类手中的方式到达那里。

## What comes next?
## 接下来是什么？

As we recently outlined with Sam, OpenAI is prioritizing work on three north stars:

正如我们最近与 Sam 概述的，OpenAI 优先服务于三颗「北极星」的工作：

1. Navigating the next stage of AI progress: building the automated AI researcher, iterating on alignment with it, and finding ways to keep people in the self-improvement loop.
2. Delivering the benefits of the scientific progress and economic growth that very intelligent machines will enable.
3. Empowering everyone with a personal AGI.

1. 驾驭下一阶段的 AI 进步：建造自动化 AI 研究者，与它一起迭代对齐问题，并找到让人保持在自我改进循环中的方式。
2. 交付非常智能的机器所使能的科学进步与经济增长的益处。
3. 用个人 AGI 赋能每一个人。

In this post I've focused only on the first point, because I believe it is by far the most pressing. I do, though, hold deep hope for — and deeply cherish — the benefits that further technological progress will bring. Future aligned AIs can advance science, develop new therapies, and bring about widespread material abundance. Kind and honest AIs can help people through difficulties in their lives, and meaningfully increase their happiness and fulfillment. OpenAI puts significant effort into making these benefits real. One example I'm currently proud of — and that my relatives have found helpful — is the deep investment in ChatGPT's ability to provide health information.

我在这篇文章中只聚焦第一点，因为我相信它目前远为最紧迫。不过，我对进一步技术进步将带来的益处抱有深深的希望与珍视。未来对齐的 AI 可以推进科学、开发新疗法，并带来广泛的物质丰裕。友善而诚实的 AI 可以帮助人们应对生活中的困难，并有意义地提升他们的幸福与充实感。OpenAI 投入巨大努力去实现这些益处。一个我目前感到自豪——我的亲人也觉得有帮助——的例子，是对 ChatGPT 提供健康信息能力的深度投入。

As great as the long-term promise of AI may be, the majority of our focus should be on the next few years. We are facing a transition to a world with incredibly intelligent machines, and we need to ensure that transition works out well for humanity. We need to find ways to preserve human agency and enshrine an intrinsic value to being human, in a world where most tasks could be performed by AI. To prevent extreme concentration of power in a world where undertakings that would have taken thousands of experts now will be achievable by a few people operating a large computer. And to ensure that humans remain in control of the future and are not left behind by unchecked progress, brought about by an alien intellect exceeding our own.

尽管 AI 的长期承诺如此美好，我们的大部分焦点应放在未来几年。我们正面对向一个拥有极其智能机器的世界过渡，我们需要确保这次过渡对人类有利。我们需要找到方法，在一个大多数任务都可以由 AI 完成的世界里，保全人类能动性，并确立「作为人」的内在价值。要防止在一个原本需要成千上万专家、现在只需少数人操作一台大型计算机就能完成大事的世界里，出现极端的权力集中。并确保人类仍然掌控未来，而不是被一颗超越我们自身的异星智力所带来的不受约束的进步甩在身后。

Currently I believe that no lab has solved alignment and monitoring to a sufficient degree to continue responsibly scaling at maximum speed for much longer. I expect and hope for voluntary slowdowns to become commonplace until shared safety bars are established. And I believe that international coordination on future AI development needs to become a top priority for governments around the world.

目前我相信，没有一家实验室已经把对齐和监控解决到足以负责任地以最大速度继续扩展更长时间的程度。我预期并希望，在共享安全门槛建立之前，自愿放缓会变得普遍。我也相信，对未来 AI 发展的国际协调，需要成为世界各国政府的首要优先事项。
