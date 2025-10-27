-- Migration: Add trial and onboarding columns to profiles table
-- Run this in Supabase SQL Editor

-- Add trial_ends_at column (for 14-day trial)
ALTER TABLE profiles
ADD COLUMN IF NOT EXISTS trial_ends_at timestamptz;

-- Add onboarding_completed column
ALTER TABLE profiles
ADD COLUMN IF NOT EXISTS onboarding_completed boolean DEFAULT false;

-- Update existing users to have trial (retroactive)
-- Set trial_ends_at to 14 days from now for existing users who don't have it
UPDATE profiles
SET trial_ends_at = NOW() + INTERVAL '14 days'
WHERE trial_ends_at IS NULL;

-- Add comment to columns for documentation
COMMENT ON COLUMN profiles.trial_ends_at IS 'Date when the 14-day Premium trial expires. Premium features available while NOW() < trial_ends_at';
COMMENT ON COLUMN profiles.onboarding_completed IS 'Whether user has completed the 3-step onboarding wizard';

-- Update the auto-create profile trigger to include trial
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  INSERT INTO public.profiles (id, email, plan, trial_ends_at, onboarding_completed)
  VALUES (
    NEW.id,
    NEW.email,
    'free',
    NOW() + INTERVAL '14 days',  -- 14-day trial
    false                         -- Onboarding not completed
  )
  ON CONFLICT (id) DO NOTHING;  -- In case profile already exists
  RETURN NEW;
END;
$$;

-- Recreate the trigger
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
AFTER INSERT ON auth.users
FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
