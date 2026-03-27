-- Migration 003: Add closure_photo column to items_lost_found
-- This column stores a base64-encoded live photo taken at the time of closing a lost & found request.
-- The photo is only accessible to admin users.

ALTER TABLE items_lost_found
    ADD COLUMN IF NOT EXISTS closure_photo TEXT;
