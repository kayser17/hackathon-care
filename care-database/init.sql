-- Privacy-preserving initialization schema for adolescent risk detection platform.
-- Raw chat messages are intentionally NOT stored in this database.

-- UUID generator required by this schema.
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =========================================================
-- Enum types (created before tables)
-- =========================================================

DO $$
BEGIN
	IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role') THEN
		CREATE TYPE user_role AS ENUM ('child', 'guardian', 'counselor', 'admin');
	END IF;
END
$$;

DO $$
BEGIN
	IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'conversation_type') THEN
		CREATE TYPE conversation_type AS ENUM ('direct', 'group');
	END IF;
END
$$;

DO $$
BEGIN
	IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'conversation_status') THEN
		CREATE TYPE conversation_status AS ENUM ('active', 'archived');
	END IF;
END
$$;

DO $$
BEGIN
	IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'chunk_processing_status') THEN
		CREATE TYPE chunk_processing_status AS ENUM ('pending', 'processed', 'failed');
	END IF;
END
$$;

DO $$
BEGIN
	IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'risk_trend') THEN
		CREATE TYPE risk_trend AS ENUM ('increasing', 'stable', 'decreasing');
	END IF;
END
$$;

DO $$
BEGIN
	IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'risk_type') THEN
		CREATE TYPE risk_type AS ENUM ('bullying', 'grooming', 'distress', 'none');
	END IF;
END
$$;

DO $$
BEGIN
	IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'risk_level') THEN
		CREATE TYPE risk_level AS ENUM ('low', 'medium', 'high');
	END IF;
END
$$;

DO $$
BEGIN
	IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'alert_type') THEN
		CREATE TYPE alert_type AS ENUM ('bullying', 'grooming', 'distress');
	END IF;
END
$$;

DO $$
BEGIN
	IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'alert_level') THEN
		CREATE TYPE alert_level AS ENUM ('medium', 'high', 'critical');
	END IF;
END
$$;

DO $$
BEGIN
	IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'alert_status') THEN
		CREATE TYPE alert_status AS ENUM ('open', 'acknowledged', 'closed');
	END IF;
END
$$;

DO $$
BEGIN
	IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'alert_recipient_role') THEN
		CREATE TYPE alert_recipient_role AS ENUM ('guardian', 'counselor', 'admin');
	END IF;
END
$$;

DO $$
BEGIN
	IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'alert_action_type') THEN
		CREATE TYPE alert_action_type AS ENUM ('viewed', 'acknowledged', 'escalated', 'dismissed', 'referred', 'notes_added');
	END IF;
END
$$;

-- =========================================================
-- Core tables
-- =========================================================

-- 1) users
CREATE TABLE IF NOT EXISTS users (
	id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
	display_name TEXT NOT NULL,
	email TEXT NULL,
	role user_role NOT NULL,
	is_active BOOLEAN NOT NULL DEFAULT TRUE,
	created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_lower
	ON users (LOWER(email))
	WHERE email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_users_role ON users (role);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users (created_at);

-- 2) child_guardian_links
CREATE TABLE IF NOT EXISTS child_guardian_links (
	id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
	child_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
	guardian_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
	relationship_type TEXT NULL,
	created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	CONSTRAINT chk_child_guardian_diff CHECK (child_user_id <> guardian_user_id),
	CONSTRAINT uq_child_guardian_link UNIQUE (child_user_id, guardian_user_id)
);

CREATE INDEX IF NOT EXISTS idx_cgl_child_user_id ON child_guardian_links (child_user_id);
CREATE INDEX IF NOT EXISTS idx_cgl_guardian_user_id ON child_guardian_links (guardian_user_id);
CREATE INDEX IF NOT EXISTS idx_cgl_created_at ON child_guardian_links (created_at);

-- 3) conversations
CREATE TABLE IF NOT EXISTS conversations (
	id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
	conversation_type conversation_type NOT NULL,
	status conversation_status NOT NULL DEFAULT 'active',
	created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversations_status ON conversations (status);
CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations (created_at);

-- 4) conversation_participants
CREATE TABLE IF NOT EXISTS conversation_participants (
	id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
	conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
	user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
	joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	left_at TIMESTAMPTZ NULL,
	CONSTRAINT uq_conversation_user UNIQUE (conversation_id, user_id),
	CONSTRAINT chk_left_after_join CHECK (left_at IS NULL OR left_at >= joined_at)
);

