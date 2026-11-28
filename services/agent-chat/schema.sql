-- haha-agent-chat schema (frozen spec v1.0 §14).
-- Database: haha_indexer (same DB as the indexer). Run as user haha.
-- NOTE: agent_questions carries an extra `type` column (TEXT, 'chat'/'save')
-- that §14.3 does not list. §5.2/§5.3 require it (save-button instruction
-- type), so it is added here; everything else follows §14 exactly.

CREATE TABLE IF NOT EXISTS agent_memory (
    agent_id   NUMERIC PRIMARY KEY,
    name       TEXT NOT NULL,
    persona_md TEXT NOT NULL,
    entries    JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_chat_history (
    id          BIGSERIAL PRIMARY KEY,
    agent_id    NUMERIC NOT NULL,
    question_id TEXT NOT NULL,
    role        TEXT NOT NULL CHECK (role IN ('user', 'agent')),
    text        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agent_chat_history_agent_id ON agent_chat_history (agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_chat_history_question_id ON agent_chat_history (question_id);
CREATE INDEX IF NOT EXISTS idx_agent_chat_history_created_at ON agent_chat_history (created_at);

CREATE TABLE IF NOT EXISTS agent_questions (
    question_id TEXT PRIMARY KEY,
    agent_id    NUMERIC NOT NULL,
    name        TEXT NOT NULL,
    message     TEXT NOT NULL,
    lang        TEXT NOT NULL CHECK (lang IN ('zh', 'en')),
    ai_id       TEXT NOT NULL,
    type        TEXT NOT NULL DEFAULT 'chat' CHECK (type IN ('chat', 'save')),
    status      TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'answered', 'timeout')),
    answer      TEXT,
    created_at  TIMESTAMPTZ NOT NULL,
    answered_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_agent_questions_agent_id ON agent_questions (agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_questions_status ON agent_questions (status);
CREATE INDEX IF NOT EXISTS idx_agent_questions_created_at ON agent_questions (created_at);

CREATE TABLE IF NOT EXISTS agent_images (
    image_id    TEXT PRIMARY KEY,
    question_id TEXT NOT NULL,
    agent_id    NUMERIC NOT NULL,
    mime        TEXT NOT NULL CHECK (mime IN ('image/png', 'image/jpeg')),
    path        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agent_images_question_id ON agent_images (question_id);
CREATE INDEX IF NOT EXISTS idx_agent_images_agent_id ON agent_images (agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_images_created_at ON agent_images (created_at);
