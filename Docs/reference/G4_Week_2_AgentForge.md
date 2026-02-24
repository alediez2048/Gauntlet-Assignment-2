# AgentForge

## Week 2: Building Your First AI Agent

### Group 4

---

## Table of Contents

- [What is an AI Agent?](#what-is-an-ai-agent)
- [Why AI Agents Matter](#why-ai-agents-matter)
- [Core Components of an AI Agent](#core-components-of-an-ai-agent)
- [Agent Architectures](#agent-architectures)
- [Building Your First Agent](#building-your-first-agent)
- [Tools and Frameworks](#tools-and-frameworks)
- [Hands-On: Code Walkthrough](#hands-on-code-walkthrough)
- [Best Practices](#best-practices)
- [Common Pitfalls](#common-pitfalls)
- [What's Next?](#whats-next)

---

## What is an AI Agent?

An AI agent is a system that can **perceive its environment**, **make decisions**, and **take actions** to achieve specific goals — with some degree of autonomy.

### Key Characteristics

- **Autonomy** — Operates without constant human intervention
- **Reactivity** — Responds to changes in its environment
- **Proactivity** — Takes initiative to achieve goals
- **Social Ability** — Interacts with other agents or humans

> "An agent is anything that can be viewed as perceiving its environment through sensors and acting upon that environment through actuators."
> — Russell & Norvig, *Artificial Intelligence: A Modern Approach*

---

## Why AI Agents Matter

### The Shift from Tools to Agents

| Traditional AI Tools | AI Agents |
|---|---|
| Single task | Multi-step workflows |
| Human-directed | Goal-directed |
| Stateless | Maintain context |
| Reactive only | Proactive + Reactive |

### Real-World Applications

- **Customer Support** — Autonomous resolution of tickets
- **Software Engineering** — Code generation, debugging, deployment
- **Research** — Literature review, data analysis, hypothesis generation
- **Personal Assistants** — Scheduling, email management, task coordination

---

## Core Components of an AI Agent

### 1. Language Model (Brain)

The foundation — an LLM that provides reasoning and language understanding capabilities.

### 2. Prompt / System Instructions

Defines the agent's persona, goals, constraints, and behavioral guidelines.

### 3. Memory

- **Short-term memory** — Current conversation context
- **Long-term memory** — Persistent knowledge (vector DBs, databases)

### 4. Tools

External capabilities the agent can invoke:

- Web search
- Code execution
- API calls
- File operations
- Database queries

### 5. Planning / Reasoning

The ability to break down complex tasks into subtasks and determine the right sequence of actions.

---

## Agent Architectures

### Simple Reflex Agent

```
Perception → Rule Matching → Action
```

- Maps directly from input to output
- No memory or planning
- Example: Basic chatbot with if/else rules

### ReAct (Reasoning + Acting)

```
Thought → Action → Observation → Thought → ...
```

- Interleaves reasoning with action
- Most common architecture for LLM-based agents
- Example: An agent that searches the web, reads results, and synthesizes an answer

### Plan-and-Execute

```
Goal → Plan → Execute Step 1 → Execute Step 2 → ... → Result
```

- Creates a full plan before executing
- Better for complex, multi-step tasks
- Example: A research agent that outlines steps before diving in

### Multi-Agent Systems

```
Agent A ↔ Agent B ↔ Agent C
         Orchestrator
```

- Multiple specialized agents collaborate
- Each agent has a specific role
- Example: One agent writes code, another reviews it, a third tests it

---

## Building Your First Agent

### Step 1: Define the Goal

What should your agent accomplish? Be specific.

**Example:** "An agent that takes a research topic, searches for relevant papers, summarizes key findings, and produces a structured report."

### Step 2: Choose Your Tools

What capabilities does your agent need?

- Web search (e.g., Tavily, SerpAPI)
- Document reading (e.g., PDF parser)
- Code execution (e.g., Python REPL)
- File I/O

### Step 3: Design the System Prompt

```
You are a research assistant agent. Your goal is to help users
understand complex topics by:
1. Searching for relevant, recent sources
2. Reading and extracting key information
3. Synthesizing findings into a clear summary
4. Citing all sources properly

Always think step-by-step. If you're unsure, search for more
information before answering.
```

### Step 4: Implement the Agent Loop

```python
while not task_complete:
    # 1. Think about what to do next
    thought = llm.reason(context)

    # 2. Decide on an action
    action = llm.select_action(thought, available_tools)

    # 3. Execute the action
    result = execute(action)

    # 4. Update context with the result
    context.add(thought, action, result)

    # 5. Check if we're done
    task_complete = llm.evaluate(context)
```

### Step 5: Test and Iterate

- Start with simple tasks
- Gradually increase complexity
- Monitor for failure modes
- Add guardrails as needed

---

## Tools and Frameworks

### LangChain / LangGraph

- Most popular framework for building agents
- Rich ecosystem of tools and integrations
- LangGraph adds stateful, multi-step workflows

### CrewAI

- Focused on multi-agent collaboration
- Role-based agent design
- Good for complex workflows with multiple specialists

### AutoGen (Microsoft)

- Multi-agent conversation framework
- Strong support for human-in-the-loop
- Good for collaborative coding tasks

### OpenAI Assistants API

- Built-in tool use (code interpreter, file search)
- Managed threads and memory
- Easiest to get started with

### Comparison

| Framework | Best For | Learning Curve | Flexibility |
|---|---|---|---|
| LangChain/LangGraph | General purpose | Medium | High |
| CrewAI | Multi-agent teams | Low | Medium |
| AutoGen | Conversational agents | Medium | High |
| OpenAI Assistants | Quick prototyping | Low | Low |

---

## Hands-On: Code Walkthrough

### A Simple ReAct Agent with LangChain

```python
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_react_agent
from langchain.tools import Tool
from langchain import hub

# 1. Initialize the LLM
llm = ChatOpenAI(model="gpt-4", temperature=0)

# 2. Define tools
tools = [
    Tool(
        name="Search",
        func=search_function,
        description="Search the web for current information"
    ),
    Tool(
        name="Calculator",
        func=calculator_function,
        description="Perform mathematical calculations"
    ),
]

# 3. Get the ReAct prompt template
prompt = hub.pull("hwchase17/react")

# 4. Create the agent
agent = create_react_agent(llm, tools, prompt)

# 5. Create the executor (handles the agent loop)
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    max_iterations=10
)

# 6. Run the agent
result = agent_executor.invoke({
    "input": "What is the population of France and what is it squared?"
})
print(result["output"])
```

### Expected Output

```
Thought: I need to find the population of France first.
Action: Search
Action Input: "current population of France"
Observation: The population of France is approximately 68 million.

Thought: Now I need to square this number.
Action: Calculator
Action Input: 68000000 ** 2
Observation: 4624000000000000

Thought: I now have both pieces of information.
Final Answer: The population of France is approximately 68 million,
and that number squared is 4,624,000,000,000,000
(4.624 quadrillion).
```

---

## Best Practices

### 1. Start Simple

Don't over-engineer. Begin with a single tool and a clear goal, then expand.

### 2. Be Explicit in Prompts

Vague instructions lead to unpredictable behavior. Tell the agent exactly what you expect.

### 3. Add Guardrails

- Set maximum iterations
- Validate tool inputs/outputs
- Implement fallback behaviors
- Add human-in-the-loop for critical decisions

### 4. Monitor and Log Everything

- Log all thoughts, actions, and observations
- Track token usage and costs
- Monitor for hallucinations and errors

### 5. Handle Failures Gracefully

Agents will fail. Plan for it:

- Retry logic with backoff
- Fallback to simpler strategies
- Clear error messages for users

---

## Common Pitfalls

### Infinite Loops

The agent gets stuck repeating the same action. **Fix:** Set `max_iterations` and add loop detection.

### Tool Misuse

The agent calls the wrong tool or passes bad inputs. **Fix:** Write clear tool descriptions and validate inputs.

### Context Window Overflow

Long conversations exceed the model's context limit. **Fix:** Summarize history, use retrieval-augmented generation.

### Hallucinated Actions

The agent invents tools or actions that don't exist. **Fix:** Strictly constrain available actions, validate before execution.

### Over-Planning

The agent spends too much time thinking and not enough doing. **Fix:** Limit reasoning steps, encourage action-taking.

---

## What's Next?

### Week 3 Preview: Advanced Agent Patterns

- **Retrieval-Augmented Generation (RAG)** — Grounding agents in real data
- **Multi-Agent Orchestration** — Coordinating teams of agents
- **Human-in-the-Loop** — When and how to involve humans
- **Evaluation & Testing** — How to measure agent performance

### Homework

1. **Build a simple agent** using any framework of your choice
2. Give it **at least 2 tools**
3. Test it on **3 different tasks**
4. Document what worked, what didn't, and why

### Resources

- [LangChain Documentation](https://docs.langchain.com)
- [LangGraph Tutorial](https://langchain-ai.github.io/langgraph/)
- [OpenAI Assistants Guide](https://platform.openai.com/docs/assistants)
- [CrewAI Documentation](https://docs.crewai.com)
- [ReAct Paper](https://arxiv.org/abs/2210.03629)

---

*AgentForge — Group 4 — Week 2*
