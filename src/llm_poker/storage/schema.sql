-- LLM Poker Arena Database Schema
-- Run this in Supabase SQL Editor to create the tables

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Tournaments table
CREATE TABLE IF NOT EXISTS tournaments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tournament_type VARCHAR(50) NOT NULL,  -- 'heads_up', 'round_robin', 'full_table'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    config JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(20) DEFAULT 'pending'  -- pending, running, completed, failed
);

-- Tournament participants
CREATE TABLE IF NOT EXISTS tournament_participants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tournament_id UUID REFERENCES tournaments(id) ON DELETE CASCADE,
    model_name VARCHAR(100) NOT NULL,
    seat_position INTEGER,
    starting_stack INTEGER NOT NULL,
    final_stack INTEGER,
    final_position INTEGER,
    total_hands_played INTEGER DEFAULT 0,
    UNIQUE(tournament_id, seat_position)
);

-- Individual hands
CREATE TABLE IF NOT EXISTS hands (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tournament_id UUID REFERENCES tournaments(id) ON DELETE CASCADE,
    hand_number INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    small_blind INTEGER NOT NULL,
    big_blind INTEGER NOT NULL,
    pot_size INTEGER,
    board_cards VARCHAR(20),
    winner_ids UUID[],
    hand_history JSONB,
    UNIQUE(tournament_id, hand_number)
);

-- Per-player hand participation
CREATE TABLE IF NOT EXISTS hand_participants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    hand_id UUID REFERENCES hands(id) ON DELETE CASCADE,
    participant_id UUID REFERENCES tournament_participants(id) ON DELETE CASCADE,
    hole_cards VARCHAR(10),
    starting_stack INTEGER NOT NULL,
    ending_stack INTEGER NOT NULL,
    profit_loss INTEGER NOT NULL,
    position VARCHAR(10),
    went_to_showdown BOOLEAN DEFAULT FALSE,
    won_hand BOOLEAN DEFAULT FALSE,
    UNIQUE(hand_id, participant_id)
);

-- Individual decisions within a hand
CREATE TABLE IF NOT EXISTS decisions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    hand_id UUID REFERENCES hands(id) ON DELETE CASCADE,
    participant_id UUID REFERENCES tournament_participants(id) ON DELETE CASCADE,
    decision_number INTEGER NOT NULL,
    street VARCHAR(10) NOT NULL,

    -- Game state at decision time
    game_state JSONB NOT NULL,

    -- LLM interaction
    prompt_messages JSONB NOT NULL,
    llm_response TEXT,
    tools_called JSONB,

    -- Parsed action
    action_type VARCHAR(20) NOT NULL,
    action_amount INTEGER,
    parse_success BOOLEAN DEFAULT TRUE,
    parse_error TEXT,
    default_action_used BOOLEAN DEFAULT FALSE,

    -- Metrics
    latency_ms INTEGER,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    cost_usd DECIMAL(10, 6),

    -- Poker metrics
    pot_odds DECIMAL(5, 2),
    equity_estimate DECIMAL(5, 2),

    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(hand_id, participant_id, decision_number)
);

-- Aggregate statistics per model per tournament
CREATE TABLE IF NOT EXISTS model_stats (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_name VARCHAR(100) NOT NULL,
    tournament_id UUID REFERENCES tournaments(id) ON DELETE CASCADE,

    -- Win metrics
    hands_played INTEGER DEFAULT 0,
    hands_won INTEGER DEFAULT 0,
    showdowns_reached INTEGER DEFAULT 0,
    showdowns_won INTEGER DEFAULT 0,

    -- Financial metrics
    total_profit_loss INTEGER DEFAULT 0,
    biggest_pot_won INTEGER DEFAULT 0,
    avg_profit_per_hand DECIMAL(10, 2),
    roi DECIMAL(5, 2),

    -- Behavioral metrics
    vpip DECIMAL(5, 2),
    pfr DECIMAL(5, 2),
    aggression_factor DECIMAL(5, 2),
    fold_to_3bet DECIMAL(5, 2),
    cbet_frequency DECIMAL(5, 2),
    bluff_frequency DECIMAL(5, 2),

    -- Tool usage
    tool_usage_rate DECIMAL(5, 2),
    pot_odds_compliance DECIMAL(5, 2),

    -- Cost metrics
    total_tokens INTEGER DEFAULT 0,
    total_cost_usd DECIMAL(10, 4) DEFAULT 0,
    avg_latency_ms INTEGER,
    parse_failure_rate DECIMAL(5, 2),

    -- ELO
    elo_rating INTEGER DEFAULT 1500,

    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(model_name, tournament_id)
);

-- Head-to-head matchup stats
CREATE TABLE IF NOT EXISTS matchup_stats (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_a VARCHAR(100) NOT NULL,
    model_b VARCHAR(100) NOT NULL,
    hands_played INTEGER DEFAULT 0,
    model_a_wins INTEGER DEFAULT 0,
    model_b_wins INTEGER DEFAULT 0,
    model_a_profit INTEGER DEFAULT 0,
    model_b_profit INTEGER DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(model_a, model_b)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_hands_tournament ON hands(tournament_id);
CREATE INDEX IF NOT EXISTS idx_decisions_hand ON decisions(hand_id);
CREATE INDEX IF NOT EXISTS idx_decisions_participant ON decisions(participant_id);
CREATE INDEX IF NOT EXISTS idx_model_stats_model ON model_stats(model_name);
CREATE INDEX IF NOT EXISTS idx_decisions_created ON decisions(created_at);
CREATE INDEX IF NOT EXISTS idx_tournament_participants_tournament ON tournament_participants(tournament_id);
CREATE INDEX IF NOT EXISTS idx_hand_participants_hand ON hand_participants(hand_id);

-- Row Level Security (optional - enable if needed)
-- ALTER TABLE tournaments ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE tournament_participants ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE hands ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE hand_participants ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE decisions ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE model_stats ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE matchup_stats ENABLE ROW LEVEL SECURITY;
