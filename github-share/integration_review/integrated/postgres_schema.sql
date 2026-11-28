BEGIN;

ALTER TABLE public.users ADD COLUMN IF NOT EXISTS point_balance integer NOT NULL DEFAULT 0
    CHECK (point_balance >= 0);

CREATE TABLE IF NOT EXISTS public.point_transactions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
    delta integer NOT NULL CHECK (delta <> 0),
    balance_after integer NOT NULL CHECK (balance_after >= 0),
    reason text NOT NULL CHECK (length(reason) > 0),
    reference_key text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, reference_key)
);

CREATE TABLE IF NOT EXISTS public.web_login_sessions (
    token_hash text PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    expires bigint NOT NULL
);

CREATE INDEX IF NOT EXISTS web_login_sessions_expiry_idx
    ON public.web_login_sessions (expires);

COMMIT;
