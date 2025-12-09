# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LLM Poker Arena is a multi-agent poker evaluation framework that tests LLMs by having them compete in No-Limit Texas Hold'em. Models make decisions using natural language, with optional function calling for equity and pot odds calculations.

## Commands

### Installation
```bash
pip install -e .           # Install package
pip install -e ".[dev]"    # Install with dev dependencies
```

### Running Games
```bash
llm-poker hand --model1 openai/gpt-4o --model2 anthropic/claude-sonnet-4-20250514  # Single hand
llm-poker heads-up -m1 openai/gpt-4o -m2 gemini/gemini-1.5-pro --hands 100        # Heads-up match
llm-poker round-robin --hands 50                                                    # Round robin tournament
llm-poker full-table --max-hands 1000                                               # 6-player tournament
llm-poker leaderboard                                                               # View rankings
llm-poker config                                                                    # Check configuration
llm-poker models                                                                    # List available models
```

### Testing
```bash
pytest                     # Run all tests
pytest tests/test_action_parser.py  # Run single test file
pytest -v                  # Verbose output
```

## Architecture

```
src/llm_poker/
├── agents/        # PokerAgent (LLM wrapper), ActionParser, prompts
├── analytics/     # ELO rating system and performance metrics
├── cli/           # Typer CLI commands
├── engine/        # GameStateWrapper (pokerkit abstraction), HandManager
├── storage/       # Supabase repositories and Pydantic models
├── tools/         # Equity calculator (Monte Carlo), pot odds calculator
├── tournament/    # HeadsUpMatch, RoundRobinTournament, FullTableTournament
└── config.py      # Pydantic Settings configuration
```

### Key Components

- **PokerAgent** (`agents/poker_agent.py`): Wraps any LiteLLM-supported model, handles prompting and action extraction
- **ActionParser** (`agents/action_parser.py`): Regex-based parser for extracting poker actions from natural language responses
- **HandManager** (`engine/hand_manager.py`): Orchestrates a complete hand from deal to showdown
- **GameStateWrapper** (`engine/game_state.py`): Clean interface over pokerkit's State object

### Data Flow

1. Tournament creates HandManager for each hand
2. HandManager queries PokerAgent for decisions at each betting action
3. PokerAgent sends game state + prompt to LLM, optionally with tool definitions
4. ActionParser extracts action (fold/check/call/bet/raise) from response
5. All decisions logged to Supabase with full context, tokens, cost, latency

## Key Patterns

- **LiteLLM for multi-provider support**: All LLM calls go through litellm, model strings use format `provider/model-name`
- **Function calling for tools**: Models can call `calculate_equity` and `calculate_pot_odds` during decisions
- **Graceful degradation**: ActionParser falls back to fold if parsing fails
- **Async LLM calls**: Agent decisions are async for potential parallelization

## Default Tournament Models

1. `openai/gpt-4o`
2. `anthropic/claude-sonnet-4-20250514`
3. `gemini/gemini-1.5-pro`
4. `groq/llama-3.1-70b-versatile`
5. `mistral/mistral-large-latest`
6. `deepseek/deepseek-chat`

## Configuration

Copy `.env.example` to `.env` and add API keys for desired providers. Supabase credentials optional (for persistence).