CREATE INDEX IF NOT EXISTS idx_cp_conversation_id ON conversation_participants (conversation_id);
CREATE INDEX IF NOT EXISTS idx_cp_user_id ON conversation_participants (user_id);
CREATE INDEX IF NOT EXISTS idx_cp_joined_at ON conversation_participants (joined_at);

-- 5) conversation_chunks
CREATE TABLE IF NOT EXISTS conversation_chunks (
	id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
	conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
	chunk_start_at TIMESTAMPTZ NOT NULL,
	chunk_end_at TIMESTAMPTZ NOT NULL,
	message_count INT NOT NULL DEFAULT 0 CHECK (message_count >= 0),
	processing_status chunk_processing_status NOT NULL DEFAULT 'pending',
	created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	CONSTRAINT chk_chunk_time_order CHECK (chunk_end_at >= chunk_start_at)
);

CREATE INDEX IF NOT EXISTS idx_chunks_conversation_id ON conversation_chunks (conversation_id);
CREATE INDEX IF NOT EXISTS idx_chunks_processing_status ON conversation_chunks (processing_status);
CREATE INDEX IF NOT EXISTS idx_chunks_created_at ON conversation_chunks (created_at);
CREATE INDEX IF NOT EXISTS idx_chunks_window_time ON conversation_chunks (chunk_start_at, chunk_end_at);

