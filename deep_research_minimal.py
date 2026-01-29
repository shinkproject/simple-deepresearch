#!/usr/bin/env python3
"""
单文件可运行的极简 Deep Research 示例。

特点：
- 免 Key 的搜索：使用 DuckDuckGo HTML 结果页（无需 API Key）。
- 生成模型：使用 OpenRouter（需设置环境变量 OPENROUTER_API_KEY）。
- 关键概念注释：Agent Loop / State Management / Memory / Tool Use。
"""

from __future__ import annotations

import json
import os
import textwrap
import time
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Dict, List, Tuple

import requests


OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-4o-mini"


class DuckDuckGoHTMLParser(HTMLParser):
    """解析 DuckDuckGo HTML 结果的超简版解析器。"""

    def __init__(self) -> None:
        super().__init__()
        self.in_result = False
        self.current_link = ""
        self.current_title = ""
        self.results: List[Tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str]]) -> None:
        if tag == "a":
            attrs_dict = dict(attrs)
            if attrs_dict.get("class") == "result__a":
                self.in_result = True
                self.current_link = attrs_dict.get("href", "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.in_result:
            self.in_result = False
            if self.current_title and self.current_link:
                self.results.append((self.current_title.strip(), self.current_link))
            self.current_title = ""
            self.current_link = ""

    def handle_data(self, data: str) -> None:
        if self.in_result:
            self.current_title += data


def search_web(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Tool Use: Web Search。使用免 Key 的 DuckDuckGo HTML 搜索结果。"""
    params = {"q": query}
    headers = {"User-Agent": "Mozilla/5.0 (compatible; DeepResearchBot/1.0)"}
    response = requests.get(
        "https://duckduckgo.com/html/", params=params, headers=headers, timeout=20
    )
    response.raise_for_status()

    parser = DuckDuckGoHTMLParser()
    parser.feed(response.text)

    results = []
    for title, url in parser.results[:max_results]:
        results.append(
            {
                "title": title,
                "url": url,
                "snippet": "",
            }
        )
    return results


def call_openrouter(messages: List[Dict[str, str]], model: str = DEFAULT_MODEL) -> str:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("请设置环境变量 OPENROUTER_API_KEY")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
    }
    response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]


@dataclass
class ResearchState:
    """State Management：集中管理运行状态，便于 Agent Loop 持续迭代。"""

    question: str
    plan: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    sources: List[Dict[str, str]] = field(default_factory=list)
    iterations: int = 0
    max_iterations: int = 3
    done: bool = False
    memory: Dict[str, List[str]] = field(
        default_factory=lambda: {"short_term": [], "long_term": []}
    )


def make_plan(question: str) -> List[str]:
    """让模型生成子问题计划。"""
    prompt = textwrap.dedent(
        f"""
        你是研究助手。请把用户问题拆成 3-5 个可检索的子问题，输出为 JSON 数组。
        问题：{question}
        """
    ).strip()
    content = call_openrouter(
        [
            {"role": "system", "content": "你是严谨的研究助理。"},
            {"role": "user", "content": prompt},
        ]
    )
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return [question]


def update_memory(state: ResearchState, new_facts: List[str]) -> None:
    """
    Memory：短期/长期记忆，用于跨轮次积累关键信息。

    - short_term: 本轮观察摘要（工作记忆 / working memory）
    - long_term: 关键事实沉淀（长期记忆 / long-term memory）
    """
    state.memory["short_term"] = new_facts[:10]
    state.memory["long_term"].extend(new_facts)
    state.memory["long_term"] = state.memory["long_term"][-20:]


def summarize_findings(state: ResearchState) -> str:
    """将收集的信息交给模型总结。"""
    sources_text = "\n".join(
        f"- {item['title']} ({item['url']})" for item in state.sources
    )
    notes_text = "\n".join(state.notes)
    prompt = textwrap.dedent(
        f"""
        根据以下研究笔记，生成结构化总结，列出关键观点，并在最后给出来源列表。
        研究笔记：
        {notes_text}

        来源：
        {sources_text}
        """
    ).strip()
    return call_openrouter(
        [
            {"role": "system", "content": "你是严谨的研究助理。"},
            {"role": "user", "content": prompt},
        ]
    )


def run_research(question: str) -> None:
    # State Management 初始化：这是 Agent 的“全局上下文”容器。
    state = ResearchState(question=question)

    # Agent Loop（循环式智能体流程）：
    # 1) Plan（任务分解） -> 2) Act（检索工具调用） -> 3) Observe（记录结果）
    # 4) Reflect（更新记忆与状态） -> 5) Decide（是否结束）
    state.plan = make_plan(question)
    print(f"计划子问题：{state.plan}")

    while not state.done and state.iterations < state.max_iterations:
        state.iterations += 1
        print(f"\n=== 第 {state.iterations} 轮 ===")

        round_notes: List[str] = []
        for sub_question in state.plan:
            print(f"检索：{sub_question}")
            results = search_web(sub_question)
            print(f"  -> 找到 {len(results)} 条结果")
            state.sources.extend(results)
            round_notes.append(f"{sub_question} -> 发现 {len(results)} 条结果")

        # Memory 更新（短期=本轮摘要，长期=累计要点）
        update_memory(state, round_notes)
        state.notes.extend(round_notes)
        print(f"记忆更新：短期 {len(state.memory['short_term'])} 条，长期 {len(state.memory['long_term'])} 条")

        # 简化策略：一轮即结束，可按需扩展为基于置信度或信息增益的停止条件
        state.done = True
        time.sleep(0.5)

    final_report = summarize_findings(state)
    print("\n=== 最终报告 ===")
    print(final_report)


if __name__ == "__main__":
    user_question = input("请输入你的研究问题：").strip()
    if not user_question:
        raise SystemExit("问题不能为空")
    run_research(user_question)
