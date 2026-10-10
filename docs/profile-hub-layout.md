# Profile Hub layout and avatar

Implementation scope requested 10/10/2026: reorganize the existing account area and add personal information/avatar using the current green/paper/serif visual system.

Desktop: compact identity card and one vertical menu on the left; selected content card on the right. Mobile: compact identity row, horizontally scrollable section menu, one-column content. Header account entry is a round avatar only (accessible name and tooltip retained).

Views: Overview (recent/pinned and counts), Saved tours, Preferences, Templates, Profile (photo/name/read-only login email/optional phone/home city/introduction), Settings (sign-in status, display controls, history data, saved planning data). No repeated title/intro blocks, disabled Google management buttons or second settings menu. Explicit application/recheck and existing history retention remain intact.

Data contract and image limits: docs/profile-hub.md. Setup: examples/profile-hub-supabase.md. Verify panel navigation, retained unsaved edits, refresh persistence, failed save/upload, photo removal/fallback, owner isolation and 320/390/1440px VI/EN light/dark screenshots. Hosted avatar verification requires the prepared Storage migration; local tests use isolated identity/storage stubs.