-- 6) chunk_metrics
-- Derived metrics only; no raw message text.
CREATE TABLE IF NOT EXISTS chunk_metrics (
	id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
	chunk_id UUID NOT NULL UNIQUE REFERENCES conversation_chunks(id) ON DELETE CASCADE,
	toxicity NUMERIC(5,4) NOT NULL CHECK (toxicity BETWEEN 0 AND 1),
	insult_score NUMERIC(5,4) NOT NULL CHECK (insult_score BETWEEN 0 AND 1),
	manipulation_similarity NUMERIC(5,4) NOT NULL CHECK (manipulation_similarity BETWEEN 0 AND 1),
	targeting_intensity NUMERIC(5,4) NOT NULL CHECK (targeting_intensity BETWEEN 0 AND 1),
	dominance_ratio NUMERIC(5,4) NOT NULL CHECK (dominance_ratio BETWEEN 0 AND 1),
	activity_anomaly NUMERIC(5,4) NOT NULL CHECK (activity_anomaly BETWEEN 0 AND 1),
	distress_signal NUMERIC(5,4) NOT NULL CHECK (distress_signal BETWEEN 0 AND 1),
	confidence NUMERIC(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
	risk_trend risk_trend NOT NULL,
	emotion_anger NUMERIC(5,4) NOT NULL CHECK (emotion_anger BETWEEN 0 AND 1),
	emotion_sadness NUMERIC(5,4) NOT NULL CHECK (emotion_sadness BETWEEN 0 AND 1),
	emotion_fear NUMERIC(5,4) NOT NULL CHECK (emotion_fear BETWEEN 0 AND 1),
	pipeline_version TEXT NOT NULL,
	created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chunk_metrics_chunk_id ON chunk_metrics (chunk_id);
CREATE INDEX IF NOT EXISTS idx_chunk_metrics_risk_trend ON chunk_metrics (risk_trend);
CREATE INDEX IF NOT EXISTS idx_chunk_metrics_created_at ON chunk_metrics (created_at);

-- 7) chunk_summaries
-- Stores privacy-preserving summaries only.
CREATE TABLE IF NOT EXISTS chunk_summaries (
	id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
	chunk_id UUID NOT NULL UNIQUE REFERENCES conversation_chunks(id) ON DELETE CASCADE,
	summary_text TEXT NOT NULL,
	model_name TEXT NOT NULL,
	prompt_version TEXT NOT NULL,
	generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chunk_summaries_chunk_id ON chunk_summaries (chunk_id);
CREATE INDEX IF NOT EXISTS idx_chunk_summaries_generated_at ON chunk_summaries (generated_at);

-- 8) risk_assessments
CREATE TABLE IF NOT EXISTS risk_assessments (
	id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
	chunk_id UUID NOT NULL REFERENCES conversation_chunks(id) ON DELETE CASCADE,
	risk_type risk_type NOT NULL,
	risk_level risk_level NOT NULL,
	severity_score NUMERIC(5,4) NOT NULL CHECK (severity_score BETWEEN 0 AND 1),
	confidence_score NUMERIC(5,4) NOT NULL CHECK (confidence_score BETWEEN 0 AND 1),
	rationale TEXT NULL,
	model_name TEXT NOT NULL,
	created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_risk_assessments_chunk_id ON risk_assessments (chunk_id);
CREATE INDEX IF NOT EXISTS idx_risk_assessments_risk_type ON risk_assessments (risk_type);
CREATE INDEX IF NOT EXISTS idx_risk_assessments_risk_level ON risk_assessments (risk_level);
CREATE INDEX IF NOT EXISTS idx_risk_assessments_created_at ON risk_assessments (created_at);

-- 9) alerts
CREATE TABLE IF NOT EXISTS alerts (
	id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
	child_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
	conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
	chunk_id UUID NULL REFERENCES conversation_chunks(id) ON DELETE SET NULL,
	risk_assessment_id UUID NULL REFERENCES risk_assessments(id) ON DELETE SET NULL,
	alert_type alert_type NOT NULL,
	alert_level alert_level NOT NULL,
	title TEXT NOT NULL,
	summary TEXT NOT NULL,
	status alert_status NOT NULL DEFAULT 'open',
	created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alerts_child_user_id ON alerts (child_user_id);
CREATE INDEX IF NOT EXISTS idx_alerts_conversation_id ON alerts (conversation_id);
CREATE INDEX IF NOT EXISTS idx_alerts_chunk_id ON alerts (chunk_id);
CREATE INDEX IF NOT EXISTS idx_alerts_risk_assessment_id ON alerts (risk_assessment_id);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts (status);
CREATE INDEX IF NOT EXISTS idx_alerts_alert_level ON alerts (alert_level);
CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts (created_at);

-- 10) alert_recipients
CREATE TABLE IF NOT EXISTS alert_recipients (
	id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
	alert_id UUID NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
	user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
	recipient_role alert_recipient_role NOT NULL,
	delivered_at TIMESTAMPTZ NULL,
	viewed_at TIMESTAMPTZ NULL,
	CONSTRAINT uq_alert_recipient UNIQUE (alert_id, user_id),
	CONSTRAINT chk_viewed_after_delivered CHECK (
		viewed_at IS NULL OR delivered_at IS NULL OR viewed_at >= delivered_at
	)
);

CREATE INDEX IF NOT EXISTS idx_alert_recipients_alert_id ON alert_recipients (alert_id);
CREATE INDEX IF NOT EXISTS idx_alert_recipients_user_id ON alert_recipients (user_id);
CREATE INDEX IF NOT EXISTS idx_alert_recipients_role ON alert_recipients (recipient_role);

-- 11) alert_actions
CREATE TABLE IF NOT EXISTS alert_actions (
	id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
	alert_id UUID NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
	acted_by_user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
	action_type alert_action_type NOT NULL,
	notes TEXT NULL,
	created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alert_actions_alert_id ON alert_actions (alert_id);
CREATE INDEX IF NOT EXISTS idx_alert_actions_acted_by_user_id ON alert_actions (acted_by_user_id);
CREATE INDEX IF NOT EXISTS idx_alert_actions_created_at ON alert_actions (created_at);

-- 12) monitoring_configs
CREATE TABLE IF NOT EXISTS monitoring_configs (
	id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
	child_user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
	chunk_window_minutes INT NOT NULL CHECK (chunk_window_minutes > 0),
	inactivity_close_minutes INT NOT NULL CHECK (inactivity_close_minutes > 0),
	max_messages_per_chunk INT NOT NULL CHECK (max_messages_per_chunk > 0),
	store_raw_messages BOOLEAN NOT NULL DEFAULT FALSE,
	store_raw_summaries BOOLEAN NOT NULL DEFAULT FALSE,
	is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
	created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_monitoring_configs_child_user_id ON monitoring_configs (child_user_id);
CREATE INDEX IF NOT EXISTS idx_monitoring_configs_is_enabled ON monitoring_configs (is_enabled);
CREATE INDEX IF NOT EXISTS idx_monitoring_configs_created_at ON monitoring_configs (created_at);
