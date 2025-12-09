"""Universal poker agent that works with any LLM via litellm."""

import json
import time
from dataclasses import dataclass, field
from typing import Any

import litellm

from llm_poker.agents.prompts import (
    DEFAULT_SYSTEM_PROMPT,
    build_action_prompt,
    build_clarification_prompt,
)
from llm_poker.agents.action_parser import ActionParser, ParsedAction
from llm_poker.tools.pot_odds import calculate_pot_odds
from llm_poker.tools.equity import calculate_equity
from llm_poker.tools.registry import POKER_TOOLS
from llm_poker.config import settings


@dataclass
class TokenUsage:
    """Token usage for a single LLM call."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class AgentResponse:
    """Response from agent's get_action call."""
    action: dict  # {"type": "fold|check|call|raise", "amount": optional}
    tool_calls: list[dict] = field(default_factory=list)
    raw_response: str = ""
    tokens: TokenUsage = field(default_factory=TokenUsage)
    latency_ms: int = 0
    cost_usd: float = 0.0
    parse_success: bool = True
    default_action_used: bool = False
    retry_used: bool = False
    error: str | None = None


class PokerAgent:
    """Universal poker agent that works with any LLM via litellm."""

    def __init__(
        self,
        model: str,
        player_name: str | None = None,
        system_prompt: str | None = None,
        temperature: float | None = None,
        timeout: int | None = None,
        max_retries: int | None = None,
    ):
        """
        Initialize a poker agent.

        Args:
            model: LiteLLM model string (e.g., "openai/gpt-4o")
            player_name: Display name for the agent
            system_prompt: Custom system prompt (uses default if not provided)
            temperature: LLM temperature (default from settings)
            timeout: Request timeout in seconds (default from settings)
            max_retries: Max retries on transient failures (default from settings)
        """
        self.model = model
        self.player_name = player_name or model.split("/")[-1]
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self.temperature = temperature or settings.llm_temperature
        self.timeout = timeout or settings.llm_timeout
        self.max_retries = max_retries or settings.llm_retries
        self.tools = POKER_TOOLS

        # Cumulative stats
        self.total_tokens = 0
        self.total_cost = 0.0
        self.total_calls = 0
        self.parse_failures = 0

    async def get_action(
        self,
        game_state: dict,
        player_index: int,
        betting_history: list[dict],
    ) -> AgentResponse:
        """
        Get action from the LLM agent.

        Args:
            game_state: Current game state snapshot dict
            player_index: Index of this player
            betting_history: History of actions in this hand

        Returns:
            AgentResponse with action and metadata
        """
        start_time = time.time()
        total_tokens = TokenUsage()
        total_cost = 0.0
        tool_calls_made = []
        retry_used = False

        # Build messages
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": build_action_prompt(
                game_state, player_index, betting_history
            )},
        ]

        try:
            # LLM call loop - handle multiple rounds of tool calls
            max_tool_rounds = 3  # Prevent infinite loops
            tool_round = 0

            while tool_round < max_tool_rounds:
                response = await self._call_llm(messages)
                total_tokens = self._add_tokens(total_tokens, response)
                total_cost += self._get_cost(response)

                assistant_message = response.choices[0].message

                # If no tool calls, we're done
                if not assistant_message.tool_calls:
                    break

                tool_round += 1

                # Execute tools and get results
                tool_results, tools_info = await self._execute_tools(
                    assistant_message.tool_calls
                )
                tool_calls_made.extend(tools_info)

                # Add assistant message with tool calls
                messages.append({
                    "role": "assistant",
                    "content": assistant_message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            }
                        }
                        for tc in assistant_message.tool_calls
                    ]
                })

                # Add tool results
                messages.extend(tool_results)

            # Get response text
            response_text = response.choices[0].message.content or ""

            # Parse action
            legal_actions = self._convert_legal_actions(game_state["legal_actions"])
            parsed = ActionParser.parse(response_text, legal_actions)

            # If parse failed, retry once with clarification
            if not parsed.success:
                retry_used = True
                messages.append({"role": "assistant", "content": response_text})
                messages.append({"role": "user", "content": build_clarification_prompt()})

                retry_response = await self._call_llm(messages)
                total_tokens = self._add_tokens(total_tokens, retry_response)
                total_cost += self._get_cost(retry_response)

                retry_text = retry_response.choices[0].message.content or ""
                parsed = ActionParser.parse(retry_text, legal_actions)
                response_text = retry_text

            # If still failed, use default action
            default_used = False
            if not parsed.success:
                parsed = ActionParser.get_default_action(legal_actions)
                default_used = True
                self.parse_failures += 1

            # Build action dict
            action = {"type": parsed.action_type}
            if parsed.amount is not None:
                action["amount"] = parsed.amount

            latency_ms = int((time.time() - start_time) * 1000)

            # Update cumulative stats
            self.total_tokens += total_tokens.total_tokens
            self.total_cost += total_cost
            self.total_calls += 1

            return AgentResponse(
                action=action,
                tool_calls=tool_calls_made,
                raw_response=response_text,
                tokens=total_tokens,
                latency_ms=latency_ms,
                cost_usd=total_cost,
                parse_success=parsed.success,
                default_action_used=default_used,
                retry_used=retry_used,
            )

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            self.parse_failures += 1

            # Return fold on error
            return AgentResponse(
                action={"type": "fold"},
                tool_calls=tool_calls_made,
                raw_response="",
                tokens=total_tokens,
                latency_ms=latency_ms,
                cost_usd=total_cost,
                parse_success=False,
                default_action_used=True,
                error=str(e),
            )

    async def _call_llm(
        self,
        messages: list[dict],
        include_tools: bool = True,
        force_text_response: bool = False,
    ) -> Any:
        """Make an LLM completion call."""
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "timeout": self.timeout,
            "num_retries": self.max_retries,
        }

        if include_tools and self.tools:
            # Check if model supports function calling
            if litellm.supports_function_calling(model=self.model):
                kwargs["tools"] = self.tools
                if force_text_response:
                    # Force text response after tool results
                    kwargs["tool_choice"] = "none"
                else:
                    kwargs["tool_choice"] = "auto"

        return await litellm.acompletion(**kwargs)

    async def _execute_tools(
        self,
        tool_calls: list,
    ) -> tuple[list[dict], list[dict]]:
        """
        Execute tool calls and return results.

        Returns:
            Tuple of (tool_result_messages, tool_info_for_logging)
        """
        results = []
        info = []

        for tc in tool_calls:
            func_name = tc.function.name
            try:
                func_args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                func_args = {}

            # Execute the tool
            if func_name == "pot_odds_calculator":
                result = calculate_pot_odds(
                    pot_size=func_args.get("pot_size", 0),
                    bet_to_call=func_args.get("bet_to_call", 0),
                )
            elif func_name == "equity_calculator":
                result = calculate_equity(
                    hole_cards=func_args.get("hole_cards", ""),
                    community_cards=func_args.get("community_cards", ""),
                    num_opponents=func_args.get("num_opponents", 1),
                )
            else:
                result = {"error": f"Unknown tool: {func_name}"}

            # Add to results
            results.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result),
            })

            # Log info
            info.append({
                "name": func_name,
                "args": func_args,
                "result": result,
            })

        return results, info

    def _convert_legal_actions(self, legal_actions: list) -> list[dict]:
        """Convert LegalAction objects to dicts for parser."""
        result = []
        for action in legal_actions:
            if hasattr(action, "__dict__"):
                result.append({
                    "action_type": action.action_type,
                    "amount": getattr(action, "amount", None),
                    "min_raise": getattr(action, "min_raise", None),
                    "max_raise": getattr(action, "max_raise", None),
                })
            else:
                result.append(action)
        return result

    def _add_tokens(self, current: TokenUsage, response: Any) -> TokenUsage:
        """Add token usage from response to current totals."""
        if hasattr(response, "usage") and response.usage:
            return TokenUsage(
                prompt_tokens=current.prompt_tokens + (response.usage.prompt_tokens or 0),
                completion_tokens=current.completion_tokens + (response.usage.completion_tokens or 0),
                total_tokens=current.total_tokens + (response.usage.total_tokens or 0),
            )
        return current

    def _get_cost(self, response: Any) -> float:
        """Extract cost from response if available."""
        if hasattr(response, "_hidden_params"):
            return response._hidden_params.get("response_cost", 0.0) or 0.0
        return 0.0

    def get_stats(self) -> dict:
        """Get cumulative statistics for this agent."""
        return {
            "model": self.model,
            "player_name": self.player_name,
            "total_calls": self.total_calls,
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost, 4),
            "parse_failures": self.parse_failures,
            "parse_failure_rate": (
                round(self.parse_failures / self.total_calls, 3)
                if self.total_calls > 0 else 0.0
            ),
        }
