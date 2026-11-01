-- Run this once in your own Supabase project's SQL Editor.
-- These are fictional restaurants and sample data for the quiz.
CREATE TABLE IF NOT EXISTS public.restaurants (
    id integer PRIMARY KEY,
    name text NOT NULL,
    cuisine text NOT NULL,
    avg_cost numeric(6,2) NOT NULL,
    rating numeric(2,1) NOT NULL,
    distance_miles numeric(3,1) NOT NULL
);
INSERT INTO public.restaurants VALUES
(1, 'Campus Tacos', 'Mexican', 10.00, 4.5, 0.5),
(2, 'Pasta Place', 'Italian', 18.00, 4.7, 1.2),
(3, 'Sushi Spot', 'Japanese', 25.00, 4.8, 2.5),
(4, 'Pizza Corner', 'Italian', 12.00, 4.2, 0.8),
(5, 'Burrito House', 'Mexican', 11.00, 4.3, 1.5),
(6, 'Burger Barn', 'American', 14.00, 4.0, 2.0)
ON CONFLICT (id) DO NOTHING;

-- A separate database login for student queries. Never use postgres in the app.
DO $$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'quiz_reader') THEN
        CREATE ROLE quiz_reader LOGIN;
    END IF;
END $$;
GRANT CONNECT ON DATABASE postgres TO quiz_reader;
GRANT USAGE ON SCHEMA public TO quiz_reader;
GRANT SELECT ON public.restaurants TO quiz_reader;
ALTER ROLE quiz_reader SET default_transaction_read_only = on;
ALTER ROLE quiz_reader SET statement_timeout = '5s';
ALTER ROLE quiz_reader SET search_path = public;

ALTER TABLE public.restaurants ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS reader_can_read ON public.restaurants;
CREATE POLICY reader_can_read ON public.restaurants
    FOR SELECT TO quiz_reader USING (true);
REVOKE ALL ON public.restaurants FROM anon, authenticated;

-- Each signed-in user can save and reopen only their own answers.
CREATE TABLE IF NOT EXISTS public.quiz_answers (
    user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    question_id integer NOT NULL CHECK (question_id BETWEEN 1 AND 5),
    answer_sql text NOT NULL CHECK (length(answer_sql) <= 5000),
    PRIMARY KEY (user_id, question_id)
);
ALTER TABLE public.quiz_answers ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.quiz_answers FROM anon, quiz_reader;
GRANT SELECT, INSERT, UPDATE ON public.quiz_answers TO authenticated;
DROP POLICY IF EXISTS own_answers_read ON public.quiz_answers;
DROP POLICY IF EXISTS own_answers_insert ON public.quiz_answers;
DROP POLICY IF EXISTS own_answers_update ON public.quiz_answers;
CREATE POLICY own_answers_read ON public.quiz_answers
    FOR SELECT TO authenticated USING ((SELECT auth.uid()) = user_id);
CREATE POLICY own_answers_insert ON public.quiz_answers
    FOR INSERT TO authenticated WITH CHECK ((SELECT auth.uid()) = user_id);
CREATE POLICY own_answers_update ON public.quiz_answers
    FOR UPDATE TO authenticated USING ((SELECT auth.uid()) = user_id)
    WITH CHECK ((SELECT auth.uid()) = user_id);

-- NEXT: in a NEW, private SQL Editor query, set the login password:
-- ALTER ROLE quiz_reader WITH PASSWORD 'a-long-random-password-you-choose';
-- Do not put the real password in this file or commit it to GitHub.
